"""Tools the agent can call. The docstrings are what the LLM reads to decide
which tool to use, so keep them clear and specific.

Every tool works inside the current chat's own Pinecone namespace. The chat
(thread_id) comes from the run config, which LangChain injects automatically:
the LLM never sees or sets it.
"""

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.config import CANDIDATES_PER_TOPIC, ON_DEMAND_MAX_MINUTES, ON_DEMAND_MIN_MINUTES, VIDEOS_PER_TOPIC
from app.retrieval import format_results, get_video_text, list_videos, search
from ingestion.build_index import index_videos
from ingestion.find_videos import rank_by_relevance, search_youtube
from ingestion.vector_store import chat_namespace, indexed_video_ids, prune_old_chat_namespaces
from ingestion.youtube_loader import is_blocked


def _namespace(config: RunnableConfig) -> str:
    return chat_namespace(config["configurable"]["thread_id"])


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
    if not already:
        prune_old_chat_namespaces()  # first videos of a new chat: clean up abandoned chats

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
            return ("YOUTUBE_BLOCKED: YouTube is temporarily blocking transcript downloads from this "
                    f"server, so the videos found for '{topic}' could not be read. This is not about "
                    "the topic; it usually clears after a while.")
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


TOOLS = [search_video_transcripts, find_videos_on_topic, list_videos_in_this_chat, get_video_transcript]
