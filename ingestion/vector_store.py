"""Pinecone vector store: create the index, add chunks, look up what's indexed.

Chunk IDs look like "<video_id>_<chunk_index>", so all chunks of a video can be
found by ID prefix, and re-adding a video overwrites its old chunks.

Usage:
    python -m ingestion.vector_store                                  # index stats + indexed videos
    python -m ingestion.vector_store "what is inside a black hole?"   # test a search
"""

import sys
from functools import lru_cache

from langchain_core.documents import Document
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from app.config import (
    EMBEDDING_DIMENSIONS,
    PINECONE_API_KEY,
    PINECONE_CLOUD,
    PINECONE_INDEX_NAME,
    PINECONE_REGION,
)
from ingestion.embeddings import get_embeddings


@lru_cache(maxsize=1)
def get_pinecone() -> Pinecone:
    if not PINECONE_API_KEY:
        raise RuntimeError("PINECONE_API_KEY is not set. Add it to your .env file.")
    return Pinecone(api_key=PINECONE_API_KEY)


def ensure_index(name: str = PINECONE_INDEX_NAME) -> None:
    """Create the Pinecone index if it doesn't exist, and check its dimension."""
    pc = get_pinecone()
    if not pc.has_index(name):
        print(f"Creating Pinecone index '{name}' ({EMBEDDING_DIMENSIONS} dims, cosine)...")
        pc.create_index(
            name=name,
            dimension=EMBEDDING_DIMENSIONS,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
        return

    dimension = pc.describe_index(name).dimension
    if dimension != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"Pinecone index '{name}' has dimension {dimension}, but the embedding model "
            f"produces {EMBEDDING_DIMENSIONS}. Delete the index or use a different name."
        )


@lru_cache(maxsize=1)
def get_index():
    return get_pinecone().Index(PINECONE_INDEX_NAME)


@lru_cache(maxsize=1)
def get_vector_store() -> PineconeVectorStore:
    """Return the LangChain vector store (used for both adding and searching)."""
    return PineconeVectorStore(index=get_index(), embedding=get_embeddings())


def add_documents(documents: list[Document]) -> int:
    """Embed and upsert chunk Documents. Existing chunks with the same ID are overwritten."""
    if not documents:
        return 0
    get_vector_store().add_documents(documents, ids=[doc.id for doc in documents])
    return len(documents)


def delete_video(video_id: str) -> None:
    """Remove all chunks of a video (e.g. before re-indexing with different chunk settings)."""
    index = get_index()
    for ids in index.list(prefix=f"{video_id}_"):
        index.delete(ids=ids)


def is_video_indexed(video_id: str) -> bool:
    return any(get_index().list(prefix=f"{video_id}_", limit=1))


def indexed_video_ids() -> set[str]:
    """IDs of all videos with at least one chunk in the index (use as skip_ids)."""
    video_ids = set()
    for ids in get_index().list():
        video_ids.update(chunk_id.rsplit("_", 1)[0] for chunk_id in ids)
    return video_ids


def main() -> None:
    ensure_index()
    stats = get_index().describe_index_stats()
    print(f"Index '{PINECONE_INDEX_NAME}': {stats.total_vector_count} chunks, "
          f"{len(indexed_video_ids())} videos")

    query = " ".join(sys.argv[1:])
    if not query:
        return

    print(f"\nTop results for: {query!r}\n")
    for doc, score in get_vector_store().similarity_search_with_score(query, k=3):
        meta = doc.metadata
        print(f"[{score:.3f}] {meta.get('title')} @ {meta.get('timestamp')}  {meta.get('timestamp_url')}")
        print(f"        {doc.page_content[:200]}...\n")


if __name__ == "__main__":
    main()
