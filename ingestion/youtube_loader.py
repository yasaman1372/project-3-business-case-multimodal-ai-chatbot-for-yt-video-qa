"""Fetch YouTube transcripts and save them to data/transcripts/<video_id>.json.

Usage:
    python -m ingestion.youtube_loader            # all videos in videos.txt
    python -m ingestion.youtube_loader --force    # re-download even if already saved

From code (e.g. an agent tool, with results from search_youtube):
    from ingestion.youtube_loader import load_transcripts
    transcripts, failed = load_transcripts(videos, topic="black holes")
"""

import argparse
import json
import re
from functools import lru_cache
from pathlib import Path

from youtube_transcript_api import CouldNotRetrieveTranscript, YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

from app.config import (
    SUPADATA_API_KEY,
    TRANSCRIPT_LANGUAGES,
    TRANSCRIPT_PROXY_URL,
    TRANSCRIPTS_DIR,
    VIDEOS_FILE,
    WEBSHARE_PROXY_PASSWORD,
    WEBSHARE_PROXY_USERNAME,
)

from ingestion.transcript_service import TranscriptServiceError, TranscriptUnavailable, fetch_from_service

# Errors that mean "this video has no usable transcript" (try the next video)
TRANSCRIPT_ERRORS = (CouldNotRetrieveTranscript, TranscriptUnavailable)

VIDEO_ID_PATTERN = re.compile(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})")


def extract_video_id(url: str) -> str | None:
    """Return the 11-character video ID from a YouTube URL, or None."""
    match = VIDEO_ID_PATTERN.search(url)
    return match.group(1) if match else None


def parse_videos_file(path: Path = VIDEOS_FILE) -> list[dict]:
    """Read videos.txt into a list of {id, url, title, topic} dicts.

    Lines starting with '# Topic:' set the topic for the URLs below them.
    Text after '#' on a URL line is used as the title.
    """
    videos, topic = [], None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("# topic:"):
            topic = line.split(":", 1)[1].strip()
            continue
        if line.startswith("#"):
            continue

        url, _, title = line.partition("#")
        video_id = extract_video_id(url)
        if not video_id:
            print(f"Skipping line (no video ID found): {line}")
            continue
        videos.append({
            "id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": title.strip(),
            "topic": topic,
        })
    return videos


@lru_cache(maxsize=1)
def get_transcript_api() -> YouTubeTranscriptApi:
    """Transcript client, routed through a proxy if one is configured in .env."""
    if WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD:
        proxy = WebshareProxyConfig(proxy_username=WEBSHARE_PROXY_USERNAME, proxy_password=WEBSHARE_PROXY_PASSWORD)
    elif TRANSCRIPT_PROXY_URL:
        proxy = GenericProxyConfig(http_url=TRANSCRIPT_PROXY_URL, https_url=TRANSCRIPT_PROXY_URL)
    else:
        proxy = None
    return YouTubeTranscriptApi(proxy_config=proxy)


def failure_reason(error: Exception) -> str:
    """Short reason name for a transcript failure, e.g. "NoTranscript" or "IpBlocked"."""
    return getattr(error, "reason", type(error).__name__)


def is_blocked(reason: str) -> bool:
    """True if a failure reason means YouTube blocked the request (not missing captions)."""
    return reason in {"RequestBlocked", "IpBlocked"}


def _fetch_with_library(video_id: str, languages: list[str]) -> dict:
    """Fallback: youtube-transcript-api directly (rate-limited by YouTube per IP)."""
    fetched = get_transcript_api().fetch(video_id, languages=languages)
    return {
        "language": fetched.language_code,
        "is_generated": fetched.is_generated,  # True = auto-generated captions
        "segments": [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched.snippets],
    }


def fetch_transcript(video: dict, languages: list[str] = TRANSCRIPT_LANGUAGES) -> dict:
    """Download one video's transcript and return it with the video's metadata.

    Uses the hosted transcript service when SUPADATA_API_KEY is set, and falls
    back to youtube-transcript-api if the service itself fails.
    Raises one of TRANSCRIPT_ERRORS if the video has no usable transcript
    (or YouTube blocks the fallback request).
    """
    fetched = None
    if SUPADATA_API_KEY:
        try:
            fetched = fetch_from_service(video["id"], languages)
        except TranscriptServiceError as e:
            print(f"  transcript service failed for {video['id']} ({e}); falling back to youtube-transcript-api")
    if fetched is None:
        fetched = _fetch_with_library(video["id"], languages)

    return {
        "video_id": video["id"],
        "url": video.get("url") or f"https://www.youtube.com/watch?v={video['id']}",
        "title": video.get("title", ""),
        "channel": video.get("channel", ""),
        "topic": video.get("topic"),
        "language": fetched["language"],
        "is_generated": fetched.get("is_generated"),
        "segments": fetched["segments"],
    }


def save_transcript(transcript: dict, output_dir: Path = TRANSCRIPTS_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{transcript['video_id']}.json"
    path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2))
    return path


def load_transcripts(videos: list[dict], topic: str | None = None, force: bool = False,
                     output_dir: Path = TRANSCRIPTS_DIR) -> tuple[list[dict], list[dict]]:
    """Fetch and save transcripts for a list of videos.

    `videos` are dicts with at least an "id" (as returned by parse_videos_file
    or search_youtube). `topic` fills in videos that don't have one.
    Already-saved transcripts are read from disk unless force=True.

    Returns (transcripts, failed) where failed is a list of {id, title, reason}.
    """
    transcripts, failed = [], []
    for video in videos:
        video = {**video, "topic": video.get("topic") or topic}
        cached = output_dir / f"{video['id']}.json"

        if cached.exists() and not force:
            transcripts.append(json.loads(cached.read_text()))
            print(f"  cached   {video['id']}  {video.get('title', '')}")
            continue

        try:
            transcript = fetch_transcript(video)
        except TRANSCRIPT_ERRORS as e:
            failed.append({"id": video["id"], "title": video.get("title", ""), "reason": failure_reason(e)})
            print(f"  FAILED   {video['id']}  {video.get('title', '')}  ({failure_reason(e)})")
            continue

        save_transcript(transcript, output_dir)
        transcripts.append(transcript)
        print(f"  saved    {video['id']}  {video.get('title', '')}  "
              f"({len(transcript['segments'])} segments)")

    return transcripts, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Download transcripts for videos.txt.")
    parser.add_argument("--file", type=Path, default=VIDEOS_FILE, help="Video list (default videos.txt)")
    parser.add_argument("--force", action="store_true", help="Re-download already saved transcripts")
    args = parser.parse_args()

    videos = parse_videos_file(args.file)
    print(f"Found {len(videos)} videos in {args.file.name}")
    transcripts, failed = load_transcripts(videos, force=args.force)

    print(f"\nDone: {len(transcripts)} transcripts in {TRANSCRIPTS_DIR.relative_to(TRANSCRIPTS_DIR.parents[1])}/, "
          f"{len(failed)} failed")
    if failed:
        print("Failed videos are usually missing captions; remove them from videos.txt "
              "or transcribe them with Whisper (ingestion/transcribe.py).")


if __name__ == "__main__":
    main()
