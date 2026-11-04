"""Tools the agent can call. The docstrings are what the LLM reads to decide
which tool to use, so keep them clear and specific."""

from langchain_core.tools import tool

from app.config import MAX_VIDEOS_PER_REQUEST
from app.retrieval import format_results, get_video_text, list_videos, search
from ingestion.build_index import index_videos
from ingestion.find_videos import search_youtube
from ingestion.vector_store import indexed_video_ids


@tool
def search_video_transcripts(query: str, video_id: str | None = None) -> str:
    """Search the indexed video transcripts for passages relevant to a question.

    Args:
        query: What to look for, phrased as a question or keywords.
        video_id: Optional. Only search inside this video (use when the user refers to a specific video).
    """
    return format_results(search(query, video_id=video_id))


@tool
def list_available_videos() -> str:
    """List all indexed videos with their title, topic, channel and video_id."""
    videos = list_videos()
    if not videos:
        return "No videos are indexed yet."
    lines = [f"- {v['title']} (topic: {v['topic'] or 'none'}"
             f"{', channel: ' + v['channel'] if v['channel'] else ''}, video_id: {v['video_id']}) {v['url']}"
             for v in videos]
    return f"{len(videos)} indexed videos:\n" + "\n".join(lines)


@tool
def get_video_transcript(video_id: str) -> str:
    """Get the full transcript of one indexed video. Use for summaries or overview questions.

    Args:
        video_id: The 11-character YouTube video ID (from list_available_videos or search results).
    """
    text = get_video_text(video_id)
    return text or f"Video {video_id} is not indexed. Call list_available_videos to see what is."


@tool
def find_and_add_videos(topic: str, count: int = 3) -> str:
    """Search YouTube for new videos on a topic and add their transcripts to the index.
    Takes 10-60 seconds. Only use when the user asks for new videos or agrees to add them.

    Args:
        topic: What to search YouTube for, e.g. "black holes" or "intermittent fasting".
        count: How many videos to add (1-5, default 3).
    """
    count = max(1, min(count, MAX_VIDEOS_PER_REQUEST))
    videos = search_youtube(topic, count=count, skip_ids=indexed_video_ids())
    if not videos:
        return f"No new suitable videos found on YouTube for '{topic}'."

    result = index_videos(videos, topic=topic, save_files=False)
    titles = {v["id"]: v["title"] for v in videos}

    lines = [f"Added {len(result['indexed'])} videos on '{topic}' ({result['chunks']} chunks):"]
    lines += [f"- {titles[vid]} (video_id: {vid})" for vid in result["indexed"]]
    if result["failed"]:
        lines.append(f"Skipped {len(result['failed'])} videos without usable captions: "
                     + ", ".join(f["title"] or f["id"] for f in result["failed"]))
    return "\n".join(lines)


TOOLS = [search_video_transcripts, list_available_videos, get_video_transcript, find_and_add_videos]
