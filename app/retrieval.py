"""Search the indexed video transcripts in Pinecone.

Usage:
    python -m app.retrieval "what is inside a black hole?"
"""

import sys

from langchain_core.documents import Document

from app.config import MAX_TRANSCRIPT_WORDS, MIN_RELEVANCE_SCORE, RETRIEVAL_K
from ingestion.vector_store import get_index, get_vector_store, indexed_video_ids


def search(query: str, k: int = RETRIEVAL_K, video_id: str | None = None,
           topic: str | None = None, min_score: float = MIN_RELEVANCE_SCORE) -> list[tuple[Document, float]]:
    """Return the k most relevant chunks as (Document, score), best first.

    Optionally restrict to one video or one topic. Chunks scoring below
    min_score are dropped, so off-topic questions return nothing.
    """
    metadata_filter = {}
    if video_id:
        metadata_filter["video_id"] = {"$eq": video_id}
    if topic:
        metadata_filter["topic"] = {"$eq": topic}

    results = get_vector_store().similarity_search_with_score(query, k=k, filter=metadata_filter or None)
    return [(doc, score) for doc, score in results if score >= min_score]


def format_results(results: list[tuple[Document, float]]) -> str:
    """Format search results as numbered passages the LLM can read and cite."""
    if not results:
        return "No relevant passages found in the indexed videos."

    passages = []
    for i, (doc, score) in enumerate(results, start=1):
        meta = doc.metadata
        passages.append(
            f"[{i}] Video: {meta.get('title', 'Unknown title')} (video_id: {meta.get('video_id')})\n"
            f"Timestamp: {meta.get('timestamp')}  Link: {meta.get('timestamp_url')}\n"
            f"Relevance: {score:.2f}\n"
            f"{doc.page_content}"
        )
    return "\n\n".join(passages)


def list_videos() -> list[dict]:
    """Return {video_id, title, topic, channel, url} for every indexed video."""
    video_ids = sorted(indexed_video_ids())
    if not video_ids:
        return []

    # The first chunk of each video carries the video's metadata
    response = get_index().fetch(ids=[f"{vid}_0" for vid in video_ids])
    videos = []
    for vid in video_ids:
        vector = response.vectors.get(f"{vid}_0")
        meta = vector.metadata if vector else {}
        videos.append({
            "video_id": vid,
            "title": meta.get("title", ""),
            "topic": meta.get("topic", ""),
            "channel": meta.get("channel", ""),
            "url": meta.get("url", f"https://www.youtube.com/watch?v={vid}"),
        })
    return videos


def get_video_text(video_id: str, max_words: int = MAX_TRANSCRIPT_WORDS) -> str | None:
    """Return a video's full transcript (rebuilt from its chunks), or None if not indexed."""
    index = get_index()
    chunk_ids = [cid for ids in index.list(prefix=f"{video_id}_") for cid in ids]
    if not chunk_ids:
        return None

    vectors = index.fetch(ids=chunk_ids).vectors
    chunks = sorted((v.metadata for v in vectors.values()), key=lambda m: m["chunk_index"])
    # Chunks overlap by design; that's harmless for summaries
    words = " ".join(m["text"] for m in chunks).split()
    text = " ".join(words[:max_words])
    return text + (" [...transcript truncated]" if len(words) > max_words else "")


def main() -> None:
    query = " ".join(sys.argv[1:]) or "what is inside a black hole?"
    print(format_results(search(query)))


if __name__ == "__main__":
    main()
