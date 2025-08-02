from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")

DATABASE_URL = "sqlite:///./chat_history.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    userinput = Column(Text)
    ai_response = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app = FastAPI()

class QueryInput(BaseModel):
    user_id: str
    userinput: str

def fetchAns_ai(conversation: list) -> str:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": conversation
    }
    response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        ai_reply = response.json()["choices"][0]["message"]["content"]
        return ai_reply.strip()
    else:
        return f"Error {response.status_code}: {response.text}"

@app.post("/askai")
def get_ai_answer(request_data: QueryInput):
    user_id = request_data.user_id
    user_input = request_data.userinput

    past_chats = db.query(ChatHistory).filter(ChatHistory.user_id == user_id).order_by(ChatHistory.timestamp).all()

    conversation = []
    for chat in past_chats:
        conversation.append({"role": "user", "content": chat.userinput})
        conversation.append({"role": "assistant", "content": chat.ai_response})
    conversation.append({"role": "user", "content": user_input})

    ai_reply = fetchAns_ai(conversation)

    chat_record = ChatHistory(
        user_id=user_id,
        userinput=user_input,
        ai_response=ai_reply
    )
    db.add(chat_record)
    db.commit()

    return {
        "status_code": 200,
        "method": "POST",
        "user_input": user_input,
        "ai_response": ai_reply
    }
    
@app.get("/askai")
def get_user_history(user_id: str):
    chats = db.query(ChatHistory).filter(ChatHistory.user_id == user_id).order_by(ChatHistory.timestamp).all()
    return [
        {"user": chat.userinput, "ai": chat.ai_response, "time": chat.timestamp}
        for chat in chats
    ]
