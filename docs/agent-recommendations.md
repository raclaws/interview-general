# Agent Recommendations

Reviewed: 2026-07-04
Reviewer: Hermes Agent (automated stack review)

## Flags

### 1. MCP Server Exposure (Medium-High)

`fastmcp>=3.0.0` ships an MCP server with the ATS (`app/mcp_server.py`). The MCP spec does not have authentication baked in yet (coming in the 2026-07-28 revision). If the MCP endpoint is reachable from outside (e.g. exposed port, reverse proxy misconfiguration), anyone can access session management tools without auth.

**Fix:** Ensure MCP server only binds to localhost or is behind a firewall rule. Alternatively, add a shared-secret header check in the MCP transport layer.

### 2. OpenAI SDK Version Pinning (Low)

`openai>=1.51.0` is a minimum pin. The OpenAI Python SDK has had breaking changes between minor versions (response model restructuring, async client API changes). For a self-hosted tool this is fine, but if distributing to others, pin exact: `openai==1.86.0` (or current).

### 3. Migration System Fragility (Low)

`database.py::_migrate()` attempts `DROP COLUMN "round"` with a try/except fallback. SQLite < 3.35 cannot drop columns. Since the Docker image uses Python 3.12 (bundles SQLite 3.41+), this works in Docker. If someone runs directly on an older distro (Ubuntu 20.04 ships SQLite 3.31), the column stays as dead weight. Not a real bug — just noise in the schema.

### 4. No Background Task Queue for LLM Calls (Low-Medium)

LLM summary generation (via `openai` client) happens synchronously in request handlers. For 1-2 candidates this is fine. For batch report generation across 20+ candidates, this could timeout or block the event loop.

**Fix when needed:** Use FastAPI `BackgroundTasks` or `asyncio.create_task()` with a progress polling endpoint. No external queue needed.

### 5. Static Files Not Cache-Busted (Low)

JS/CSS files in `/static/` have no versioning hash. Deploy a JS change → users with cached old version get stale behavior until hard-refresh.

**Quick fix:** Add `?v={{ git_hash }}` or a build timestamp to static file includes in `base.html`.

### 6. weasyprint Dependency Weight (Informational)

The Dockerfile installs `libpango`, `libcairo`, `libgdk-pixbuf`, `libglib2.0` for weasyprint (offer letter PDF generation). This adds ~80MB to the image. If PDF generation is rarely used, consider making it optional (separate container/endpoint) or switching to a lighter approach (pdfkit + wkhtmltopdf, or client-side print-to-PDF).

## Verdict

No stack replan needed. FastAPI + HTMX + SQLite + WebSocket sync is the correct architecture for a self-hosted multi-user ATS. Ship it.
