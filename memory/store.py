import math
import sqlite3
import os
import re
import time
import threading
import logging
from datetime import datetime

log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "starbot_memory.db")

# All valid memory categories
CATEGORIES = ("preference", "knowledge", "project", "experience", "bug", "todo")


class MemoryStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._pref_cache: list[str] = []
        self._pref_cache_time: float = 0
        self._lock = threading.Lock()
        self._con = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA synchronous=NORMAL")
        self._init_db()
        self._migrate_schema()
        self._migrate_fts_trigram()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_db(self):
        with self._lock:
            self._con.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS db_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content, content_rowid='id'
                );
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    DELETE FROM memories_fts WHERE rowid = old.id;
                END;
            """)

    def _migrate_schema(self):
        """Add columns that were introduced after the original table was created."""
        for sql in (
            "ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0",
            "ALTER TABLE memories ADD COLUMN importance INTEGER DEFAULT 5",
        ):
            try:
                with self._lock:
                    self._con.execute(sql)
                    self._con.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

    def _migrate_fts_trigram(self):
        """Upgrade FTS5 to trigram tokenizer (handles Chinese without spaces)."""
        try:
            with self._lock:
                row = self._con.execute(
                    "SELECT value FROM db_meta WHERE key='fts_tokenizer'"
                ).fetchone()
                if row and row[0] == "trigram":
                    return
            with self._lock:
                self._con.executescript("""
                    DROP TRIGGER IF EXISTS memories_ai;
                    DROP TRIGGER IF EXISTS memories_ad;
                    DROP TABLE IF EXISTS memories_fts;
                    CREATE VIRTUAL TABLE memories_fts USING fts5(
                        content, content_rowid='id', tokenize='trigram'
                    );
                    INSERT INTO memories_fts(rowid, content)
                        SELECT id, content FROM memories;
                    CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
                        INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
                    END;
                    CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
                        DELETE FROM memories_fts WHERE rowid = old.id;
                    END;
                    INSERT OR REPLACE INTO db_meta(key, value)
                        VALUES('fts_tokenizer','trigram');
                """)
            log.info("Memory FTS upgraded to trigram tokenizer")
        except sqlite3.Error as e:
            log.debug("FTS trigram migration skipped (old SQLite?): %s", e)

    # ── Write ─────────────────────────────────────────────────────────────────

    def save(self, category: str, content: str, importance: int = 5) -> bool:
        """Insert memory. Returns False if exact duplicate already exists.

        Args:
            category:   One of CATEGORIES (preference/knowledge/project/experience/bug/todo).
            content:    The text to store.
            importance: Relevance weight 1-10 (default 5). Higher = retrieved first.
        """
        if category not in CATEGORIES:
            category = "knowledge"
        importance = max(1, min(10, int(importance)))
        try:
            with self._lock:
                dup = self._con.execute(
                    "SELECT id FROM memories WHERE category=? AND substr(content,1,200)=?",
                    (category, content[:200]),
                ).fetchone()
                if dup:
                    return False
                self._con.execute(
                    "INSERT INTO memories (category, content, importance) VALUES (?, ?, ?)",
                    (category, content, importance),
                )
                self._con.commit()
            self._pref_cache_time = 0
            return True
        except sqlite3.Error as e:
            log.debug("memory save error: %s", e)
            return False

    def delete_by_id(self, memory_id: int) -> bool:
        """Delete a single memory by its primary key."""
        try:
            with self._lock:
                self._con.execute("DELETE FROM memories WHERE id=?", (memory_id,))
                self._con.commit()
            self._pref_cache_time = 0
            return True
        except sqlite3.Error as e:
            log.debug("memory delete error: %s", e)
            return False

    def delete_by_category(self, category: str) -> int:
        """Delete all memories in a category. Returns number of rows deleted."""
        try:
            with self._lock:
                cur = self._con.execute("DELETE FROM memories WHERE category=?", (category,))
                self._con.commit()
            self._pref_cache_time = 0
            return cur.rowcount
        except sqlite3.Error as e:
            log.debug("memory delete_by_category error: %s", e)
            return 0

    def clear_all(self) -> int:
        """Delete ALL memories. Returns number of rows deleted."""
        try:
            with self._lock:
                cur = self._con.execute("DELETE FROM memories")
                self._con.commit()
            self._pref_cache = []
            self._pref_cache_time = 0
            return cur.rowcount
        except sqlite3.Error as e:
            log.debug("memory clear_all error: %s", e)
            return 0

    def list_by_category(self, category: str = "", limit: int = 20) -> list[dict]:
        """Return memories filtered by category (or all if empty), newest first."""
        try:
            with self._lock:
                if category:
                    rows = self._con.execute(
                        "SELECT id, category, content, importance, created_at FROM memories "
                        "WHERE category=? ORDER BY created_at DESC LIMIT ?",
                        (category, limit),
                    ).fetchall()
                else:
                    rows = self._con.execute(
                        "SELECT id, category, content, importance, created_at FROM memories "
                        "ORDER BY created_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            return [
                {"id": r[0], "category": r[1], "content": r[2],
                 "importance": r[3] or 5, "created_at": r[4]}
                for r in rows
            ]
        except sqlite3.Error as e:
            log.debug("memory list error: %s", e)
            return []

    def stats(self) -> dict:
        """Return memory count grouped by category."""
        try:
            with self._lock:
                rows = self._con.execute(
                    "SELECT category, COUNT(*) FROM memories GROUP BY category ORDER BY COUNT(*) DESC"
                ).fetchall()
            return {r[0]: r[1] for r in rows}
        except sqlite3.Error as e:
            log.debug("memory stats error: %s", e)
            return {}

    # ── Housekeeping / cleanup ────────────────────────────────────────────────

    def cleanup_low_importance(self, *, max_age_days: int = 30, importance_threshold: int = 3) -> int:
        """Delete low-importance, old memories to avoid长期堆积无关内容。

        - importance ≤ importance_threshold
        - created_at 早于 max_age_days 天前
        Returns number of rows deleted.
        """
        importance_threshold = max(1, min(10, int(importance_threshold)))
        try:
            with self._lock:
                cur = self._con.execute(
                    """
                    DELETE FROM memories
                    WHERE importance <= ?
                      AND datetime(created_at) <= datetime('now', ?)
                    """,
                    (importance_threshold, f"-{int(max_age_days)} days"),
                )
                self._con.commit()
            self._pref_cache_time = 0
            return cur.rowcount
        except sqlite3.Error as e:
            log.debug("memory cleanup_low_importance error: %s", e)
            return 0

    # ── Keyword extraction ────────────────────────────────────────────────────

    @staticmethod
    def _keywords(query: str) -> list[str]:
        """Extract distinct search keywords from a natural-language query.

        Returns a deduplicated list ordered by usefulness:
        - Chinese segments of 3-6 chars (long enough for trigram FTS, short enough to match)
        - Chinese segments of 2 chars  (too short for trigram FTS, but fine for LIKE)
        - English words of 3+ chars
        - If nothing found: the first 12 chars of the query as a last resort

        We intentionally limit Chinese segments to ≤6 chars to avoid picking up
        function-word runs like "最近学习了什么" as a single useless keyword.
        """
        # Split on non-CJK non-ASCII boundaries to isolate runs of each type
        zh3 = re.findall(r'[\u4e00-\u9fff]{3,6}', query)   # best for FTS5 trigram
        zh2 = re.findall(r'[\u4e00-\u9fff]{2}',   query)   # LIKE only (trigram needs ≥3)
        en  = re.findall(r'[a-zA-Z]{3,}',          query)

        seen: set[str] = set()
        result: list[str] = []
        for kw in zh3 + en + zh2:          # zh3/en first — better for FTS
            kw_lower = kw.lower()
            if kw_lower not in seen and kw.strip():
                seen.add(kw_lower)
                result.append(kw)

        if not result:
            fallback = query.strip()[:12]
            if fallback:
                result.append(fallback)
        return result

    # ── Core search ───────────────────────────────────────────────────────────

    @staticmethod
    def _relevance_score(item: dict) -> float:
        """Score = importance * time_decay.

        Time decay: half-life of 30 days (recent memories rank higher).
        importance defaults to 5 when not present in the row.
        """
        importance = item.get("importance") or 5
        created_at = item.get("created_at", "")
        try:
            dt = datetime.fromisoformat(str(created_at))
            age_days = max(0, (datetime.now() - dt).days)
        except Exception:
            age_days = 0
        decay = math.exp(-age_days / 30.0)   # half-life 30 days
        return importance * decay

    def _fts_one(self, token: str, limit: int, category: str | None = None) -> list[dict]:
        """Single-keyword FTS5 search using subquery (avoids FTS virtual table JOIN issues).

        Uses phrase-quoted MATCH so trigram tokenizer treats the token as a
        literal substring to find, not as separate words.
        Silently returns [] on any error so callers always get a list.
        """
        if len(token) < 3:          # FTS5 trigram requires ≥3 codepoints
            return []
        try:
            safe = token.replace('"', '""')
            with self._lock:
                if category:
                    rows = self._con.execute(
                        """SELECT id, category, content, importance, created_at FROM memories
                           WHERE category=? AND id IN (
                               SELECT rowid FROM memories_fts
                               WHERE memories_fts MATCH ?
                           )
                           LIMIT ?""",
                        (category, f'"{safe}"', limit * 2),   # over-fetch, then re-rank
                    ).fetchall()
                else:
                    rows = self._con.execute(
                        """SELECT id, category, content, importance, created_at FROM memories
                           WHERE id IN (
                               SELECT rowid FROM memories_fts
                               WHERE memories_fts MATCH ?
                           )
                           LIMIT ?""",
                        (f'"{safe}"', limit * 2),   # over-fetch, then re-rank
                    ).fetchall()
            items = [
                {"id": r[0], "category": r[1], "content": r[2],
                 "importance": r[3] or 5, "created_at": r[4]}
                for r in rows
            ]
            items.sort(key=self._relevance_score, reverse=True)
            return items[:limit]
        except sqlite3.Error as e:
            log.debug("FTS search error for %r: %s", token, e)
            return []

    def _like_one(self, token: str, limit: int, category: str | None = None) -> list[dict]:
        """Single-keyword LIKE search — always works, no minimum length."""
        try:
            with self._lock:
                if category:
                    rows = self._con.execute(
                        """SELECT id, category, content, importance, created_at FROM memories
                           WHERE category=? AND content LIKE ?
                           LIMIT ?""",
                        (category, f"%{token}%", limit * 2),
                    ).fetchall()
                else:
                    rows = self._con.execute(
                        """SELECT id, category, content, importance, created_at FROM memories
                           WHERE content LIKE ?
                           LIMIT ?""",
                        (f"%{token}%", limit * 2),
                    ).fetchall()
            items = [
                {"id": r[0], "category": r[1], "content": r[2],
                 "importance": r[3] or 5, "created_at": r[4]}
                for r in rows
            ]
            items.sort(key=self._relevance_score, reverse=True)
            return items[:limit]
        except sqlite3.Error as e:
            log.debug("LIKE search error for %r: %s", token, e)
            return []

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search for a single keyword (the best one extracted from query).

        Tries FTS5 first for ranking quality; falls back to LIKE if FTS
        returns nothing or the keyword is too short for trigram.
        """
        kws = self._keywords(query)
        token = kws[0] if kws else query[:12]

        results = self._fts_one(token, limit)
        if results:
            self._bump_access([r["id"] for r in results if "id" in r])
            return results

        return self._like_one(token, limit)

    def search_multi(self, query: str, limit: int = 8, category: str | None = None) -> list[dict]:
        """Multi-keyword search — the main entry-point for memory recall.

        Extracts every meaningful keyword from the query and searches for
        each one independently (FTS → LIKE), merging and deduplicating
        results by content prefix.  This handles natural-language queries
        like "帮我找关于Python异步编程的学习笔记" correctly.
        """
        keywords = self._keywords(query)
        seen: set[str] = set()
        results: list[dict] = []

        cat = (category or "").strip().lower() or None
        if cat and cat not in CATEGORIES:
            cat = None

        def _add(items: list) -> None:
            for item in items:
                key = item.get("content", "")[:120]
                if key not in seen:
                    seen.add(key)
                    results.append(item)

        for kw in keywords[:8]:
            if len(results) >= limit:
                break
            need = max(2, limit - len(results))
            # FTS first, then LIKE if FTS gives nothing
            found = self._fts_one(kw, need, category=cat) or self._like_one(kw, need, category=cat)
            _add(found)

        # Bump access counts once for all found items
        if results:
            self._bump_access([r["id"] for r in results if "id" in r])
        return results[:limit]

    def _bump_access(self, ids: list[int]) -> None:
        """Increment access_count for matched memories by id (best-effort)."""
        if not ids:
            return
        try:
            with self._lock:
                self._con.execute(
                    f"UPDATE memories SET access_count=access_count+1 "
                    f"WHERE id IN ({','.join('?' * len(ids))})",
                    ids,
                )
                self._con.commit()
        except sqlite3.Error:
            pass

    # ── Convenience ───────────────────────────────────────────────────────────

    def get_relevant(self, task: str, limit: int = 8) -> list[str]:
        return [r["content"] for r in self.search_multi(task, limit)]

    def get_preferences(self) -> list[str]:
        if self._pref_cache and time.time() - self._pref_cache_time < 300:
            return self._pref_cache
        try:
            with self._lock:
                rows = self._con.execute(
                    "SELECT content FROM memories WHERE category='preference' "
                    "ORDER BY access_count DESC, created_at DESC"
                ).fetchall()
            self._pref_cache = [r[0] for r in rows]
            self._pref_cache_time = time.time()
            return self._pref_cache
        except sqlite3.Error as e:
            log.debug("memory get_preferences error: %s", e)
            return self._pref_cache

    def cleanup_old(self, keep_days: int = 30):
        """删除超过 keep_days 天且 access_count=0 的旧记忆。"""
        try:
            with self._lock:
                self._con.execute(
                    "DELETE FROM memories WHERE access_count=0 "
                    "AND created_at < datetime('now', ?)",
                    (f"-{keep_days} days",),
                )
                self._con.commit()
        except sqlite3.Error as e:
            log.debug("memory cleanup error: %s", e)
