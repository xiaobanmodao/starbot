import sqlite3
import json
from . import tool


@tool(
    name="sqlite_query",
    description="Execute a SQL query on a SQLite database file. Returns results as JSON.",
    params={
        "properties": {
            "db_path": {"type": "string", "description": "Path to SQLite database file"},
            "sql": {"type": "string", "description": "SQL query to execute"},
        },
        "required": ["db_path", "sql"],
    },
    dangerous=True,
)
def sqlite_query(db_path: str, sql: str) -> str:
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql)
        if sql.strip().upper().startswith("SELECT") or sql.strip().upper().startswith("PRAGMA"):
            rows = [dict(r) for r in cur.fetchall()[:200]]
            conn.close()
            return json.dumps(rows, ensure_ascii=False, default=str)
        else:
            conn.commit()
            affected = cur.rowcount
            conn.close()
            return f"OK, {affected} rows affected"
    except Exception as e:
        return f"[error] {e}"
