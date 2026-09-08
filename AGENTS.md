# AGENTS.md — INS ATS (Interview Form Summarizer)

## Project Context

**Stack:** Python 3.12 / FastAPI / SQLModel / SQLite / Jinja2 / OpenAI-compatible LLM

**North Star:** A self-hosted, zero-dependency HR/ATS platform covering the full recruitment lifecycle: job management, candidate pipelines, structured interview sessions with template-driven scoring, test assignments with file upload, review batches, offer letter generation, LLM-powered summaries and reports, and a BU portal for manpower requests.

## Architecture

```
interview-general/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory, route registration, static mount, security headers
│   ├── models.py            # SQLModel schemas — 27+ tables, all data shapes
│   ├── database.py          # SQLite engine, WAL mode, migrations, session factory, soft-delete purge
│   ├── auth.py              # bcrypt hashing, itsdangerous cookie sessions, login rate limiting
│   ├── llm.py               # OpenAI-compatible client — session summary + 3 report types (general/job/pipeline)
│   ├── nocodb.py            # NocoDB API client for candidate import
│   ├── cli.py               # CLI commands (create-admin)
│   ├── mcp_server.py        # FastMCP server — create/get/list sessions, jobs, candidates, tasks
│   ├── helpers.py           # render_gone, compute_pipeline_scores (HR/Culture avg), compute_fit (salary/notice/criteria)
│   ├── activity.py          # Activity trail — FK-walk comment propagation (session → pipeline → candidate → job)
│   ├── export.py            # PDF (WeasyPrint) + CSV export for pipelines and scorecards
│   ├── offers.py            # Offer letter HTML generation + PDF rendering
│   ├── reports.py           # Report data collection (general/job/pipeline)
│   ├── seed.py              # Template seeding (Default, Culture Alignment, HR Interview), managed data, legacy migrations
│   └── routes/
│       ├── __init__.py
│       ├── admin.py         # Dashboard, session CRUD, bulk actions, table views, peek panel, restore/purge
│       ├── interview.py     # Token-gated interview form rendering + submission (criteria scores, multi-interviewer)
│       ├── candidates.py    # Candidate CRUD, pipeline creation/stage/notes, NocoDB import, signals
│       ├── jobs.py          # Job CRUD, criteria CRUD, auto-close on headcount, pipeline listing
│       ├── test_portal.py   # Candidate-facing test portal — token auth, file upload with security hardening
│       ├── review.py        # Test review batches — token-gated scoring portal for reviewers
│       ├── sync.py          # WebSocket real-time sync engine — hydrate + change stream for all entities
│       ├── settings.py      # Managed lists (positions/levels/job-types), BU CRUD, LLM config, account, offer config
│       ├── reports.py       # LLM-powered reports — general (org health), job (funnel), pipeline (candidate assessment)
│       ├── portal.py        # BU portal — token-gated view for BU heads to see jobs + submit manpower requests
│       ├── requests.py      # Manpower request management — approve/reject, auto-create job
│       ├── tasks.py         # Task management — create/update/complete on any entity (job/pipeline/candidate)
│       ├── offers.py        # Offer letter CRUD — generate HTML/PDF, download
│       ├── share.py         # Public share pages — candidate profile (/s/{token}), pipeline fit card (/p/{token})
│       ├── benchmark.py     # Salary benchmark — stats API + chart explorer page
│       ├── webhooks.py      # NocoDB webhook receiver — auto-upsert candidates on NocoDB changes
│       ├── docs.py          # Static user guide pages (/guide/*)
│       └── perf.py          # Performance/debug endpoints
├── templates/               # ~88 Jinja2 templates (server-rendered, HTMX-driven)
├── static/
│   ├── style.css
│   ├── uploads/             # Test file uploads (volume-mounted in Docker)
│   ├── reports/             # Generated report files
│   └── offers/              # Generated offer letters (HTML + PDF)
├── requirements.txt
├── Dockerfile
├── interview.db             # Auto-created SQLite (WAL mode)
└── .env                     # Config (seed values, DB overrides at runtime)
```

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `main.py` | App assembly — mounts 18 route modules, static files, security headers, `format_text` Jinja filter |
| `models.py` | Data shapes only — 27 SQLModel tables, dimension constants, `not_deleted()` filter helper |
| `database.py` | Connection management — WAL mode, column migrations, soft-delete auto-purge (30-day TTL), seed orchestration |
| `auth.py` | Auth boundary — bcrypt hash/verify, itsdangerous signed cookies (7-day TTL), in-memory login rate limiter, session version invalidation |
| `llm.py` | LLM boundary — `generate_summary_dynamic()` for session summaries, `generate_report()` for 3 report types, config stored in DB |
| `nocodb.py` | External API — fetch candidate from NocoDB, upsert to local DB |
| `helpers.py` | Shared view helpers — `compute_pipeline_scores()` (HR/Culture averages), `compute_fit()` (salary/notice/criteria fit) |
| `activity.py` | Activity trail — FK-walk comment propagation (session → pipeline → candidate → job) |
| `export.py` | Export — PDF (WeasyPrint via Jinja2) and CSV (UTF-8 BOM) for pipelines and scorecards |
| `offers.py` | Offer letter — HTML template rendering, PDF conversion, file management |
| `reports.py` | Report data — aggregates pipeline/session/score data for LLM report generation |
| `seed.py` | Idempotent seeding — 3 templates (Default, Culture Alignment, HR Interview), 7 BUs, managed lists, legacy job_id migration, section guidance backfill |
| `mcp_server.py` | Agent interface — create/get/list sessions, jobs, candidates, tasks; search candidates via NocoDB |

