"""Tests for app/tools.py and app/agent.py. Run with: pytest tests/test_agent.py -v"""

import uuid

import pytest
from langchain_core.messages import AIMessage

from app import tools
from app.tools import TOOLS


def test_all_tools_have_descriptions():
    names = {t.name for t in TOOLS}
    assert names == {"search_video_transcripts", "list_available_videos",
                     "get_video_transcript", "find_and_add_videos"}
    assert all(len(t.description) > 30 for t in TOOLS)


def test_find_and_add_videos_caps_count(monkeypatch):
    requested = {}
    monkeypatch.setattr(tools, "indexed_video_ids", lambda: set())
    monkeypatch.setattr(tools, "search_youtube",
                        lambda topic, count, skip_ids: requested.update(count=count) or [])

    result = tools.find_and_add_videos.invoke({"topic": "space", "count": 50})

    assert requested["count"] == 5
    assert "No new suitable videos" in result


def test_get_video_transcript_unknown_video(monkeypatch):
    monkeypatch.setattr(tools, "get_video_text", lambda video_id: None)
    assert "not indexed" in tools.get_video_transcript.invoke({"video_id": "XXXXXXXXXXX"})


# --- real agent (calls OpenAI + Pinecone; skipped by default) ---

def tool_calls(thread_id):
    from app.agent import get_agent
    messages = get_agent().get_state({"configurable": {"thread_id": thread_id}}).values["messages"]
    return [tc["name"] for m in messages if isinstance(m, AIMessage) for tc in m.tool_calls]


@pytest.mark.skipif("not config.getoption('--run-network')", reason="needs --run-network")
def test_agent_searches_and_cites():
    from app.agent import ask
    thread = str(uuid.uuid4())
    answer = ask("What is inside a black hole?", thread)
    assert "search_video_transcripts" in tool_calls(thread)
    assert "youtube.com/watch?v=" in answer


@pytest.mark.skipif("not config.getoption('--run-network')", reason="needs --run-network")
def test_agent_does_not_add_videos_without_asking():
    from app.agent import ask
    thread = str(uuid.uuid4())
    ask("What is the best pasta recipe?", thread)
    assert "find_and_add_videos" not in tool_calls(thread)


# --- FastAPI endpoints (agent and Pinecone replaced with fakes) ---

from fastapi.testclient import TestClient

from app import app as app_module


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "chat", lambda q, t: {"answer": f"echo: {q}", "tools_used": ["x"]})
    monkeypatch.setattr(app_module, "list_videos", lambda: [
        {"video_id": "AAAAAAAAAAA", "title": "T", "topic": "space", "channel": "", "url": "u"}])
    return TestClient(app_module.app)


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_videos(client):
    assert client.get("/api/videos").json()[0]["video_id"] == "AAAAAAAAAAA"


def test_chat_creates_and_keeps_thread_id(client):
    first = client.post("/api/chat", json={"message": "hi"}).json()
    assert first["answer"] == "echo: hi" and first["thread_id"]

    second = client.post("/api/chat", json={"message": "again", "thread_id": first["thread_id"]}).json()
    assert second["thread_id"] == first["thread_id"]


def test_chat_rejects_empty_message(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_chat_returns_500_when_agent_fails(client, monkeypatch):
    def boom(q, t):
        raise RuntimeError("model down")
    monkeypatch.setattr(app_module, "chat", boom)
    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 500 and "model down" in response.json()["detail"]
