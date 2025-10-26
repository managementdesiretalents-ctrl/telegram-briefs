from datetime import datetime, timezone
from typing import List, Dict, Any

try:
    import zoneinfo
    LOCAL_TZ = zoneinfo.ZoneInfo("Australia/Brisbane")
except Exception:
    LOCAL_TZ = None

def _to_local_date_str(ts_utc) -> str:
    if isinstance(ts_utc, (int, float)):
        dt = datetime.fromtimestamp(float(ts_utc), tz=timezone.utc)
    else:
        s = str(ts_utc)
        try:
            dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        except Exception:
            try:
                dt = datetime.fromtimestamp(float(s), tz=timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)
    if LOCAL_TZ:
        dt = dt.astimezone(LOCAL_TZ)
    return dt.strftime("%-d %b %Y")

def _who(from_me) -> str:
    return "YOU" if str(from_me).lower() in ("1","true") else "THEM"

def _snip(text: str, n=180) -> str:
    t = (text or "").replace("\n"," ").strip()
    return (t[:n] + "…") if len(t) > n else t

def _old_note(ts) -> str:
    try:
        s = str(ts)
        dt = datetime.fromisoformat(s)
    except Exception:
        try:
            dt = datetime.fromtimestamp(float(s))
        except Exception:
            return ""
    if (datetime.utcnow() - dt.replace(tzinfo=None)).days > 60:
        return f" (from {_to_local_date_str(ts)})"
    return ""

def synthesize_answer(query: str, hits: List[Dict[str,Any]]) -> str:
    if not hits:
        return "**Conclusion:** I couldn’t find anything relevant."
    concl = _snip(hits[0].get("text",""), 220)
    note = _old_note(hits[0].get("ts_utc"))
    lines=[]
    for h in hits[:6]:
        lines.append(f'[{_to_local_date_str(h.get("ts_utc"))}, {_who(h.get("from_me"))}] "{_snip(h.get("text",""))}"')
    return f"**Conclusion{note}:** {concl}\n" + "\n".join(lines)

def summarize_window(rows: List[Dict[str,Any]]) -> str:
    if not rows:
        return "No messages in the chosen window."
    bullets=[]; actions=[]
    for r in rows[-40:]:
        s=_snip(r.get("text",""))
        who=_who(r.get("from_me"))
        if any(k in s.lower() for k in ("todo","action","next","please","due","deadline")):
            actions.append(f"- [{who}] {s}")
        else:
            bullets.append(f"- [{who}] {s}")
    out=["**Call Prep**","*Recent context since last call/private/video (or 48h fallback):*"]
    out.extend(bullets[:10] or ["- (quiet thread)"])
    if actions:
        out.append("\n**Today’s action items**")
        out.extend(actions[:5])
    return "\n".join(out)
