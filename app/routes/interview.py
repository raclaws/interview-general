from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import InterviewSession, Response

router = APIRouter()


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("/i/{token}", response_class=HTMLResponse)
async def interview_form(request: Request, token: str, db: Session = Depends(get_session)):
    session = db.exec(
        select(InterviewSession).where(InterviewSession.token == token)
    ).first()
    if not session:
        return HTMLResponse("Invalid or expired link.", status_code=404)
    if session.status == "completed":
        return RedirectResponse(f"/i/{token}/done", status_code=303)
    return _render(request, "interview_form.html", {"session": session})


@router.post("/i/{token}")
async def interview_submit(
    request: Request,
    token: str,
    q1: int = Form(...),
    q2: int = Form(...),
    q3: int = Form(...),
    q4: int = Form(...),
    q5: str = Form(...),
    free_text: str = Form(""),
    db: Session = Depends(get_session),
):
    session = db.exec(
        select(InterviewSession).where(InterviewSession.token == token)
    ).first()
    if not session or session.status == "completed":
        return HTMLResponse("This session has already been submitted.", status_code=400)

    q5_bool = q5.lower() in ("yes", "true", "1")

    response = Response(
        session_id=session.id,
        q1=q1,
        q2=q2,
        q3=q3,
        q4=q4,
        q5=q5_bool,
        free_text=free_text if free_text.strip() else None,
        submitted_at=datetime.utcnow(),
        summary="",
    )
    db.add(response)
    session.status = "completed"
    db.add(session)
    db.commit()
    return RedirectResponse(f"/i/{token}/done", status_code=303)


@router.get("/i/{token}/done", response_class=HTMLResponse)
async def interview_done(request: Request, token: str, db: Session = Depends(get_session)):
    session = db.exec(
        select(InterviewSession).where(InterviewSession.token == token)
    ).first()
    if not session:
        return HTMLResponse("Invalid link.", status_code=404)
    return _render(request, "interview_done.html", {"session": session})
