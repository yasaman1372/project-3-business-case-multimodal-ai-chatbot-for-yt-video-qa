"""Tests for app/tools.py, app/agent.py and app/app.py. Run with: pytest tests/test_agent.py -v"""

import pytest
from langchain_core.messages import AIMessage

from app import tools
from app.tools import TOOLS
from ingestion.vector_store import chat_namespace, new_thread_id

CONFIG = {"configurable": {"thread_id": "1700000000-abc"}}


@pytest.fixture(autouse=True)
def no_ranking(monkeypatch):
    monkeypatch.setattr(tools, "rank_by_relevance", lambda question, videos: videos)


def test_all_tools_have_descriptions_and_hide_config():
    names = {t.name for t in TOOLS}
    assert names == {"search_video_transcripts", "find_videos_on_topic",
                     "list_videos_in_this_chat", "get_video_transcript"}
    assert all(len(t.description) > 30 for t in TOOLS)
    # The chat id is injected by LangChain, never chosen by the LLM
    assert all("config" not in t.args for t in TOOLS)


def test_new_thread_ids_start_with_a_timestamp():
    thread_id = new_thread_id()
    assert thread_id.split("-")[0].isdigit()
    assert chat_namespace(thread_id) == f"chat-{thread_id}"


def test_search_tool_uses_this_chats_namespace(monkeypatch):
    seen = {}
    monkeypatch.setattr(tools, "search", lambda q, namespace, video_id=None: seen.update(ns=namespace) or [])
    result = tools.search_video_transcripts.invoke({"query": "rome"}, config=CONFIG)
    assert seen["ns"] == "chat-1700000000-abc"
    assert "No relevant passages" in result


def test_find_videos_indexes_into_this_chat(monkeypatch):
    calls = {}
    monkeypatch.setattr(tools, "indexed_video_ids", lambda ns: set())
    monkeypatch.setattr(tools, "prune_old_chat_namespaces", lambda: calls.update(pruned=True))
    monkeypatch.setattr(tools, "search_youtube", lambda topic, **kw: [
        {"id": "AAAAAAAAAAA", "title": "Rome falls", "channel": "History Ch"}])
    monkeypatch.setattr(tools, "index_videos", lambda videos, **kw: calls.update(kw) or {
        "indexed": ["AAAAAAAAAAA"], "failed": [], "skipped": [], "chunks": 5})

    result = tools.find_videos_on_topic.invoke({"topic": "fall of Rome", "question": "Why did Rome fall?"}, config=CONFIG)

    assert calls["namespace"] == "chat-1700000000-abc"
    assert calls["save_files"] is False
    assert calls["pruned"] is True  # first videos of a new chat trigger cleanup
    assert "Rome falls (History Ch)" in result


def test_find_videos_reports_when_nothing_found(monkeypatch):
    monkeypatch.setattr(tools, "indexed_video_ids", lambda ns: {"BBBBBBBBBBB"})
    monkeypatch.setattr(tools, "search_youtube", lambda topic, **kw: [])
    assert "No suitable YouTube videos" in tools.find_videos_on_topic.invoke({"topic": "x", "question": "x?"}, config=CONFIG)


def test_get_video_transcript_unknown_video(monkeypatch):
    monkeypatch.setattr(tools, "get_video_text", lambda video_id, namespace: None)
    result = tools.get_video_transcript.invoke({"video_id": "XXXXXXXXXXX"}, config=CONFIG)
    assert "not in this chat" in result


# --- real agent (calls OpenAI, YouTube + Pinecone; skipped by default) ---

def tool_calls(thread_id):
    from app.agent import get_agent
    messages = get_agent().get_state({"configurable": {"thread_id": thread_id}}).values["messages"]
    return [tc["name"] for m in messages if isinstance(m, AIMessage) for tc in m.tool_calls]


@pytest.mark.skipif("not config.getoption('--run-network')", reason="needs --run-network")
def test_agent_finds_videos_on_demand_then_reuses_them():
    from app.agent import ask
    from ingestion.vector_store import delete_namespace

    thread = new_thread_id()
    try:
        answer = ask("Why did the Roman Empire fall?", thread)
        first_calls = tool_calls(thread)
        assert "find_videos_on_topic" in first_calls
        assert "youtube.com/watch?v=" in answer

        ask("What role did the army play in that?", thread)
        follow_up_calls = tool_calls(thread)[len(first_calls):]
        assert "find_videos_on_topic" not in follow_up_calls  # follow-up reuses this chat's videos
    finally:
        delete_namespace(chat_namespace(thread))


