"""Tests for ingestion/youtube_loader.py. Run with: pytest tests/test_ingestion.py -v

These tests don't hit YouTube: network calls are replaced with fakes.
"""

import json

import pytest
from youtube_transcript_api import TranscriptsDisabled

from ingestion import youtube_loader
from ingestion.youtube_loader import extract_video_id, load_transcripts, parse_videos_file


# --- extract_video_id ---

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=TOJAKmAk3NY",
    "https://www.youtube.com/watch?v=TOJAKmAk3NY&t=42s",
    "https://youtu.be/TOJAKmAk3NY",
    "https://www.youtube.com/shorts/TOJAKmAk3NY",
])
def test_extract_video_id_supports_url_formats(url):
    assert extract_video_id(url) == "TOJAKmAk3NY"


def test_extract_video_id_returns_none_for_non_youtube_url():
    assert extract_video_id("https://example.com/video") is None


# --- parse_videos_file ---

def test_parse_videos_file_reads_topics_and_titles(tmp_path):
    videos_file = tmp_path / "videos.txt"
    videos_file.write_text(
        "# Topic: black holes\n"
        "https://www.youtube.com/watch?v=TOJAKmAk3NY  # Inside a Black Hole\n"
        "\n"
        "# Topic: nutrition\n"
        "https://youtu.be/e-P5IFTqB98\n"
        "# just a comment\n"
        "not a url\n"
    )

    videos = parse_videos_file(videos_file)

    assert [v["id"] for v in videos] == ["TOJAKmAk3NY", "e-P5IFTqB98"]
    assert videos[0]["topic"] == "black holes"
    assert videos[0]["title"] == "Inside a Black Hole"
    assert videos[1]["topic"] == "nutrition"
    assert videos[1]["title"] == ""


# --- load_transcripts ---

def fake_transcript(video):
    return {
        "video_id": video["id"],
        "title": video.get("title", ""),
        "topic": video.get("topic"),
        "segments": [{"text": "hello world", "start": 0.0, "duration": 1.0}],
    }


def test_load_transcripts_saves_json(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_loader, "fetch_transcript", fake_transcript)

    transcripts, failed = load_transcripts([{"id": "AAAAAAAAAAA"}], topic="space", output_dir=tmp_path)

    assert failed == []
    saved = json.loads((tmp_path / "AAAAAAAAAAA.json").read_text())
    assert saved["topic"] == "space"
    assert saved["segments"][0]["text"] == "hello world"
    assert transcripts == [saved]


def test_load_transcripts_uses_cache(tmp_path, monkeypatch):
    (tmp_path / "AAAAAAAAAAA.json").write_text(json.dumps({"video_id": "AAAAAAAAAAA", "cached": True}))

    def should_not_be_called(video):
        raise AssertionError("fetch_transcript was called for a cached video")

    monkeypatch.setattr(youtube_loader, "fetch_transcript", should_not_be_called)

    transcripts, _ = load_transcripts([{"id": "AAAAAAAAAAA"}], output_dir=tmp_path)

    assert transcripts[0]["cached"] is True


def test_load_transcripts_force_ignores_cache(tmp_path, monkeypatch):
    (tmp_path / "AAAAAAAAAAA.json").write_text(json.dumps({"video_id": "AAAAAAAAAAA", "cached": True}))
    monkeypatch.setattr(youtube_loader, "fetch_transcript", fake_transcript)

    transcripts, _ = load_transcripts([{"id": "AAAAAAAAAAA"}], force=True, output_dir=tmp_path)

    assert "cached" not in transcripts[0]


def test_load_transcripts_continues_after_failure(tmp_path, monkeypatch):
    def fetch_or_fail(video):
        if video["id"] == "BADBADBADBA":
            raise TranscriptsDisabled(video["id"])
        return fake_transcript(video)

    monkeypatch.setattr(youtube_loader, "fetch_transcript", fetch_or_fail)

    transcripts, failed = load_transcripts(
        [{"id": "BADBADBADBA", "title": "No captions"}, {"id": "AAAAAAAAAAA"}], output_dir=tmp_path
    )

    assert [t["video_id"] for t in transcripts] == ["AAAAAAAAAAA"]
    assert failed == [{"id": "BADBADBADBA", "title": "No captions", "reason": "TranscriptsDisabled"}]
    assert not (tmp_path / "BADBADBADBA.json").exists()


