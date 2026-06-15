# AGENTS.md — Interview Form Summarizer

## Project Context

**Stack:** Python 3.12 / FastAPI / SQLModel / SQLite / Jinja2 / OpenAI-compatible LLM

**North Star:** A self-hosted, zero-dependency interview assessment tool where admin creates sessions, interviewers submit via token links, and AI summarizes results. Lightweight, opinionated, no cloud lock-in.

## Architecture

```
interview-general/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory, route registration, static mount
│   ├── models.py            # SQLModel schemas (Session, Admin, Settings)
│   ├── database.py          # SQLite engine, session factory, table creation
│   ├── auth.py              # bcrypt password hashing, cookie-based session auth
│   ├── llm.py               # OpenAI-compatible client, summarization prompt
│   ├── nocodb.py            # NocoDB API client for candidate search
│   ├── cli.py               # CLI commands (create-admin)
│   ├── mcp_server.py        # FastMCP server exposing session tools
│   └── routes/
│       ├── admin.py         # Dashboard, session CRUD, settings, results
│       └── interview.py     # Token validation, form rendering, submission
├── templates/
│   ├── base.html            # Layout shell
│   ├── dashboard.html       # Admin session list
│   ├── session_new.html     # Create session form
│   ├── session_detail.html  # View session + results
│   ├── session_edit.html    # Edit session
│   ├── settings.html        # LLM config dashboard
│   ├── interview_form.html  # Interviewer-facing form
│   ├── interview_done.html  # Post-submission confirmation
│   └── login.html           # Admin login
├── static/
│   └── style.css
├── requirements.txt
├── interview.db             # Auto-created SQLite
└── .env                     # Config (seed values, DB overrides at runtime)
```

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `main.py` | App assembly — mounts routes, static, lifespan events |
| `models.py` | Data shapes only — no business logic |
| `database.py` | Connection management — engine, sessions, init |
| `auth.py` | Auth boundary — hash, verify, session cookies |
| `llm.py` | LLM boundary — single summarize function, config from DB |
| `nocodb.py` | External API — candidate search, optional |
| `routes/admin.py` | Admin flows — behind auth middleware |
| `routes/interview.py` | Interviewer flows — behind token validation |
| `mcp_server.py` | Agent interface — create/get/list sessions |

### Key Patterns

- **Route split:** Admin routes require auth cookie. Interview routes require valid token. Never mixed.
- **Token-gated access:** Each session generates a unique token. Interviewer hits `/interview/{token}`. Token consumed on form submission — no reuse.
- **LLM abstraction:** `app/llm.py` wraps any OpenAI-compatible API. Config lives in DB (editable from `/settings`), falls back to `.env` on first boot.
- **No frontend framework:** Server-rendered Jinja2 templates. One CSS file. No JS build step.

## Development Standards

### Commands
```bash
pip install -r requirements.txt          # Install deps
uvicorn app.main:app --reload --port 8000  # Dev server
python -m app.cli create-admin <user> <pw>  # Create admin
python -m app.mcp_server                  # MCP server (agent access)
```

### Naming
- Files: `snake_case.py`
- Routes: `snake_case` functions, RESTful paths
- Models: `PascalCase` classes
- Templates: `snake_case.html`

### Commit Style
- Imperative mood, short subject: `Add session edit page`, `Fix token validation on resubmit`
- No prefixes (no feat:, fix:, etc.)

### Constraints
- No external DB — SQLite only
- No JS frameworks — Jinja2 + plain CSS
- No multi-tenant — single admin
- Tokens are single-use
- LLM provider-agnostic (OpenAI-compatible endpoint)

## Sprint Status

### Active
- [ ] Move LLM summary generation to admin result page (instead of interview submission)
- [ ] Allow manual candidate name/details entry as alternative to NocoDB search

### Backlog
- [ ] One-click copy scores + summary as markdown
- [ ] Default hide salary on interview form, admin toggle per session
- [ ] Template-based custom interview dimensions beyond fixed Q1-Q5
- [ ] N interviewers per session with individual tokens + cross-evaluator LLM summary
- [ ] Admin can edit session details + results, add interview date field
- [ ] Dashboard page to manage LLM config without restart
