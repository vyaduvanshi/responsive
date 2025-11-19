import logging
from fastapi import APIRouter, WebSocket, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from services.chat_orchestrator import chat_orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    logger.info(f"WebSocket connected for session id:{session_id}")

    try:
        while True:
            #Wait for message from client
            msg = await websocket.receive_text()
            logger.info(f"Received message: {msg}")

            #Streaming response token by token
            async for token in chat_orchestrator.process_message(session_id, msg, db):
                await websocket.send_text(token) #sending to client
            
            #Send end-of-message marker
            await websocket.send_text("[DONE]")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        logger.info("WebSocket closed")
