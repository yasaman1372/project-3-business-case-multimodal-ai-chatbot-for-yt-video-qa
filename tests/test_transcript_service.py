"""Tests for the hosted transcript service (ingestion/transcript_service.py).
Run with: pytest tests/test_transcript_service.py -v

HTTP calls are faked, so no API credits are used.
"""

import httpx
import pytest

from ingestion import transcript_service, youtube_loader
from ingestion.transcript_service import TranscriptServiceError, TranscriptUnavailable, fetch_from_service

SEGMENTS = [{"text": "Picasso was born", "offset": 1500, "duration": 2000, "lang": "en"},
            {"text": "  ", "offset": 3500, "duration": 500, "lang": "en"},
            {"text": "in Malaga.", "offset": 4000, "duration": 1500, "lang": "en"}]


@pytest.fixture
def fake_api(monkeypatch):
    """Replace HTTP calls with a queue of (status, json) responses."""
    monkeypatch.setattr(transcript_service, "SUPADATA_API_KEY", "test-key")
    monkeypatch.setattr(transcript_service.time, "sleep", lambda s: None)
    responses, calls = [], []

    def fake_request(client, url, params=None):
        calls.append(url)
        status, body = responses.pop(0)
        return httpx.Response(status, json=body)

    monkeypatch.setattr(transcript_service, "_request", fake_request)
    return responses, calls


def test_converts_milliseconds_and_drops_empty_segments(fake_api):
    responses, _ = fake_api
    responses.append((200, {"content": SEGMENTS, "lang": "en"}))

    result = fetch_from_service("O6_u_SMHtgo")

    assert result["language"] == "en"
    assert result["segments"] == [{"text": "Picasso was born", "start": 1.5, "duration": 2.0},
                                  {"text": "in Malaga.", "start": 4.0, "duration": 1.5}]


def test_polls_job_for_long_videos(fake_api):
    responses, calls = fake_api
    responses += [(202, {"jobId": "job-1"}), (200, {"status": "active"}),
                  (200, {"status": "completed", "content": SEGMENTS, "lang": "en"})]

    result = fetch_from_service("O6_u_SMHtgo")

    assert len(result["segments"]) == 2
    assert calls[-1].endswith("/job-1")


@pytest.mark.parametrize("status, reason", [(206, "NoTranscript"), (404, "VideoUnavailable"), (403, "VideoRestricted")])
def test_video_problems_mean_try_another_video(fake_api, status, reason):
    responses, _ = fake_api
    responses.append((status, {}))
    with pytest.raises(TranscriptUnavailable) as e:
        fetch_from_service("O6_u_SMHtgo")
    assert e.value.reason == reason


def test_wrong_language_is_unavailable(fake_api):
    responses, _ = fake_api
    responses.append((200, {"content": SEGMENTS, "lang": "fr"}))
    with pytest.raises(TranscriptUnavailable):
        fetch_from_service("O6_u_SMHtgo")


@pytest.mark.parametrize("status", [401, 429, 500])
def test_service_problems_are_service_errors(fake_api, status):
    responses, _ = fake_api
    responses.append((status, {"error": "nope"}))
    with pytest.raises(TranscriptServiceError):
        fetch_from_service("O6_u_SMHtgo")


def test_loader_uses_service_then_falls_back(monkeypatch):
    monkeypatch.setattr(youtube_loader, "SUPADATA_API_KEY", "test-key")
    library_calls = []
    monkeypatch.setattr(youtube_loader, "_fetch_with_library",
                        lambda vid, langs: library_calls.append(vid) or {"language": "en", "segments": []})

    # service works -> library not used
    monkeypatch.setattr(youtube_loader, "fetch_from_service",
                        lambda vid, langs: {"language": "en", "segments": [{"text": "hi", "start": 0, "duration": 1}]})
    assert youtube_loader.fetch_transcript({"id": "AAAAAAAAAAA"})["segments"][0]["text"] == "hi"
    assert library_calls == []

    # service down -> falls back to the library
    def service_down(vid, langs):
        raise TranscriptServiceError("quota")
    monkeypatch.setattr(youtube_loader, "fetch_from_service", service_down)
    youtube_loader.fetch_transcript({"id": "AAAAAAAAAAA"})
    assert library_calls == ["AAAAAAAAAAA"]


def test_loader_does_not_fall_back_when_video_has_no_captions(monkeypatch):
    monkeypatch.setattr(youtube_loader, "SUPADATA_API_KEY", "test-key")

    def no_captions(vid, langs):
        raise TranscriptUnavailable("NoTranscript")
    monkeypatch.setattr(youtube_loader, "fetch_from_service", no_captions)
    monkeypatch.setattr(youtube_loader, "_fetch_with_library", lambda vid, langs: pytest.fail("should not fall back"))

    with pytest.raises(TranscriptUnavailable):
        youtube_loader.fetch_transcript({"id": "AAAAAAAAAAA"})


@pytest.mark.skipif("not config.getoption('--run-network')", reason="needs --run-network and SUPADATA_API_KEY")
def test_real_service():
    from app.config import SUPADATA_API_KEY
    if not SUPADATA_API_KEY:
        pytest.skip("SUPADATA_API_KEY not set")
    assert fetch_from_service("O6_u_SMHtgo")["segments"]
