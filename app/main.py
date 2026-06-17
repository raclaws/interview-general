from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.exceptions import HTTPException
from dotenv import load_dotenv

load_dotenv()

from app.database import create_tables
from app.routes.admin import router as admin_router
from app.routes.interview import router as interview_router
from app.routes.candidates import router as candidates_router

app = FastAPI(title="Interview Form Summarizer")


@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
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


@app.on_event("startup")
def on_startup():
    create_tables()
