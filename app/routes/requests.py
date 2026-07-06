from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import (
    AdminUser, BusinessUnit, ManpowerRequest, Job, not_deleted,
)
from app.activity import record_activity

router = APIRouter(prefix="/requests")


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("", response_class=HTMLResponse)
async def requests_list(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    requests_all = db.exec(
        select(ManpowerRequest).where(not_deleted(ManpowerRequest))
        .order_by(ManpowerRequest.created_at.desc())
    ).all()

    bus = {bu.id: bu for bu in db.exec(select(BusinessUnit)).all()}

    return _render(request, "requests/list.html", {
        "admin": admin, "requests": requests_all, "bus": bus,
    })


@router.get("/{request_id}", response_class=HTMLResponse)
async def request_detail(
    request: Request,
    request_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    mp_request = db.get(ManpowerRequest, request_id)
    if not mp_request or mp_request.deleted_at:
        return HTMLResponse("Not found", status_code=404)

    bu = db.get(BusinessUnit, mp_request.business_unit_id)
    linked_job = db.get(Job, mp_request.job_id) if mp_request.job_id else None

    return _render(request, "requests/detail.html", {
        "admin": admin, "mp_request": mp_request, "bu": bu, "linked_job": linked_job,
    })


@router.post("/{request_id}/approve", response_class=HTMLResponse)
async def request_approve(
    request: Request,
    request_id: int,
    recruiter: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    mp_request = db.get(ManpowerRequest, request_id)
    if not mp_request or mp_request.status != "pending" or mp_request.deleted_at:
        return HTMLResponse("Cannot approve", status_code=400)

    bu = db.get(BusinessUnit, mp_request.business_unit_id)

    job = Job(
        title=f"{mp_request.position} — {mp_request.level}",
        position=mp_request.position,
        level=mp_request.level,
        job_type=mp_request.job_type,
        business_unit_id=mp_request.business_unit_id,
        headcount=mp_request.headcount,
        priority=mp_request.priority,
        target_date=mp_request.target_date,
        description=mp_request.description,
        recruiter=recruiter.strip() or (bu.default_recruiter if bu else None),
        status="open",
    )
    db.add(job)
    db.flush()

    mp_request.status = "approved"
    mp_request.job_id = job.id
    mp_request.updated_at = datetime.utcnow()
    db.add(mp_request)
    db.commit()

    record_activity(db, "job", job.id, f"Job created from manpower request by {mp_request.requested_by}")

    return RedirectResponse(f"/requests/{request_id}", status_code=303)


@router.post("/{request_id}/reject", response_class=HTMLResponse)
async def request_reject(
    request: Request,
    request_id: int,
    admin_notes: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    mp_request = db.get(ManpowerRequest, request_id)
    if not mp_request or mp_request.status != "pending" or mp_request.deleted_at:
        return HTMLResponse("Cannot reject", status_code=400)

    mp_request.status = "rejected"
    mp_request.admin_notes = admin_notes.strip() or None
    mp_request.updated_at = datetime.utcnow()
    db.add(mp_request)
    db.commit()

    return RedirectResponse(f"/requests/{request_id}", status_code=303)
