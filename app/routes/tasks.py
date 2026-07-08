import json as json_mod
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import (
    AdminUser, Task, Job, CandidatePipeline, Candidate, BusinessUnit, not_deleted,
)
from app.activity import record_activity
from app.routes.sync import hub

router = APIRouter(prefix="/tasks")

VALID_STATUSES = ("pending", "in_progress", "done", "cancelled")
VALID_PRIORITIES = ("none", "low", "medium", "high", "urgent")


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _toast_error(request: Request, msg: str):
    return HTMLResponse(
        f'<div class="form-error">{msg}</div>',
        headers={"HX-Trigger": f'{{"toast":{{"value":"{msg}","severity":"error"}}}}'},
    )


def _is_sync_list(request: Request) -> bool:
    current = request.headers.get("HX-Current-URL", "")
    return current.rstrip("/").endswith("/tasks")


def _entity_display(db: Session, entity_type: str, entity_id: int) -> str:
    if entity_type == "job":
        job = db.get(Job, entity_id)
        if job:
            bu = db.get(BusinessUnit, job.business_unit_id)
            return f"{job.position} — {job.level}" + (f" — {bu.name}" if bu else "")
    elif entity_type == "pipeline":
        pipeline = db.get(CandidatePipeline, entity_id)
        if pipeline:
            candidate = db.get(Candidate, pipeline.candidate_id)
            job = db.get(Job, pipeline.job_id) if pipeline.job_id else None
            parts = []
            if candidate:
                parts.append(candidate.name)
            if job:
                parts.append(job.position)
            return " — ".join(parts) if parts else f"Pipeline #{entity_id}"
    return ""


def _assignee_options_for(db: Session, entity_type: str, entity_id: int) -> list[str]:
    options = set()
    if entity_type == "job":
        job = db.get(Job, entity_id)
        if job:
            if job.recruiter:
                options.add(job.recruiter)
            if job.backup_recruiter:
                options.add(job.backup_recruiter)
            bu = db.get(BusinessUnit, job.business_unit_id)
            if bu and bu.head:
                options.add(bu.head)
    elif entity_type == "pipeline":
        pipeline = db.get(CandidatePipeline, entity_id)
        if pipeline and pipeline.job_id:
            job = db.get(Job, pipeline.job_id)
            if job:
                if job.recruiter:
                    options.add(job.recruiter)
                if job.backup_recruiter:
                    options.add(job.backup_recruiter)
                bu = db.get(BusinessUnit, job.business_unit_id)
                if bu and bu.head:
                    options.add(bu.head)
    return sorted(options)


