import asyncio
import logging
import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from db.db_models import Document, DocumentChunk, Session, SessionChatHistory
from db.vectordb import vectordb
from services.memory_service import memory_service



logger = logging.getLogger(__name__)


class SessionService:

    async def create_session(self, db: AsyncSession):
        session_id = str(uuid.uuid4())
        logger.info(f"Creating session {session_id}")

        db.add(Session(id=session_id, session_name=None))
        await db.commit()

        return session_id

    async def list_sessions(self, db: AsyncSession):
        logger.info("Fetching all sessions")

        result = await db.execute(select(Session))
        sessions = result.scalars().all()
        return sessions
    
    async def get_chat_history(self, session_id: str, db: AsyncSession):
        """Return ordered chat history for a session."""
        result = await db.execute(select(SessionChatHistory)
                                  .where(SessionChatHistory.session_id == session_id)
                                  .order_by(SessionChatHistory.created_at.asc()))
        rows = result.scalars().all()
        return [{"role": r.role, "content": r.content, "timestamp": r.created_at.isoformat()} for r in rows]


    async def delete_session(self, session_id: str, db: AsyncSession):
        
        logger.info(f"User triggered session delete for session id:{session_id}")

        #Instant Redis memory deletion
        memory_service.clear_redis_short_term(session_id)

        #Performs remaining deletions as a background task
        asyncio.create_task(self._background_cleanup(session_id))

    async def _background_cleanup(self, session_id: str):
        """
        Performs the following deletions in background
        - SQLite SessionLongTermMemory and SessionShortTermMemory
        - ChromaDB embeddings
        - SQLite DocumentChunks
        - SQLite Documents
        - SQLite Session row
        """
        logger.info(f"Background cleanup started for session id:{session_id}")

        #Opening a new DB session to finish deleting as a background task
        async with AsyncSessionLocal() as db:
            try:
                #Deleting SessionLongTermMemory and SessionShortTermMemory when deleting a session
                await memory_service.delete_all_session_memory(session_id, db)
                logger.info(f"Deleted all SessionLongTermMemory and SessionShortTermMemory for session id:{session_id}")

                #Deleting ChromaDB chunk collection embeddings
                vectordb.delete_session_embeddings("chunks", session_id)
                logger.info(f"[{session_id}] Deleted ChromaDB vectors from chunk collection")

                #Deleting ChromaDB ltm collection embeddings
                vectordb.delete_session_embeddings("ltm", session_id)
                logger.info(f"[{session_id}] Deleted ChromaDB vectors from LTM collection")

                #Deleting SessionChatHistory for this session
                await db.execute(delete(SessionChatHistory).where(SessionChatHistory.session_id == session_id))
                logger.info(f"Deleted SessionChatHistory rows for session id:{session_id}")

                #Deleting Document chunks
                await db.execute(delete(DocumentChunk).where(DocumentChunk.session_id == session_id))
                logger.info(f"Deleted all DocumentChunk rows for session id:{session_id}")

                #Deleting Documents
                await db.execute(delete(Document).where(Document.session_id == session_id))
                logger.info(f"Deleted all Document rows for session id:{session_id}")

                #Deleting Session row
                await db.execute(delete(Session).where(Session.id == session_id))
                logger.info(f"Deleted all Session rows for session id:{session_id}")

                await db.commit()
                logger.info(f"Background cleanup complete for session id:{session_id}")

            except Exception as e:
                logger.error(f"Cleanup failed for session id:{session_id}: {e}")


session_service = SessionService()
