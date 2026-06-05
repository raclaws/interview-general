# Interview Form Summarizer

A lightweight self-hosted webapp for generating on-demand interview assessment sessions. Admin creates a session with candidate context, shares a token link with the interviewer, and AI summarizes the submission.

## Quick Start

### 1. Clone

```bash
git clone https://github.com/raclaws/interview-general.git
cd interview-general
```

### 2. Install dependencies

```bash
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

## Deploy with systemd (Linux)

### 1. Set up on server

```bash
cd /opt
git clone https://github.com/raclaws/interview-general.git
cd interview-general
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with production values
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
ExecStart=/opt/interview-general/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. Start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable interview-general
sudo systemctl start interview-general
sudo systemctl status interview-general
```

### 4. Reverse proxy (nginx)

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
    }
}
```

Then enable HTTPS with certbot:

```bash
sudo certbot --nginx -d interview.yourdomain.com
```

## Deploy with Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build and run

```bash
docker build -t interview-general .
docker run -d \
  --name interview-general \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/interview.db:/app/interview.db \
  interview-general
```

### Create admin user in container

```bash
docker exec -it interview-general python -m app.cli create-admin admin <your-password>
```

## MCP Server

Run alongside the main app for agent access:

```bash
python -m app.mcp_server
```

Exposes tools: `create_session`, `get_session`, `list_sessions`. No auth required (internal use only).

## LLM Configuration

LLM settings (base URL, API key, model, system prompt) can be changed from the admin dashboard at `/settings` without restarting the server.

## Notes

- The `.env` file is the initial config; once you save settings from the dashboard, DB values take precedence
- SQLite DB is created automatically on first run
- Interview token links are single-use — once submitted, the token is consumed
- NocoDB integration is optional — you can create sessions with manual candidate entry
