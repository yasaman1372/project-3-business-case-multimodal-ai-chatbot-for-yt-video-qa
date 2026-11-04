"""Embedding model used to turn text chunks (and user questions) into vectors.

The same model must be used for indexing and for searching, so both the
ingestion pipeline and the app get it from here.

Usage:
    python -m ingestion.embeddings "some text"     # quick check: prints vector size
"""

import sys
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from app.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, OPENAI_API_KEY


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """Return the shared OpenAI embedding model (created once)."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
    return OpenAIEmbeddings(model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)


def main() -> None:
    text = " ".join(sys.argv[1:]) or "What happens inside a black hole?"
    vector = get_embeddings().embed_query(text)
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Text: {text!r}")
    print(f"Vector: {len(vector)} dimensions, first values {[round(v, 4) for v in vector[:5]]}")


if __name__ == "__main__":
    main()
