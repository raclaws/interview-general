# Spec — Draft (auto-generated)

## Intent
A lightweight self-hosted webapp for generating on-demand interview assessment sessions. Admin creates a session with candidate context, shares a token link with the interviewer, and AI summarizes the submission.

## Architecture Boundaries
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
