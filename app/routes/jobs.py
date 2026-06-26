import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import (
    AdminUser, Job, BusinessUnit, ManagedPosition, ManagedLevel, ManagedJobType,
    CandidatePipeline, PIPELINE_ENDED_STAGES, Candidate, PIPELINE_STAGES, Comment,
)
from app.routes.sync import hub as sync_hub
from app.activity import record_activity
from app.helpers import render_gone

router = APIRouter()


def _serialize_job_for_broadcast(job: Job, bu: BusinessUnit | None, db: Session) -> dict:
    from sqlalchemy import func
    pipeline_count = db.exec(
        select(func.count(CandidatePipeline.id)).where(CandidatePipeline.job_id == job.id)
    ).one()
    filled = db.exec(
        select(func.count(CandidatePipeline.id)).where(
            CandidatePipeline.job_id == job.id, CandidatePipeline.stage == "hired"
        )
    ).one()
    return {
        "id": str(job.id),
        "title": job.title,
        "status": job.status,
        "priority": job.priority,
        "jobType": job.job_type,
        "buName": bu.name if bu else "",
        "recruiter": job.recruiter or "",
        "headcount": job.headcount,
        "filled": filled,
        "pipelineCount": pipeline_count,
        "updatedAt": int(job.updated_at.timestamp() * 1000) if job.updated_at else 0,
    }


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _job_context(db: Session):
    """Load dropdown options for job forms."""
    positions = db.exec(select(ManagedPosition).order_by(ManagedPosition.order)).all()
    levels = db.exec(select(ManagedLevel).order_by(ManagedLevel.order)).all()
    job_types = db.exec(select(ManagedJobType).order_by(ManagedJobType.order)).all()
    bus = db.exec(select(BusinessUnit).where(BusinessUnit.is_active == True).order_by(BusinessUnit.name)).all()
    return {
        "positions": positions,
        "levels": levels,
        "job_types": job_types,
        "business_units": bus,
    }


