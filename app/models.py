from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    class_name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page = Column(Integer, nullable=False)
    text = Column(String, nullable=False)
    qdrant_id = Column(String, unique=True, nullable=False)

    document = relationship("Document", back_populates="chunks")

class UserState(Base):
    __tablename__ = "user_states"
    user_id = Column(Integer, primary_key=True)
    role = Column(String, nullable=True)
    step = Column(String, nullable=True)
    class_name = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    history = Column(JSON, nullable=True, default=list)
    extra = Column(JSON, nullable=True, default=dict)