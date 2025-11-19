from pydantic import BaseModel
from typing import List, Optional, Dict, Any


#Schemas for document endpoints
class DocumentUploadResponse(BaseModel):
    session_id: str
    session_name: Optional[str]
    status: str


#Schemas for session endpoints
class ListSessionsResponse(BaseModel):
    sessions: List[Dict[str, str]]


class DeleteSessionResponse(BaseModel):
    deleted: bool


class ChatHistoryResponse(BaseModel):
    history: List[Dict[str, Any]]
