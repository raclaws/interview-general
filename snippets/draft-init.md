# Snippets — Draft (auto-generated)

## Patterns
### Route split (admin vs interview)
Admin routes behind auth, interview routes behind token validation. Clean separation in `app/routes/admin.py` and `app/routes/interview.py`.

### LLM abstraction
`app/llm.py` wraps OpenAI client. Config loaded from DB (fallback to .env). Single function call for summarization.

### Token-gated access
Sessions have unique tokens. Interviewer accesses form via `/interview/{token}`. Token consumed on submission — no reuse.

## Key Modules
- **app/main.py** — FastAPI app factory, route registration, static mount
- **app/models.py** — SQLModel schemas (Session, Admin, Settings)
- **app/database.py** — SQLite engine, session factory, table creation
- **app/auth.py** — bcrypt password hashing, cookie-based session auth
- **app/llm.py** — OpenAI-compatible client, summarization prompt
- **app/nocodb.py** — NocoDB API client for candidate search
- **app/cli.py** — CLI commands (create-admin)
- **app/mcp_server.py** — FastMCP server exposing session tools
- **app/routes/admin.py** — Dashboard, session CRUD, settings, results
- **app/routes/interview.py** — Token validation, form rendering, submission
