import os  # environment variables
import secrets  # safe key compare
import time  # waqt naapne ke liye
import uuid  # request id banane ke liye
from contextlib import asynccontextmanager  # startup/shutdown ke liye
from dotenv import load_dotenv  # .env file parhne ke liye
from fastapi import FastAPI, Header, HTTPException  # FastAPI ke hisse
from fastapi.responses import FileResponse  # chat page bhejne ke liye
from pydantic import BaseModel, Field  # input validation

load_dotenv()  # .env load karo (sab imports se pehle env chahiye)

import db  # noqa: E402  database
import tools  # noqa: E402  business logic
from agents import TradeDeskBot, build_llm, load_tools  # noqa: E402  agents
from limits import Limits  # noqa: E402  rate limit aur cost cap
from logs import log_event  # noqa: E402  structured logs

DB_PATH = os.path.abspath(os.getenv("DB_PATH", "trade_desk.db"))  # database ka poora path
os.environ["DB_PATH"] = DB_PATH  # taake MCP server bhi wohi use kare
limits = Limits(int(os.getenv("RATE_LIMIT_PER_MIN", "10")), int(os.getenv("DAILY_LLM_CALLS", "300")))  # limits


@asynccontextmanager
async def lifespan(app):
    """Startup: prepare database, start MCP tools, build the bot."""
    conn = db.get_connection(DB_PATH)  # database kholo
    db.init_db(conn)  # tables banao
    db.seed_db(conn)  # sample data daalo (agar khali ho)
    conn.close()  # band karo
    app.state.bot = TradeDeskBot(build_llm(), await load_tools(DB_PATH))  # bot tayyar
    yield  # app chalti rahe


app = FastAPI(title="Trade Desk Agent", lifespan=lifespan)  # app banao


def keys_from_env(name):
    """Read comma separated keys from an env variable."""
    return [k.strip() for k in os.getenv(name, "").split(",") if k.strip()]  # list of keys


def key_ok(key, allowed):
    """Safe key check. If no keys are configured, everything is refused."""
    return bool(key) and any(secrets.compare_digest(key.encode(), a.encode()) for a in allowed)  # barabar hai?


def need_admin(key):
    """Stop the request unless the admin key is correct."""
    if not key_ok(key, keys_from_env("ADMIN_API_KEY")):  # key galat
        raise HTTPException(status_code=401, detail="Invalid API key")  # 401 error


class ChatRequest(BaseModel):
    """Input of POST /chat."""
    message: str = Field(min_length=1, max_length=500)  # 1 se 500 characters
    session_id: str = Field(pattern=r"^[A-Za-z0-9-]{8,64}$")  # sirf harf, number, dash


@app.get("/health")
def health():
    """Used by the hosting platform to check the app is alive."""
    return {"status": "ok"}  # sab theek


@app.get("/")
def chat_page():
    """Serve the simple web chat page."""
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "chat.html"))  # page bhejo


@app.post("/chat")
async def chat(req: ChatRequest, x_api_key: str = Header(default="")):
    """Customer chat. Needs a client token in the X-API-Key header."""
    if not key_ok(x_api_key, keys_from_env("CLIENT_TOKENS")):  # token galat
        raise HTTPException(status_code=401, detail="Invalid API key")  # 401
    if not limits.rate_ok(x_api_key):  # bohat tez requests
        raise HTTPException(status_code=429, detail="Too many requests, please wait a minute")  # 429
    if not limits.daily_ok():  # aaj ki cost limit poori
        raise HTTPException(status_code=503, detail="Daily limit reached, please try tomorrow")  # 503
    request_id = uuid.uuid4().hex[:8]  # chhota request id
    start = time.time()  # shuru ka waqt
    try:  # bot fail ho sakta hai
        result = await app.state.bot.chat(req.session_id, req.message)  # bot se jawab lo
    except Exception as error:  # koi bhi error
        log_event(request_id=request_id, event="chat_error", error=type(error).__name__)  # sirf error ka naam log
        raise HTTPException(status_code=500, detail="Something went wrong, please try again")  # customer ko saada message
    limits.add_calls(result["llm_calls"])  # model calls gino
    log_event(request_id=request_id, event="chat", agent=result["agent"], llm_calls=result["llm_calls"],
              ms=int((time.time() - start) * 1000), message=req.message)  # structured log (masked)
    return {"reply": result["reply"], "agent": result["agent"]}  # customer ko jawab


@app.get("/handoffs")
def get_handoffs(status: str = "open", x_api_key: str = Header(default="")):
    """Sales reps: list handoffs (open, claimed, closed, all)."""
    need_admin(x_api_key)  # admin key check
    conn = db.get_connection(DB_PATH)  # database kholo
    try:  # hamesha band karna hai
        result = tools.list_handoffs(conn, status)  # list lo
    finally:  # hamesha chalega
        conn.close()  # band karo
    if "error" in result:  # galat status
        raise HTTPException(status_code=400, detail=result["error"])  # 400
    return result  # list wapas


def change_handoff(function, handoff_id, key):
    """Shared code for claim and close."""
    need_admin(key)  # admin key check
    conn = db.get_connection(DB_PATH)  # database kholo
    try:  # hamesha band karna hai
        result = function(conn, handoff_id)  # status badlo
    finally:  # hamesha chalega
        conn.close()  # band karo
    if "error" in result:  # masla hua
        code = 404 if "not found" in result["error"] else 409  # nahi mila ya galat status
        raise HTTPException(status_code=code, detail=result["error"])  # error bhejo
    return result  # naya status


@app.post("/handoffs/{handoff_id}/claim")
def claim(handoff_id: int, x_api_key: str = Header(default="")):
    """Sales rep takes an open handoff."""
    return change_handoff(tools.claim_handoff, handoff_id, x_api_key)  # claim karo


@app.post("/handoffs/{handoff_id}/close")
def close(handoff_id: int, x_api_key: str = Header(default="")):
    """Sales rep closes a handoff."""
    return change_handoff(tools.close_handoff, handoff_id, x_api_key)  # close karo
