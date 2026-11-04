"""Tests for app/retrieval.py. Run with: pytest tests/test_retrieval.py -v"""

import pytest
from langchain_core.documents import Document

from app import retrieval
from app.retrieval import format_results


class FakeStore:
    """Stands in for Pinecone: records the filter and returns fixed results."""

    def __init__(self, results):
        self.results, self.last_filter, self.namespace = results, "not called", "not called"

    def similarity_search_with_score(self, query, k, filter=None):
        self.last_filter = filter
        return self.results[:k]


def doc(video_id="AAAAAAAAAAA", start=65):
    return Document(page_content="Black holes bend spacetime.", metadata={
        "video_id": video_id, "title": "Test video", "timestamp": "1:05",
        "timestamp_url": f"https://www.youtube.com/watch?v={video_id}&t={start}s",
    })


@pytest.fixture
def fake_store(monkeypatch):
    store = FakeStore([(doc(), 0.6), (doc(), 0.3), (doc(), 0.1)])
    def fake_get_vector_store(namespace=None):
        store.namespace = namespace
        return store
    monkeypatch.setattr(retrieval, "get_vector_store", fake_get_vector_store)
    return store


def test_search_drops_low_scores(fake_store):
    results = retrieval.search("black holes", k=3, min_score=0.25)
    assert [score for _, score in results] == [0.6, 0.3]


def test_search_without_filters(fake_store):
    retrieval.search("black holes")
    assert fake_store.last_filter is None


def test_search_uses_the_chat_namespace(fake_store):
    retrieval.search("black holes", namespace="chat-123")
    assert fake_store.namespace == "chat-123"


def test_search_filters_by_video_and_topic(fake_store):
    retrieval.search("black holes", video_id="AAAAAAAAAAA", topic="space")
    assert fake_store.last_filter == {"video_id": {"$eq": "AAAAAAAAAAA"}, "topic": {"$eq": "space"}}


def test_format_results_includes_citation_info():
    text = format_results([(doc(), 0.6)])
    assert "[1] Video: Test video (video_id: AAAAAAAAAAA)" in text
    assert "Timestamp: 1:05" in text
    assert "https://www.youtube.com/watch?v=AAAAAAAAAAA&t=65s" in text
    assert "Black holes bend spacetime." in text


def test_format_results_empty():
    assert "No relevant passages" in format_results([])


# --- real Pinecone (skipped by default) ---

@pytest.mark.skipif("not config.getoption('--run-network')", reason="needs --run-network")
def test_real_search_on_and_off_topic():
    assert retrieval.search("what is inside a black hole?")
    assert retrieval.search("best pasta recipe") == []
