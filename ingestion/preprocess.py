"""Clean raw transcripts and save them to data/processed/<video_id>.json.

Removes caption noise ([music], [Applause], ♪, >> speaker markers) and extra
whitespace, while keeping each segment's start time for timestamped citations.

Deliberately NOT done: lowercasing, lemmatization, stopword removal. Embedding
models and the LLM both work best on natural sentences.

Usage:
    python -m ingestion.preprocess

From code (e.g. right after load_transcripts):
    from ingestion.preprocess import preprocess_transcript
    clean = preprocess_transcript(transcript)
"""

import json
import re
from pathlib import Path

from app.config import PROCESSED_DIR, TRANSCRIPTS_DIR

TAG_PATTERN = re.compile(r"\[[^\]]*\]")  # [music], [Applause], [Laughter], ...
NOISE_PATTERN = re.compile(r"♪|>>")       # music notes, speaker-change markers
WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Remove caption tags and noise, and normalise whitespace."""
    text = TAG_PATTERN.sub(" ", text)
    text = NOISE_PATTERN.sub(" ", text)
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def preprocess_transcript(transcript: dict) -> dict:
    """Return a copy of the transcript with cleaned segments (empty ones dropped)."""
    segments = []
    for segment in transcript["segments"]:
        text = clean_text(segment["text"])
        if text:
            segments.append({**segment, "text": text})

    return {
        **transcript,
        "segments": segments,
        "word_count": sum(len(s["text"].split()) for s in segments),
    }


def preprocess_all(input_dir: Path = TRANSCRIPTS_DIR, output_dir: Path = PROCESSED_DIR) -> list[dict]:
    """Clean every transcript in input_dir and save it to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    processed = []
    for path in sorted(input_dir.glob("*.json")):
        raw = json.loads(path.read_text())
        clean = preprocess_transcript(raw)
        (output_dir / path.name).write_text(json.dumps(clean, ensure_ascii=False, indent=2))
        processed.append(clean)

        removed = len(raw["segments"]) - len(clean["segments"])
        print(f"  {clean['video_id']}  {clean['word_count']:>5} words  "
              f"({removed} empty segments dropped)  {clean.get('title', '')}")
    return processed


def main() -> None:
    print(f"Cleaning transcripts from {TRANSCRIPTS_DIR.name}/ ...")
    processed = preprocess_all()
    print(f"\nDone: {len(processed)} transcripts saved to {PROCESSED_DIR.relative_to(PROCESSED_DIR.parents[1])}/")


if __name__ == "__main__":
    main()
