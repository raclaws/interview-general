# Interview Form Summarizer

A lightweight self-hosted webapp for managing interview pipelines and generating AI-powered assessment summaries. Admin creates candidates, manages pipeline stages, creates interview sessions, shares token links with interviewers, and views auto-aggregated scorecards.

**Current version: v0.2**

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
- **Provider-agnostic** — any OpenAI-compatible endpoint (base URL + key + model)
- **Dashboard-editable** — LLM settings configurable from `/settings` without restart

### UI
- **Dark mode** — Catppuccin Mocha palette throughout
- **Sidebar navigation** — Dashboard, Interview, Pipelines, Candidates, Settings
- **Table module** — client-side search, filter, sort, group-by on all list pages
- **Context menus** — right-click actions on table rows
- **Clickable rows** — navigate to detail by clicking anywhere

### Admin
- **Editable sessions** — modify details + results after creation
- **Cancel/expire sessions** — admin can invalidate pending sessions
- **Copy token link** — one-click copy interview URL from dashboard
- **Copy as Markdown** — export results as formatted markdown
- **Salary toggle** — hidden by default, admin toggles per session
- **Consent prompt** — data + AI disclosure required before submission

### Integrations
- **NocoDB** — candidate search/import (optional, manual entry supported)
- **MCP server** — agent access for session management

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
