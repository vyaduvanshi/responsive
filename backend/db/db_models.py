from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    filename = Column(String)
    content_type = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, index=True)
    session_id = Column(String, index=True)
    chunk_index = Column(Integer)
    text = Column(Text)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    session_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))


class SessionShortTermMemory(Base):
    __tablename__ = "session_short_term_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    role = Column(String) #"user" or "assistant"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))


class SessionLongTermMemory(Base):
    __tablename__ = "session_long_term_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    order_index = Column(Integer)
    summary = Column(Text)


class SessionChatHistory(Base):
    __tablename__ = "session_chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String)
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))