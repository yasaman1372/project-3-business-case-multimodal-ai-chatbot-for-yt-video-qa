"""Search YouTube for a topic (YouTube Data API v3) and append the top video URLs to videos.txt.

Requires YOUTUBE_API_KEY in .env.
Quota: each search costs ~101 units of the free 10,000/day (~100 searches per day).

Usage:
    python -m ingestion.find_videos "black holes"
    python -m ingestion.find_videos "intermittent fasting" -n 15 --max-minutes 30
    python -m ingestion.find_videos "black holes" --captions-only

From code (e.g. an agent tool):
    from ingestion.find_videos import get_video_details, search_youtube
    videos = search_youtube("black holes", count=5)
    details = get_video_details(["O6_u_SMHtgo"])   # title, channel, length, ...
"""

import argparse
import re
from pathlib import Path

import httpx

from app.config import MAX_VIDEO_MINUTES, MIN_VIDEO_MINUTES, VIDEOS_FILE, YOUTUBE_API_KEY

API_URL = "https://www.googleapis.com/youtube/v3"


def _api_get(endpoint: str, params: dict) -> dict:
    """Call a YouTube Data API endpoint and return the JSON response."""
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is not set. Add it to your .env file.")

    response = httpx.get(f"{API_URL}/{endpoint}", params={**params, "key": YOUTUBE_API_KEY}, timeout=15)
    if response.status_code != 200:
        message = response.json().get("error", {}).get("message", response.text)
        raise RuntimeError(f"YouTube API error ({response.status_code}): {message}")
    return response.json()


def _duration_seconds(iso_duration: str) -> int:
    """Convert an ISO 8601 duration like 'PT1H2M3S' to seconds."""
    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", iso_duration)
    if not match:
        return 0
    days, hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def get_video_details(video_ids: list[str]) -> list[dict]:
    """Title, channel, publish date, length and description for up to 50 videos (1 quota unit).

    Unknown or private videos are left out.
    """
    if not video_ids:
        return []
    response = _api_get("videos", {"part": "snippet,contentDetails", "id": ",".join(video_ids[:50])})
    videos = []
    for item in response.get("items", []):
        snippet = item["snippet"]
        videos.append({
            "id": item["id"],
            "title": snippet["title"],
            "channel": snippet["channelTitle"],
            "published": snippet["publishedAt"][:10],  # YYYY-MM-DD
            "description": snippet.get("description", ""),
            "duration_seconds": _duration_seconds(item["contentDetails"]["duration"]),
            "url": f"https://www.youtube.com/watch?v={item['id']}",
        })
    return videos


def search_youtube(topic: str, count: int = 10, min_minutes: int = MIN_VIDEO_MINUTES,
                   max_minutes: int = MAX_VIDEO_MINUTES,
                   skip_ids: set[str] = frozenset(), captions_only: bool = False,
                   language: str = "en") -> list[dict]:
    """Return up to `count` new videos for `topic` whose length is within the given range."""
    # Fetch extra results because some get filtered out by duration / skip_ids
    search_params = {
        "part": "snippet",
        "q": topic,
        "type": "video",
        "maxResults": min(50, count * 3),
        "relevanceLanguage": language,
    }
    if captions_only:
        search_params["videoCaption"] = "closedCaption"

    results = _api_get("search", search_params)
    ids = [item["id"]["videoId"] for item in results.get("items", [])
           if item["id"]["videoId"] not in skip_ids]
    if not ids:
        return []

    # Search results don't include duration, so look it up (costs 1 quota unit)
    by_id = {video["id"]: video for video in get_video_details(ids)}

    videos = []
    for video_id in ids:  # keep search relevance order
        video = by_id.get(video_id)
        if not video or not (min_minutes * 60 <= video["duration_seconds"] <= max_minutes * 60):
            continue
        videos.append(video)
        if len(videos) == count:
            break
    return videos


def rank_by_relevance(question: str, videos: list[dict]) -> list[dict]:
    """Sort videos by how well their title + description match the question (best first).

    Uses one batched embedding call, so it's cheap and needs no transcript downloads.
    Each returned video gets a "relevance" score (cosine similarity, 0-1).
    """
    if len(videos) <= 1:
        return videos
    from ingestion.embeddings import get_embeddings  # lazy: the CLI doesn't need OpenAI

    embeddings = get_embeddings()
    texts = [f"{v['title']}\n{v.get('description', '')[:500]}" for v in videos]
    video_vectors = embeddings.embed_documents(texts)
    question_vector = embeddings.embed_query(question)

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
        return dot / norm if norm else 0.0

    scored = [{**v, "relevance": round(cosine(question_vector, vec), 3)} for v, vec in zip(videos, video_vectors)]
    return sorted(scored, key=lambda v: v["relevance"], reverse=True)


def existing_video_ids(path: Path) -> set[str]:
    """Collect video IDs already listed in the file, to avoid duplicates."""
    if not path.exists():
        return set()
    return set(re.findall(r"v=([\w-]{11})", path.read_text()))


def append_to_file(path: Path, topic: str, videos: list[dict]) -> None:
    """Append a topic section with one URL per line (title kept as a comment)."""
    lines = [f"# Topic: {topic}"]
    lines += [f"{v['url']}  # {v['title']}" for v in videos]

    needs_gap = path.exists() and path.read_text().strip()
    with path.open("a") as f:
        if needs_gap:
            f.write("\n")
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Find YouTube videos for a topic.")
    parser.add_argument("topic", help="Search topic, e.g. 'black holes'")
    parser.add_argument("-n", "--count", type=int, default=10, help="Number of videos (default 10)")
    parser.add_argument("--min-minutes", type=int, default=MIN_VIDEO_MINUTES,
                        help=f"Skip shorter videos (default {MIN_VIDEO_MINUTES})")
    parser.add_argument("--max-minutes", type=int, default=MAX_VIDEO_MINUTES,
                        help=f"Skip longer videos (default {MAX_VIDEO_MINUTES})")
    parser.add_argument("--captions-only", action="store_true",
                        help="Only videos with uploaded captions (excludes auto-generated)")
    parser.add_argument("--file", type=Path, default=VIDEOS_FILE, help="Output file (default videos.txt)")
    args = parser.parse_args()

    seen = existing_video_ids(args.file)
    new_videos = search_youtube(args.topic, args.count, args.min_minutes, args.max_minutes,
                                seen, args.captions_only)

    if not new_videos:
        print("No new videos found.")
        return

    append_to_file(args.file, args.topic, new_videos)
    print(f"Added {len(new_videos)} videos under '# Topic: {args.topic}' in {args.file.name}:")
    for v in new_videos:
        print(f"  - {v['title']} ({v['duration_seconds'] // 60} min, {v['channel']})")


if __name__ == "__main__":
    main()
