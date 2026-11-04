"""Full ingestion pipeline: videos -> transcripts -> clean -> chunks -> Pinecone.

Usage:
    python -m ingestion.build_index            # index everything in videos.txt (skips already indexed)
    python -m ingestion.build_index --reindex  # re-chunk and re-embed already indexed videos too

From code (e.g. an agent tool, with results from search_youtube):
    from ingestion.build_index import index_videos
    result = index_videos(videos, topic="black holes", save_files=False)
"""

import argparse

from youtube_transcript_api import CouldNotRetrieveTranscript

from app.config import VIDEOS_FILE
from ingestion.chunking import chunk_transcript
from ingestion.preprocess import preprocess_transcript
from ingestion.vector_store import add_documents, delete_video, ensure_index, indexed_video_ids
from ingestion.youtube_loader import fetch_transcript, load_transcripts, parse_videos_file


def index_videos(videos: list[dict], topic: str | None = None, reindex: bool = False,
                 save_files: bool = True) -> dict:
    """Fetch, clean, chunk and store videos in Pinecone.

    save_files=True caches transcripts in data/transcripts/ (local runs).
    save_files=False keeps everything in memory (deployed app, where disk isn't persistent).

    Returns {"indexed": [...], "skipped": [...], "failed": [...], "chunks": n}.
    """
    ensure_index()
    already = indexed_video_ids()
    to_index = [v for v in videos if reindex or v["id"] not in already]
    skipped = [v["id"] for v in videos if v not in to_index]

    if save_files:
        transcripts, failed = load_transcripts(to_index, topic=topic)
    else:
        transcripts, failed = [], []
        for video in to_index:
            try:
                transcripts.append(fetch_transcript({**video, "topic": video.get("topic") or topic}))
            except CouldNotRetrieveTranscript as e:
                failed.append({"id": video["id"], "title": video.get("title", ""),
                               "reason": type(e).__name__})

    total_chunks = 0
    for transcript in transcripts:
        documents = chunk_transcript(preprocess_transcript(transcript))
        if reindex:
            delete_video(transcript["video_id"])  # old chunk count may differ
        total_chunks += add_documents(documents)
        print(f"  indexed  {transcript['video_id']}  {len(documents):>3} chunks  {transcript.get('title', '')}")

    return {
        "indexed": [t["video_id"] for t in transcripts],
        "skipped": skipped,
        "failed": failed,
        "chunks": total_chunks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Index videos.txt into Pinecone.")
    parser.add_argument("--reindex", action="store_true", help="Re-embed videos that are already indexed")
    args = parser.parse_args()

    videos = parse_videos_file(VIDEOS_FILE)
    print(f"Found {len(videos)} videos in {VIDEOS_FILE.name}\n")
    result = index_videos(videos, reindex=args.reindex)

    print(f"\nDone: {len(result['indexed'])} indexed ({result['chunks']} chunks), "
          f"{len(result['skipped'])} already indexed, {len(result['failed'])} failed")


if __name__ == "__main__":
    main()
