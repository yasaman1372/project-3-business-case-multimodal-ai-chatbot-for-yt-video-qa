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