# --- FastAPI endpoints (agent and Pinecone replaced with fakes) ---

from fastapi.testclient import TestClient

from app import app as app_module


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "chat", lambda q, t: {"answer": f"echo: {q}", "tools_used": ["x"]})
    monkeypatch.setattr(app_module, "list_videos", lambda ns: [
        {"video_id": "AAAAAAAAAAA", "title": ns, "topic": "space", "channel": "", "url": "u"}])
    return TestClient(app_module.app)


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_chat_videos_lists_this_chats_namespace(client):
    assert client.get("/api/chat/1700000000-abc/videos").json()[0]["title"] == "chat-1700000000-abc"


def test_chat_creates_and_keeps_thread_id(client):
    first = client.post("/api/chat", json={"message": "hi"}).json()
    assert first["answer"] == "echo: hi" and first["thread_id"].split("-")[0].isdigit()

    second = client.post("/api/chat", json={"message": "again", "thread_id": first["thread_id"]}).json()
    assert second["thread_id"] == first["thread_id"]


def test_chat_rejects_bad_thread_id(client):
    assert client.post("/api/chat", json={"message": "hi", "thread_id": "../../etc"}).status_code == 422


def test_end_chat_deletes_namespace(client, monkeypatch):
    deleted = []
    monkeypatch.setattr(app_module, "delete_namespace", deleted.append)
    assert client.delete("/api/chat/1700000000-abc").status_code == 200
    assert deleted == ["chat-1700000000-abc"]


def test_chat_rejects_empty_message(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_chat_returns_500_when_agent_fails(client, monkeypatch):
    def boom(q, t):
        raise RuntimeError("model down")
    monkeypatch.setattr(app_module, "chat", boom)
    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 500 and "model down" in response.json()["detail"]


def test_find_videos_reports_youtube_blocking(monkeypatch):
    monkeypatch.setattr(tools, "indexed_video_ids", lambda ns: {"BBBBBBBBBBB"})
    monkeypatch.setattr(tools, "search_youtube", lambda topic, **kw: [{"id": "AAAAAAAAAAA", "title": "t", "channel": "c"}])
    monkeypatch.setattr(tools, "index_videos", lambda videos, **kw: {
        "indexed": [], "skipped": [], "chunks": 0,
        "failed": [{"id": "AAAAAAAAAAA", "title": "t", "reason": "IpBlocked"}]})
    assert tools.find_videos_on_topic.invoke({"topic": "picasso", "question": "who is picasso"}, config=CONFIG).startswith("YOUTUBE_BLOCKED")


def test_find_videos_reports_missing_captions(monkeypatch):
    monkeypatch.setattr(tools, "indexed_video_ids", lambda ns: {"BBBBBBBBBBB"})
    monkeypatch.setattr(tools, "search_youtube", lambda topic, **kw: [{"id": "AAAAAAAAAAA", "title": "t", "channel": "c"}])
    monkeypatch.setattr(tools, "index_videos", lambda videos, **kw: {
        "indexed": [], "skipped": [], "chunks": 0,
        "failed": [{"id": "AAAAAAAAAAA", "title": "t", "reason": "TranscriptsDisabled"}]})
    assert "none had usable captions" in tools.find_videos_on_topic.invoke({"topic": "x", "question": "x?"}, config=CONFIG)


def test_find_videos_ranks_candidates_by_the_question(monkeypatch):
    ranked_with = {}
    monkeypatch.setattr(tools, "indexed_video_ids", lambda ns: {"BBBBBBBBBBB"})
    monkeypatch.setattr(tools, "search_youtube", lambda topic, **kw: [
        {"id": "AAAAAAAAAAA", "title": "a", "channel": "c"}, {"id": "CCCCCCCCCCC", "title": "c", "channel": "c"}])
    monkeypatch.setattr(tools, "rank_by_relevance",
                        lambda question, videos: ranked_with.update(q=question) or list(reversed(videos)))
    monkeypatch.setattr(tools, "index_videos", lambda videos, **kw: ranked_with.update(order=[v["id"] for v in videos]) or {
        "indexed": [videos[0]["id"]], "failed": [], "skipped": [], "chunks": 3})

    tools.find_videos_on_topic.invoke({"topic": "t", "question": "Why?"}, config=CONFIG)

    assert ranked_with["q"] == "Why?"
    assert ranked_with["order"] == ["CCCCCCCCCCC", "AAAAAAAAAAA"]  # indexing follows the ranking
