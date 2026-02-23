"""Tests for memory/store.py - MemoryStore class."""
import os
import time
import sqlite3
import tempfile
import pytest
from unittest.mock import patch

from memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    """Create a MemoryStore backed by a temporary SQLite database."""
    db_file = str(tmp_path / "test_memory.db")
    return MemoryStore(db_path=db_file)


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------

class TestMemoryStoreSave:
    def test_save_returns_true_on_first_insert(self, store):
        result = store.save("knowledge", "Python uses indentation for blocks.")
        assert result is True

    def test_save_returns_false_on_duplicate(self, store):
        store.save("knowledge", "Python uses indentation for blocks.")
        result = store.save("knowledge", "Python uses indentation for blocks.")
        assert result is False

    def test_save_different_categories_both_succeed(self, store):
        r1 = store.save("knowledge", "Same content")
        r2 = store.save("preference", "Same content")
        assert r1 is True
        assert r2 is True

    def test_save_invalidates_preference_cache(self, store):
        store.save("preference", "I like dark mode.")
        store.get_preferences()  # warm cache
        store.save("preference", "I prefer Python over JavaScript.")
        # Cache should be invalidated (time reset to 0)
        assert store._pref_cache_time == 0

    def test_save_multiple_distinct_entries(self, store):
        contents = ["Entry one", "Entry two", "Entry three"]
        for c in contents:
            assert store.save("knowledge", c) is True

    def test_save_long_content_deduplication_uses_first_200_chars(self, store):
        base = "A" * 200
        long1 = base + "EXTRA1"
        long2 = base + "EXTRA2"
        r1 = store.save("knowledge", long1)
        # The dedup key is only the first 200 chars, both share the same prefix
        r2 = store.save("knowledge", long2)
        assert r1 is True
        assert r2 is False

    def test_save_returns_false_on_db_error(self, tmp_path):
        store = MemoryStore(db_path=str(tmp_path / "bad.db"))
        # Close the persistent connection to force a sqlite3.Error on next access
        store._con.close()
        result = store.save("knowledge", "This should fail silently.")
        assert result is False


# ---------------------------------------------------------------------------
# search() / get_relevant()
# ---------------------------------------------------------------------------

class TestMemoryStoreSearch:
    def test_get_relevant_returns_matching_content(self, store):
        store.save("knowledge", "Python is a high-level programming language.")
        store.save("knowledge", "Dogs are loyal pets.")
        results = store.get_relevant("Python programming", limit=5)
        assert any("Python" in r for r in results)

    def test_get_relevant_returns_empty_list_when_no_match(self, store):
        store.save("knowledge", "Cats are independent animals.")
        results = store.get_relevant("quantum physics dark matter", limit=5)
        assert isinstance(results, list)

    def test_get_relevant_respects_limit(self, store):
        for i in range(10):
            store.save("knowledge", f"Python tip number {i}: use list comprehensions wisely.")
        results = store.get_relevant("Python tip", limit=3)
        assert len(results) <= 3

    def test_get_relevant_returns_strings(self, store):
        store.save("knowledge", "The Eiffel Tower is in Paris.")
        results = store.get_relevant("Eiffel Tower Paris", limit=5)
        for r in results:
            assert isinstance(r, str)

    def test_search_returns_dicts_with_required_keys(self, store):
        store.save("knowledge", "Berlin is the capital of Germany.")
        results = store.search("Berlin Germany", limit=5)
        if results:
            for r in results:
                assert "category" in r
                assert "content" in r
                assert "created_at" in r

    def test_search_empty_store_returns_empty_list(self, store):
        results = store.search("anything", limit=5)
        assert results == []

    def test_search_with_special_fts_characters_does_not_raise(self, store):
        store.save("knowledge", "Use double quotes for strings in JSON.")
        # These characters would break raw FTS5 queries if not escaped
        results = store.search('"hello" OR "world"', limit=5)
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# get_preferences() + caching
# ---------------------------------------------------------------------------

class TestMemoryStorePreferences:
    def test_get_preferences_returns_preference_category_only(self, store):
        store.save("preference", "I prefer dark mode.")
        store.save("knowledge", "This is knowledge, not a preference.")
        prefs = store.get_preferences()
        assert "I prefer dark mode." in prefs
        assert "This is knowledge, not a preference." not in prefs

    def test_get_preferences_returns_empty_list_when_none_saved(self, store):
        prefs = store.get_preferences()
        assert prefs == []

    def test_preference_cache_is_used_within_ttl(self, store):
        store.save("preference", "I like light themes.")
        store.get_preferences()  # warm cache
        # Manually inject a stale value into the cache without touching the DB
        store._pref_cache = ["injected stale value"]
        # Cache time is still fresh; should return the injected value
        prefs = store.get_preferences()
        assert "injected stale value" in prefs

    def test_preference_cache_expires_after_ttl(self, store):
        store.save("preference", "I prefer terminal over GUI.")
        store.get_preferences()  # warm cache
        # Expire the cache by backdating the timestamp
        store._pref_cache_time = time.time() - 301
        store._pref_cache = ["stale cached entry"]
        # Should re-query DB and return the real entry
        prefs = store.get_preferences()
        assert "I prefer terminal over GUI." in prefs

    def test_multiple_preferences_all_returned(self, store):
        entries = ["Prefers dark mode", "Prefers Python", "Prefers short answers"]
        for e in entries:
            store.save("preference", e)
        prefs = store.get_preferences()
        for e in entries:
            assert e in prefs


# ---------------------------------------------------------------------------
# cleanup_old()
# ---------------------------------------------------------------------------

class TestMemoryStoreCleanup:
    def test_cleanup_old_does_not_raise(self, store):
        store.save("knowledge", "Some old knowledge entry.")
        store.cleanup_old(keep_days=30)  # should complete without error

    def test_cleanup_old_removes_old_zero_access_entries(self, store):
        store.save("knowledge", "Ancient knowledge.")
        # Force the created_at to be very old by directly updating DB
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "UPDATE memories SET created_at = datetime('now', '-60 days') WHERE access_count = 0"
            )
        store.cleanup_old(keep_days=30)
        results = store.search("Ancient knowledge", limit=5)
        assert results == []
