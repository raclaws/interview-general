import uuid
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import Candidate, CandidatePipeline, CandidateSignal, AdminUser, Job, not_deleted

router = APIRouter()


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.post("/candidate/{candidate_id}/share")
async def generate_share_link(
    request: Request,
    candidate_id: int,
    hide_salary: str = Form("on"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return RedirectResponse("/candidates", status_code=303)
    candidate.share_token = str(uuid.uuid4())
    candidate.share_hide_salary = hide_salary == "on"
    db.add(candidate)
    db.commit()
    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.post("/candidate/{candidate_id}/revoke-share")
async def revoke_share_link(
    request: Request,
    candidate_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return RedirectResponse("/candidates", status_code=303)
    candidate.share_token = None
    db.add(candidate)
    db.commit()
    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.get("/s/{token}", response_class=HTMLResponse)
async def shared_candidate_view(
    request: Request,
    token: str,
    db: Session = Depends(get_session),
):
    candidate = db.exec(
        select(Candidate).where(Candidate.share_token == token)
    ).first()
    if not candidate:
        return HTMLResponse("<h1>Link expired or invalid</h1>", status_code=404)

    signal = db.exec(
        select(CandidateSignal).where(CandidateSignal.candidate_id == candidate.id)
    ).first()

    pipelines = db.exec(
        select(CandidatePipeline)
        .where(CandidatePipeline.candidate_id == candidate.id, not_deleted(CandidatePipeline))
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()

    pipeline_jobs = {}
    for p in pipelines:
        if p.job_id:
            job = db.get(Job, p.job_id)
            if job:
                pipeline_jobs[p.id] = job

    return _render(request, "share/candidate.html", {
        "candidate": candidate,
        "signal": signal,
        "pipelines": pipelines,
        "pipeline_jobs": pipeline_jobs,
        "hide_salary": candidate.share_hide_salary,
    })
