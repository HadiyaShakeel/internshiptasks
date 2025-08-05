
from sqlalchemy.orm import Session
from app.models import ChatHistory

def save_chat(db: Session, chat: ChatHistory):
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat

def get_all_chats(db: Session):
    return db.query(ChatHistory).all()

def delete_chat(db: Session, chat_id: int):
    chat = db.query(ChatHistory).filter(ChatHistory.id == chat_id).first()
    if chat:
        db.delete(chat)
        db.commit()
        return True
    return False

def update_chat(db: Session, chat_id: int, new_data: dict):
    chat = db.query(ChatHistory).filter(ChatHistory.id == chat_id).first()
    if not chat:
        return None
    for key, value in new_data.items():
        setattr(chat, key, value)
    db.commit()
    db.refresh(chat)
    return chat
