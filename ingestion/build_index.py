"""Full ingestion pipeline: videos -> transcripts -> clean -> chunks -> Pinecone.

Usage:
    python -m ingestion.build_index            # index everything in videos.txt (skips already indexed)
    python -m ingestion.build_index --reindex  # re-chunk and re-embed already indexed videos too

From code (e.g. the agent's on-demand video search, into one chat's namespace):
    from ingestion.build_index import index_videos
    result = index_videos(videos, topic="black holes", namespace="chat-...", save_files=False)
"""

import argparse
from concurrent.futures import ThreadPoolExecutor

from app.config import VIDEOS_FILE
from ingestion.chunking import chunk_transcript
from ingestion.preprocess import preprocess_transcript
from ingestion.vector_store import add_documents, delete_video, ensure_index, indexed_video_ids
from ingestion.youtube_loader import (
    TRANSCRIPT_ERRORS,
    failure_reason,
    fetch_transcript,
    load_transcripts,
    parse_videos_file,
)


def _fetch_in_parallel(videos: list[dict], topic: str | None) -> tuple[list[dict], list[dict]]:
    """Download transcripts concurrently (much faster than one by one at request time)."""
    def fetch(video):
        try:
            return fetch_transcript({**video, "topic": video.get("topic") or topic}), None
        except TRANSCRIPT_ERRORS as e:
            return None, {"id": video["id"], "title": video.get("title", ""), "reason": failure_reason(e)}

    transcripts, failed = [], []
    with ThreadPoolExecutor(max_workers=max(1, len(videos))) as pool:
        for transcript, failure in pool.map(fetch, videos):
            if transcript:
                transcripts.append(transcript)
            else:
                failed.append(failure)
    return transcripts, failed


def _fetch_best(videos: list[dict], topic: str | None, needed: int) -> tuple[list[dict], list[dict]]:
    """Fetch transcripts in the given (ranked) order until `needed` succeed.

    Downloads in parallel batches of just the number still missing, so with
    good candidates only `needed` transcripts are requested from YouTube.
    """
    transcripts, failed, position = [], [], 0
    while len(transcripts) < needed and position < len(videos):
        batch = videos[position:position + needed - len(transcripts)]
        position += len(batch)
        got, lost = _fetch_in_parallel(batch, topic)
        transcripts += got
        failed += lost
        if lost and all(f["reason"] in {"RequestBlocked", "IpBlocked"} for f in lost) and not got:
            break  # YouTube is blocking us; more requests won't help
    return transcripts, failed


def index_videos(videos: list[dict], topic: str | None = None, reindex: bool = False,
                 save_files: bool = True, namespace: str | None = None, max_videos: int | None = None) -> dict:
    """Fetch, clean, chunk and store videos in Pinecone.

    save_files=True caches transcripts in data/transcripts/ (local runs).
    save_files=False keeps everything in memory (deployed app, where disk isn't persistent).
    namespace: which Pinecone namespace to write to (None = default, used by the CLI).
    max_videos: index at most N videos, trying candidates in the given order and
        skipping ones without captions (pass ranked extra candidates).

    Returns {"indexed": [...], "skipped": [...], "failed": [...], "chunks": n}.
    """
    ensure_index()
    already = indexed_video_ids(namespace)
    to_index = [v for v in videos if reindex or v["id"] not in already]
    skipped = [v["id"] for v in videos if v not in to_index]

    if save_files:
        transcripts, failed = load_transcripts(to_index, topic=topic)
    elif max_videos is not None:
        transcripts, failed = _fetch_best(to_index, topic, max_videos)
    else:
        transcripts, failed = _fetch_in_parallel(to_index, topic)

    documents = []
    for transcript in transcripts:
        chunks = chunk_transcript(preprocess_transcript(transcript))
        if reindex:
            delete_video(transcript["video_id"], namespace)  # old chunk count may differ
        documents.extend(chunks)
        print(f"  indexed  {transcript['video_id']}  {len(chunks):>3} chunks  {transcript.get('title', '')}")

    total_chunks = add_documents(documents, namespace)  # one batched embedding call

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
