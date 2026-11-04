"""Tests for spoken questions (app/speech.py and POST /api/transcribe).
Run with: pytest tests/test_speech.py -v

OpenAI is faked, so no API credits are used.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import app as app_module
from app import speech
from app.speech import SpeechError, transcribe_question


@pytest.fixture
def fake_openai(monkeypatch):
    """Replace the OpenAI client; the returned list records (model, filename) per call."""
    calls, reply = [], {"text": "  Why did the Roman Empire fall?  "}

    def create(model, file):
        calls.append((model, file[0]))
        return SimpleNamespace(text=reply["text"])

    client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    monkeypatch.setattr(speech, "get_client", lambda: client)
    return calls, reply


def test_returns_trimmed_text(fake_openai):
    calls, _ = fake_openai
    assert transcribe_question(b"audio", "question.webm") == "Why did the Roman Empire fall?"
    assert calls == [(speech.TRANSCRIBE_MODEL, "question.webm")]


@pytest.mark.parametrize("audio, filename, message", [
    (b"audio", "notes.txt", "Unsupported file type"),
    (b"audio", "clip.mov", "Unsupported file type"),
    (b"", "question.webm", "empty"),
    (b"x" * (speech.MAX_AUDIO_BYTES + 1), "question.mp3", "larger than"),
])
def test_rejects_unusable_files_without_calling_openai(fake_openai, audio, filename, message):
    calls, _ = fake_openai
    with pytest.raises(SpeechError, match=message):
        transcribe_question(audio, filename)
    assert calls == []


def test_silence_is_an_error(fake_openai):
    _, reply = fake_openai
    reply["text"] = "   "
    with pytest.raises(SpeechError, match="No speech"):
        transcribe_question(b"audio", "question.m4a")


# --- endpoint ---

def test_endpoint_returns_text(fake_openai):
    client = TestClient(app_module.app)
    response = client.post("/api/transcribe", files={"file": ("question.mp4", b"audio", "audio/mp4")})
    assert response.status_code == 200
    assert response.json() == {"text": "Why did the Roman Empire fall?"}


def test_endpoint_explains_bad_files(fake_openai):
    client = TestClient(app_module.app)
    response = client.post("/api/transcribe", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_endpoint_needs_a_file():
    assert TestClient(app_module.app).post("/api/transcribe").status_code == 422