def _filled_count(db: Session, job_id: int) -> int:
    pipelines = db.exec(
        select(CandidatePipeline).where(
            CandidatePipeline.job_id == job_id,
            CandidatePipeline.stage == "hired",
        )
    ).all()
    return len(pipelines)


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_list(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    bus = db.exec(select(BusinessUnit).where(BusinessUnit.is_active == True)).all()
    bu_names = sorted(b.name for b in bus)
    return _render(request, "jobs_list.html", {"admin": admin, "bu_names": bu_names})


@router.get("/job/new", response_class=HTMLResponse)
async def job_new_form(
    request: Request,
    next: str = None,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    ctx = _job_context(db)
    ctx["admin"] = admin
    ctx["next"] = next
    return _render(request, "job_form.html", ctx)


@router.post("/job/new")
async def job_new_submit(
    request: Request,
    position: str = Form(...),
    level: str = Form(...),
    job_type: str = Form("Full-time"),
    business_unit_id: int = Form(...),
    headcount: int = Form(1),
    recruiter: str = Form(""),
    backup_recruiter: str = Form(""),
    hiring_manager: str = Form(""),
    priority: str = Form("normal"),
    salary_range_min: str = Form(""),
    salary_range_max: str = Form(""),
    target_date: str = Form(""),
    description: str = Form(""),
    notes: str = Form(""),
    source: str = Form(""),
    next: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    bu = db.get(BusinessUnit, business_unit_id)
    if not bu:
        return HTMLResponse("Business unit not found", status_code=404)

    final_recruiter = recruiter.strip() or bu.default_recruiter or None
    final_hm = hiring_manager.strip() or bu.head or None

    job = Job(
        position=position.strip(),
        level=level.strip(),
        job_type=job_type.strip(),
        business_unit_id=business_unit_id,
        headcount=max(1, headcount),
        recruiter=final_recruiter,
        backup_recruiter=backup_recruiter.strip() or None,
        hiring_manager=final_hm,
        priority=priority if priority in ("urgent", "high", "normal", "low") else "normal",
        salary_range_min=max(0, int(salary_range_min)) if salary_range_min.strip() else None,
        salary_range_max=max(0, int(salary_range_max)) if salary_range_max.strip() else None,
        target_date=target_date.strip() or None,
        description=description.strip() or None,
        notes=notes.strip() or None,
        source=source.strip() or None,
        title="",
    )
    job.title = job.generate_title(bu.name)

    db.add(job)
    db.commit()
    db.refresh(job)

    asyncio.create_task(sync_hub.broadcast("jobs", "insert", str(job.id), _serialize_job_for_broadcast(job, bu, db)))

    return RedirectResponse(next or f"/job/{job.id}", status_code=303)


@router.get("/job/{job_id}", response_class=HTMLResponse)
async def job_detail(
    request: Request,
    job_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    job = db.get(Job, job_id)
    if not job:
        return render_gone(request, "Job", "/jobs", "Jobs")

    bu = db.get(BusinessUnit, job.business_unit_id)
    pipelines = db.exec(
        select(CandidatePipeline).where(CandidatePipeline.job_id == job.id)
    ).all()
    filled = len([p for p in pipelines if p.stage == "hired"])

    # Join candidate names for display
    pipeline_data = []
    for p in pipelines:
        candidate = db.get(Candidate, p.candidate_id)
        pipeline_data.append({"pipeline": p, "candidate": candidate})

    return _render(request, "job_detail.html", {
        "admin": admin,
        "job": job,
        "bu": bu,
        "pipelines": pipelines,
        "pipeline_data": pipeline_data,
        "filled": filled,
        "trail": db.exec(
            select(Comment).where(Comment.entity_type == "job", Comment.entity_id == job_id).order_by(Comment.created_at)
        ).all(),
    })


@router.get("/job/{job_id}/edit", response_class=HTMLResponse)
async def job_edit_form(
    request: Request,
    job_id: int,
    next: str = None,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    job = db.get(Job, job_id)
    if not job:
        return HTMLResponse("Not found", status_code=404)

    ctx = _job_context(db)
    ctx["admin"] = admin
    ctx["job"] = job
    ctx["editing"] = True
    ctx["next"] = next or f"/job/{job_id}"
    return _render(request, "job_form.html", ctx)


@router.post("/job/{job_id}/edit")
async def job_edit_submit(
    request: Request,
    job_id: int,
    position: str = Form(...),
    level: str = Form(...),
    job_type: str = Form("Full-time"),
    business_unit_id: int = Form(...),
    headcount: int = Form(1),
    recruiter: str = Form(""),
    backup_recruiter: str = Form(""),
    hiring_manager: str = Form(""),
    priority: str = Form("normal"),
    salary_range_min: str = Form(""),
    salary_range_max: str = Form(""),
    target_date: str = Form(""),
    description: str = Form(""),
    notes: str = Form(""),
    source: str = Form(""),
    title_locked: str = Form(""),
    next: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    job = db.get(Job, job_id)
    if not job:
        return HTMLResponse("Not found", status_code=404)

    bu = db.get(BusinessUnit, business_unit_id)
    if not bu:
        return HTMLResponse("Business unit not found", status_code=404)

    job.position = position.strip()
    job.level = level.strip()
    job.job_type = job_type.strip()
    job.business_unit_id = business_unit_id
    job.headcount = max(1, headcount)
    job.recruiter = recruiter.strip() or bu.default_recruiter or None
    job.backup_recruiter = backup_recruiter.strip() or None
    job.hiring_manager = hiring_manager.strip() or bu.head or None
    job.priority = priority if priority in ("urgent", "high", "normal", "low") else "normal"
    job.salary_range_min = int(salary_range_min) if salary_range_min.strip() else None
    job.salary_range_max = int(salary_range_max) if salary_range_max.strip() else None
    job.target_date = target_date.strip() or None
    job.description = description.strip() or None
    job.notes = notes.strip() or None
    job.source = source.strip() or None
    job.title_locked = title_locked == "on"

    if not job.title_locked:
        job.title = job.generate_title(bu.name)

    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()

    bu = db.get(BusinessUnit, job.business_unit_id)
    asyncio.create_task(sync_hub.broadcast("jobs", "update", str(job.id), _serialize_job_for_broadcast(job, bu, db)))

    return RedirectResponse(next or f"/job/{job.id}", status_code=303)


@router.post("/job/{job_id}/close")
async def job_close(
    request: Request,
    job_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    job = db.get(Job, job_id)
    if not job:
        return HTMLResponse("Not found", status_code=404)

    job.status = "closed"
    job.closed_date = datetime.utcnow().strftime("%Y-%m-%d")
    job.updated_at = datetime.utcnow()
    record_activity(db, "job", job.id, "Job closed")
    db.add(job)
    db.commit()

    bu = db.get(BusinessUnit, job.business_unit_id)
    asyncio.create_task(sync_hub.broadcast("jobs", "update", str(job.id), _serialize_job_for_broadcast(job, bu, db)))

    if request.headers.get("HX-Request"):
        resp = HTMLResponse("")
        resp.headers["HX-Trigger"] = json.dumps({"toast": {"message": "Job closed", "severity": ""}})
        resp.headers["HX-Refresh"] = "true"
        return resp

    return RedirectResponse(f"/job/{job.id}", status_code=303)


@router.post("/job/{job_id}/reopen")
async def job_reopen(
    request: Request,
    job_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    job = db.get(Job, job_id)
    if not job:
        return HTMLResponse("Not found", status_code=404)

    job.status = "open"
    job.closed_date = None
    job.updated_at = datetime.utcnow()
    record_activity(db, "job", job.id, "Job reopened")
    db.add(job)
    db.commit()

    bu = db.get(BusinessUnit, job.business_unit_id)
    asyncio.create_task(sync_hub.broadcast("jobs", "update", str(job.id), _serialize_job_for_broadcast(job, bu, db)))

    if request.headers.get("HX-Request"):
        resp = HTMLResponse("")
        resp.headers["HX-Trigger"] = json.dumps({"toast": {"message": "Job reopened", "severity": ""}})
        resp.headers["HX-Refresh"] = "true"
        return resp

    return RedirectResponse(f"/job/{job.id}", status_code=303)


@router.post("/job/{job_id}/delete")
async def job_delete(
    request: Request,
    job_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from sqlalchemy import func

    job = db.get(Job, job_id)
    if not job:
        return HTMLResponse("Not found", status_code=404)

    pipeline_count = db.exec(
        select(func.count(CandidatePipeline.id)).where(CandidatePipeline.job_id == job.id)
    ).one()

    if pipeline_count > 0:
        msg = f"Cannot delete: {pipeline_count} pipeline{'s' if pipeline_count > 1 else ''} linked to this job. Close it instead."
        if request.headers.get("HX-Request"):
            resp = HTMLResponse("")
            resp.headers["HX-Trigger"] = json.dumps({"toast": {"message": msg, "severity": "warning"}})
            return resp
        return RedirectResponse(f"/job/{job.id}", status_code=303)

    job.deleted_at = datetime.utcnow()
    db.add(job)
    db.commit()

    asyncio.create_task(sync_hub.broadcast("jobs", "delete", str(job.id), {"id": str(job.id)}))

    if request.headers.get("HX-Request"):
        resp = HTMLResponse("")
        current_path = request.headers.get("HX-Current-URL", "").split("?")[0].rstrip("/")
        if current_path.endswith(f"/job/{job_id}"):
            resp.headers["HX-Redirect"] = "/jobs"
        resp.headers["HX-Trigger"] = json.dumps({"undoable-delete": {"type": "job", "id": str(job_id), "label": job.title}})
        return resp

    return RedirectResponse("/jobs", status_code=303)


@router.post("/job/{job_id}/links")
async def job_add_link(
    request: Request,
    job_id: int,
    link_title: str = Form(...),
    link_url: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    job = db.get(Job, job_id)
    if not job:
        return HTMLResponse("Not found", status_code=404)

    links = json.loads(job.links) if job.links else []
    links.append({"title": link_title.strip(), "url": link_url.strip()})
    job.links = json.dumps(links)
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()

    if request.headers.get("HX-Request"):
        return _render(request, "partials/job_links.html", {"job": job, "admin": admin})

    return RedirectResponse(f"/job/{job.id}", status_code=303)


@router.post("/job/{job_id}/links/{link_idx}/delete")
async def job_delete_link(
    request: Request,
    job_id: int,
    link_idx: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    job = db.get(Job, job_id)
    if not job:
        return HTMLResponse("Not found", status_code=404)

    links = json.loads(job.links) if job.links else []
    if 0 <= link_idx < len(links):
        links.pop(link_idx)
    job.links = json.dumps(links)
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()

    if request.headers.get("HX-Request"):
        return _render(request, "partials/job_links.html", {"job": job, "admin": admin})

    return RedirectResponse(f"/job/{job.id}", status_code=303)


@router.post("/job/{job_id}/add-candidate")
async def job_add_candidate(
    request: Request,
    job_id: int,
    mode: str = Form(...),
    candidate_id: int = Form(None),
    nocodb_id: int = Form(None),
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    current_position: str = Form(""),
    cv_link: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    job = db.get(Job, job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)

    bu = db.get(BusinessUnit, job.business_unit_id)

    if mode == "existing":
        if not candidate_id:
            return HTMLResponse('<div class="form-error">Please select a candidate.</div>')
        candidate = db.get(Candidate, candidate_id)
        if not candidate:
            return HTMLResponse('<div class="form-error">Candidate not found.</div>')
    elif mode == "nocodb":
        if not nocodb_id:
            return HTMLResponse('<div class="form-error">Please select a candidate from NocoDB.</div>')
        from app.nocodb import fetch_candidate
        snapshot = await fetch_candidate(nocodb_id)
        if not snapshot or snapshot.get("_error") or not snapshot.get("email"):
            error_msg = snapshot.get("_error", "Candidate not found in NocoDB.") if snapshot else "Candidate not found in NocoDB."
            return HTMLResponse(f'<div class="form-error">{error_msg}</div>')
        email_val = snapshot.get("email", "").strip()
        candidate = db.exec(select(Candidate).where(Candidate.email == email_val)).first()
        if not candidate:
            candidate = Candidate(
                name=snapshot.get("name", ""),
                email=email_val,
                phone=snapshot.get("phone") or None,
                nocodb_id=nocodb_id,
                current_position=snapshot.get("current_position") or None,
                yoe=snapshot.get("yoe") or None,
                languages=snapshot.get("languages") or None,
                cloud=snapshot.get("cloud") or None,
                tools=snapshot.get("tools") or None,
                working_arrangement=snapshot.get("working_arrangement") or None,
                current_salary=snapshot.get("current_salary") or None,
                expected_salary=snapshot.get("expected_salary") or None,
                notice_period=snapshot.get("notice_period") or None,
                cv_link=snapshot.get("cv_link") or None,
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
    else:
        if not name.strip() or not email.strip():
            return HTMLResponse('<div class="form-error">Name and email are required.</div>')
        candidate = db.exec(select(Candidate).where(Candidate.email == email.strip())).first()
        if not candidate:
            candidate = Candidate(
                name=name.strip(),
                email=email.strip(),
                phone=phone.strip() or None,
                current_position=current_position.strip() or None,
                cv_link=cv_link.strip() or None,
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)

    existing_pipeline = db.exec(
        select(CandidatePipeline).where(
            CandidatePipeline.candidate_id == candidate.id,
            CandidatePipeline.job_id == job_id,
        )
    ).first()

    if existing_pipeline and existing_pipeline.stage not in PIPELINE_ENDED_STAGES:
        return HTMLResponse(f'<div class="form-error">{candidate.name} already has an active pipeline for this job.</div>')

    if existing_pipeline and existing_pipeline.stage in PIPELINE_ENDED_STAGES:
        pass  # Allow re-adding (new round)

    mmyy = datetime.utcnow().strftime("%m%y")
    bu_name = bu.name if bu else "N/A"
    display_name = f"{job.position} {mmyy} #1 — {bu_name}"

    pipeline = CandidatePipeline(
        candidate_id=candidate.id,
        job_id=job_id,
        display_name=display_name,
        position=job.position,
        business_unit=bu_name,
        stage="screening",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(pipeline)
    db.commit()

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            "",
            headers={"HX-Redirect": f"/job/{job.id}"},
        )

    return RedirectResponse(f"/job/{job.id}", status_code=303)
