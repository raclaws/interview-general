# INS ATS

A lightweight self-hosted ATS webapp for managing jobs, candidates, interview pipelines, and generating AI-powered assessment summaries. Admin creates jobs, adds candidates, manages pipeline stages, creates interview sessions, shares token links with interviewers, and views auto-aggregated scorecards.

**Current version: v1.2**

## Features

### Core
- **Candidate management** — profiles with position, YoE, salary, skills, languages
- **Pipeline tracking** — per-candidate pipelines with configurable stages (screening → hired/rejected)
- **Scorecard** — auto-aggregated from completed sessions, per-interviewer + average scores
- **Configurable templates** — 3 seeded (Default, Culture Alignment, HR Interview) with custom sections, conditional logic
- **Multiple interviewers** — N interviewers per session, each with unique token link
- **Dynamic measurement types** — rating 1-4, single/multi select, short/long text

### AI
- **Lazy LLM summaries** — generated on admin demand, not on submission (saves tokens)
- **Cross-evaluator analysis** — auto-switches to multi-evaluator prompt for 2+ interviewers
- **Structured editorial reports** — General, Pipeline, Job reports with fixed HTML templates + LLM JSON output
- **Report history** — slide-in peek panel with filter context, guard for LLM config + empty data
- **Provider-agnostic** — any OpenAI-compatible endpoint (base URL + key + model)
- **Dashboard-editable** — LLM settings configurable from `/settings` without restart

### UI
- **Monochrome theme** — "Whiter Shade of Pale" grey-scale, color only for semantic meaning
- **Sidebar navigation** — Dashboard, Jobs, Candidates, Pipelines, Interview, Review, Settings
- **Sync engine** — real-time list updates via IndexedDB + WebSocket, client-side filter/sort
- **hx-boost page transitions** — instant navigation without full page reload
- **Side peek panel** — click comment icon on any list row for entity summary + activity trail
- **Detail page actions** — 4 semantic clusters (Navigate, Export, Mutate, Destruct)
- **Form system** — CSS utility classes (.form-card, .form-row, .form-field, .form-footer)
- **Context menus** — right-click actions on table rows
- **Clickable rows** — navigate to detail by clicking anywhere
- **Filter + Display menus** — icon buttons with vertical popovers, active choices as removable pills
- **Mobile sidebar** — hamburger toggle + close button

### Admin
- **Editable sessions** — modify details + results after creation
- **Cancel/expire sessions** — admin can invalidate pending sessions (interviewers marked cancelled)
- **Job CRUD** — create, edit, close/reopen, delete (with pipeline guard)
- **Comments + activity trail** — timestamped comments + auto-generated events on all entities
- **Tab-focus freshness** — stale page detection for shared-account use
- **Return context** — forms remember referrer, Cancel/submit returns to origin
- **Copy token link** — one-click copy interview URL from dashboard
- **Copy as Markdown** — export results as formatted markdown
- **Salary toggle** — hidden by default, admin toggles per session
- **Consent prompt** — data + AI disclosure required before submission
- **Dashboard** — attention surface (overdue interviews, expired tests, stale pipelines) + activity feed
- **Interviewer guidance** — example questions, good answers, red flags per template section
- **Offer letter module** — generate from pipeline detail, configurable salary calc (Rp/% per factor), preview + PDF download + email draft copy
- **NocoDB bulk sync** — one-click import all candidates + webhook for real-time create/update/delete
- **Render-limit tables** — load all data, render 100 rows + "Show more", viewport-filling skeleton

- **Signal engine** — 5-band salary positioning (WELL_BELOW→WELL_ABOVE), CV-extracted skills, boolean keyword search
- **Task system** — lightweight to-dos linked to jobs/pipelines, sync-list, inline status change
- **Shareable candidate profiles** — public `/s/{token}` links with salary show/hide toggle
- **Searchable picker** — combobox replacement for long select lists (ARIA-compliant)
- **Collapsible group headers** — click to collapse/expand grouped table rows
- **BU portal** — manpower requests, job/pipeline visibility, comments
- **LinkedIn post generation** — LLM-powered job post from structured data
- **User guide** — `/guide` with 10 pages in Bahasa Indonesia

### Integrations
- **NocoDB** — bulk import + real-time webhook sync (optional, manual entry supported)
- **MCP server** — 12 tools: sessions, jobs, pipelines, candidates, tasks
- **Signal engine** — pre-computed salary positioning + CV skills via `recompute.py` worker
- **Offer letter generation** — salary calc, 4-variant template (BPJS × probation), HTML + PDF via weasyprint
- **Webhook receiver** — `/api/webhooks/nocodb` with HMAC secret auth, handles insert/update/delete