# --- real network call (skipped by default) ---

@pytest.mark.skipif("not config.getoption('--run-network')", reason="needs --run-network")
def test_fetch_transcript_real_video():
    transcript = youtube_loader.fetch_transcript({"id": "e-P5IFTqB98", "title": "Kurzgesagt"})
    assert transcript["segments"]
    assert transcript["language"] == "en"


# --- preprocess ---

from ingestion.preprocess import clean_text, preprocess_all, preprocess_transcript


@pytest.mark.parametrize("raw, expected", [
    ("known as a super massive [music] black", "known as a super massive black"),
    ("[Applause] thank you [Laughter]", "thank you"),
    ("♪ la la ♪", "la la"),
    (">> Speaker two here", "Speaker two here"),
    ("too   many\nspaces ", "too many spaces"),
    ("Sagittarius A* is huge.", "Sagittarius A* is huge."),  # normal text untouched
])
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


def test_preprocess_transcript_drops_empty_segments_and_keeps_timestamps():
    raw = {
        "video_id": "AAAAAAAAAAA",
        "title": "Test",
        "segments": [
            {"text": "[music]", "start": 0.0, "duration": 2.0},
            {"text": "black holes [music] are", "start": 2.0, "duration": 3.0},
            {"text": "strange", "start": 5.0, "duration": 1.0},
        ],
    }

    clean = preprocess_transcript(raw)

    assert clean["segments"] == [
        {"text": "black holes are", "start": 2.0, "duration": 3.0},
        {"text": "strange", "start": 5.0, "duration": 1.0},
    ]
    assert clean["word_count"] == 4
    assert clean["title"] == "Test"
    assert len(raw["segments"]) == 3  # original not modified


def test_preprocess_all_writes_files(tmp_path):
    input_dir, output_dir = tmp_path / "raw", tmp_path / "processed"
    input_dir.mkdir()
    (input_dir / "AAAAAAAAAAA.json").write_text(json.dumps({
        "video_id": "AAAAAAAAAAA",
        "segments": [{"text": "hello [music] world", "start": 0.0, "duration": 1.0}],
    }))

    preprocess_all(input_dir, output_dir)

    saved = json.loads((output_dir / "AAAAAAAAAAA.json").read_text())
    assert saved["segments"][0]["text"] == "hello world"


# --- chunking ---

from ingestion.chunking import chunk_transcript, format_timestamp


def make_transcript(n_segments, words_per_segment=6, sentence_every=5):
    """Fake cleaned transcript: segments of `words_per_segment` words, 2s apart."""
    segments = []
    for i in range(n_segments):
        text = " ".join(f"w{i}_{k}" for k in range(words_per_segment))
        if (i + 1) % sentence_every == 0:
            text += "."
        segments.append({"text": text, "start": i * 2.0, "duration": 2.0})
    return {"video_id": "AAAAAAAAAAA", "title": "Test video", "topic": "space",
            "channel": "", "url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
            "segments": segments}


@pytest.mark.parametrize("seconds, expected", [(0, "0:00"), (65.7, "1:05"), (3725, "1:02:05")])
def test_format_timestamp(seconds, expected):
    assert format_timestamp(seconds) == expected


def test_short_transcript_is_one_chunk():
    chunks = chunk_transcript(make_transcript(10))
    assert len(chunks) == 1
    assert chunks[0].metadata["word_count"] == 60


def test_chunks_respect_max_size_and_cover_everything():
    transcript = make_transcript(300)  # 1800 words
    chunks = chunk_transcript(transcript, target_words=250, max_words=350, overlap_words=50)

    assert len(chunks) > 1
    assert all(c.metadata["word_count"] <= 350 for c in chunks)
    # first and last words of the transcript are included
    assert chunks[0].page_content.startswith("w0_0")
    assert chunks[-1].page_content.endswith(transcript["segments"][-1]["text"])