### Route Modules

| Route | Prefix | Auth | Purpose |
|-------|--------|------|---------|
| `admin.py` | `/` | Admin cookie | Dashboard, sessions, bulk ops, views, peek panel, restore/purge |
| `interview.py` | `/i/{token}` | Token | Interview form + submission (multi-interviewer, criteria scores) |
| `candidates.py` | `/candidate/*` | Admin cookie | Candidate CRUD, pipeline lifecycle, NocoDB import |
| `jobs.py` | `/job/*` | Admin cookie | Job CRUD, criteria CRUD, auto-close, pipeline listing |
| `test_portal.py` | `/test/{token}` | Token + password | Candidate test portal — view instructions, upload files |
| `review.py` | `/review/{token}` | Token | Reviewer portal — grade test submissions in batch |
| `sync.py` | `/sync/*` | Admin cookie + WS | REST hydrate + WebSocket change stream |
| `settings.py` | `/settings/*` | Admin cookie | Managed lists, BUs, LLM config, account, offer config |
| `reports.py` | `/reports/*` | Admin cookie | LLM reports — general, job, pipeline; PDF generation |
| `portal.py` | `/portal/{token}` | BU token | BU head portal — view jobs, submit manpower requests |
| `requests.py` | `/requests/*` | Admin cookie | Manpower request management — approve/reject/create-job |
| `tasks.py` | `/tasks/*` | Admin cookie | Task CRUD on any entity |
| `offers.py` | `/offers/*` | Admin cookie | Offer letter generation, HTML/PDF download |
| `share.py` | `/s/{token}`, `/p/{token}` | Share token | Public candidate profile + pipeline fit card |
| `benchmark.py` | `/benchmark`, `/api/salary-stats` | Admin cookie | Salary benchmark explorer |
| `webhooks.py` | `/api/webhooks/*` | Secret header | NocoDB webhook — auto-upsert candidates |
| `docs.py` | `/guide/*` | None | Static user guide pages |
| `perf.py` | `/perf/*` | Admin cookie | Performance/debug endpoints |

### Key Data Model

**Core entities:** Candidate → CandidatePipeline → InterviewSession → SessionInterviewer → Response → ResponseScore

**Job tracking:** Job (position/level/BU/headcount) → JobCriteria (tiered r1/r2) → CriteriaScore

**Assessment flow:** TestAssignment (candidate uploads) → ReviewBatch → ReviewScore (reviewer grades)

**Operations:** OfferLetter (from pipeline), ManpowerRequest (BU → admin → Job), Task (on any entity), Comment (activity trail + notes)

**Config:** Setting (key-value DB config), Template + TemplateSection (structured interview forms), BusinessUnit, ManagedPosition/Level/JobType

### Key Patterns

