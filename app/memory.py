"""Conversation memory for the agent.

LangGraph stores each conversation's messages under a thread_id, so follow-up
questions ("what else does that video say?") have context.

InMemorySaver keeps conversations in the server's RAM. That's fine locally,
but on Vercel each request may run on a fresh instance, so memory can be lost
between messages. For production, swap in a persistent checkpointer (e.g.
langgraph-checkpoint-postgres with a free Neon/Supabase database) here; nothing
else in the app needs to change.
"""

from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver


@lru_cache(maxsize=1)
def get_checkpointer() -> InMemorySaver:
    """Return the shared conversation store."""
    return InMemorySaver()
