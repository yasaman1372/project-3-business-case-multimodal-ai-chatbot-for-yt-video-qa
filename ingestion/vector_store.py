"""Pinecone vector store: create the index, add chunks, look up what's indexed.

Each chat gets its own Pinecone *namespace* ("chat-<thread_id>"), so videos
found for one conversation never mix with another's. The default namespace
(None) is used by the offline CLI tools.

Chunk IDs look like "<video_id>_<chunk_index>", so all chunks of a video can be
found by ID prefix, and re-adding a video overwrites its old chunks.

Usage:
    python -m ingestion.vector_store                                  # index stats per namespace
    python -m ingestion.vector_store "what is inside a black hole?"   # test a search (default namespace)
"""

import re
import sys
import time
import uuid
from functools import lru_cache

from langchain_core.documents import Document
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from app.config import (
    CHAT_INDEX_TTL_HOURS,
    EMBEDDING_DIMENSIONS,
    PINECONE_API_KEY,
    PINECONE_CLOUD,
    PINECONE_INDEX_NAME,
    PINECONE_REGION,
)
from ingestion.embeddings import get_embeddings

CHAT_NAMESPACE_PREFIX = "chat-"


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


@lru_cache(maxsize=64)
def get_vector_store(namespace: str | None = None) -> PineconeVectorStore:
    """Return the LangChain vector store for one namespace (used for adding and searching)."""
    return PineconeVectorStore(index=get_index(), embedding=get_embeddings(), namespace=namespace)


# ---------- Per-chat namespaces ----------

def chat_namespace(thread_id: str) -> str:
    """The Pinecone namespace holding the videos found for one conversation."""
    return f"{CHAT_NAMESPACE_PREFIX}{thread_id}"


def new_thread_id() -> str:
    """Conversation IDs start with a timestamp so old chat namespaces can be cleaned up."""
    return f"{int(time.time())}-{uuid.uuid4().hex[:12]}"


def delete_namespace(namespace: str) -> None:
    """Delete every chunk in a namespace. Does nothing if the namespace doesn't exist."""
    try:
        get_index().delete(delete_all=True, namespace=namespace)
    except Exception as e:  # Pinecone returns 404 for unknown namespaces
        if "not found" not in str(e).lower() and "404" not in str(e):
            raise


def prune_old_chat_namespaces(max_age_hours: float = CHAT_INDEX_TTL_HOURS) -> list[str]:
    """Delete chat namespaces older than max_age_hours (chats nobody closed)."""
    cutoff = time.time() - max_age_hours * 3600
    deleted = []
    for namespace in get_index().describe_index_stats().namespaces:
        match = re.match(rf"{CHAT_NAMESPACE_PREFIX}(\d+)-", namespace)
        if match and int(match.group(1)) < cutoff:
            delete_namespace(namespace)
            deleted.append(namespace)
    return deleted


# ---------- Adding / listing ----------

def add_documents(documents: list[Document], namespace: str | None = None) -> int:
    """Embed and upsert chunk Documents (one batched embedding call). Same IDs are overwritten."""
    if not documents:
        return 0
    get_vector_store(namespace).add_documents(documents, ids=[doc.id for doc in documents])
    return len(documents)


def delete_video(video_id: str, namespace: str | None = None) -> None:
    """Remove all chunks of a video (e.g. before re-indexing with different chunk settings)."""
    index = get_index()
    for ids in index.list(prefix=f"{video_id}_", namespace=namespace or ""):
        index.delete(ids=ids, namespace=namespace or "")


def is_video_indexed(video_id: str, namespace: str | None = None) -> bool:
    return any(get_index().list(prefix=f"{video_id}_", limit=1, namespace=namespace or ""))


def indexed_video_ids(namespace: str | None = None) -> set[str]:
    """IDs of all videos with at least one chunk in the namespace (use as skip_ids)."""
    video_ids = set()
    for ids in get_index().list(namespace=namespace or ""):
        video_ids.update(chunk_id.rsplit("_", 1)[0] for chunk_id in ids)
    return video_ids


def main() -> None:
    ensure_index()
    stats = get_index().describe_index_stats()
    print(f"Index '{PINECONE_INDEX_NAME}': {stats.total_vector_count} chunks")
    for namespace, info in stats.namespaces.items():
        print(f"  namespace {namespace or '(default)'}: {info.vector_count} chunks")

    query = " ".join(sys.argv[1:])
    if not query:
        return

    print(f"\nTop results for: {query!r} (default namespace)\n")
    for doc, score in get_vector_store().similarity_search_with_score(query, k=3):
        meta = doc.metadata
        print(f"[{score:.3f}] {meta.get('title')} @ {meta.get('timestamp')}  {meta.get('timestamp_url')}")
        print(f"        {doc.page_content[:200]}...\n")


if __name__ == "__main__":
    main()
