"""Conversation memory for the agent.

LangGraph stores each conversation's messages under a thread_id, so follow-up
questions ("what else does that video say?") have context.

If DATABASE_URL is set, conversations are stored in Postgres. Vercel may run each
request on a fresh instance, so production needs this to keep a chat's context
between messages. Without DATABASE_URL, conversations stay in the server's RAM,
which is fine for local development and tests.
"""

import re
import time
from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import CHAT_INDEX_TTL_HOURS, DATABASE_URL

POOL_TIMEOUT_SECONDS = 10  # fail fast if the database can't be reached


def _postgres_checkpointer(url: str) -> PostgresSaver:
    pool = ConnectionPool(
        conninfo=url,
        min_size=1,
        max_size=5,
        timeout=POOL_TIMEOUT_SECONDS,
        # Serverless instances freeze between requests and the database closes idle
        # connections, so test each connection before handing it out.
        check=ConnectionPool.check_connection,
        kwargs={
            "autocommit": True,          # required by PostgresSaver
            "row_factory": dict_row,     # required by PostgresSaver
            "prepare_threshold": None,   # prepared statements break on pooled (PgBouncer) URLs
        },
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()  # creates or migrates the tables; does nothing if they're up to date
    return checkpointer


@lru_cache(maxsize=1)
def get_checkpointer() -> BaseCheckpointSaver:
    """Return the shared conversation store."""
    if DATABASE_URL:
        return _postgres_checkpointer(DATABASE_URL)
    return InMemorySaver()


def prune_old_conversations(max_age_hours: float = CHAT_INDEX_TTL_HOURS) -> list[str]:
    """Delete saved conversations older than max_age_hours (chats nobody closed).

    A conversation's age comes from the timestamp at the start of its thread_id.
    Conversations in RAM disappear with the server, so only Postgres needs this.
    """
    checkpointer = get_checkpointer()
    if not isinstance(checkpointer, PostgresSaver):
        return []

    with checkpointer.conn.connection() as conn:
        rows = conn.execute("SELECT DISTINCT thread_id FROM checkpoints").fetchall()

    cutoff = time.time() - max_age_hours * 3600
    deleted = []
    for row in rows:
        match = re.match(r"(\d+)-", row["thread_id"])
        if match and int(match.group(1)) < cutoff:
            checkpointer.delete_thread(row["thread_id"])
            deleted.append(row["thread_id"])
    return deleted
