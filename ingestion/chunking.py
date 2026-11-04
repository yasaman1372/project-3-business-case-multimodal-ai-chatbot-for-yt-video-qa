"""Split cleaned transcripts into overlapping, timestamped chunks (LangChain Documents).

Chunks are built from whole caption segments, so every chunk knows the time it
starts in the video. That lets the bot cite answers like "at 4:32" with a link
that jumps straight to that moment.

Usage:
    python -m ingestion.chunking      # chunks data/processed/*.json, writes chunks.jsonl to inspect

From code:
    from ingestion.chunking import chunk_transcript
    documents = chunk_transcript(clean_transcript)
"""

import json
from pathlib import Path

from langchain_core.documents import Document

from app.config import (
    CHUNK_MAX_WORDS,
    CHUNK_OVERLAP_WORDS,
    CHUNK_TARGET_WORDS,
    CHUNKS_FILE,
    PROCESSED_DIR,
)

SENTENCE_ENDINGS = (".", "?", "!")


def format_timestamp(seconds: float) -> str:
    """Format seconds as m:ss or h:mm:ss."""
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _word_count(segment: dict) -> int:
    return len(segment["text"].split())


def _make_document(transcript: dict, segments: list[dict], index: int) -> Document:
    """Build one chunk Document from a run of consecutive segments."""
    start = segments[0]["start"]
    end = segments[-1]["start"] + segments[-1].get("duration", 0)
    text = " ".join(s["text"] for s in segments)

    metadata = {
        "video_id": transcript["video_id"],
        "title": transcript.get("title"),
        "channel": transcript.get("channel"),
        "topic": transcript.get("topic"),
        "language": transcript.get("language"),
        "url": transcript.get("url"),
        "chunk_index": index,
        "start": round(start, 1),
        "end": round(end, 1),
        "timestamp": format_timestamp(start),
        "timestamp_url": f"https://www.youtube.com/watch?v={transcript['video_id']}&t={int(start)}s",
        "word_count": len(text.split()),
    }
    # Pinecone rejects null metadata values, so drop empty fields
    metadata = {k: v for k, v in metadata.items() if v not in (None, "")}

    return Document(id=f"{transcript['video_id']}_{index}", page_content=text, metadata=metadata)


def chunk_transcript(transcript: dict, target_words: int = CHUNK_TARGET_WORDS,
                     max_words: int = CHUNK_MAX_WORDS,
                     overlap_words: int = CHUNK_OVERLAP_WORDS) -> list[Document]:
    """Split one cleaned transcript into overlapping chunks.

    A chunk ends at the first sentence boundary after `target_words`, or at
    `max_words` if no boundary comes. The next chunk starts `overlap_words`
    back, so ideas that span a boundary appear whole in at least one chunk.
    """
    segments = transcript["segments"]
    chunks: list[Document] = []
    i = 0

    while i < len(segments):
        # Grow the chunk segment by segment
        j, words = i, 0
        while j < len(segments):
            if j > i and words + _word_count(segments[j]) > max_words:
                break
            words += _word_count(segments[j])
            j += 1
            if words >= target_words and segments[j - 1]["text"].endswith(SENTENCE_ENDINGS):
                break

        # Absorb a short leftover tail if it still fits under max_words
        remaining = sum(_word_count(s) for s in segments[j:])
        if remaining < overlap_words * 2 and words + remaining <= max_words:
            j, words = len(segments), words + remaining

        # A short last chunk starts further back instead (more overlap, normal size)
        if j == len(segments) and chunks and words < target_words:
            while i > 0 and words < target_words:
                i -= 1
                words += _word_count(segments[i])

        chunks.append(_make_document(transcript, segments[i:j], len(chunks)))
        if j >= len(segments):
            break

        # Step back to create the overlap (always advance at least one segment)
        back, overlap = j, 0
        while back > i + 1 and overlap < overlap_words:
            back -= 1
            overlap += _word_count(segments[back])
        i = back

    return chunks


def chunk_all(input_dir: Path = PROCESSED_DIR, output_file: Path = CHUNKS_FILE) -> list[Document]:
    """Chunk every processed transcript and write all chunks to a JSONL file for inspection."""
    documents = []
    for path in sorted(input_dir.glob("*.json")):
        transcript = json.loads(path.read_text())
        chunks = chunk_transcript(transcript)
        documents.extend(chunks)

        sizes = [c.metadata["word_count"] for c in chunks]
        print(f"  {transcript['video_id']}  {len(chunks):>3} chunks  "
              f"(words: min {min(sizes)}, avg {sum(sizes) // len(sizes)}, max {max(sizes)})  "
              f"{transcript.get('title', '')}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w") as f:
        for doc in documents:
            f.write(json.dumps({"id": doc.id, "text": doc.page_content, "metadata": doc.metadata},
                               ensure_ascii=False) + "\n")
    return documents


def main() -> None:
    print(f"Chunking transcripts from {PROCESSED_DIR.name}/ ...")
    documents = chunk_all()
    print(f"\nDone: {len(documents)} chunks. Inspect them in "
          f"{CHUNKS_FILE.relative_to(CHUNKS_FILE.parents[2])}")


if __name__ == "__main__":
    main()
