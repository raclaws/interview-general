# INS ATS (v0.4)

A lightweight self-hosted ATS webapp for managing jobs, candidates, interview pipelines, and generating AI-powered assessment summaries. Admin creates jobs, adds candidates, manages pipeline stages, creates interview sessions, shares token links with interviewers, and views auto-aggregated scorecards.

## Architecture

- FastAPI backend (Python 3.12, uvicorn)
- SQLite persistence via SQLModel ORM
- Jinja2 server-rendered templates (no frontend framework)
- HTMX for inline updates (pipeline stage, notes, summary generation, settings CRUD)
- OpenAI-compatible LLM integration for interview summarization
- NocoDB integration for candidate lookup (optional, with 10s timeout + error handling)
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
- **Job as anchor entity** — all hiring activity flows from a Job (position + level + BU + metadata)
- **Idempotent migration** — legacy data auto-adopted on startup, no manual intervention needed

## Data Hierarchy

```
BusinessUnit (name, head, default_recruiter)
  └── Job (position + level + job_type + headcount + recruiter + status)
        └── Pipeline (candidate + job junction, stage tracking)
              └── Session (template + interviewers)
                    └── Response (per interviewer, scores + free text)
              └── TestAssignment (external test link + submission)
              └── Scorecard (auto-aggregated from completed sessions)
        └── ReviewBatch (reviewer + scored test submissions)

Candidate (email as unique key, independent of Job)
  └── Pipelines (one per Job application)
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
- Job must exist before pipeline creation
- Pipeline requires both candidate_id + job_id
- Sessions/tests inherit position/BU context from pipeline.job

## Project Structure

- `app/main.py` — FastAPI app factory, route registration, static mount
- `app/models.py` — SQLModel schemas (BusinessUnit, Job, Candidate, Pipeline, Session, Template, PipelineScore, ManagedPosition, ManagedLevel, ManagedJobType, etc.)
- `app/database.py` — SQLite engine, session factory, table creation, auto-migration
- `app/auth.py` — bcrypt password hashing, cookie-based session auth
- `app/llm.py` — OpenAI-compatible client, summarization prompt, settings helpers
- `app/nocodb.py` — NocoDB API client with timeout + error handling
- `app/cli.py` — CLI commands (create-admin)
- `app/mcp_server.py` — FastMCP server exposing session tools
- `app/seed.py` — Template seeding + managed data seeding + legacy migration
- `app/routes/admin.py` — Dashboard, session CRUD, settings, login/logout
- `app/routes/jobs.py` — Job CRUD, add candidate to pipeline
- `app/routes/settings.py` — BU management, managed lists (positions, levels, job types)
- `app/routes/interview.py` — Token validation, form rendering, submission
- `app/routes/candidates.py` — Candidate CRUD, pipeline management, scorecard, test assignment, review batches
- `app/routes/review.py` — Review portal (token-gated, public)
- `app/routes/test_portal.py` — Test submission portal (token-gated, public)
- `app/routes/sync.py` — Real-time sync endpoints for client table engine

## Patterns

- Admin routes behind auth; interview/test/review portals behind token validation
- Job is the anchor entity — pipeline creation requires a Job
- HTMX used for: pipeline stage changes, notes, settings CRUD, score submission, summary generation
- Toast notifications via `HX-Trigger: toast:Message` header pattern
- Auto-migration in `database.py` adds missing columns on startup
- `seed_managed_data()` seeds reference data (find-or-create, idempotent)
- `migrate_legacy_job_ids()` adopts old position+BU strings into Job model (idempotent, every startup)
- Settings page uses tabbed layout with HTMX partial swaps
- Sidebar order: Dashboard → Jobs → Candidates → Pipelines → Interview → Test → Settings
- Breadcrumb navigation on all admin pages via `{% block breadcrumb %}` in base_app.html
- NocoDB calls wrapped with 10s timeout, connection error handling, `_error` key in response

## Sidebar Navigation

```
Dashboard       /
Jobs            /jobs
Candidates      /candidates
Pipelines       /pipelines
Interview       /sessions
Test            /review-batches
Settings        /settings (tabbed: LLM, BU, Positions, Levels, Job Types, Templates)
```

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

## Migration (v0.1 → v0.2)

Automatic on first startup after deploy:
1. New tables created (BusinessUnit, Job, ManagedPosition, ManagedLevel, ManagedJobType)
2. `job_id` column added to `candidate_pipelines` and `review_batches`
3. BU + managed lists seeded from defaults
4. Jobs auto-created from distinct (position, BU) pairs in existing pipelines
5. All pipelines/batches backfilled with matching `job_id`
6. Position strings not in managed list get added automatically

No manual steps required. Old data preserved — legacy string fields kept for backward compat.

## Agent Protocol

This project uses StratVibe (Substrate) for structured agent orchestration. See `.substrate/` for protocol rules (taxonomy, roles, token budgets, handoffs). Agent entrypoint is `AGENTS.md`.

## Dev

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Default port: 8000, Python >=3.12, FastAPI >=0.115.0, SQLModel 0.0.22.

## Lessons Learned (CLA-27)

- **Migration scripts must be idempotent** — crash mid-migration + restart should not duplicate data or skip steps. Use find-or-create, not insert-if-empty.
- **Normalize strings before matching** — `.strip().lower()` on both sides prevents silent mismatches ("R&D" vs "R&D " vs "r&d").
- **Infer state from data, don't assume defaults** — migrated Jobs should derive status (open/closed) and headcount from actual pipeline stages, not hardcode `open` + `headcount=1`.
- **`hidden` attribute on `<tr>` is unreliable** — use `style="display:none"` for form toggle visibility in tables.
- **Remove dead form params after refactoring** — unused `Form(...)` params in FastAPI routes don't crash but create confusion and accept garbage data.
- **HTMX swap targets matter for perceived performance** — if the swap replaces the element containing the trigger, callbacks (`hx-on::after-request`) may not fire. Use `HX-Trigger` response headers instead.
- **External API calls need timeouts** — NocoDB without timeout blocks the whole request indefinitely if the service is down. 10s timeout + error key pattern keeps UI responsive.
- **Duplicate checks must cover all entry points** — a record can be created from multiple routes (Job detail, Candidate detail, Session form). Each path needs its own dup check.
- **Test clickable rows need `data-href`** — `clickable-row` class without `data-href` navigates to "undefined". Either add the href or remove the class.
- **Seed managed lists from actual data** — if prod has free-text entries ("Product Designer") not in the seeded list, admin can't create new Jobs with that position. Migration should add them to ManagedPosition automatically.
- **`onsubmit` doesn't block `hx-post` or boosted forms** — use `hx-confirm` exclusively for destructive actions inside HTMX-managed containers.
- **hx-boost makes ALL child forms HTMX-managed** — links inside forms inherit `hx-target`. Cancel links must have `hx-boost="false"` to prevent partial swaps.
- **Soft delete needs not_deleted() on ALL queries** — every SELECT that renders data to users must filter `deleted_at IS NULL`. Missing one filter = ghost records.
