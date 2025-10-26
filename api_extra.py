from logging_setup import setup_logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import PlainTextResponse
import os, logging
from retrieval import connect, search_messages, find_last_call_anchor, get_window
from format_helpers import synthesize_answer, summarize_window

router = APIRouter()
logger = setup_logging('telegram_briefs')
DB_PATH = os.getenv("DB_PATH", "briefs.db")

@router.post("/question")
async def question(request: Request,
                   text: str = Form(default=""),
                   user_name: str = Form(default=""),
                   user_id: str = Form(default="")):
    try:
        logger.info("/question user=%s(%s) text=%r", user_name, user_id, text)
        conn = connect(DB_PATH)
        hits = search_messages(conn, text, limit=200)
        answer = synthesize_answer(text, hits)
        return PlainTextResponse(answer)
    except Exception:
        logger.exception("/question failed")
        return PlainTextResponse("Sorry, something went wrong.", status_code=500)

@router.post("/callprep")
async def callprep(request: Request,
                   text: str = Form(default=""),
                   user_name: str = Form(default=""),
                   user_id: str = Form(default="")):
    try:
        logger.info("/callprep user=%s(%s) text=%r", user_name, user_id, text)
        conn = connect(DB_PATH)
        start = find_last_call_anchor(conn, fallback_hours=48)
        rows = get_window(conn, start)
        summary = summarize_window(rows)
        return PlainTextResponse(summary)
    except Exception:
        logger.exception("/callprep failed")
        return PlainTextResponse("Sorry, something went wrong.", status_code=500)
