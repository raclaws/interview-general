from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import (
    AdminUser, Candidate, CandidatePipeline, InterviewSession,
    SessionInterviewer, Template, PIPELINE_STAGES,
)
from app.routes.admin import POSITIONS, BUSINESS_UNITS

router = APIRouter()


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("/candidates", response_class=HTMLResponse)
async def candidates_list(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidates = db.exec(
        select(Candidate).order_by(Candidate.updated_at.desc())
    ).all()
    candidate_data = []
    for c in candidates:
        pipelines = db.exec(
            select(CandidatePipeline).where(CandidatePipeline.candidate_id == c.id)
        ).all()
        candidate_data.append({"candidate": c, "pipelines": pipelines})
    return _render(request, "candidates_list.html", {
        "candidate_data": candidate_data,
        "admin": admin,
        "stages": PIPELINE_STAGES,
    })


@router.get("/candidate/{candidate_id}", response_class=HTMLResponse)
async def candidate_detail(
    request: Request,
    candidate_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    pipelines = db.exec(
        select(CandidatePipeline)
        .where(CandidatePipeline.candidate_id == candidate.id)
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()

    sessions = db.exec(
        select(InterviewSession)
        .where(InterviewSession.candidate_id == candidate.id)
        .order_by(InterviewSession.created_at.desc())
    ).all()

    session_data = []
    for s in sessions:
        interviewers = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        total = len(interviewers)
        completed = len([i for i in interviewers if i.status == "completed"])
        session_data.append({"session": s, "total": total, "completed": completed})

    templates = db.exec(select(Template).order_by(Template.name)).all()

    return _render(request, "candidate_detail.html", {
        "candidate": candidate,
        "pipelines": pipelines,
        "session_data": session_data,
        "admin": admin,
        "stages": PIPELINE_STAGES,
        "positions": POSITIONS,
        "business_units": BUSINESS_UNITS,
        "templates": templates,
    })


@router.get("/candidate/{candidate_id}/edit", response_class=HTMLResponse)
async def candidate_edit_form(
    request: Request,
    candidate_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)
    return _render(request, "candidate_edit.html", {"candidate": candidate, "admin": admin})


@router.post("/candidate/{candidate_id}/edit")
async def candidate_edit_submit(
    request: Request,
    candidate_id: int,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    current_position: str = Form(""),
    yoe: str = Form(""),
    languages: str = Form(""),
    cloud: str = Form(""),
    tools: str = Form(""),
    working_arrangement: str = Form(""),
    current_salary: str = Form(""),
    expected_salary: str = Form(""),
    notice_period: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    candidate.name = name.strip()
    candidate.email = email.strip()
    candidate.phone = phone.strip() or None
    candidate.current_position = current_position.strip() or None
    candidate.yoe = yoe.strip() or None
    candidate.languages = languages.strip() or None
    candidate.cloud = cloud.strip() or None
    candidate.tools = tools.strip() or None
    candidate.working_arrangement = working_arrangement.strip() or None
    candidate.current_salary = current_salary.strip() or None
    candidate.expected_salary = expected_salary.strip() or None
    candidate.notice_period = notice_period.strip() or None
    candidate.updated_at = datetime.utcnow()
    db.add(candidate)
    db.commit()
    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.post("/candidate/{candidate_id}/pipeline")
async def pipeline_create(
    request: Request,
    candidate_id: int,
    position: str = Form(""),
    business_unit: str = Form(""),
    stage: str = Form("screening"),
    notes: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    pipeline = CandidatePipeline(
        candidate_id=candidate.id,
        position=position.strip() or None,
        business_unit=business_unit.strip() or None,
        stage=stage if stage in PIPELINE_STAGES else "screening",
        notes=notes.strip() or None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(pipeline)
    db.commit()

    if request.headers.get("HX-Request"):
        db.refresh(pipeline)
        pipelines = db.exec(
            select(CandidatePipeline)
            .where(CandidatePipeline.candidate_id == candidate.id)
            .order_by(CandidatePipeline.updated_at.desc())
        ).all()
        return _render(request, "partials/pipeline_list.html", {
            "pipelines": pipelines,
            "candidate": candidate,
            "stages": PIPELINE_STAGES,
        })

    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.post("/candidate/{candidate_id}/pipeline/{pipeline_id}/stage")
async def pipeline_update_stage(
    request: Request,
    candidate_id: int,
    pipeline_id: int,
    stage: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline or pipeline.candidate_id != candidate_id:
        return HTMLResponse("Not found", status_code=404)

    if stage in PIPELINE_STAGES:
        pipeline.stage = stage
        pipeline.updated_at = datetime.utcnow()
        db.add(pipeline)
        db.commit()

    if request.headers.get("HX-Request"):
        pipelines = db.exec(
            select(CandidatePipeline)
            .where(CandidatePipeline.candidate_id == candidate_id)
            .order_by(CandidatePipeline.updated_at.desc())
        ).all()
        candidate = db.get(Candidate, candidate_id)
        return _render(request, "partials/pipeline_list.html", {
            "pipelines": pipelines,
            "candidate": candidate,
            "stages": PIPELINE_STAGES,
        })

    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.post("/candidate/{candidate_id}/pipeline/{pipeline_id}/notes")
async def pipeline_update_notes(
    request: Request,
    candidate_id: int,
    pipeline_id: int,
    notes: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline or pipeline.candidate_id != candidate_id:
        return HTMLResponse("Not found", status_code=404)

    pipeline.notes = notes.strip() or None
    pipeline.updated_at = datetime.utcnow()
    db.add(pipeline)
    db.commit()

    if request.headers.get("HX-Request"):
        pipelines = db.exec(
            select(CandidatePipeline)
            .where(CandidatePipeline.candidate_id == candidate_id)
            .order_by(CandidatePipeline.updated_at.desc())
        ).all()
        candidate = db.get(Candidate, candidate_id)
        return _render(request, "partials/pipeline_list.html", {
            "pipelines": pipelines,
            "candidate": candidate,
            "stages": PIPELINE_STAGES,
        })

    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)
