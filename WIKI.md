# Interview Form Summarizer — Wiki

## Overview

A lightweight self-hosted webapp for managing interview pipelines and generating AI-powered assessment summaries. Admin creates candidates, manages pipeline stages, creates interview sessions, shares token links with interviewers, and views auto-aggregated scorecards.

**Status:** v0.3 (Production Beta)

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12+, FastAPI, uvicorn |
| Database | SQLite via SQLModel |
| Frontend | Jinja2 templates, HTMX, vanilla JS |
| Icons | Lucide (inline SVG) |
| LLM | OpenAI-compatible client |
| MCP | FastMCP (SSE transport) |
| Candidate source | NocoDB REST API (optional) |
| Deploy | Docker, systemd + nginx, Cloudflare Tunnel |

---

## Setup

```bash
cd interview-general
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
python -m app.cli create-admin <username> <password>
uvicorn app.main:app --reload
```

MCP server (separate process):
```bash
python -m app.mcp_server
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NOCODB_BASE_URL` | NocoDB instance URL (e.g. `https://ats.deadalus.site`) |
| `NOCODB_API_KEY` | NocoDB PAT token |
| `NOCODB_TABLE_ID` | Candidate_ALL table ID (`mqf1wqf4abbaqtx`) |
| `NOCODB_BASE_ID` | NocoDB base ID (`pj16ynf0v7ds1mh`) |
| `LLM_BASE_URL` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | LLM API key |
| `LLM_MODEL` | Model name (e.g. `gpt-4o`) |
| `ADMIN_SESSION_SECRET` | Secret for session cookie signing |
| `DATABASE_URL` | SQLite path (default: `sqlite:///./interview.db`) |

---

## Core Flow

1. Admin logs in (`/login`)
2. Admin creates candidate (manual or NocoDB import) and pipeline
3. Admin creates session (`/session/new`) — selects candidate/pipeline, template, fills job title + interviewer names
4. App generates unique token links per interviewer
5. Interviewers open `/i/[token]` — see candidate context (read-only), accept consent/declaration, fill template-based sections, submit
6. Admin views results at `/session/[id]`, generates AI summary on demand
7. AI auto-switches: single-eval prompt for 1 interviewer, cross-eval for 2+
8. Scorecard auto-aggregates from completed session responses

---

## Pages

| Route | Access | Purpose |
|-------|--------|---------|
| `/login` | Public | Admin login |
| `/` | Admin | Dashboard — stats cards + upcoming interviews |
| `/sessions` | Admin | Session list with filters, sort, group-by, bulk actions |
| `/session/new` | Admin | Create session (template picker, multiple interviewers) |
| `/session/[id]` | Admin | View results, scores side-by-side, AI summary |
| `/session/[id]/edit` | Admin | Edit session details, add interviewers |
| `/session/[id]/cancel` | Admin | Cancel/expire a pending session |
| `/pipelines` | Admin | Pipeline list with stage overview |
| `/pipeline/[id]` | Admin | Pipeline detail with scorecard |
| `/candidates` | Admin | Candidate list |
| `/candidate/[id]` | Admin | Candidate profile + interview history + "Add Interview" |
| `/templates` | Admin | List/manage interview templates |
| `/templates/[id]` | Admin | View template sections |
| `/settings` | Admin | LLM config + system prompt |
| `/i/[token]` | Public (token-gated) | Interview assessment form |
| `/i/[token]/done` | Public | Post-submit confirmation |
| `/api/candidates?q=` | Admin | Candidate search JSON endpoint |

---

## Templates & Measurement Types

Assessment forms are template-driven. 3 seeded templates:
- **Default** — 5 sections (4 ratings + 1 yes/no gut check)
- **Culture Alignment** — 14 sections (7 single-select + 4 ratings + 1 multi-select + 1 single-select + 1 long text)
- **HR Interview** — 7 sections with conditional logic (Recommended → Culture Fit ratings, Skip/NOK → Veto Flag)

Measurement types:
- `rating_1_4` — radio 1-4 with custom anchors
- `single_select` — radio, custom options
- `multi_select` — checkboxes with max selections
- `short_text` — single line input
- `long_text` — textarea

Conditional sections: shown/hidden based on another section's value (JS-driven).

---

## UI

- **Sidebar navigation** — fixed left panel (admin pages only), Catppuccin Mocha dark bg, accent active state
- **Lucide icons** — inline SVG stroke icons for sidebar nav + hamburger
- **Public pages** — standalone clean layout (no sidebar)
- **Design system** — Catppuccin Mocha dark mode, card-based, compact buttons
- **Table module** — `table.js` with search, filter, sort, group-by, custom views, bulk selection
- **Advanced filters** — pill-based compound filtering with save/switch/delete presets
- **Bulk selection** — hover-reveal checkboxes, Ctrl+Click toggle, Shift+Click range, bulk delete bar
- **Keyboard shortcuts** — global system (`?` help overlay, `j/k` nav, `n` new, `e` edit, `Del` delete)
- **Context menus** — right-click actions on table rows
- **Clickable rows** — navigate to detail by clicking anywhere (suppressed with Ctrl/Shift modifiers)
- **HTMX** — partial page updates for LLM summary, stage changes, notes (no full reload)
- **Perceived performance** — loading states on all submit buttons, HTMX indicators
- **Responsive** — mobile sidebar collapses to hamburger with close button

---

## Data Model

### admin_users
- `id`, `username`, `hashed_password`

