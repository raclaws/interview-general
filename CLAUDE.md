# Interview Form Summarizer

A lightweight self-hosted webapp for generating on-demand interview assessment sessions. Admin creates a session with candidate context, shares a token link with the interviewer, and AI summarizes the submission.

## Architecture

- FastAPI backend (Python 3.12, uvicorn)
- SQLite persistence via SQLModel ORM
- Jinja2 server-rendered templates (no frontend framework)
- OpenAI-compatible LLM integration for interview summarization
- NocoDB integration for candidate lookup (optional)
- MCP server for agent access (create/get/list sessions)
- Admin auth via bcrypt + session cookies (itsdangerous)

## Key Decisions

- **SQLite over Postgres** — single-file deployment, no external DB dependency
- **Server-side rendering over SPA** — simplicity, no JS build step
- **Token-based interview links** — single-use, stateless sharing with interviewers
- **LLM config in DB** — dashboard-editable without restart, .env is initial seed only
- **Provider-agnostic LLM** — any OpenAI-compatible endpoint via base URL + key + model

## Constraints

- Self-hosted, no cloud dependency
- Single admin user model (no multi-tenant)
- Interview tokens are single-use — consumed on submission
- NocoDB is optional — manual candidate entry supported

## Project Structure

- `app/main.py` — FastAPI app factory, route registration, static mount
- `app/models.py` — SQLModel schemas (Session, Admin, Settings)
- `app/database.py` — SQLite engine, session factory, table creation
- `app/auth.py` — bcrypt password hashing, cookie-based session auth
- `app/llm.py` — OpenAI-compatible client, summarization prompt
- `app/nocodb.py` — NocoDB API client for candidate search
- `app/cli.py` — CLI commands (create-admin)
- `app/mcp_server.py` — FastMCP server exposing session tools
- `app/routes/admin.py` — Dashboard, session CRUD, settings, results
- `app/routes/interview.py` — Token validation, form rendering, submission

## Patterns

- Admin routes behind auth, interview routes behind token validation. Split in `app/routes/admin.py` and `app/routes/interview.py`.
- `app/llm.py` wraps OpenAI client. Config loaded from DB (fallback to .env). Single function call for summarization.
- Sessions have unique tokens. Interviewer accesses form via `/interview/{token}`. Token consumed on submission.

## Environment Variables

| Key | Required | Description |
|-----|----------|-------------|
| LLM_BASE_URL | yes | OpenAI-compatible endpoint |
| LLM_API_KEY | yes | LLM provider API key |
| LLM_MODEL | yes | Model identifier |
| ADMIN_SESSION_SECRET | yes | Cookie signing secret |
| DATABASE_URL | no | SQLite connection string (default: sqlite:///./interview.db) |
| NOCODB_BASE_URL | no | NocoDB instance URL for candidate lookup |
| NOCODB_API_KEY | no | NocoDB PAT token |
| NOCODB_TABLE_ID | no | NocoDB table for candidates |
| NOCODB_BASE_ID | no | NocoDB base identifier |

## Agent Protocol

This project uses StratVibe (Substrate) for structured agent orchestration. See `.substrate/` for protocol rules (taxonomy, roles, token budgets, handoffs). Agent entrypoint is `AGENTS.md`.

## Dev

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Default port: 8000, Python >=3.12, FastAPI >=0.115.0, SQLModel 0.0.22.