- **Route split:** Admin routes require auth cookie (`get_current_admin`). Interview/test/review/portal routes require valid token. Share routes are public. Never mixed.
- **Token-gated access:** Session interviewers get unique tokens (`/i/{token}`). Tests get token + password (`/test/{token}`). Review batches get tokens. BU portals get `portal_token`. Share pages get `share_token` / `share_token_full`. All single-use where appropriate.
- **Soft deletes:** Jobs, Pipelines, Sessions, Tests, Tasks use `deleted_at` timestamp. Filter with `not_deleted()` helper. Auto-purged after 30 days on startup.
- **Activity trail:** `record_activity()` writes a Comment with `kind="activity"` and propagates up the FK chain (session → pipeline → candidate → job).
- **Real-time sync:** WebSocket hub broadcasts inserts/updates/deletes to connected admin clients. All mutation endpoints fire async broadcasts.
- **LLM abstraction:** `app/llm.py` wraps any OpenAI-compatible API. Config stored in DB (editable from `/settings/llm`), falls back to `.env` on first boot. Summary generated on-demand from admin session detail page (not during interview submission).
- **No frontend framework:** Server-rendered Jinja2 templates with HTMX for interactivity. One CSS file. No JS build step.
- **Session limits:** Max 4 sessions per pipeline. Only 1 HR Interview per pipeline.
- **Template-driven forms:** TemplateSections support `rating_1_4`, `single_select`, `multi_select`, `short_text`, `long_text` measurement types, with conditional sections (condition_section_id + condition_value).

## Development Standards

### Commands
```bash
pip install -r requirements.txt              # Install deps
uvicorn app.main:app --reload --port 8000    # Dev server
python -m app.cli create-admin <user> <pw>   # Create admin
python -m app.mcp_server                      # MCP server (agent access)
```

### Naming
- Files: `snake_case.py`
- Routes: `snake_case` functions, RESTful paths
- Models: `PascalCase` classes
- Templates: `snake_case.html`
- DB columns: `snake_case`

### Commit Style
- Imperative mood, short subject: `Add session edit page`, `Fix token validation on resubmit`
- No prefixes (no feat:, fix:, etc.)

### Constraints
- No external DB — SQLite only (WAL mode for concurrency)
- No JS frameworks — Jinja2 + HTMX + plain CSS
- No multi-tenant — single admin
- Tokens are single-use where marked
- LLM provider-agnostic (OpenAI-compatible endpoint)
- Max 4 interview sessions per pipeline

### Patterns to Follow
- Use `not_deleted(model)` for all queries on soft-deletable entities
- Use `_render(request, name, context)` helper in routes with templates
- Use `render_gone(request, label, back_url, back_label)` for soft-deleted entity pages
- Use `record_activity(db, source_type, source_id, body, pipeline_id=...)` for audit trail
- Broadcast changes via `asyncio.create_task(sync_hub.broadcast(...))` after mutations
- Prefer `db.exec(select(...))` over `db.query(...)` — SQLModel 0.0.22 style
- Use `col(Model.field)` for WHERE clauses, `func.count()` for aggregates
- Batch queries (IN clauses) instead of per-item queries in loops — see `compute_pipeline_scores` and `_pipeline_partial_context` for patterns

### Known Pitfalls
- `sqlmodel==0.0.22` pinned — newer versions break `col()` usage
- SQLite doesn't support `ALTER TABLE DROP COLUMN` on older versions — `_migrate()` handles this with try/except
- `pydantic_core` version must match `pydantic` — the project needs its own venv, don't use the Hermes system Python
- No test suite exists — verify changes manually with the dev server
- `cookies.txt` is untracked and should be gitignored or deleted

## Current Status

### Completed
- [x] Move LLM summary generation to admin result page (on-demand via `/session/{id}/generate-summary`)
- [x] Allow manual candidate name/details entry (3 entry modes: pipeline, nocodb, manual)
- [x] Multi-interviewer sessions with individual tokens
- [x] Template-based interview forms with conditional sections
- [x] Job criteria scoring (r1/r2 tiered, 0/1/2 scale)
- [x] Test assignments with file upload (security-hardened)
- [x] Review batches for test grading
- [x] Pipeline fit analysis (salary, notice, criteria coverage)
- [x] Offer letter generation (HTML + PDF)
- [x] LLM-powered reports (general, job, pipeline)
- [x] BU portal for manpower requests
- [x] Public share pages (candidate profile, pipeline fit card)
- [x] Real-time WebSocket sync
- [x] Salary benchmark explorer
- [x] NocoDB webhook auto-sync
- [x] Activity trail with FK propagation
- [x] Soft deletes with 30-day auto-purge
- [x] Session version invalidation for admin password resets

### No Tests
The project has zero automated tests. All verification is manual via the dev server.
