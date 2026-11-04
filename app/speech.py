"""Speech-to-text for questions asked by voice (microphone) or as an audio/video file.

The browser records or uploads the audio, the API sends it to OpenAI's
transcription model, and the text goes into the message box so the user can
check it before sending.

Usage (quick check):
    python -m app.speech question.m4a
"""

import sys
from functools import lru_cache
from pathlib import Path

from openai import OpenAI

from app.config import MAX_AUDIO_MB, OPENAI_API_KEY, TRANSCRIBE_MODEL

# File types OpenAI's transcription API accepts (audio, and video containers with an audio track)
AUDIO_FORMATS = {"flac", "m4a", "mp3", "mp4", "mpeg", "mpga", "oga", "ogg", "wav", "webm"}
MAX_AUDIO_BYTES = MAX_AUDIO_MB * 1024 * 1024


class SpeechError(Exception):
    """The audio can't be turned into a question (wrong format, too big, no speech)."""


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
    return OpenAI(api_key=OPENAI_API_KEY)


def transcribe_question(audio: bytes, filename: str) -> str:
    """Return the text spoken in an audio/video file. Raises SpeechError for unusable files."""
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in AUDIO_FORMATS:
        raise SpeechError(f"Unsupported file type '.{extension}'. Use one of: "
                          f"{', '.join(sorted(AUDIO_FORMATS))}.")
    if not audio:
        raise SpeechError("The recording is empty.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise SpeechError(f"The file is larger than {MAX_AUDIO_MB} MB. Try a shorter clip.")

    result = get_client().audio.transcriptions.create(model=TRANSCRIBE_MODEL, file=(filename, audio))
    text = result.text.strip()
    if not text:
        raise SpeechError("No speech was found in the recording.")
    return text


def main() -> None:
    path = Path(sys.argv[1])
    print(transcribe_question(path.read_bytes(), path.name))


if __name__ == "__main__":
    main()
