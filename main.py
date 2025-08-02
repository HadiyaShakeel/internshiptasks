from fastapi import FastAPI
from pydantic import BaseModel
import requests

import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")

app = FastAPI()

class QueryInput(BaseModel):
    userinput: str
    
def fetchAns_ai(userinput: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": userinput}
        ]
    }

    response = requests.post(OPENAI_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        ai_reply = response.json()["choices"][0]["message"]["content"]
        return ai_reply.strip()
    else:
        return f"Error {response.status_code}: {response.text}"
    
    
@app.post("/ask-ai")
def get_ai_answer(request_data: QueryInput):
    reply = fetchAns_ai(request_data.userinput)
    return {
        "status_code": 200,
        "method": "POST",
        "user_input": request_data.userinput,
        "ai_response": reply}
    
@app.get("/ask-ai")
def get_ai_answer_get(userinput: str):
    reply = fetchAns_ai(userinput)
    return {
        "status_code": 200,
        "method": "GET",
        "user_input": userinput,
        "ai_response": reply
    }
    
    
    