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
# Hosted transcript service (preferred): fetches YouTube captions from its own servers,
# so YouTube's IP rate limits don't affect us. https://supadata.ai
SUPADATA_API_KEY = os.getenv("SUPADATA_API_KEY")
# Optional proxy for transcript downloads. YouTube blocks transcript requests from IPs
# that send many of them, and from most cloud servers (e.g. Vercel). Set either:
WEBSHARE_PROXY_USERNAME = os.getenv("WEBSHARE_PROXY_USERNAME")  # Webshare "residential" proxy
WEBSHARE_PROXY_PASSWORD = os.getenv("WEBSHARE_PROXY_PASSWORD")
TRANSCRIPT_PROXY_URL = os.getenv("TRANSCRIPT_PROXY_URL")        # or any http(s) proxy URL
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"  # the free Starter plan only supports aws/us-east-1

# --- YouTube ---
TRANSCRIPT_LANGUAGES = ["en"]  # preferred transcript languages, in order
SUPADATA_PARALLEL_REQUESTS = 1  # Supadata free plan allows 1 request/second; raise on paid plans
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

# --- Speech-to-text (questions asked by voice or as an audio/video file) ---
TRANSCRIBE_MODEL = "gpt-4o-mini-transcribe"  # ~$0.003/min; "whisper-1" also works (~$0.006/min)
MAX_AUDIO_MB = 4             # Vercel rejects request bodies over 4.5 MB

# --- Retrieval ---
RETRIEVAL_K = 4              # chunks returned per search
MIN_RELEVANCE_SCORE = 0.25   # drop chunks less similar than this (cosine, 0-1); measured:
                             # on-topic questions 0.31-0.65, off-topic <= 0.18
MAX_TRANSCRIPT_WORDS = 6000  # cap for the full-transcript tool (summaries)

# --- Evaluation (evaluation/langsmith_eval.py) ---
EVAL_DATASET_NAME = "yt-video-qa-eval"  # LangSmith dataset built from evaluation/eval_questions.csv
EVAL_JUDGE_MODEL = "gpt-5.4-mini"       # LLM that grades correctness and groundedness

# --- On-demand video search (per chat) ---
VIDEOS_PER_TOPIC = 3         # videos fetched and embedded when a chat needs a new topic
CANDIDATES_PER_TOPIC = 8     # YouTube results ranked by relevance to the question;
                             # only the best VIDEOS_PER_TOPIC are downloaded and embedded
ON_DEMAND_MIN_MINUTES = 4    # shorter videos rarely explain much
ON_DEMAND_MAX_MINUTES = 25   # longer videos make the first answer slow to embed
CHAT_INDEX_TTL_HOURS = 24    # chat namespaces older than this are deleted automatically
MAX_LINKED_VIDEO_MINUTES = 90  # longest video a user can add by pasting its link

# --- Shared video cache ---
# Every video a chat reads is also kept (already embedded) in one shared namespace, so
# later chats reuse it: no transcript download (no Supadata credit) and no embedding cost.
VIDEO_CACHE_NAMESPACE = "video-cache"
VIDEO_CACHE_MAX_CHUNKS = 20_000  # ~1,300 videos, ~160 MB of the free plan's 2 GB;
                                 # the cache is cleared when it grows past this