## Quick Start

### 1. Clone

```bash
git clone https://github.com/raclaws/interview-general.git
cd interview-general
```

### 2. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
NOCODB_BASE_URL=https://your-nocodb-instance.com
NOCODB_API_KEY=your_nocodb_pat_token
NOCODB_TABLE_ID=mqf1wqf4abbaqtx
NOCODB_BASE_ID=pj16ynf0v7ds1mh
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_llm_api_key
LLM_MODEL=gpt-4o
ADMIN_SESSION_SECRET=change-this-to-a-random-secret
DATABASE_URL=sqlite:///./interview.db
```

### 4. Create admin user

```bash
python -m app.cli create-admin <username> <password>
```

### 5. Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

App is now at `http://localhost:8000`

## Deploy on VPS (systemd + nginx)

### 1. Set up on server

```bash
cd /opt
git clone https://github.com/raclaws/interview-general.git
cd interview-general
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # Edit with production values
python -m app.cli create-admin admin <your-password>
```

### 2. Create systemd service

```bash
sudo nano /etc/systemd/system/interview-general.service
```

```ini
[Unit]
Description=Interview Form Summarizer
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/interview-general
Environment="PATH=/opt/interview-general/venv/bin"
EnvironmentFile=/opt/interview-general/.env
ExecStart=/opt/interview-general/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. Set permissions

```bash
sudo chown -R www-data:www-data /opt/interview-general
sudo chmod 600 /opt/interview-general/.env
```

### 4. Start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable interview-general
sudo systemctl start interview-general
sudo systemctl status interview-general
```

### 5. Reverse proxy (nginx)

```bash
sudo nano /etc/nginx/sites-available/interview-general
```

```nginx
server {
    listen 80;
    server_name interview.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/interview-general /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. HTTPS with certbot

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d interview.yourdomain.com
```

### 7. Updating

```bash
cd /opt/interview-general
sudo -u www-data git pull
sudo -u www-data venv/bin/pip install -r requirements.txt
sudo systemctl restart interview-general
```

## Deploy with Docker

### Production

```bash
docker compose up -d --build
docker exec -it interview-general python -m app.cli create-admin admin <your-password>
```

Production runs on port 8000 with `docker-compose.yml`.

### Staging

```bash
docker compose -f docker-compose.staging.yml up -d --build
docker exec -it interview-staging python -m app.cli create-admin admin <your-password>
```

Staging runs on port 8001 with a separate database (`interview_staging.db`). Configure `.env.staging` for staging-specific values.

## Deploy with Cloudflare Tunnel (free)

If you're running the app on a home machine or VPS without a public IP / domain setup:

```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Quick tunnel (temporary URL, no account needed)
cloudflared tunnel --url http://localhost:8000

# Persistent (requires Cloudflare account + domain)
cloudflared tunnel login
cloudflared tunnel create interview-general
cloudflared tunnel route dns interview-general interview.yourdomain.com
cloudflared service install
```

## MCP Server

Run alongside the main app for agent access:

```bash
python -m app.mcp_server
```

Tools: `create_session(candidate_id, job_title, round, interviewer_names)`, `get_session(session_id)`, `list_sessions(candidate_id?)`. No auth required (internal use only).

## LLM Configuration

LLM settings (base URL, API key, model, system prompt) can be changed from `/settings` without restarting. Initial values come from `.env`, then DB takes precedence once saved via dashboard.

## Notes

- **DB auto-created** on first run (SQLite). Templates seeded automatically.
- **Auto-migration** — new columns added to existing tables on startup without data loss.
- **Tokens are single-use** — consumed on submission per interviewer.
- **NocoDB is optional** — manual candidate entry always available.
- **Job title auto-fills** from NocoDB candidate's current position.
- **Salary hidden by default** — admin toggles per session.
- **Session limits** — max 4 sessions per pipeline, max 1 HR Interview template per pipeline.
- **Session cancellation** is irreversible (hard cancel).
- **Python ≥3.12** required. FastAPI ≥0.115, SQLModel 0.0.22.

## Changelog

