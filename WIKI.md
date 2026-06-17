# Interview Form Summarizer — Wiki

## Overview

A lightweight self-hosted webapp for generating on-demand interview assessment sessions. Admin creates a session with candidate context from NocoDB, shares a token link with the interviewer, and AI summarizes the submission.

**Status:** P-B (Production Beta)

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python, FastAPI |
| Database | SQLite via SQLModel |
| Frontend | Jinja2 templates, vanilla JS |
| LLM | OpenAI-compatible client |
| MCP | FastMCP (SSE transport) |
| Candidate source | NocoDB REST API (read-only) |

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
2. Admin creates session (`/session/new`) — searches NocoDB or manual entry, selects template, fills job title + round + interviewer names
3. App generates unique token links per interviewer
4. Interviewers open `/i/[token]` — see candidate context (read-only), fill template-based sections, submit
5. Admin views results at `/session/[id]`, generates AI summary on demand
6. AI auto-switches: single-eval for 1 interviewer, cross-eval for 2+

---

## Pages

| Route | Access | Purpose |
|-------|--------|---------|
| `/login` | Public | Admin login |
| `/` | Admin | Dashboard — list sessions with progress |
| `/session/new` | Admin | Create session (template picker, multiple interviewers) |
| `/session/[id]` | Admin | View results, scores side-by-side, AI summary |
| `/session/[id]/edit` | Admin | Edit session details, add interviewers |
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

- **Sidebar navigation** — fixed left panel (admin pages only), charcoal bg, teal active state
- **Public pages** — standalone clean layout (no sidebar)
- **Design system** — monochrome + teal (#0d9488) accent, card-based, compact buttons
- **HTMX** — partial page updates for LLM summary generation (no full reload)
- **Perceived performance** — loading states on all submit buttons, HTMX indicators
- **Responsive** — mobile sidebar collapses to hamburger

---

## Data Model

### admin_users
- `id`, `username`, `hashed_password`

### sessions
- `id`, `token` (unique, URL-safe), `candidate_id`, `candidate_snapshot` (JSON), `job_title`, `round`, `interviewer_name`, `status` (pending/completed), `created_at`

### responses
- `id`, `session_id` (FK), `q1`–`q4` (int 1–4), `q5` (bool), `free_text` (optional), `submitted_at`, `summary` (LLM output)

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `create_session(candidate_id, job_title, round, interviewer_name)` | Returns shareable URL |
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

- [ ] Move LLM summary generation to admin result page (lazy generation, saves tokens, instant interviewer submission)
- [ ] Add "Regenerate Summary" button on admin result page
- [ ] Session expiry (optional TTL)
- [ ] Candidate snapshot display improvements

---

## File Structure

```
interview-general/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── auth.py
│   ├── nocodb.py
│   ├── llm.py
│   ├── mcp_server.py
│   ├── cli.py
│   └── routes/
│       ├── __init__.py
│       ├── admin.py
│       └── interview.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── session_new.html
│   ├── interview_form.html
│   ├── interview_done.html
│   └── session_detail.html
├── static/
│   └── style.css
├── .env.example
├── requirements.txt
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
