from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import google.generativeai as genai
import asyncio
import json
import uuid
import time
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
from langsmith import Client

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

genai.configure(api_key=api_key)

os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "default_project")
langsmith_client = Client()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    exit()

model = genai.GenerativeModel(model_name="gemini-2.5-flash-preview-05-20")

chat_histories = {}

INPUT_COST_PER_TOKEN = 0.00000025
OUTPUT_COST_PER_TOKEN = 0.00000050


def estimate_tokens_from_text(text: str):
    """A very rough estimate for tokens based on character count."""
    if not text:
        return 0
    return max(1, len(text) // 4)

def estimate_tokens_from_messages(messages):
    """Estimates tokens for a list of messages."""
    count = 0
    for msg in messages:
        for part in msg.get("parts", []):
            count += estimate_tokens_from_text(part)
    return count


@app.get("/")
def read_root():
    return {"message": "Hello from the FastAPI Gemini server!"}


@app.get("/get_history")
async def get_history(session_id: str):
    """
    Retrieves chat history from Firestore for a given session_id.
    """
    try:
        doc_ref = db.collection("chat_sessions").document(session_id)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            history = data.get("messages", [])

            formatted_history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in history
            ]

            chat_histories[session_id] = [
                {"role": msg["role"], "parts": [msg["content"]]}
                for msg in history
            ]

            return {"history": formatted_history}
        else:
            return {"history": []}
    except Exception as e:
        print(f"Error retrieving history: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving history")


@app.get("/delete_chat")
async def delete_chat(session_id: str):
    """
    Deletes a chat session from Firestore and memory.
    """
    try:
        db.collection("chat_sessions").document(session_id).delete()
        chat_histories.pop(session_id, None)
        return {"message": f"Session {session_id} deleted successfully."}
    except Exception as e:
        print(f"Error deleting chat session: {e}")
        raise HTTPException(status_code=500, detail="Error deleting chat session")


@app.get("/stats")
async def get_stats():
    """
    Retrieves overall usage statistics from Firestore.
    """
    total_chats = 0
    total_messages = 0
    total_tokens = 0
    total_cost = 0
    total_latency = 0

    chat_summaries = []

    try:
        docs = db.collection("chat_sessions").stream()

        for doc in docs:
            total_chats += 1
            data = doc.to_dict()
            messages = data.get("messages", [])

            chat_total_messages = len(messages)
            chat_total_tokens = 0
            chat_total_latency = 0
            chat_total_cost = 0

            for msg in messages:
                total_messages += 1

                input_tokens = msg.get("total_input_tokens", 0)
                output_tokens = msg.get("total_output_tokens", 0)

                chat_total_tokens += input_tokens + output_tokens

                cost = (input_tokens * INPUT_COST_PER_TOKEN) + (output_tokens * OUTPUT_COST_PER_TOKEN)
                chat_total_cost += cost
                total_cost += cost

                if msg.get("role") == "model":
                    latency = msg.get("latency", 0)
                    total_latency += latency
                    chat_total_latency += latency

            total_tokens += chat_total_tokens

            chat_summaries.append({
                "session_id": doc.id,
                "total_messages": chat_total_messages,
                "total_tokens": chat_total_tokens,
                "total_latency_ms": round(chat_total_latency * 1000, 2),
                "total_cost": round(chat_total_cost, 6)
            })

        average_latency_ms_per_message = (total_latency / (total_messages / 2)) * 1000 if total_messages > 0 else 0
        average_messages_per_chat = total_messages / total_chats if total_chats > 0 else 0

        stats = {
            "overall_stats": {
                "total_chats": total_chats,
                "total_messages": total_messages,
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 6),
                "total_latency_ms": round(total_latency * 1000, 2),
                "average_latency_ms_per_message": round(average_latency_ms_per_message, 2),
                "average_messages_per_chat": round(average_messages_per_chat, 2)
            },
            "chat_summaries": chat_summaries
        }

        return JSONResponse(stats)

    except Exception as e:
        print(f"Error retrieving stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving stats")


# --- Updated `chat` endpoint to use LangSmith's trace model ---

@app.get("/chat")
async def chat(prompt: str, session_id: str = None):
    if session_id == "null":
        session_id = None

    if not session_id:
        session_id = str(uuid.uuid4())
        chat_histories[session_id] = []
        db.collection("chat_sessions").document(session_id).set({
            "createdAt": firestore.SERVER_TIMESTAMP,
            "messages": []
        })

    history = chat_histories.get(session_id, [])

    system_prompt = "You are Hadiya's Bot, a friendly, helpful, and concise assistant."

    messages_to_send = [
        {"role": "user", "parts": [system_prompt]},
        {"role": "model", "parts": ["Understood. How can I help you?"]},
    ]
    messages_to_send.extend(history)
    messages_to_send.append({"role": "user", "parts": [prompt]})

    # --- LangSmith: Create the run at the start of the trace ---
    # We create a run with the inputs and a unique ID.
    try:
        run = langsmith_client.create_run(
            name="chat",
            inputs={"user_message": prompt},
            run_type="llm",  # Specify the run type
            project_name=os.getenv("LANGCHAIN_PROJECT")
        )
    except Exception as e:
        print(f"LangSmith run creation failed: {e}")
        run = None  # Handle cases where LangSmith is unavailable

    try:
        total_input_tokens = model.count_tokens(contents=messages_to_send).total_tokens
        if total_input_tokens == 0:
            total_input_tokens = estimate_tokens_from_messages(messages_to_send)
    except Exception as e:
        print(f"Error counting input tokens: {e}")
        total_input_tokens = estimate_tokens_from_messages(messages_to_send)

    async def stream_response():
        full_llm_response = ""
        start_time = time.time()

        try:
            response_chunks = model.generate_content(contents=messages_to_send, stream=True)

            for chunk in response_chunks:
                if chunk.text:
                    full_llm_response += chunk.text
                    data = {"content": chunk.text, "session_id": session_id}
                    yield f"data: {json.dumps(data)}\n\n"
                    await asyncio.sleep(0.01)

            latency = time.time() - start_time
            current_time = datetime.datetime.now(tz=datetime.timezone.utc)

            try:
                total_output_tokens = model.count_tokens(contents=[
                    {"role": "model", "parts": [full_llm_response]}
                ]).total_tokens
                if total_output_tokens == 0:
                    total_output_tokens = estimate_tokens_from_text(full_llm_response)
            except Exception as e:
                print(f"Error counting output tokens: {e}")
                total_output_tokens = estimate_tokens_from_text(full_llm_response)

            history.append({"role": "user", "parts": [prompt]})
            history.append({"role": "model", "parts": [full_llm_response]})
            chat_histories[session_id] = history

            db.collection("chat_sessions").document(session_id).update({
                "messages": firestore.ArrayUnion([
                    {"role": "user", "content": prompt, "timestamp": current_time, "total_input_tokens": total_input_tokens},
                    {"role": "model", "content": full_llm_response, "timestamp": current_time, "latency": latency, "total_output_tokens": total_output_tokens}
                ])
            })

            # --- LangSmith: Update the run with the final output and latency ---
            if run:
                try:
                    langsmith_client.update_run(
                        run.id,
                        outputs={"bot_message": full_llm_response},
                        end_time=time.time(),
                        extra={"latency_ms": round(latency * 1000, 2)}
                    )
                except Exception as e:
                    print(f"LangSmith run update failed: {e}")

            yield "data: [DONE]\n\n"

        except Exception as e:
            print(f"Error with Gemini API: {e}")
            error_message = f"Error with Gemini API: {e}"
            yield f"data: {json.dumps({'content': error_message})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")
