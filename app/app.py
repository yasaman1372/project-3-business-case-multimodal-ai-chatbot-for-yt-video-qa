"""FastAPI backend for the YouTube QA chatbot.

Endpoints (all under /api so the React app and the API share one domain on Vercel):
    GET  /api/health   quick check that the server is up
    GET  /api/videos   indexed videos, for the sidebar
    POST /api/chat     {"message", "thread_id"?} -> {"answer", "thread_id", "tools_used"}

Run locally:
    uvicorn app.app:app --reload --port 8000
    then open http://localhost:8000/docs to try the endpoints
"""

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agent import chat
from app.config import CHAT_MODEL
from app.retrieval import list_videos

logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Video QA", version="1.0")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    thread_id: str | None = Field(None, description="Omit to start a new conversation")


class ChatResponse(BaseModel):
    answer: str
    thread_id: str
    tools_used: list[str]
    seconds: float


class Video(BaseModel):
    video_id: str
    title: str
    topic: str
    channel: str
    url: str


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "model": CHAT_MODEL}


@app.get("/api/videos", response_model=list[Video])
def videos() -> list[dict]:
    try:
        return list_videos()
    except Exception as e:
        logger.exception("Failed to list videos")
        raise HTTPException(status_code=502, detail=f"Could not reach the vector database: {e}")


# Plain `def` (not async): FastAPI runs it in a thread, so the blocking agent call
# doesn't freeze the server for other requests.
@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> dict:
    thread_id = request.thread_id or str(uuid.uuid4())
    start = time.perf_counter()
    try:
        result = chat(request.message.strip(), thread_id)
    except Exception as e:
        logger.exception("Agent failed")
        raise HTTPException(status_code=500, detail=f"The assistant failed to answer: {e}")

    return {**result, "thread_id": thread_id, "seconds": round(time.perf_counter() - start, 2)}
