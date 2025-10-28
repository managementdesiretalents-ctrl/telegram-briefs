from __future__ import annotations

import logging
import shlex
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

# Small, opinionated expansions to make natural queries hit the SQLite LIKE
# searches.  Only a handful of high-signal terms are expanded and we keep the
# lists short so the query remains fast.
EXPANSIONS: Dict[str, List[str]] = {
    "call": ["call", "calls", "phone call", "video call", "vc"],
    "video": ["video", "video call", "vc", "zoom"],
    "private": ["private", "privates", "private show"],
    "stream": ["stream", "streaming", "chaturbate", "cb"],
    "book": ["book", "booked", "booking", "schedule"],
    "confirm": ["confirm", "confirmed", "confirmation"],
    "resched": ["resched", "reschedule", "rescheduled", "rescheduling"],
    "cancel": ["cancel", "cancelled", "canceled", "cancellation"],
    "time": ["time", "what time", "when"],
    "tomorrow": ["tomorrow", "tmrw"],
    "today": ["today", "tonight"],
    "deposit": ["deposit", "pay", "payment", "paid"],
    "makeup": ["makeup", "mascara", "eyeliner", "no makeup"],
}


def _escape_like(t: str) -> str:
    """Escape tokens for use inside a LIKE clause."""

    # Escape backslash first, then % and _
    t = t.replace("\\", "\\\\")
    t = t.replace("%", "\\%").replace("_", "\\_")
    return t


def _tokenize(raw: str) -> List[str]:
    """Phrase-aware tokenisation that respects quotes ("video call")."""

    if not raw:
        return []
    try:
        toks = shlex.split(raw)
    except Exception:
        toks = raw.split()
    return [t.strip() for t in toks if t.strip()]


def _expand_token(tok: str) -> Iterable[str]:
    key = tok.lower()
    return EXPANSIONS.get(key, [tok])


def expand_query(raw: str) -> List[str]:
    """Expand each token while keeping quoted phrases intact."""

    tokens = _tokenize(raw)
    expanded: List[str] = []
    for tok in tokens:
        expanded.extend(_expand_token(tok))

    # Dedupe while preserving order.  If expansion produced nothing (shouldn't
    # happen) fall back to the original tokens to keep behaviour predictable.
    seen = set()
    out: List[str] = []
    for candidate in expanded or tokens:
        cand_lower = candidate.lower()
        if cand_lower not in seen:
            seen.add(cand_lower)
            out.append(candidate)

    logger.info("search expand -> tokens=%r expanded=%r", tokens, out)
    return out


def connect(db_path: str = "briefs.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]


def search_messages(conn: sqlite3.Connection, query: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Lightweight retrieval using LIKE clauses on the expanded terms."""

    try:
        terms = expand_query(query)
        if not terms:
            return []
        where = " OR ".join(["text LIKE ? ESCAPE '\\'" for _ in terms])
        like_params = [f"%{_escape_like(t)}%" for t in terms]
        sql = (
            "SELECT id, peer_id, msg_id, ts_utc, from_me, text, message_id "
            "FROM messages "
            f"WHERE {where} "
            "ORDER BY ts_utc DESC "
            "LIMIT ?"
        )
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
        cur = conn.execute(
            """
            SELECT ts_utc FROM messages
            WHERE text LIKE '%call%' OR text LIKE '%video%' OR text LIKE '%private%'
            ORDER BY ts_utc DESC LIMIT 1
            """
        )
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
        cur = conn.execute(
            """
            SELECT id, peer_id, msg_id, ts_utc, from_me, text, message_id
            FROM messages
            WHERE ts_utc >= ?
            ORDER BY ts_utc ASC
            """,
            (start_utc.isoformat().replace("+00:00", ""),),
        )
        return rows_to_dicts(cur.fetchall())
    except Exception:
        logger.exception("get_window failed")
        return []
