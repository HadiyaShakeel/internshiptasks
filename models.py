from app.db_base import Base
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from datetime import datetime

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_input = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    cost = Column(String, nullable=True)
    latency = Column(Float, nullable=True)
