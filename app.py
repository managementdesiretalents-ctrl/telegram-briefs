
import os, hmac, hashlib, time, sqlite3, threading
from urllib.parse import parse_qs
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from openai import OpenAI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


load_dotenv()
DB = "briefs.db"
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SKIP_VERIFY = os.getenv("SLACK_SKIP_VERIFY","0") == "1"
assert OPENAI_KEY, "Missing OPENAI_API_KEY in .env"
assert SLACK_BOT_TOKEN, "Missing SLACK_BOT_TOKEN in .env"

ai = OpenAI(api_key=OPENAI_KEY)
slack = WebClient(token=SLACK_BOT_TOKEN)
tz = ZoneInfo("Australia/Brisbane")
PEER_ID = 7740422022

app = FastAPI()

def verify_slack(req: Request, body: bytes) -> bool:
    ts = req.headers.get("X-Slack-Request-Timestamp", "")
    sig = req.headers.get("X-Slack-Signature", "")
    if not ts or not sig:
        return False
    try:
        if abs(time.time() - int(ts)) > 300:
            return False
    except:
        return False
    base = f"v0:{ts}:{body.decode('utf-8')}".encode("utf-8")
    mac = hmac.new(SLACK_SIGNING_SECRET.encode("utf-8"), base, hashlib.sha256).hexdigest()
    calc = f"v0={mac}"
    return hmac.compare_digest(calc, sig)

def db_connect():
    return sqlite3.connect(DB)

def get_today_date_label():
    now_local = datetime.now(tz)
    return f"{int(now_local.strftime('%d'))}/{int(now_local.strftime('%m'))}/{now_local.strftime('%y')}"

def get_latest_summary_for_channel(channel_id: str):
    con = db_connect()
    row = con.execute(
        "SELECT ts, text, date_label FROM summaries WHERE channel_id=? ORDER BY posted_utc DESC LIMIT 1",
        (channel_id,)
    ).fetchone()
    con.close()
    if row:
        return {"ts": row[0], "text": row[1], "date_label": row[2]}
    return None

def post_in_thread(channel_id: str, thread_ts: str, text: str):
    try:
        slack.chat_postMessage(channel=channel_id, text=text, thread_ts=thread_ts)
    except SlackApiError as e:
        print("Slack thread post failed:", e.response.get("error"))

def fetch_messages_since(iso_utc: str):
    con = db_connect()
    rows = con.execute("""
        SELECT ts_utc, from_me, text
        FROM messages
        WHERE ts_utc >= ?
          AND peer_id = ?
        ORDER BY ts_utc ASC
    """, (iso_utc, PEER_ID)).fetchall()
    con.close()
    return rows

def clean_text(t: str) -> str:
    return " ".join(((t or "").replace("\n"," ").replace("\r"," ")).split())

def ai_answer(question: str, msgs: list, facts: list) -> str:
    lines = []
    for ts, me, txt in msgs[-250:]:
        who = "SHE" if me == 1 else "HE"
        lines.append(f"{ts} — {who}: {clean_text(txt)}")
    fact_lines = [f"- {f}" for f in facts[-100:]]
    sys_prompt = "Answer concisely (≤ 80 words) based ONLY on the context below. If not in context, say you don't have that info. Plain English. No emojis."
    user_prompt = f"""Context — recent messages:
{chr(10).join(lines)}

Context — stored facts:
{chr(10).join(fact_lines) if fact_lines else "(none)"}

Question: {question}
Give a short answer in one or two sentences."""
    resp = ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":sys_prompt},{"role":"user","content":user_prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()

