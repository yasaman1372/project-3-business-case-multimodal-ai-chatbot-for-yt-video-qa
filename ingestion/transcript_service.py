"""Hosted transcript service (Supadata) for YouTube captions.

YouTube rate-limits caption downloads by IP address and blocks most cloud
servers (e.g. Vercel). Supadata fetches the captions from its own servers, so
we just send it a video URL and get the timestamped transcript back.

Docs: https://docs.supadata.ai  (GET /v1/transcript, header x-api-key)
Only existing captions are requested (mode=native: 1 credit per video).

Usage (quick check):
    python -m ingestion.transcript_service O6_u_SMHtgo
"""

import sys
import time

import httpx

from app.config import SUPADATA_API_KEY, TRANSCRIPT_LANGUAGES

API_URL = "https://api.supadata.ai/v1/transcript"
JOB_TIMEOUT_SECONDS = 40  # long videos are processed as a job we poll


class TranscriptUnavailable(Exception):
    """The video has no usable transcript (not a service problem: try another video)."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


class TranscriptServiceError(Exception):
    """The service itself failed (bad key, quota, outage): fall back to another method."""


def _request(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response:
    try:
        return client.get(url, params=params, headers={"x-api-key": SUPADATA_API_KEY}, timeout=30)
    except httpx.HTTPError as e:
        raise TranscriptServiceError(f"Could not reach Supadata: {e}") from e


def _check(response: httpx.Response) -> dict:
    """Turn a Supadata response into JSON, or raise the matching error."""
    code = response.status_code
    if code in (200, 202):
        return response.json()
    if code == 206:
        raise TranscriptUnavailable("NoTranscript", "the video has no captions")
    if code == 404:
        raise TranscriptUnavailable("VideoUnavailable", "video not found or private")
    if code == 403:
        raise TranscriptUnavailable("VideoRestricted", "video requires sign-in or is restricted")
    raise TranscriptServiceError(f"Supadata HTTP {code}: {response.text[:200]}")


def fetch_from_service(video_id: str, languages: list[str] = TRANSCRIPT_LANGUAGES) -> dict:
    """Return {"language", "segments": [{text, start, duration}]} with times in seconds.

    Raises TranscriptUnavailable (try another video) or TranscriptServiceError (fall back).
    """
    if not SUPADATA_API_KEY:
        raise TranscriptServiceError("SUPADATA_API_KEY is not set")

    params = {
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "lang": languages[0],
        "mode": "native",  # existing captions only, never paid AI generation
        "text": "false",
    }
    with httpx.Client() as client:
        data = _check(_request(client, API_URL, params))

        # Long videos come back as a job to poll
        if "jobId" in data:
            job_url = f"{API_URL}/{data['jobId']}"
            deadline = time.monotonic() + JOB_TIMEOUT_SECONDS
            while True:
                time.sleep(1)
                data = _check(_request(client, job_url))
                status = data.get("status")
                if status == "completed":
                    break
                if status == "failed":
                    raise TranscriptUnavailable("TranscriptFailed", str(data.get("error", "")))
                if time.monotonic() > deadline:
                    raise TranscriptServiceError("Supadata job timed out")

    language = data.get("lang") or ""
    if not any(language.startswith(lang) for lang in languages):
        raise TranscriptUnavailable("NoTranscriptInLanguage", f"only '{language}' available")

    segments = [
        {"text": item["text"], "start": item["offset"] / 1000, "duration": item.get("duration", 0) / 1000}
        for item in data.get("content") or []
        if item.get("text", "").strip()
    ]
    if not segments:
        raise TranscriptUnavailable("NoSpeech", "empty transcript")
    return {"language": language, "segments": segments}


def main() -> None:
    video_id = sys.argv[1] if len(sys.argv) > 1 else "O6_u_SMHtgo"
    start = time.perf_counter()
    result = fetch_from_service(video_id)
    print(f"{video_id}: {len(result['segments'])} segments, language {result['language']}, "
          f"{time.perf_counter() - start:.1f}s")
    for seg in result["segments"][:3]:
        print(f"  [{seg['start']:6.1f}s] {seg['text']}")


if __name__ == "__main__":
    main()
