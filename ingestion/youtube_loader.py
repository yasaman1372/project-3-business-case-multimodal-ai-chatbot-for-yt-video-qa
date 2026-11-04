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
from pathlib import Path

from youtube_transcript_api import CouldNotRetrieveTranscript, YouTubeTranscriptApi

from app.config import TRANSCRIPT_LANGUAGES, TRANSCRIPTS_DIR, VIDEOS_FILE

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


def fetch_transcript(video: dict, languages: list[str] = TRANSCRIPT_LANGUAGES) -> dict:
    """Download one video's transcript and return it with the video's metadata.

    Raises CouldNotRetrieveTranscript if captions are disabled, missing, or blocked.
    """
    fetched = YouTubeTranscriptApi().fetch(video["id"], languages=languages)
    return {
        "video_id": video["id"],
        "url": video.get("url") or f"https://www.youtube.com/watch?v={video['id']}",
        "title": video.get("title", ""),
        "channel": video.get("channel", ""),
        "topic": video.get("topic"),
        "language": fetched.language_code,
        "is_generated": fetched.is_generated,  # True = auto-generated captions
        "segments": [
            {"text": s.text, "start": s.start, "duration": s.duration}
            for s in fetched.snippets
        ],
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
        except CouldNotRetrieveTranscript as e:
            failed.append({"id": video["id"], "title": video.get("title", ""),
                           "reason": type(e).__name__})
            print(f"  FAILED   {video['id']}  {video.get('title', '')}  ({type(e).__name__})")
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
