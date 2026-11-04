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

from app.config import SUPADATA_API_KEY, SUPADATA_PARALLEL_REQUESTS, VIDEO_CACHE_NAMESPACE, VIDEOS_FILE
from ingestion.chunking import chunk_transcript
from ingestion.preprocess import preprocess_transcript
from ingestion.vector_store import (
    CHAT_NAMESPACE_PREFIX,
    add_documents,
    cached_video_ids,
    copy_videos,
    delete_video,
    ensure_index,
    indexed_video_ids,
)
from ingestion.youtube_loader import (
    TRANSCRIPT_ERRORS,
    failure_reason,
    fetch_transcript,
    load_transcripts,
    parse_videos_file,
)


def _fetch_in_parallel(videos: list[dict], topic: str | None) -> tuple[list[dict], list[dict]]:
    """Download transcripts concurrently (much faster than one by one at request time).

    With Supadata, at most SUPADATA_PARALLEL_REQUESTS at once (free plan: 1 request/second).
    """
    def fetch(video):
        try:
            return fetch_transcript({**video, "topic": video.get("topic") or topic}), None
        except TRANSCRIPT_ERRORS as e:
            return None, {"id": video["id"], "title": video.get("title", ""), "reason": failure_reason(e)}

    transcripts, failed = [], []
    workers = min(len(videos), SUPADATA_PARALLEL_REQUESTS) if SUPADATA_API_KEY else len(videos)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for transcript, failure in pool.map(fetch, videos):
            if transcript:
                transcripts.append(transcript)
            else:
                failed.append(failure)
    return transcripts, failed


def _fetch_best(videos: list[dict], topic: str | None, needed: int,
                cached: set[str] = frozenset()) -> tuple[list[dict], list[str], list[dict]]:
    """Take videos in the given (ranked) order until `needed` are ready.

    Videos in `cached` are ready without downloading. The rest are downloaded in
    batches of just the number still missing, so with good candidates only
    `needed` transcripts are requested.
    Returns (transcripts, reused cached video IDs, failed).
    """
    transcripts, reused, failed, position = [], [], [], 0
    while len(transcripts) + len(reused) < needed and position < len(videos):
        batch = videos[position:position + needed - len(transcripts) - len(reused)]
        position += len(batch)
        reused += [v["id"] for v in batch if v["id"] in cached]
        got, lost = _fetch_in_parallel([v for v in batch if v["id"] not in cached], topic)
        transcripts += got
        failed += lost
        if lost and all(f["reason"] in {"RequestBlocked", "IpBlocked"} for f in lost) and not got:
            break  # YouTube is blocking us; more requests won't help
    return transcripts, reused, failed


def index_videos(videos: list[dict], topic: str | None = None, reindex: bool = False,
                 save_files: bool = True, namespace: str | None = None, max_videos: int | None = None) -> dict:
    """Fetch, clean, chunk and store videos in Pinecone.

    save_files=True caches transcripts in data/transcripts/ (local runs).
    save_files=False keeps everything in memory (deployed app, where disk isn't persistent).
    namespace: which Pinecone namespace to write to (None = default, used by the CLI).
    max_videos: index at most N videos, trying candidates in the given order and
        skipping ones without captions (pass ranked extra candidates).

    Chat namespaces use the shared video cache: videos any chat has read before are
    copied from it (no download, no embedding), and new ones are added to it.

    Returns {"indexed": [...], "skipped": [...], "failed": [...], "chunks": n}.
    """
    ensure_index()
    already = indexed_video_ids(namespace)
    to_index = [v for v in videos if reindex or v["id"] not in already]
    skipped = [v["id"] for v in videos if v not in to_index]

    use_cache = (namespace or "").startswith(CHAT_NAMESPACE_PREFIX)
    cached = cached_video_ids([v["id"] for v in to_index]) if use_cache and not reindex else set()

    reused = []
    if save_files:
        transcripts, failed = load_transcripts(to_index, topic=topic)
    elif max_videos is not None:
        transcripts, reused, failed = _fetch_best(to_index, topic, max_videos, cached)
    else:
        reused = [v["id"] for v in to_index if v["id"] in cached]
        transcripts, failed = _fetch_in_parallel([v for v in to_index if v["id"] not in cached], topic)

    documents = []
    for transcript in transcripts:
        chunks = chunk_transcript(preprocess_transcript(transcript))
        if reindex:
            delete_video(transcript["video_id"], namespace)  # old chunk count may differ
        documents.extend(chunks)
        print(f"  indexed  {transcript['video_id']}  {len(chunks):>3} chunks  {transcript.get('title', '')}")

    # one batched embedding call; new videos also go to the shared cache
    total_chunks = add_documents(documents, namespace, also_to=[VIDEO_CACHE_NAMESPACE] if use_cache else [])
    if reused:
        total_chunks += copy_videos(reused, VIDEO_CACHE_NAMESPACE, namespace)
        print(f"  reused   {', '.join(reused)}  (from the shared cache)")

    ready = set(reused) | {t["video_id"] for t in transcripts}
    return {
        "indexed": [v["id"] for v in to_index if v["id"] in ready],  # in the given (ranked) order
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
