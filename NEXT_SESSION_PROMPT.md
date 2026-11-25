You are helping me (Asad) build "Trade Desk Agent" step by step. Talk in simple Roman Urdu.
Code simple, a simple English comment on every line, tool docstrings in English. Ask before coding if unclear. Keep answers short.

Environment: Ubuntu, Python 3.10, venv, ~/Downloads/PROJECTS PRODUCTION/trade_desk. Gemini model "gemini-3.5-flash-lite" via langchain-google-genai, key GEMINI_API_KEY in .env (never print). Keep "mcp<2" pinned; server uses `from mcp.server.fastmcp import FastMCP`; MCP tools are async only (ainvoke, asyncio).

Decisions: no quotes/prices/discounts (human handoff); prices never shown; stock only in words; order status needs order ID + email (same error for wrong email or missing order); business rules in tools.py; handoffs idempotent; private data masked in logs; no refunds.

STATUS: Milestones 1-6 written. Router pattern (1 router call + 1 agent with tool loop, max 5 rounds, history last 6 msgs, max 1000 sessions). Files: db.py, tools.py, trade_server.py, utils.py, agents.py, limits.py, logs.py, api.py, static/chat.html, tests (25 pass with fake model), Dockerfile, docker-compose.yml, render.yaml, CI. 
Verified: unit tests only. NOT yet run on my machine: smoke_test_server.py, uvicorn, real Gemini, Docker, Render.

NEXT STEPS: 1) run smoke test + uvicorn locally and fix errors (paste them here). 2) replace SAMPLE data with real company data (stock thresholds, lead times). 3) move SQLite to Postgres (Neon) for deploy. 4) deploy on Render free. 5) Milestone 7: WhatsApp adapter on /chat. 6) pin versions with `pip freeze`.
