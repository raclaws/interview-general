# Interview Form Summarizer — Wiki

## Overview

A lightweight self-hosted webapp for generating on-demand interview assessment sessions. Admin creates a session with candidate context from NocoDB, shares a token link with the interviewer, and AI summarizes the submission.

**Status:** P-A (Pre-Alpha)

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
2. Admin creates session (`/session/new`) — searches NocoDB for candidate, fills job title + round + interviewer name
3. App generates a shareable token link
4. Interviewer opens `/i/[token]` — sees candidate context (read-only), rates 5 dimensions, submits
5. App generates AI summary, stores everything in SQLite
6. Admin views results at `/session/[id]`

---

## Pages

| Route | Access | Purpose |
|-------|--------|---------|
| `/login` | Public | Admin login |
| `/` | Admin | Dashboard — list sessions, create new |
| `/session/new` | Admin | Create session form with candidate picker |
| `/session/[id]` | Admin | View results, scores, AI summary |
| `/i/[token]` | Public (token-gated) | Interview assessment form |
| `/i/[token]/done` | Public | Post-submit confirmation |
| `/api/candidates?q=` | Admin | Candidate search JSON endpoint |

---

## Assessment Dimensions

| # | Dimension | Type | Description |
|---|-----------|------|-------------|
| Q1 | Comprehension Depth | 1–4 rating | How they locate the actual problem |
| Q2 | Execution Reliability | 1–4 rating | How they close loops under pressure |
| Q3 | Adaptive Range | 1–4 rating | How they operate before a new plan exists |
| Q4 | Signal Clarity | 1–4 rating | How legible their thinking is to others |
| Q5 | Gut Check | Yes/No | Would you work with this person? |

### Anchor Scale (Q1–Q4)

| Score | Meaning |
|-------|---------|
| 1 | Clear no, would not proceed under any reframe |
| 2 | Significant gaps, would need strong compensating signal |
| 3 | Meets bar, proceed with normal weight |
| 4 | Strong signal, prioritize |

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
