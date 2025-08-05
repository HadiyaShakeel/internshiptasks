import requests
import time
import os
from dotenv import load_dotenv
from .prompts import get_system_prompt

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")

def fetch_answer(conversation):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    start_time = time.time()

    response = requests.post(OPENAI_API_URL, headers=headers, json={
        "model": "gpt-3.5-turbo",
        "messages": conversation
    })

    latency = time.time() - start_time

    if response.status_code == 200:
        result = response.json()
        reply = result["choices"][0]["message"]["content"]
        usage = result["usage"]
        return reply.strip(), usage["total_tokens"], 0.002 * usage["total_tokens"] / 1000, latency
    else:
        return f"Error {response.status_code}", 0, 0, 0
