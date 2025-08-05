import os
import time
import httpx
from dotenv import load_dotenv
from .prompts import get_system_prompt,create_traceable_chain, log_step, end_trace
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("https://api.openai.com/v1/chat/completions")

async def fetch_answer(conversation):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    start_time = time.time()

    async with httpx.AsyncClient() as client:
        response = await client.post(OPENAI_API_URL, headers=headers, json={
            "model": "gpt-3.5-turbo",
            "messages": conversation
        })

    latency = round(time.time() - start_time, 2)

    if response.status_code == 200:
        result = response.json()
        reply = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        cost = round(total_tokens * 0.002 / 1000, 6)  # adjust rate as needed
        return reply.strip(), total_tokens, cost, latency
    else:
        return f"Error {response.status_code}", 0, 0, latency
