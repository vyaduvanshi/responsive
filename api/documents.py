from fastapi import APIRouter, UploadFile, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from db.database import get_db
from db.db_models import Session
from api.schemas import DocumentUploadResponse
from services.ingestion_service import ingestion_service
from services.session_service import session_service



logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload",  response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile, db: AsyncSession = Depends(get_db)):

    logger.info("Document upload received. Creating session")

    #Creating session with document upload
    session_id = await session_service.create_session(db)
    logger.info(f"New session created: {session_id}. Added to SQLite DB")

    #Ingesting document under this session
    await ingestion_service.ingest(file, db, session_id=session_id)
    logger.info(f"Document ingested into session {session_id}")

    session_row = await db.get(Session, session_id)

    return DocumentUploadResponse(
        session_id=session_id,
        session_name=session_row.session_name,
        status="ingested"
    )