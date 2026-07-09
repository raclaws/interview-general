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

app = FastAPI(title="Interview Form Summarizer")


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


@app.on_event("startup")
def on_startup():
    create_tables()
