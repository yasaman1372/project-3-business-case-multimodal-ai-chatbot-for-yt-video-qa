"""Central settings for the project: paths, model names, API keys.

Import from here instead of hard-coding values in each module:
    from app.config import TRANSCRIPTS_DIR, TRANSCRIPT_LANGUAGES
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
PROCESSED_DIR = DATA_DIR / "processed"
AUDIO_DIR = DATA_DIR / "raw" / "audio"
VIDEOS_FILE = PROJECT_ROOT / "videos.txt"
CHUNKS_FILE = PROCESSED_DIR / "chunks.jsonl"  # for inspection only

# --- API keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "yt-video-qa")
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"  # the free Starter plan only supports aws/us-east-1

# --- YouTube ---
TRANSCRIPT_LANGUAGES = ["en"]  # preferred transcript languages, in order
MIN_VIDEO_MINUTES = 3
MAX_VIDEO_MINUTES = 40

# --- Chunking (in words) ---
CHUNK_TARGET_WORDS = 250   # try to end a chunk at a sentence boundary after this
CHUNK_MAX_WORDS = 350      # always end a chunk here
CHUNK_OVERLAP_WORDS = 50   # words repeated at the start of the next chunk

# --- Models ---
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536  # must match the Pinecone index
CHAT_MODEL = "gpt-5.4-mini"
REASONING_EFFORT = "low"     # low = faster answers; raise for harder questions

# --- Retrieval ---
RETRIEVAL_K = 4              # chunks returned per search
MIN_RELEVANCE_SCORE = 0.25   # drop chunks less similar than this (cosine, 0-1); measured:
                             # on-topic questions 0.31-0.65, off-topic <= 0.18
MAX_TRANSCRIPT_WORDS = 6000  # cap for the full-transcript tool (summaries)

# --- Agent tools ---
MAX_VIDEOS_PER_REQUEST = 5   # videos the agent may add per request (latency + quota)
