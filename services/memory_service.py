import json
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from db.db_models import SessionLongTermMemory, SessionShortTermMemory, SessionChatHistory
from db.redis_client import redis_client
from services.llm_service import llm_service
from utils.prompt_utils import load_prompt
from utils.tokenizer import estimate_tokens
from db.vectordb import vectordb


SHORT_TERM_LIMIT = 2000
logger = logging.getLogger(__name__)


class MemoryService:

    SHORT_KEY_TEMPLATE = "session:{session_id}:short_memory"

    #Add message to Redis
    def add_short_term_to_redis(self, session_id: str, role: str, content: str):
        
        key = self.SHORT_KEY_TEMPLATE.format(session_id=session_id)
        msg = {"role": role, "content": content}
        redis_client.rpush(key, json.dumps(msg))


    #Add message to Redis and SQLite
    async def add_short_term(self, session_id: str, role: str, content: str, db: AsyncSession):

        self.add_short_term_to_redis(session_id, role, content)
        logger.info(f"[{session_id}] Added short-term memory message ({role}) to redis")

        db.add(SessionShortTermMemory(session_id=session_id, role=role, content=content))
        logger.info(f"[{session_id}] Added short-term memory message ({role}) to STM")

        db.add(SessionChatHistory(session_id=session_id, role=role, content=content))
        logger.info(f"[{session_id}] Added short-term memory message ({role}) to SessionChatHistory")
        await db.commit()


    #Load short term memory from SQLite to Redis (useful when user switches session, restarts app)
    async def restore_short_term(self, session_id: str, db: AsyncSession):
        key = self.SHORT_KEY_TEMPLATE.format(session_id=session_id)

        logger.info(f"Restoring short-term memory into Redis for session id: {session_id}")

        #Clearing Redis first
        redis_client.delete(key)

        #Fetching ShortTermMemory rows from SQLite
        result = await db.execute(select(SessionShortTermMemory).where(SessionShortTermMemory.session_id == session_id))
        rows = result.scalars().all()

        for row in rows:
            redis_client.rpush(key, json.dumps({"role": row.role, "content": row.content}))
        logger.info(f"Restored {len(rows)} messages into Redis for session id: {session_id}")


    #Retrieve short term memory from Redis
    async def get_short_term(self, session_id: str, db: AsyncSession):
        key = self.SHORT_KEY_TEMPLATE.format(session_id=session_id)
        items = redis_client.lrange(key, 0, -1)

        #If Redis is empty (eg- after restart, session switch), restore from SQLite
        if not items:
            logger.info(f"Session id: [{session_id}] Redis is empty, restoring from SQLite")
            await self.restore_short_term(session_id, db)
            items = redis_client.lrange(key, 0, -1)

        #Parse JSON entries
        msgs = [json.loads(x) for x in items]
        return msgs


    #Keep last n messages in redis
    def keep_last_n_short_term(self, session_id: str, n: int = 4):
        key = self.SHORT_KEY_TEMPLATE.format(session_id=session_id)
        redis_client.ltrim(key, -n, -1)


    #Clear Redis memory for session (when switching sessions or deleting session)
    def clear_redis_short_term(self, session_id: str):
        key = self.SHORT_KEY_TEMPLATE.format(session_id=session_id)
        redis_client.delete(key)
        logger.info(f"Cleared Redis short-term memory for session id:{session_id}")


    #Delete rows from SessionShortTermMemory after they've been summarized and stored in SessionLongTermMemory
    async def trim_short_term_sqlite(self, session_id: str, db: AsyncSession, n: int = 3):
        
        result = await db.execute(select(SessionShortTermMemory.id)
                                  .where(SessionShortTermMemory.session_id == session_id)
                                  .order_by(SessionShortTermMemory.id.desc()).limit(n))
        keep_ids = [row[0] for row in result.fetchall()]

        if not keep_ids:
            return

        #Delete everything except those rows
        await db.execute(delete(SessionShortTermMemory)
                         .where(SessionShortTermMemory.session_id == session_id)
                         .where(SessionShortTermMemory.id.not_in(keep_ids)))
        await db.commit()


    #Freeing SessionLongTermMemory and SessionShortTermMemory when deleting a session
    async def delete_all_session_memory(self, session_id: str, db: AsyncSession):
        logger.info(f"Deleting all SessionLongTermMemory and SessionShortTermMemory for session id:{session_id}")

        #Delete session from SessionShortTermMemory in SQLite
        await db.execute(delete(SessionShortTermMemory).where(SessionShortTermMemory.session_id == session_id))

        #Delete session from SessionLongTermMemory in SQLite
        await db.execute(delete(SessionLongTermMemory).where(SessionLongTermMemory.session_id == session_id))
        await db.commit()


    #Add SessionLongTermMemory object to SQLite DB
    async def append_long_term(self, session_id: str, summary: str, db: AsyncSession):
        mem = SessionLongTermMemory(session_id=session_id,
                                    summary=summary)
        db.add(mem)
        await db.commit()

        #Creating embedding for LTM summary
        emb = await llm_service.embed(summary)
        #Adding to LTM ChromaDB collection
        vectordb.add_vector(collection_name="ltm", embedding=emb, 
                            metadata={"session_id": session_id, "summary": summary}, vector_id=None)


    async def get_long_term(self, session_id: str, db: AsyncSession):
        result = await db.execute(select(SessionLongTermMemory).where(SessionLongTermMemory.session_id == session_id))
        return result.scalars().all()


    #Summarization Logic
    async def maybe_summarize(self, session_id: str, db: AsyncSession):
        short_memory = await self.get_short_term(session_id, db)
        if not short_memory:
            return

        text = " ".join([x["content"] for x in short_memory])

        tokens = estimate_tokens(text)
        if tokens < SHORT_TERM_LIMIT:
            return

        #Summarizing using LLM
        logger.info(f"Length of STM {len(text)} > {SHORT_TERM_LIMIT} for session id:{session_id}\nSummarizing and storing in LTM")
        template = load_prompt("summarize_prompt.txt")
        prompt = template.format(text=text)
        summary = await llm_service.summarize(prompt)

        #Saving to long term memory
        await self.append_long_term(session_id, summary, db)

        #Clearing redis memory except last 3 turns
        self.keep_last_n_short_term(session_id, n=4)

        #Deleting the rows from SessionShortTermMemory
        await self.trim_short_term_sqlite(session_id, db)
        logger.info(f"Summarized and stored in LTM for session id:{session_id}. Deleted STM.")


memory_service = MemoryService()
