"""Tests for app/memory.py. Run with: pytest tests/test_memory.py -v"""

import time
from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app import memory


@pytest.fixture(autouse=True)
def fresh_checkpointer():
    memory.get_checkpointer.cache_clear()
    yield
    memory.get_checkpointer.cache_clear()


def test_uses_ram_without_a_database_url(monkeypatch):
    monkeypatch.setattr(memory, "DATABASE_URL", None)
    assert isinstance(memory.get_checkpointer(), InMemorySaver)


def test_empty_database_url_counts_as_unset(monkeypatch):
    monkeypatch.setattr(memory, "DATABASE_URL", "")
    assert isinstance(memory.get_checkpointer(), InMemorySaver)


def test_uses_postgres_when_a_database_url_is_set(monkeypatch):
    seen = {}

    class FakePool:
        check_connection = object()

        def __init__(self, **options):
            seen["options"] = options

    class FakeSaver:
        def __init__(self, pool):
            seen["pool"] = pool

        def setup(self):
            seen["setup"] = True

    monkeypatch.setattr(memory, "DATABASE_URL", "postgresql://example/db")
    monkeypatch.setattr(memory, "ConnectionPool", FakePool)
    monkeypatch.setattr(memory, "PostgresSaver", FakeSaver)

    assert isinstance(memory.get_checkpointer(), FakeSaver)
    assert isinstance(seen["pool"], FakePool)
    assert seen["setup"] is True
    assert seen["options"]["conninfo"] == "postgresql://example/db"
    assert seen["options"]["check"] is FakePool.check_connection
    assert seen["options"]["kwargs"]["autocommit"] is True
    assert seen["options"]["kwargs"]["prepare_threshold"] is None


def test_store_is_built_once(monkeypatch):
    monkeypatch.setattr(memory, "DATABASE_URL", None)
    assert memory.get_checkpointer() is memory.get_checkpointer()


def test_pruning_does_nothing_for_conversations_in_ram(monkeypatch):
    monkeypatch.setattr(memory, "DATABASE_URL", None)
    assert memory.prune_old_conversations() == []


def test_pruning_deletes_only_old_timestamped_conversations(monkeypatch):
    class FakeSaver:
        conn = MagicMock()
        delete_thread = MagicMock()

    now = int(time.time())
    old, recent = f"{now - 25 * 3600}-old", f"{now - 3600}-recent"
    connection = FakeSaver.conn.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        {"thread_id": old}, {"thread_id": recent}, {"thread_id": "no-timestamp"},
    ]
    monkeypatch.setattr(memory, "PostgresSaver", FakeSaver)
    monkeypatch.setattr(memory, "get_checkpointer", FakeSaver)

    assert memory.prune_old_conversations(max_age_hours=24) == [old]
    FakeSaver.delete_thread.assert_called_once_with(old)
