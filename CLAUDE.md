# Interview Form Summarizer

A lightweight self-hosted webapp for managing interview pipelines and generating AI-powered assessment summaries. Admin creates candidates, manages pipeline stages, creates interview sessions, shares token links with interviewers, and views auto-aggregated scorecards.

## Architecture

- FastAPI backend (Python 3.12, uvicorn)
- SQLite persistence via SQLModel ORM
- Jinja2 server-rendered templates (no frontend framework)
- HTMX for inline updates (pipeline stage, notes, summary generation)
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
- **Scorecard auto-populates** — reads from completed session responses, not manual entry
- **Session limits per pipeline** — max 4 total, max 1 HR Interview template

## Data Hierarchy

```
Candidate (email as unique key)
  └── Pipeline (position + BU + stage)
        └── Session (round + template + interviewers)
              └── Response (per interviewer, scores + free text)
        └── Scorecard (auto-aggregated from completed sessions)
```

## Scorecard Dimensions (fixed)

- **HR (max 12):** Ownership with Accountability, Maturity & Growth Mindset, Supportive & Collaborative
- **Culture (max 16):** Execution Excellence, Learn Fast Adapt Faster, Impact Over Activity, Clarity & Structured Thinking
- **Total: 28** — plus Drive & Dream (multi-select) and notes per category
- Auto-populated from HR Interview and Culture Alignment template responses

## Constraints

- Self-hosted, no cloud dependency
- Single admin user model (no multi-tenant)
- Interview tokens are single-use — consumed on submission
- NocoDB is optional — manual candidate entry supported
- Session creation auto-differentiates job title: `Position #N — Mon YYYY`

## Project Structure

- `app/main.py` — FastAPI app factory, route registration, static mount
- `app/models.py` — SQLModel schemas (Candidate, Pipeline, Session, Template, PipelineScore, etc.)
- `app/database.py` — SQLite engine, session factory, table creation, auto-migration
- `app/auth.py` — bcrypt password hashing, cookie-based session auth
- `app/llm.py` — OpenAI-compatible client, summarization prompt, settings helpers
- `app/nocodb.py` — NocoDB API client for candidate search
- `app/cli.py` — CLI commands (create-admin)
- `app/mcp_server.py` — FastMCP server exposing session tools
- `app/seed.py` — Default template seeding (Default, Culture Alignment, HR Interview)
- `app/routes/admin.py` — Dashboard, session CRUD, settings, login/logout
- `app/routes/interview.py` — Token validation, form rendering, submission
- `app/routes/candidates.py` — Candidate CRUD, pipeline management, scorecard view

## Patterns

- Admin routes behind auth, interview routes behind token validation
- `app/routes/candidates.py` handles all candidate/pipeline/scorecard logic
- Sessions nest under pipelines; scorecard aggregates from completed sessions
- HTMX used for pipeline stage changes, notes, delete, and LLM summary generation
- Auto-migration in `database.py` adds missing columns to existing SQLite tables on startup
- Breadcrumb navigation on all admin pages via `{% block breadcrumb %}` in base_app.html

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
