# Atomic — Draft (auto-generated)

## Config
| Key | Value | Source |
|-----|-------|--------|
| DATABASE_URL | sqlite:///./interview.db | .env |
| LLM_MODEL | gpt-4o | .env / DB settings |
| ADMIN_SESSION_SECRET | (secret) | .env |

## Environment Variables
| Key | Required | Description |
|-----|----------|-------------|
| NOCODB_BASE_URL | no | NocoDB instance URL for candidate lookup |
| NOCODB_API_KEY | no | NocoDB PAT token |
| NOCODB_TABLE_ID | no | NocoDB table for candidates |
| NOCODB_BASE_ID | no | NocoDB base identifier |
| LLM_BASE_URL | yes | OpenAI-compatible endpoint |
| LLM_API_KEY | yes | LLM provider API key |
| LLM_MODEL | yes | Model identifier |
| ADMIN_SESSION_SECRET | yes | Cookie signing secret |
| DATABASE_URL | no | SQLite connection string (default: sqlite:///./interview.db) |

## Constants
| Key | Value |
|-----|-------|
| Default port | 8000 |
| Python version | >=3.12 |
| Framework | FastAPI >=0.115.0 |
| ORM | SQLModel 0.0.22 |
