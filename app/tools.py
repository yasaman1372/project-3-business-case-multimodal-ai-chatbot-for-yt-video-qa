"""Tools the agent can call. The docstrings are what the LLM reads to decide
which tool to use, so keep them clear and specific.

The video tools work inside the current chat's own Pinecone namespace. The chat
(thread_id) comes from the run config, which LangChain injects automatically:
the LLM never sees or sets it.
"""

import re

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.config import (
    CANDIDATES_PER_TOPIC,
    MAX_LINKED_VIDEO_MINUTES,
    ON_DEMAND_MAX_MINUTES,
    ON_DEMAND_MIN_MINUTES,
    VIDEOS_PER_TOPIC,
)
from app.retrieval import format_results, get_video_text, list_videos, search
from ingestion.build_index import index_videos
from ingestion.find_videos import get_video_details as fetch_video_details  # length check for links
from ingestion.find_videos import rank_by_relevance, search_youtube
from ingestion.vector_store import chat_namespace, indexed_video_ids, limit_video_cache, prune_old_chat_namespaces
from ingestion.youtube_loader import extract_video_id, is_blocked

YOUTUBE_BLOCKED = ("YOUTUBE_BLOCKED: YouTube is temporarily blocking transcript downloads from this server, "
                   "so {what} could not be read. This is not about the question; it usually clears after a while.")


def _namespace(config: RunnableConfig) -> str:
    return chat_namespace(config["configurable"]["thread_id"])


def _clean_up_before_first_videos(already: set[str]) -> None:
    """When a chat gets its first videos, delete abandoned chats and keep the video cache small."""
    if not already:
        prune_old_chat_namespaces()
        limit_video_cache()


def _format_duration(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"


@tool
def search_video_transcripts(query: str, config: RunnableConfig, video_id: str | None = None) -> str:
    """Search the transcripts of the videos already found in this chat for passages relevant to a question.

    Args:
        query: What to look for, phrased as a question or keywords.
        video_id: Optional. Only search inside this video (use when the user refers to a specific video).
    """
    return format_results(search(query, namespace=_namespace(config), video_id=video_id))


@tool
def find_videos_on_topic(topic: str, question: str, config: RunnableConfig) -> str:
    """Search YouTube for videos about a topic, pick the ones most relevant to the user's
    question, then read, embed and add their transcripts to this chat so they can be
    searched. Takes 15-40 seconds.

    Args:
        topic: A short YouTube search phrase for the subject of the question,
            e.g. "fall of the Roman Empire" or "Van Gogh Starry Night".
        question: The user's question, used to choose the most relevant videos.
    """
    namespace = _namespace(config)
    already = indexed_video_ids(namespace)
    _clean_up_before_first_videos(already)

    videos = search_youtube(topic, count=CANDIDATES_PER_TOPIC, min_minutes=ON_DEMAND_MIN_MINUTES,
                            max_minutes=ON_DEMAND_MAX_MINUTES, skip_ids=already)
    if not videos:
        return f"No suitable YouTube videos found for '{topic}'."

    # Keep the candidates whose title/description best match the question
    videos = rank_by_relevance(question, videos)
    result = index_videos(videos, topic=topic, save_files=False, namespace=namespace,
                          max_videos=VIDEOS_PER_TOPIC)
    titles = {v["id"]: f"{v['title']} ({v['channel']})" for v in videos}

    if not result["indexed"]:
        if result["failed"] and all(is_blocked(f["reason"]) for f in result["failed"]):
            return YOUTUBE_BLOCKED.format(what=f"the videos found for '{topic}'")
        return f"Found videos for '{topic}', but none had usable captions."
    lines = [f"Added {len(result['indexed'])} videos on '{topic}' to this chat:"]
    lines += [f"- {titles[vid]} (video_id: {vid})" for vid in result["indexed"]]
    lines.append("Now call search_video_transcripts to find the relevant passages.")
    return "\n".join(lines)


@tool
def list_videos_in_this_chat(config: RunnableConfig) -> str:
    """List the videos found so far in this chat, with title, topic, channel and video_id."""
    videos = list_videos(_namespace(config))
    if not videos:
        return "No videos have been found in this chat yet."
    lines = [f"- {v['title']} (topic: {v['topic'] or 'none'}"
             f"{', channel: ' + v['channel'] if v['channel'] else ''}, video_id: {v['video_id']}) {v['url']}"
             for v in videos]
    return f"{len(videos)} videos in this chat:\n" + "\n".join(lines)


@tool
def get_video_transcript(video_id: str, config: RunnableConfig) -> str:
    """Get the full transcript of one video in this chat. Use for summaries or overview questions.

    Args:
        video_id: The 11-character YouTube video ID (from list_videos_in_this_chat or search results).
    """
    text = get_video_text(video_id, namespace=_namespace(config))
    return text or f"Video {video_id} is not in this chat. Call list_videos_in_this_chat to see what is."


@tool
def add_video_by_url(url: str, config: RunnableConfig) -> str:
    """Read one specific YouTube video into this chat from its link, so it can be searched and
    summarised. Use when the user pastes a YouTube link or video ID. Takes 5-20 seconds.

    Args:
        url: The YouTube link (youtube.com/watch?v=..., youtu.be/..., /shorts/...) or the 11-character video ID.
    """
    url = url.strip()
    video_id = url if re.fullmatch(r"[\w-]{11}", url) else extract_video_id(url)
    if not video_id:
        return f"'{url}' is not a YouTube video link."

    namespace = _namespace(config)
    already = indexed_video_ids(namespace)
    if video_id in already:
        return f"This video is already in this chat (video_id: {video_id})."

    details = fetch_video_details([video_id])
    if not details:
        return f"Video {video_id} was not found on YouTube (it may be private or deleted)."
    video = details[0]
    if video["duration_seconds"] > MAX_LINKED_VIDEO_MINUTES * 60:
        return (f"'{video['title']}' is {_format_duration(video['duration_seconds'])} long; videos longer "
                f"than {MAX_LINKED_VIDEO_MINUTES} minutes can't be added.")

    _clean_up_before_first_videos(already)
    result = index_videos([video], topic=video["title"], save_files=False, namespace=namespace, max_videos=1)
    if not result["indexed"]:
        if result["failed"] and is_blocked(result["failed"][0]["reason"]):
            return YOUTUBE_BLOCKED.format(what=f"'{video['title']}'")
        return f"'{video['title']}' has no English captions, so its transcript can't be read."
    return (f"Added '{video['title']}' ({video['channel']}, video_id: {video_id}) to this chat. "
            "Now call search_video_transcripts with this video_id to answer a question about it, "
            "or get_video_transcript to summarise it.")


TOOLS = [search_video_transcripts, find_videos_on_topic, add_video_by_url, list_videos_in_this_chat,
         get_video_transcript]
