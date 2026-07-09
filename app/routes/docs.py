from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/docs")


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("", response_class=HTMLResponse)
async def docs_home(request: Request):
    return _render(request, "docs/home.html")


@router.get("/{page}", response_class=HTMLResponse)
async def docs_page(request: Request, page: str):
    allowed = [
        "mulai", "jobs", "kandidat", "pipeline", "tugas",
        "wawancara", "portal", "pengaturan", "laporan", "mcp",
    ]
    if page not in allowed:
        return HTMLResponse("Halaman tidak ditemukan", status_code=404)
    return _render(request, f"docs/{page}.html")
