from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    BusinessUnit, ManpowerRequest, Job, CandidatePipeline,
    ManagedPosition, ManagedLevel, ManagedJobType, not_deleted,
)

router = APIRouter(prefix="/portal")


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _get_bu(token: str, db: Session):
    """Validate token and return the BusinessUnit or None."""
    return db.exec(
        select(BusinessUnit).where(BusinessUnit.portal_token == token, BusinessUnit.portal_token.isnot(None))
    ).first()


@router.get("/{token}", response_class=HTMLResponse)
async def portal_home(request: Request, token: str, db: Session = Depends(get_session)):
    bu = _get_bu(token, db)
    if not bu:
        return HTMLResponse("Invalid or expired portal link.", status_code=404)

    requests_list = db.exec(
        select(ManpowerRequest)
        .where(ManpowerRequest.business_unit_id == bu.id, not_deleted(ManpowerRequest))
        .order_by(ManpowerRequest.created_at.desc())
    ).all()

    return _render(request, "portal/home.html", {
        "bu": bu, "token": token, "requests": requests_list, "active_tab": "requests",
    })


@router.get("/{token}/jobs", response_class=HTMLResponse)
async def portal_jobs(request: Request, token: str, db: Session = Depends(get_session)):
    bu = _get_bu(token, db)
    if not bu:
        return HTMLResponse("Invalid or expired portal link.", status_code=404)

    jobs = db.exec(
        select(Job).where(Job.business_unit_id == bu.id, Job.status == "open", not_deleted(Job))
        .order_by(Job.created_at.desc())
    ).all()

    from sqlmodel import func, col
    job_pipeline_counts = {}
    if jobs:
        count_rows = db.exec(
            select(CandidatePipeline.job_id, func.count(CandidatePipeline.id))
            .where(CandidatePipeline.job_id.in_([j.id for j in jobs]), not_deleted(CandidatePipeline))
            .group_by(CandidatePipeline.job_id)
        ).all()
        job_pipeline_counts = {job_id: cnt for job_id, cnt in count_rows}

    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return _render(request, "portal/jobs_tab.html", {
            "bu": bu, "token": token, "jobs": jobs, "pipeline_counts": job_pipeline_counts, "active_tab": "jobs",
        })

    return _render(request, "portal/home.html", {
        "bu": bu, "token": token, "requests": [], "jobs": jobs,
        "pipeline_counts": job_pipeline_counts, "active_tab": "jobs",
    })


@router.get("/{token}/requests", response_class=HTMLResponse)
async def portal_requests_tab(request: Request, token: str, db: Session = Depends(get_session)):
    bu = _get_bu(token, db)
    if not bu:
        return HTMLResponse("Invalid or expired portal link.", status_code=404)

    requests_list = db.exec(
        select(ManpowerRequest)
        .where(ManpowerRequest.business_unit_id == bu.id, not_deleted(ManpowerRequest))
        .order_by(ManpowerRequest.created_at.desc())
    ).all()

    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return _render(request, "portal/requests_tab.html", {
            "bu": bu, "token": token, "requests": requests_list, "active_tab": "requests",
        })

    return _render(request, "portal/home.html", {
        "bu": bu, "token": token, "requests": requests_list, "active_tab": "requests",
    })


@router.get("/{token}/request", response_class=HTMLResponse)
async def portal_request_form(request: Request, token: str, db: Session = Depends(get_session)):
    bu = _get_bu(token, db)
    if not bu:
        return HTMLResponse("Invalid or expired portal link.", status_code=404)

    positions = db.exec(select(ManagedPosition).order_by(ManagedPosition.order)).all()
    levels = db.exec(select(ManagedLevel).order_by(ManagedLevel.order)).all()
    job_types = db.exec(select(ManagedJobType).order_by(ManagedJobType.order)).all()

    return _render(request, "portal/form.html", {
        "bu": bu, "token": token,
        "positions": positions, "levels": levels, "job_types": job_types,
    })


@router.post("/{token}/request", response_class=HTMLResponse)
async def portal_request_submit(
    request: Request,
    token: str,
    requested_by: str = Form(...),
    position: str = Form(...),
    level: str = Form(...),
    job_type: str = Form("Full-time"),
    headcount: int = Form(1),
    priority: str = Form("normal"),
    target_date: str = Form(""),
    description: str = Form(""),
    justification: str = Form(...),
    db: Session = Depends(get_session),
):
    bu = _get_bu(token, db)
    if not bu:
        return HTMLResponse("Invalid or expired portal link.", status_code=404)

    # Server-side validation
    headcount = max(1, min(99, headcount))
    if priority not in ("normal", "high", "urgent"):
        priority = "normal"

    # Validate position/level/job_type exist in managed lists
    pos_exists = db.exec(select(ManagedPosition).where(ManagedPosition.title == position.strip())).first()
    lvl_exists = db.exec(select(ManagedLevel).where(ManagedLevel.label == level.strip())).first()
    jt_exists = db.exec(select(ManagedJobType).where(ManagedJobType.label == job_type.strip())).first()

    if not pos_exists or not lvl_exists or not jt_exists:
        positions = db.exec(select(ManagedPosition).order_by(ManagedPosition.order)).all()
        levels = db.exec(select(ManagedLevel).order_by(ManagedLevel.order)).all()
        job_types = db.exec(select(ManagedJobType).order_by(ManagedJobType.order)).all()
        return _render(request, "portal/form.html", {
            "bu": bu, "token": token,
            "positions": positions, "levels": levels, "job_types": job_types,
            "error": "Invalid selection. Please use the provided options.",
        })

    mp_request = ManpowerRequest(
        business_unit_id=bu.id,
        requested_by=requested_by.strip(),
        position=position.strip(),
        level=level.strip(),
        job_type=job_type.strip(),
        headcount=headcount,
        priority=priority,
        target_date=target_date.strip() or None,
        description=description.strip() or None,
        justification=justification.strip(),
    )
    db.add(mp_request)
    db.commit()

    return RedirectResponse(f"/portal/{token}", status_code=303)


@router.get("/{token}/request/{request_id}", response_class=HTMLResponse)
async def portal_request_detail(request: Request, token: str, request_id: int, db: Session = Depends(get_session)):
    bu = _get_bu(token, db)
    if not bu:
        return HTMLResponse("Invalid or expired portal link.", status_code=404)

    mp_request = db.get(ManpowerRequest, request_id)
    if not mp_request or mp_request.business_unit_id != bu.id or mp_request.deleted_at:
        return HTMLResponse("Not found.", status_code=404)

    linked_job = db.get(Job, mp_request.job_id) if mp_request.job_id else None

    return _render(request, "portal/detail.html", {
        "bu": bu, "token": token, "mp_request": mp_request, "linked_job": linked_job,
    })