@router.get("", response_class=HTMLResponse)
async def tasks_list(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    return _render(request, "tasks/list.html")


@router.get("/new", response_class=HTMLResponse)
async def task_new_form(
    request: Request,
    entity_type: str = "",
    entity_id: int = 0,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    jobs = db.exec(select(Job).where(not_deleted(Job), Job.status == "open").order_by(Job.title)).all()
    pipelines = db.exec(
        select(CandidatePipeline, Candidate)
        .join(Candidate, CandidatePipeline.candidate_id == Candidate.id)
        .where(not_deleted(CandidatePipeline))
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()
    pipeline_options = []
    for p, c in pipelines:
        job = db.get(Job, p.job_id) if p.job_id else None
        label = c.name + (" — " + job.position if job else "")
        pipeline_options.append({"id": p.id, "label": label})

    return _render(request, "tasks/form.html", {
        "jobs": jobs,
        "pipeline_options": pipeline_options,
        "prefill_type": entity_type,
        "prefill_id": entity_id,
    })


@router.get("/{task_id}", response_class=HTMLResponse)
async def task_detail(
    request: Request,
    task_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    task = db.get(Task, task_id)
    if not task or task.deleted_at:
        return HTMLResponse("Not found", status_code=404)
    task._display = _entity_display(db, task.entity_type, task.entity_id)
    assignee_options = _assignee_options_for(db, task.entity_type, task.entity_id)

    return _render(request, "tasks/detail.html", {
        "task": task,
        "assignee_options": assignee_options,
    })


@router.post("/new", response_class=HTMLResponse)
async def task_create(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
    title: str = Form(...),
    entity_type: str = Form(...),
    entity_id: str = Form(""),
    priority: str = Form("none"),
    due_date: str = Form(""),
    assigned_to: str = Form(""),
):
    title = title.strip()
    if not title or len(title) > 200:
        return _toast_error(request, "Title is required (max 200 chars)")
    if entity_type not in ("job", "pipeline"):
        return _toast_error(request, "Invalid entity type")

    try:
        entity_id_int = int(entity_id)
    except (ValueError, TypeError):
        entity_id_int = 0
    if not entity_id_int:
        return _toast_error(request, "Please select a job or pipeline")
    if priority not in VALID_PRIORITIES:
        priority = "none"

    if entity_type == "job":
        entity = db.get(Job, entity_id_int)
        if not entity or entity.deleted_at:
            return _toast_error(request, "Job not found")
    else:
        entity = db.get(CandidatePipeline, entity_id_int)
        if not entity or entity.deleted_at:
            return _toast_error(request, "Pipeline not found")

    task = Task(
        title=title,
        entity_type=entity_type,
        entity_id=entity_id_int,
        priority=priority,
        due_date=due_date.strip() or None,
        assigned_to=assigned_to.strip() or None,
    )
    db.add(task)
    db.flush()

    pipeline_id = entity_id if entity_type == "pipeline" else None
    record_activity(db, entity_type, entity_id, f"Task created: {title}", pipeline_id=pipeline_id)
    db.commit()

    await hub.broadcast("tasks", "insert", str(task.id))

    if not request.headers.get("HX-Request"):
        return RedirectResponse("/tasks", status_code=303)

    headers = {"HX-Trigger": '{"toast":{"value":"Task created","severity":"success"}}'}
    if _is_sync_list(request):
        pass
    else:
        headers["HX-Refresh"] = "true"
    return HTMLResponse("", headers=headers)


@router.post("/{task_id}/status", response_class=HTMLResponse)
async def task_status_change(
    request: Request,
    task_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
    status: str = Form(...),
):
    task = db.get(Task, task_id)
    if not task or task.deleted_at:
        return HTMLResponse("Not found", status_code=404)
    if status not in VALID_STATUSES:
        return _toast_error(request, "Invalid status")
    if task.status == status:
        return HTMLResponse("", status_code=200)

    task.status = status
    task.updated_at = datetime.utcnow()
    db.flush()

    pipeline_id = task.entity_id if task.entity_type == "pipeline" else None
    record_activity(db, task.entity_type, task.entity_id, f"Task {status}: {task.title}", pipeline_id=pipeline_id)
    db.commit()

    await hub.broadcast("tasks", "update", str(task.id))

    headers = {"HX-Trigger": '{"toast":{"value":"Status updated","severity":"success"}}'}
    if not _is_sync_list(request):
        headers["HX-Refresh"] = "true"
    return HTMLResponse("", headers=headers)


@router.post("/{task_id}/edit", response_class=HTMLResponse)
async def task_edit(
    request: Request,
    task_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
    title: str = Form(None),
    description: str = Form(None),
    priority: str = Form(None),
    due_date: str = Form(None),
    assigned_to: str = Form(None),
):
    task = db.get(Task, task_id)
    if not task or task.deleted_at:
        return HTMLResponse("Not found", status_code=404)

    if title is not None:
        title = title.strip()
        if not title or len(title) > 200:
            return _toast_error(request, "Title is required (max 200 chars)")
        task.title = title
    if description is not None:
        task.description = description.strip() or None
    if priority is not None and priority in VALID_PRIORITIES:
        task.priority = priority
    if due_date is not None:
        task.due_date = due_date.strip() or None
    if assigned_to is not None:
        task.assigned_to = assigned_to.strip() or None

    task.updated_at = datetime.utcnow()
    db.commit()

    await hub.broadcast("tasks", "update", str(task.id))
    headers = {"HX-Trigger": '{"toast":{"value":"Task updated","severity":"success"}}'}
    if not _is_sync_list(request):
        headers["HX-Refresh"] = "true"
    return HTMLResponse("", headers=headers)


@router.post("/{task_id}/delete", response_class=HTMLResponse)
async def task_delete(
    request: Request,
    task_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    task = db.get(Task, task_id)
    if not task or task.deleted_at:
        return HTMLResponse("", status_code=200)

    task.deleted_at = datetime.utcnow()
    task.updated_at = datetime.utcnow()
    db.commit()

    await hub.broadcast("tasks", "delete", str(task.id))

    resp = HTMLResponse("")
    current_path = request.headers.get("HX-Current-URL", "").split("?")[0].rstrip("/")
    if current_path.endswith(f"/tasks/{task_id}"):
        resp.headers["HX-Redirect"] = "/tasks"
    resp.headers["HX-Trigger"] = json_mod.dumps({
        "undoable-delete": {"type": "task", "id": str(task_id), "label": task.title},
    })
    return resp