def test_chunks_end_at_sentence_boundary_when_possible():
    chunks = chunk_transcript(make_transcript(300), target_words=250, max_words=350)
    assert all(c.page_content.endswith(".") for c in chunks[:-1])


def test_consecutive_chunks_overlap():
    chunks = chunk_transcript(make_transcript(300), overlap_words=50)
    for prev, nxt in zip(chunks, chunks[1:]):
        first_words_of_next = nxt.page_content.split()[:6]
        assert " ".join(first_words_of_next) in prev.page_content


def test_no_tiny_last_chunk():
    chunks = chunk_transcript(make_transcript(300), target_words=250, overlap_words=50)
    assert chunks[-1].metadata["word_count"] >= 100


def test_chunk_metadata_and_ids():
    chunks = chunk_transcript(make_transcript(300))
    meta = chunks[1].metadata

    assert [c.id for c in chunks] == [f"AAAAAAAAAAA_{i}" for i in range(len(chunks))]
    assert meta["video_id"] == "AAAAAAAAAAA"
    assert meta["topic"] == "space"
    assert meta["timestamp_url"] == f"https://www.youtube.com/watch?v=AAAAAAAAAAA&t={int(meta['start'])}s"
    assert meta["start"] < meta["end"]
    assert "channel" not in meta  # empty values dropped (Pinecone rejects nulls)
    assert all(v is not None for c in chunks for v in c.metadata.values())


def test_last_chunk_never_exceeds_max_even_with_short_tail():
    # 66 segments x 6 words = 396 words: one max-size chunk leaves a short tail
    chunks = chunk_transcript(make_transcript(66, sentence_every=1000), target_words=250, max_words=350)
    assert all(c.metadata["word_count"] <= 350 for c in chunks)
    assert chunks[-1].metadata["word_count"] >= 250


# --- build_index (Pinecone and YouTube replaced with fakes) ---

from ingestion import build_index


def test_index_videos_skips_indexed_and_reports_failures(monkeypatch):
    stored = []
    monkeypatch.setattr(build_index, "ensure_index", lambda: None)
    monkeypatch.setattr(build_index, "indexed_video_ids", lambda: {"OLDOLDOLDOL"})
    monkeypatch.setattr(build_index, "add_documents", lambda docs: stored.extend(docs) or len(docs))

    def fake_fetch(video):
        if video["id"] == "BADBADBADBA":
            raise TranscriptsDisabled(video["id"])
        return {**make_transcript(100), "video_id": video["id"], "topic": video.get("topic")}

    monkeypatch.setattr(build_index, "fetch_transcript", fake_fetch)

    videos = [{"id": "OLDOLDOLDOL"}, {"id": "NEWNEWNEWNE"}, {"id": "BADBADBADBA"}]
    result = build_index.index_videos(videos, topic="space", save_files=False)

    assert result["indexed"] == ["NEWNEWNEWNE"]
    assert result["skipped"] == ["OLDOLDOLDOL"]
    assert [f["id"] for f in result["failed"]] == ["BADBADBADBA"]
    assert result["chunks"] == len(stored) > 0
    assert all(d.id.startswith("NEWNEWNEWNE_") and d.metadata["topic"] == "space" for d in stored)


def test_missing_api_keys_give_clear_errors(monkeypatch):
    from ingestion import embeddings, vector_store

    monkeypatch.setattr(embeddings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(vector_store, "PINECONE_API_KEY", None)
    embeddings.get_embeddings.cache_clear()
    vector_store.get_pinecone.cache_clear()

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        embeddings.get_embeddings()
    with pytest.raises(RuntimeError, match="PINECONE_API_KEY"):
        vector_store.get_pinecone()


@pytest.mark.skipif("not config.getoption('--run-network')", reason="needs --run-network")
def test_embedding_dimensions_match_config():
    from app.config import EMBEDDING_DIMENSIONS
    from ingestion.embeddings import get_embeddings

    assert len(get_embeddings().embed_query("black holes")) == EMBEDDING_DIMENSIONS
