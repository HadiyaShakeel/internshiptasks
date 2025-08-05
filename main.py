from fastapi import FastAPI, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from openai import AsyncOpenAI
from dotenv import load_dotenv
import time, os, asyncio

from app.models import ChatHistory
from app.database import get_db
from app.crud import save_chat, get_all_chats, delete_chat
from app.langsmith_utils import create_traceable_chain, log_step, end_trace
from app.prompts import get_system_prompt

load_dotenv()

app = FastAPI()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.get("/stream")
async def stream_chat(user_id: str, userinput: str, db: Session = Depends(get_db)):
    trace = create_traceable_chain()

    async def event_stream():
        system_prompt = get_system_prompt()
        log_step(trace, "System Prompt", {}, {"prompt": system_prompt})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": userinput}
        ]

        start = time.time()
        full_response = ""

        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=True
        )

        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                token = delta.content
                full_response += token
                yield token

        latency = round(time.time() - start, 2)
        total_tokens = len(userinput.split()) + len(full_response.split())
        cost = round(total_tokens * 0.00001, 6)

        chat = ChatHistory(user_input=userinput, assistant_response=full_response, cost=cost)
        db.add(chat)
        db.commit()

        log_step(trace, "AI Response", {}, {"response": full_response})
        log_step(trace, "Latency", {}, {"seconds": latency})
        log_step(trace, "Cost", {}, {"tokens": total_tokens, "cost": cost})
        end_trace(trace)

    return StreamingResponse(event_stream(), media_type="text/plain")

@app.get("/stats")
async def stats(db: Session = Depends(get_db)):
    chats = get_all_chats(db)
    total_cost = sum(float(c.cost or 0) for c in chats)
    total_tokens = sum(len((c.user_input or "").split()) + len((c.assistant_response or "").split()) for c in chats)

    return JSONResponse({
        "total_chats": len(chats),
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 4),
        "avg_latency": "N/A"
    })

@app.delete("/chat/{chat_id}")
async def delete(chat_id: int, db: Session = Depends(get_db)):
    delete_chat(db, chat_id)
    return {"message": "Deleted"}