def ai_call_prep(since_iso: str) -> str:
    msgs = fetch_messages_since(since_iso)
    dlabel = get_today_date_label()
    if not msgs:
        return f"Date: {dlabel}\n\n- No new messages since last call.\n\nAny privates/ calls?\n- None mentioned."
    CALL_KEYS = ("call","private","cb","chaturbate","stream","record","book","booked","confirm","confirmed",
                 "resched","reschedule","cancel","canceled","time","am","pm","o'clock","tomorrow","today",
                 "makeup","no makeup","natural","surprise")
    lines, call_lines = [], []
    for ts, me, txt in msgs:
        who = "SHE" if me==1 else "HE"
        s = f"{ts} — {who}: {clean_text(txt)}"
        lines.append(s)
        low = s.lower()
        if any(k in low for k in CALL_KEYS):
            call_lines.append(s)
    chat_snippet = "\n".join(lines[-400:])
    call_snippet = "\n".join(call_lines[-200:]) if call_lines else "(none)"
    style = open("summary_style.txt","r",encoding="utf-8").read().replace("{date_au}", dlabel)
    out = ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":style},
            {"role":"user","content":f"Here are messages since the last call (UTC):\n\n{chat_snippet}\n\nCall-related lines only (filtered):\n{call_snippet}\n\nWrite the report now, following the layout and rules exactly."}
        ],
        temperature=0.2,
    ).choices[0].message.content.strip()
    if len(out.split()) > 250:
        out = ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"Shorten to ≤250 words. Keep EXACT same format and meaning."},
                      {"role":"user","content":out}],
            temperature=0.0
        ).choices[0].message.content.strip()
    return out

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

def handle_update(channel_id: str, thread_ts: str, user_id: str, text: str):
    con = db_connect()
    con.execute(
        "INSERT INTO facts(created_utc, author_slack_id, text, source, confidence) VALUES (?,?,?,?,?)",
        (datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), user_id, text, "manual", "high")
    )
    con.commit(); con.close()
    post_in_thread(channel_id, thread_ts, f"✔ Added fact: {text}")

def handle_question(channel_id: str, thread_ts: str, question: str):
    ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    msgs = fetch_messages_since(ninety_days_ago)
    con = db_connect()
    facts = [r[0] for r in con.execute("SELECT text FROM facts ORDER BY id ASC").fetchall()]
    con.close()
    answer = ai_answer(question, msgs, facts)
    post_in_thread(channel_id, thread_ts, f"*Q:* {question}\n*A:* {answer}")

def handle_callprep(channel_id: str, thread_ts: str):
    con = db_connect()
    row = con.execute("SELECT occurred_utc FROM calls ORDER BY occurred_utc DESC LIMIT 1").fetchone()
    con.close()
    since_iso = row[0] if row else (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prep = ai_call_prep(since_iso)
    post_in_thread(channel_id, thread_ts, f"*Call prep (since last call)*\n{prep}")

def handle_markcall(channel_id: str, thread_ts: str, note: str):
    con = db_connect()
    now_utc = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    con.execute("INSERT INTO calls(occurred_utc, source, notes) VALUES (?,?,?)", (now_utc, "manual", note.strip()))
    con.commit(); con.close()
    msg = "✔ Marked last call as now (UTC)."
    if note.strip():
        msg += f" Note: {note.strip()}"
    post_in_thread(channel_id, thread_ts, msg)

@app.post("/slack/command")
async def slack_command(request: Request):
    body = await request.body()
    if not SKIP_VERIFY and not verify_slack(request, body):
        return Response(status_code=403)
    data = parse_qs(body.decode())
    command = (data.get("command", [""])[0] or "").strip()
    text = (data.get("text", [""])[0] or "").strip()
    user_id = (data.get("user_id", [""])[0] or "").strip()
    channel_id = (data.get("channel_id", [""])[0] or "").strip()
    latest = get_latest_summary_for_channel(channel_id)
    if not latest:
        return JSONResponse({"response_type":"ephemeral","text":"I couldn't find today's summary thread here yet. Post the daily summary first."})
    thread_ts = latest["ts"]

    if command == "/update":
        threading.Thread(target=handle_update, args=(channel_id, thread_ts, user_id, text), daemon=True).start()
        return PlainTextResponse("Saving… will reply in thread.", status_code=200)
    if command == "/question":
        threading.Thread(target=handle_question, args=(channel_id, thread_ts, text), daemon=True).start()
        return PlainTextResponse("Working… will reply in thread.", status_code=200)
    if command in ("/callprep", "/call-prep"):
        threading.Thread(target=handle_callprep, args=(channel_id, thread_ts), daemon=True).start()
        return PlainTextResponse("Preparing… will reply in thread.", status_code=200)
    if command == "/markcall":
        threading.Thread(target=handle_markcall, args=(channel_id, thread_ts, text), daemon=True).start()
        return PlainTextResponse("Marked… will reply in thread.", status_code=200)
    return PlainTextResponse(f"Unknown command: {command}", status_code=200)

# --- injected by setup ---
import api_extra
try:
    app.include_router(api_extra.router)
except Exception:
    pass
# --- end injection ---
