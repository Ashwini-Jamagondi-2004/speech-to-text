from sqlalchemy import Column, Integer, String, Text, Float, DateTime, func
from .database import Base


class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, default="Untitled")
    text = Column(Text, nullable=False, default="")
    language = Column(String(20), nullable=True)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)