### v1.2 (2026-07-21)
- Signal engine integration — 5-band salary positioning, CV-extracted skills, boolean keyword search (AND/OR/NOT)
- Task system — lightweight to-dos linked to jobs/pipelines, sync-list with inline status change
- Shareable candidate profiles — public `/s/{token}` links with salary show/hide toggle, revokable
- Searchable picker (combobox) — ARIA-compliant replacement for long select lists
- Collapsible group headers — click to collapse/expand on all sync-list pages
- Security hardening — rate-limited login (5/5min), 7-day cookie expiry, session invalidation on password change, security headers (HSTS, X-Frame-Options, nosniff, Referrer-Policy), SRI on htmx CDN, OpenAPI docs disabled
- Password change — Settings → Account tab, invalidates all other sessions
- Auto-create admin from `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars on startup
- Accessibility — visible focus indicators (:focus-visible), muted text contrast fixed to 4.5:1+
- Jinja2 macros — `inline_edit`, `inline_select`, `detail_actions`, `comment_section` (templates/macros/detail.html)
- Recompute worker — `candidate-search/recompute.py` with --full, --incremental, --watch modes
- WAL mode enabled for concurrent SQLite read/write
- User guide at `/guide` — 10 pages in Bahasa Indonesia with Playwright screenshots
- MCP server expanded to 12 tools (jobs, pipelines, candidates, tasks)
- Design system documentation (DESIGN_SYSTEM.md) + component inventory (COMPONENTS.md)

### v1.1 (2026-07-02)
- Offer letter generation module — salary calc, 4-variant Jinja2 template (BPJS × probation change), HTML + PDF via weasyprint
- Typed offer calc config — each factor toggleable between fixed (Rp) and percentage (%), configurable from Settings
- NocoDB bulk sync — paginated import of all candidates, webhook receiver for real-time create/update/delete
- Render-limit for large tables — load all data into IDB, render 100 rows + "Show more", viewport-filling skeleton
- Interviewer guidance — example questions, good answers, red flags on template sections (Culture Alignment backfill)
- Email draft copy — rich text clipboard (HTML) for offer emails
- Offer soft-delete — muted row with "deleted" badge, no hard delete

### v1.0 (2026-06-27)
- Full lifecycle complete — no workarounds needed for any hiring flow
- Soft delete + undo (Ctrl+Z stack, Recently Deleted page, 30-day purge)
- Structured editorial reports (General, Pipeline, Job) with fixed HTML templates + LLM JSON output
- Report history with slide-in peek panel, filter context, LLM config + empty data guards
- Auth on WebSocket + API endpoints, cookie hardening
- Security fixes (purge null deref, cascade, dedup)

### v0.4 (2026-06-26)
- Monochrome theme "Whiter Shade of Pale" — grey-scale, color only for semantic meaning
- Sync engine on all list pages (real-time via WebSocket, client-side filter/sort/search)
- Unified Filter + Display menu system with removable pills
- hx-boost page transitions (instant navigation, no full reload)
- Comments + Activity trail with side peek panel on all list pages
- Activity events propagate via FK-walk (pipeline → candidate, job)
- Dashboard rewrite: attention surface, upcoming interviews, quick actions, activity feed
- Form CSS system (.form-card, .form-row, .form-field, .form-footer, .btn--loading)
- Detail page action standard: 4 semantic clusters (Navigate, Export, Mutate, Destruct)
- Page refresh standard: toast+refresh for state changes, conditional redirect for deletes
- Tab-focus freshness: stale page detection for shared-account use
- Return context: forms remember referrer via ?next= param
- Job delete route with pipeline count guard
- Cancel consistency: interviewers + tests marked cancelled properly
- Deleted table.js (replaced by sync-list.js)
- Sidebar renamed: Test → Review
- Branding: INS ATS + favicon

### v0.3 (2026-06-23)
- Lucide inline SVG icons for sidebar navigation
- Mobile sidebar close button
- Bulk selection with hover-reveal checkboxes
- Ctrl+Click toggle and Shift+Click range select on rows
- Bulk delete action bar
- Global keyboard shortcut system with `?` help overlay
- Custom views: save/switch/delete filter presets (pill UI)
- Advanced filter: pill-based compound filtering
- Persistent filter/sort/group state via URL params
- Dashboard revamp: stats cards + upcoming interviews widget
- NocoDB CV link in candidate snapshot
- Sprint 1 quick wins: validation, LLM params, copy links, partial scorecard
- Various bug fixes (context menu, session delete, inline stage edit, group-by)

### v0.2 (2026-06-18)
- Dark mode (Catppuccin Mocha) with full hardcoded color removal
- Sidebar navigation with collapsible mobile hamburger
- `table.js` module: search, filter, sort, group-by on all list pages
- Context menus and clickable rows (Linear-style)
- Pipeline list and detail pages
- Candidate history with inline stage/notes editing
- Scorecard auto-populate from completed sessions
- Staging environment (`docker-compose.staging.yml`, port 8001)
- Group-by DOM reordering fix

### v0.1 (2026-06-17)
- Initial release: sessions, templates, multi-interviewer, LLM summaries
- Candidate + Pipeline models, NocoDB integration
- Admin auth, settings page, consent prompt
- Docker + systemd + Cloudflare Tunnel deployment
