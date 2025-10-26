from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import logging, shlex

logger = logging.getLogger(__name__)

# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated ecop# Small, opinionated"i# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, opinionated exp# Small, om # Small, opinionatemakeup": ["makeup", "mascara", "eyeliner", "no makeup"],
}

def _escape_like(t: str) -> str:
    # Escape backslash first, then % and _
    t = t.replace("\\", "\\\\")
    t = t.replace("%", "\\%").replace("_", "\\_")
    return t

def _tokenize(raw: str) -> List[str]:
    """
    Phrase-aware tokenization: respects quotes, e.g. "video call".
    """
    if not raw:
        return []
    try:
        toks = shlex.split(raw)
    except Exception:
        toks = raw.split()
    return [t.strip() for t in toks if t.strip()]

def expand_query(raw: str) -> List[str]:
    """
    Expand each token; keep quoted phrases intact.
    """
    tokens = _tokenize(raw)
    expanded: List[str] = []
    for tok in tokens:
        key = tok.lower()
        expanded.extend(EXPANSIONS.get(key, [tok]))
    # dedupe preserving order
    seen = set()
    out = []
    for x in expanded or tokens:
        xl = x.lower()
        if xl not in seen:
            seen.add(xl)
            out.append(x)
    logger.info("search expand -> tokens=%r expanded=%r", tokens, out)
    return out

def connect(db_path: str = "briefs.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def rows_to_dicts(rows) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]

def search_messages(conn: sqlite3.Connection, query: str, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Lightweight retrieval over SQLite: LIKE on expanded terms/phrases, ordered by recency.
    """
    try:
        terms = expand_query(query)
        if not terms:
            return []
        where = " OR ".join(["text LIKE ? ESCAPE '\'" for _ in terms])
        like_params = [f"%{_escape_like(t)}%" for t in terms]
        sql = f"""
            SELECT id, peer_id, msg_id, ts_utc, from_me, text, message_id
            FROM messages
            WHERE {where}
            ORDER BY ts_utc DESC
            LIMIT ?
        """
        cur = conn.execute(sql, (*like_params, limit))
        rows = rows_to_dicts(cur.fetchall())
        logger.info("search rows=%d limit=%d", len(rows), limit)
        return rows
    except Exception:
        logger.exception("search_messages failed")
        return []

def find_last_call_anchor(conn: sqlite3.Connection, fallback_hours: int = 48) -> datetime:
    now = datetime.now(timezone.utc)
    try:
        cur = conn.execute("""
            SELECT ts_utc FROM messages
            WHERE text LIKE '%call%' OR text LIKE '%video%' OR text LIKE '%private%'
            ORDER BY ts_utc DESC LIMIT 1
        """)
        row = cur.fetchone()
        if row and row["ts_utc"]:
            s = str(row["ts_utc"])
            try:
                return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
            except Exception:
                return datetime.fromtimestamp(float(s), tz=timezone.utc)
    except Exception:
        logger.exception("find_last_call_anchor failed")
    return now - timedelta(hours=fallback_hours)

def get_window(conn: sqlite3.Connection, start_utc: datetime) -> List[Dict[str, Any]]:
    try:
        cur = conn.execute("""
            SELECT id, peer_id, msg_id, ts_utc, from_me, text, message_id
            FROM messages
            WHERE ts_utc >= ?
            ORDER BY ts_utc ASC
        """, (start_utc.isoformat().replace("+00:00",""),))
        return rows_to_dicts(cur.fetchall())
    except Exception:
        logger.exception("get_window failed")
        return []
