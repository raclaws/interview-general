from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.exceptions import HTTPException
from dotenv import load_dotenv

load_dotenv()

from app.database import create_tables
from app.routes.admin import router as admin_router
from app.routes.interview import router as interview_router
from app.routes.candidates import router as candidates_router
from app.routes.test_portal import router as test_portal_router
from app.routes.sync import router as sync_router
from app.routes.perf import router as perf_router
from app.routes.review import router as review_router
from app.routes.jobs import router as jobs_router
from app.routes.settings import router as settings_router
from app.routes.reports import router as reports_router
from app.routes.webhooks import router as webhooks_router
from app.routes.offers import router as offers_router
from app.routes.portal import router as portal_router
from app.routes.requests import router as requests_router
from app.routes.tasks import router as tasks_router
from app.routes.docs import router as docs_router
from app.routes.share import router as share_router
from app.routes.benchmark import router as benchmark_router

app = FastAPI(title="Interview Form Summarizer", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https" or "localhost" not in request.headers.get("host", ""):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        if request.headers.get("HX-Request") == "true":
            return HTMLResponse("", status_code=200, headers={"HX-Redirect": "/login"})
        return RedirectResponse("/login", status_code=303)
    if exc.status_code == 404:
        return templates.TemplateResponse(request, "404.html", status_code=404)
    raise exc

BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["from_json"] = lambda s: __import__("json").loads(s) if s else []


def _format_text(text):
    """Lightweight bullet/number formatting for long_text fields."""
    import re
    from markupsafe import Markup
    if not text:
        return ""
    lines = text.split("\n")
    html = []
    in_ul = False
    in_ol = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^[-*]\s+", stripped):
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            if in_ol:
                html.append("</ol>")
                in_ol = False
            content = re.sub(r"^[-*]\s+", "", stripped)
            html.append(f"<li>{Markup.escape(content)}</li>")
        elif re.match(r"^\d+\.\s+", stripped):
            if not in_ol:
                html.append("<ol>")
                in_ol = True
            if in_ul:
                html.append("</ul>")
                in_ul = False
            content = re.sub(r"^\d+\.\s+", "", stripped)
            html.append(f"<li>{Markup.escape(content)}</li>")
        else:
            if in_ul:
                html.append("</ul>")
                in_ul = False
            if in_ol:
                html.append("</ol>")
                in_ol = False
            if stripped:
                html.append(f"<p>{Markup.escape(stripped)}</p>")
    if in_ul:
        html.append("</ul>")
    if in_ol:
        html.append("</ol>")
    return Markup("\n".join(html))


templates.env.filters["format_text"] = _format_text
app.state.templates = templates

app.include_router(admin_router)
app.include_router(interview_router)
app.include_router(candidates_router)
app.include_router(test_portal_router)
app.include_router(sync_router)
app.include_router(perf_router)
app.include_router(review_router)
app.include_router(jobs_router)
app.include_router(settings_router)
app.include_router(reports_router)
app.include_router(webhooks_router)
app.include_router(offers_router)
app.include_router(portal_router)
app.include_router(requests_router)
app.include_router(tasks_router)
app.include_router(docs_router)
app.include_router(share_router)
app.include_router(benchmark_router)


@app.on_event("startup")
def on_startup():
    create_tables()
    # Warn if using default session secret
    import os
    secret = os.getenv("ADMIN_SESSION_SECRET", "change-me")
    if secret == "change-me":
        import logging
        logging.getLogger("uvicorn.error").warning(
            "SECURITY: ADMIN_SESSION_SECRET is using the default value. Set a strong secret in .env"
        )
    # Auto-create admin from env vars if not exists
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    if username and password:
        from sqlmodel import Session, select
        from app.models import AdminUser
        from app.auth import hash_password
        from app.database import engine as db_engine
        with Session(db_engine) as db:
            existing = db.exec(select(AdminUser).where(AdminUser.username == username)).first()
            if not existing:
                db.add(AdminUser(username=username, hashed_password=hash_password(password)))
                db.commit()