### candidates
- `id`, `email` (unique), `name`, `phone`, `current_position`, `yoe`, `skills`, `languages`, `current_salary`, `expected_salary`, `notice_period`, `created_at`

### pipelines
- `id`, `candidate_id` (FK), `position`, `business_unit`, `stage`, `notes`, `created_at`

### pipeline_scores (scorecard)
- `id`, `pipeline_id` (FK), auto-aggregated from completed session responses

### sessions
- `id`, `candidate_id` (FK), `pipeline_id` (FK), `job_title`, `template_id` (FK), `status` (pending/completed/cancelled), `interview_date`, `created_at`

### interviewers
- `id`, `session_id` (FK), `interviewer_name`, `token` (unique, URL-safe)

### responses
- `id`, `interviewer_id` (FK), `session_id` (FK), `scores` (JSON), `free_text`, `submitted_at`, `summary` (LLM output)

### templates
- `id`, `name`, `sections` (JSON — measurement types, options, conditions)

### settings
- `id`, `key`, `value` — LLM config, system prompt, stored in DB

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `create_session(candidate_id, job_title, round, interviewer_names)` | Returns shareable URLs |
| `get_session(session_id)` | Returns status, scores, summary |
| `list_sessions(candidate_id?)` | Lists sessions, optionally filtered |

No auth required (internal agent use).

---

## NocoDB Field Mapping

| NocoDB Field | Snapshot Key |
|---|---|
| Full-Name | `name` |
| Phone Number | `phone` |
| Email | `email` |
| Current Formal Positions | `current_position` |
| Total Years of Experience | `yoe` |
| Programming Language (professionally used) | `languages` |
| Cloud Expertise | `cloud` |
| Other professional related tools used | `tools` |
| Working arrangement preferences | `working_arrangement` |
| (Full-time) Current Salary (Nett in IDR) | `current_salary` |
| (Full-time) Expected Salary (Nett in IDR) | `expected_salary` |
| (Full-time) Notice Period | `notice_period` |

---

## Backlog

Tracked in Linear (hr-insignia workspace, Claude-Workspace team). See project boards for current sprint and backlog items.

---

## File Structure

```
interview-general/
├── app/
│   ├── __init__.py
│   ├── main.py          — FastAPI app factory, route registration
│   ├── models.py        — SQLModel schemas
│   ├── database.py      — SQLite engine, auto-migration
│   ├── auth.py          — bcrypt + cookie-based session auth
│   ├── nocodb.py        — NocoDB API client
│   ├── llm.py           — OpenAI-compatible LLM client
│   ├── mcp_server.py    — FastMCP server (SSE)
│   ├── cli.py           — CLI commands (create-admin)
│   ├── seed.py          — Default template seeding
│   └── routes/
│       ├── __init__.py
│       ├── admin.py     — Dashboard, session CRUD, settings
│       ├── interview.py — Token validation, form, submission
│       └── candidates.py — Candidate/pipeline/scorecard
├── templates/
│   ├── base_app.html    — Admin layout (sidebar, scripts)
│   ├── base.html        — Public layout
│   ├── login.html
│   ├── dashboard.html
│   ├── sessions_list.html
│   ├── session_new.html
│   ├── session_detail.html
│   ├── session_edit.html
│   ├── candidates_list.html
│   ├── candidate_detail.html
│   ├── pipelines_list.html
│   ├── pipeline_detail.html
│   ├── pipeline_score.html
│   ├── templates_list.html
│   ├── template_detail.html
│   ├── settings.html
│   ├── interview_form.html
│   ├── interview_done.html
│   └── partials/
├── static/
│   ├── style.css        — Catppuccin Mocha theme
│   ├── table.js         — Table module (filter, sort, group, bulk)
│   └── shortcuts.js     — Global keyboard shortcuts
├── .env.example
├── requirements.txt
├── docker-compose.yml
├── docker-compose.staging.yml
├── Dockerfile
├── README.md
└── WIKI.md
```

---

## Notes: Cloudflare Free Deployment

The simplest free deployment path is **Cloudflare Tunnel** — no code changes, free HTTPS, DDoS protection.

### How it works
- App runs on any machine (local PC, VPS, Raspberry Pi)
- `cloudflared` creates a secure tunnel from your machine to Cloudflare's edge
- You get a public URL with HTTPS — either `*.trycloudflare.com` (temporary) or your own domain

### Quick start (temporary URL, no account needed)

```bash
# Install cloudflared
# Windows: winget install cloudflare.cloudflared
# Linux: curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared

# Start the app
uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal — instant public URL
cloudflared tunnel --url http://localhost:8000
```

This gives you a `https://random-words.trycloudflare.com` URL immediately. Good for testing/demos.

### Persistent setup (own domain, free Cloudflare account)

```bash
# Login to Cloudflare
cloudflared tunnel login

# Create a named tunnel
cloudflared tunnel create interview-general

# Configure (creates ~/.cloudflared/config.yml)
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <TUNNEL_ID>
credentials-file: ~/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: interview.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
EOF

# Add DNS record (CNAME to tunnel)
cloudflared tunnel route dns interview-general interview.yourdomain.com

# Run as service
cloudflared service install
cloudflared service start
```

### Why this over Workers/Pages
- FastAPI is Python — Workers run JS/WASM (would require full rewrite)
- D1 is SQLite-compatible but Workers API is different from SQLModel
- Tunnel requires zero code changes — app stays exactly as-is
- Free tier includes: HTTPS, DDoS protection, caching, analytics
