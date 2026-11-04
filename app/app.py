"""FastAPI backend for the YouTube QA chatbot.

Each conversation (thread_id) has its own memory and its own Pinecone namespace
with the videos found for it.

Endpoints (all under /api so the React app and the API share one domain on Vercel):
    GET    /api/health              quick check that the server is up
    POST   /api/chat                {"message", "thread_id"?} -> {"answer", "thread_id", "tools_used", "seconds"}
    GET    /api/chat/{id}/videos    videos found so far in a conversation
    DELETE /api/chat/{id}           end a conversation: delete its videos/embeddings

Run locally:
    uvicorn app.app:app --reload --port 8000
    then open http://localhost:8000/docs to try the endpoints
"""

import logging
import time

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field

from app.agent import chat
from app.config import CHAT_MODEL
from app.memory import get_checkpointer
from app.retrieval import list_videos
from ingestion.vector_store import chat_namespace, delete_namespace, new_thread_id

logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Video QA", version="2.0")

THREAD_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    thread_id: str | None = Field(None, pattern=THREAD_ID_PATTERN, description="Omit to start a new conversation")


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


# Plain `def` (not async): FastAPI runs it in a thread, so the blocking agent call
# doesn't freeze the server for other requests.
@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> dict:
    thread_id = request.thread_id or new_thread_id()
    start = time.perf_counter()
    try:
        result = chat(request.message.strip(), thread_id)
    except Exception as e:
        logger.exception("Agent failed")
        raise HTTPException(status_code=500, detail=f"The assistant failed to answer: {e}")

    return {**result, "thread_id": thread_id, "seconds": round(time.perf_counter() - start, 2)}


@app.get("/api/chat/{thread_id}/videos", response_model=list[Video])
def chat_videos(thread_id: str = Path(..., pattern=THREAD_ID_PATTERN)) -> list[dict]:
    try:
        return list_videos(chat_namespace(thread_id))
    except Exception as e:
        logger.exception("Failed to list videos")
        raise HTTPException(status_code=502, detail=f"Could not reach the vector database: {e}")


@app.delete("/api/chat/{thread_id}")
def end_chat(thread_id: str = Path(..., pattern=THREAD_ID_PATTERN)) -> dict:
    """Delete a conversation's embeddings (and its memory, if the checkpointer supports it)."""
    try:
        delete_namespace(chat_namespace(thread_id))
    except Exception as e:
        logger.exception("Failed to delete namespace")
        raise HTTPException(status_code=502, detail=f"Could not reach the vector database: {e}")

    checkpointer = get_checkpointer()
    if hasattr(checkpointer, "delete_thread"):
        checkpointer.delete_thread(thread_id)
    return {"deleted": thread_id}
