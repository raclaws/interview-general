"""
Sync endpoints for real-time client sync engine.
Provides REST hydrate + WebSocket change stream.
"""

import asyncio
import json
import time
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, Request
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import (
    InterviewSession, SessionInterviewer, Template, CandidatePipeline, AdminUser,
    Job, BusinessUnit, Candidate, CandidateSignal, ReviewBatch, ReviewScore, PipelineScore,
    TestAssignment, Comment, Task, not_deleted,
)


def _comment_counts(db: Session, entity_type: str, entity_ids: list[int]) -> dict[int, int]:
    """Batch query comment counts for a set of entity IDs."""
    if not entity_ids:
        return {}
    from sqlalchemy import func
    rows = db.exec(
        select(Comment.entity_id, func.count(Comment.id)).where(
            Comment.entity_type == entity_type,
            Comment.entity_id.in_(entity_ids),
        ).group_by(Comment.entity_id)
    ).all()
    return {eid: cnt for eid, cnt in rows}


class SyncHub:
    """In-process pub/sub hub for WebSocket connections. No Redis needed."""

    def __init__(self):
        self._connections: list[dict] = []

    async def connect(self, ws: WebSocket, tables: list[str]):
        await ws.accept()
        entry = {"ws": ws, "tables": set(tables)}
        self._connections.append(entry)
        return entry

    def disconnect(self, entry: dict):
        if entry in self._connections:
            self._connections.remove(entry)

    async def broadcast(self, table: str, event_type: str, record_id: str, data: dict | None = None):
        event = {
            "table": table,
            "id": record_id,
            "type": event_type,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        message = json.dumps(event, default=str)
        dead = []
        for entry in self._connections:
            if table in entry["tables"]:
                try:
                    await entry["ws"].send_text(message)
                except Exception:
                    dead.append(entry)
        for d in dead:
            self._connections.remove(d)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


hub = SyncHub()
router = APIRouter(prefix="/sync")


def _serialize_session(s: InterviewSession, interviewers, template, pipeline, db=None) -> dict:
    snapshot = json.loads(s.candidate_snapshot) if s.candidate_snapshot else {}
    position = ""
    business_unit = ""
    if pipeline:
        if pipeline.job_id and db:
            job = db.get(Job, pipeline.job_id)
            if job:
                position = job.position or ""
                bu = db.get(BusinessUnit, job.business_unit_id)
                business_unit = bu.name if bu else ""
        else:
            position = pipeline.position or ""
            business_unit = pipeline.business_unit or ""
    return {
        "id": str(s.id),
        "candidateName": snapshot.get("name", ""),
        "candidateId": s.candidate_id,
        "jobTitle": s.job_title,
        "status": s.status,
        "templateName": template.name if template else "",
        "templateId": s.template_id,
        "pipelineId": s.pipeline_id,
        "position": position,
        "businessUnit": business_unit,
        "interviewerCount": len(interviewers),
        "completedCount": len([i for i in interviewers if i.status == "completed"]),
        "interviewers": [{"name": i.interviewer_name, "token": i.token} for i in interviewers],
        "interviewDate": s.interview_date,
        "createdAt": int(s.created_at.timestamp() * 1000) if s.created_at else 0,
    }


def _hydrate_sessions(db: Session, since: int | None):
    query = select(InterviewSession).where(not_deleted(InterviewSession))
    if since:
        since_dt = datetime.utcfromtimestamp(since / 1000)
        query = query.where(InterviewSession.created_at > since_dt)
    query = query.order_by(InterviewSession.created_at.desc())

    sessions = db.exec(query).all()
    counts = _comment_counts(db, "session", [s.id for s in sessions])
    results = []
    for s in sessions:
        interviewers = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        template = db.get(Template, s.template_id) if s.template_id else None
        pipeline = db.get(CandidatePipeline, s.pipeline_id) if s.pipeline_id else None
        row = _serialize_session(s, interviewers, template, pipeline, db)
        row["commentCount"] = counts.get(s.id, 0)
        results.append(row)
    return results


def _hydrate_jobs(db: Session, since: int | None):
    from sqlalchemy import func

    query = select(Job).where(Job.title != "_Unassigned", not_deleted(Job))
    if since:
        since_dt = datetime.utcfromtimestamp(since / 1000)
        query = query.where(Job.updated_at > since_dt)
    query = query.order_by(Job.updated_at.desc())

    jobs = db.exec(query).all()

    # Batch: pipeline counts + filled counts per job
    job_ids = [j.id for j in jobs]
    pipeline_counts: dict = {}
    filled_counts: dict = {}
    if job_ids:
        rows = db.exec(
            select(
                CandidatePipeline.job_id,
                func.count(CandidatePipeline.id).label("total"),
                func.sum(func.iif(CandidatePipeline.stage == "hired", 1, 0)).label("filled"),
            )
            .where(CandidatePipeline.job_id.in_(job_ids), not_deleted(CandidatePipeline))
            .group_by(CandidatePipeline.job_id)
        ).all()
        for row in rows:
            pipeline_counts[row[0]] = row[1]
            filled_counts[row[0]] = int(row[2] or 0)

    counts = _comment_counts(db, "job", job_ids)

    # Batch: task counts per job
    task_total_map: dict = {}
    task_done_map: dict = {}
    if job_ids:
        task_rows = db.exec(
            select(
                Task.entity_id,
                func.count(Task.id).label("total"),
                func.sum(func.iif(Task.status == "done", 1, 0)).label("done"),
            )
            .where(Task.entity_type == "job", Task.entity_id.in_(job_ids), not_deleted(Task))
            .group_by(Task.entity_id)
        ).all()
        for row in task_rows:
            task_total_map[row[0]] = row[1]
            task_done_map[row[0]] = int(row[2] or 0)

    results = []
    for job in jobs:
        bu = db.get(BusinessUnit, job.business_unit_id)
        results.append({
            "id": str(job.id),
            "title": job.title,
            "status": job.status,
            "priority": job.priority,
            "jobType": job.job_type,
            "buName": bu.name if bu else "",
            "recruiter": job.recruiter or "",
            "headcount": job.headcount,
            "filled": filled_counts.get(job.id, 0),
            "pipelineCount": pipeline_counts.get(job.id, 0),
            "commentCount": counts.get(job.id, 0),
            "tasksDone": task_done_map.get(job.id, 0),
            "tasksTotal": task_total_map.get(job.id, 0),
            "updatedAt": int(job.updated_at.timestamp() * 1000) if job.updated_at else 0,
        })
    return results


def _hydrate_candidates(db: Session, since: int | None, filters: dict | None = None):
    from sqlalchemy import func

    query = select(Candidate).where(Candidate.nocodb_deleted == False)
    if since:
        since_dt = datetime.utcfromtimestamp(since / 1000)
        query = query.where(Candidate.updated_at > since_dt)

    if filters:
        if filters.get("q"):
            q = filters["q"]
            query = query.where(Candidate.name.ilike(f"%{q}%") | Candidate.email.ilike(f"%{q}%"))
        if filters.get("lang"):
            query = query.where(Candidate.languages.ilike(f"%{filters['lang']}%"))
        if filters.get("cloud"):
            query = query.where(Candidate.cloud.ilike(f"%{filters['cloud']}%"))
        if filters.get("tools"):
            query = query.where(Candidate.tools.ilike(f"%{filters['tools']}%"))
        if filters.get("position"):
            query = query.where(Candidate.current_position.ilike(f"%{filters['position']}%"))
        if filters.get("arrangement"):
            query = query.where(Candidate.working_arrangement.ilike(f"%{filters['arrangement']}%"))
        if filters.get("notice"):
            query = query.where(Candidate.notice_period.ilike(f"%{filters['notice']}%"))

    query = query.order_by(Candidate.updated_at.desc())

    candidates = db.exec(query).all()
    if not candidates:
        return []

    candidate_ids = [c.id for c in candidates]

    # Batch: pipeline counts + stages
    pipeline_rows = db.exec(
        select(
            CandidatePipeline.candidate_id,
            func.count(CandidatePipeline.id).label("count"),
            func.group_concat(CandidatePipeline.stage).label("stages_csv"),
        )
        .where(CandidatePipeline.candidate_id.in_(candidate_ids))
        .where(not_deleted(CandidatePipeline))
        .group_by(CandidatePipeline.candidate_id)
    ).all()
    pipeline_map = {r[0]: {"count": r[1], "stages": r[2] or ""} for r in pipeline_rows}

    # Batch: session counts
    session_rows = db.exec(
        select(
            InterviewSession.candidate_id,
            func.count(InterviewSession.id).label("count"),
        )
        .where(InterviewSession.candidate_id.in_(candidate_ids))
        .where(not_deleted(InterviewSession))
        .group_by(InterviewSession.candidate_id)
    ).all()
    session_map = {r[0]: r[1] for r in session_rows}

    # Batch: signal data
    signal_rows = db.exec(
        select(CandidateSignal).where(CandidateSignal.candidate_id.in_(candidate_ids))
    ).all()
    signal_map = {s.candidate_id: s for s in signal_rows}

    counts = _comment_counts(db, "candidate", candidate_ids)
    results = []
    for c in candidates:
        p_info = pipeline_map.get(c.id, {"count": 0, "stages": ""})
        stages = list(set(s for s in p_info["stages"].split(",") if s))
        sig = signal_map.get(c.id)
        row = {
            "id": str(c.id),
            "name": c.name,
            "email": c.email or "",
            "currentPosition": c.current_position or "",
            "stages": ",".join(stages),
            "pipelineCount": p_info["count"],
            "sessionCount": session_map.get(c.id, 0),
            "commentCount": counts.get(c.id, 0),
            "updatedAt": int(c.updated_at.timestamp() * 1000) if c.updated_at else 0,
        }
        if sig:
            skills = sig.skills_explicit
            if sig.skills_contextual:
                skills = skills + "," + sig.skills_contextual if skills else sig.skills_contextual
            row.update({
                "salaryLabel": sig.salary_label,
                "percentile": sig.percentile,
                "comparisonSource": sig.comparison_source,
                "flagCount": sig.flag_count,
                "roleBucket": sig.role_bucket,
                "skills": skills,
                "domains": sig.domains,
                "companyCategory": sig.company_category,
                "totalYears": sig.total_years,
                "trajectory": sig.trajectory,
                "employmentStatus": sig.employment_status,
            })
        results.append(row)
    return results


def _hydrate_review_batches(db: Session, since: int | None):
    from sqlalchemy import func

    query = select(ReviewBatch)
    if since:
        since_dt = datetime.utcfromtimestamp(since / 1000)
        query = query.where(ReviewBatch.created_at > since_dt)
    query = query.order_by(ReviewBatch.created_at.desc())

    batches = db.exec(query).all()
    if not batches:
        return []

    batch_ids = [b.id for b in batches]
    scored_rows = db.exec(
        select(
            ReviewScore.review_batch_id,
            func.count(ReviewScore.id).label("scored"),
        )
        .where(ReviewScore.review_batch_id.in_(batch_ids), ReviewScore.submitted_at != None)
        .group_by(ReviewScore.review_batch_id)
    ).all()
    scored_map = {r[0]: r[1] for r in scored_rows}

    results = []
    for b in batches:
        results.append({
            "id": str(b.id),
            "reviewerName": b.reviewer_name,
            "position": b.position or "",
            "businessUnit": b.business_unit or "",
            "token": b.token,
            "scored": scored_map.get(b.id, 0),
            "createdAt": int(b.created_at.timestamp() * 1000) if b.created_at else 0,
        })
    return results


def _hydrate_pipelines(db: Session, since: int | None):
    from sqlalchemy import func
    from app.models import PIPELINE_STAGES

    query = select(CandidatePipeline, Candidate).join(
        Candidate, CandidatePipeline.candidate_id == Candidate.id
    ).where(not_deleted(CandidatePipeline))
    if since:
        since_dt = datetime.utcfromtimestamp(since / 1000)
        query = query.where(CandidatePipeline.updated_at > since_dt)
    query = query.order_by(CandidatePipeline.updated_at.desc())

    rows = db.exec(query).all()
    if not rows:
        return []

    pipeline_ids = [p.id for p, _ in rows]

    # Batch: session counts
    session_rows = db.exec(
        select(
            InterviewSession.pipeline_id,
            func.count(SessionInterviewer.id).label("total"),
            func.sum(func.iif(SessionInterviewer.status == "completed", 1, 0)).label("completed"),
        )
        .join(SessionInterviewer, SessionInterviewer.session_id == InterviewSession.id)
        .where(InterviewSession.pipeline_id.in_(pipeline_ids), not_deleted(InterviewSession))
        .group_by(InterviewSession.pipeline_id)
    ).all()
    session_map = {r[0]: {"total": r[1], "completed": int(r[2] or 0)} for r in session_rows}

    # Batch: test counts
    test_rows = db.exec(
        select(
            TestAssignment.pipeline_id,
            func.count(TestAssignment.id).label("total"),
            func.sum(func.iif(TestAssignment.status == "submitted", 1, 0)).label("submitted"),
        )
        .where(TestAssignment.pipeline_id.in_(pipeline_ids), not_deleted(TestAssignment))
        .group_by(TestAssignment.pipeline_id)
    ).all()
    test_map = {r[0]: {"total": r[1], "submitted": int(r[2] or 0)} for r in test_rows}

    # Batch: scores
    scores = db.exec(select(PipelineScore).where(PipelineScore.pipeline_id.in_(pipeline_ids))).all()
    scores_map = {s.pipeline_id: s for s in scores}

    # Batch: job titles
    job_ids = set(p.job_id for p, _ in rows if p.job_id)
    jobs_map = {}
    if job_ids:
        jobs_list = db.exec(select(Job).where(Job.id.in_(job_ids))).all()
        jobs_map = {j.id: j.title for j in jobs_list}

    comment_counts = _comment_counts(db, "pipeline", pipeline_ids)

    # Batch: task counts per pipeline
    task_total_map: dict = {}
    task_done_map: dict = {}
    if pipeline_ids:
        task_rows = db.exec(
            select(
                Task.entity_id,
                func.count(Task.id).label("total"),
                func.sum(func.iif(Task.status == "done", 1, 0)).label("done"),
            )
            .where(Task.entity_type == "pipeline", Task.entity_id.in_(pipeline_ids), not_deleted(Task))
            .group_by(Task.entity_id)
        ).all()
        for row in task_rows:
            task_total_map[row[0]] = row[1]
            task_done_map[row[0]] = int(row[2] or 0)

    results = []
    for pipeline, candidate in rows:
        sc = scores_map.get(pipeline.id)
        hr_avg = round(sc.hr_total / 3, 1) if sc and sc.hr_total else 0
        culture_avg = round(sc.culture_total / 4, 1) if sc and sc.culture_total else 0
        s_counts = session_map.get(pipeline.id, {"total": 0, "completed": 0})
        tc = test_map.get(pipeline.id, {"total": 0, "submitted": 0})
        job_title = jobs_map.get(pipeline.job_id, "") if pipeline.job_id else ""

        results.append({
            "id": str(pipeline.id),
            "candidateName": candidate.name,
            "candidateId": pipeline.candidate_id,
            "jobTitle": job_title,
            "stage": pipeline.stage,
            "businessUnit": pipeline.business_unit or "",
            "displayName": pipeline.display_name or "",
            "sessionTotal": s_counts["total"],
            "sessionCompleted": s_counts["completed"],
            "testTotal": tc["total"],
            "testSubmitted": tc["submitted"],
            "hrAvg": hr_avg,
            "cultureAvg": culture_avg,
            "commentCount": comment_counts.get(pipeline.id, 0),
            "tasksDone": task_done_map.get(pipeline.id, 0),
            "tasksTotal": task_total_map.get(pipeline.id, 0),
            "updatedAt": int(pipeline.updated_at.timestamp() * 1000) if pipeline.updated_at else 0,
        })
    return results


def _hydrate_tests(db: Session, since: int | None):
    from sqlalchemy import func

    query = select(TestAssignment, CandidatePipeline, Candidate).join(
        CandidatePipeline, TestAssignment.pipeline_id == CandidatePipeline.id
    ).join(
        Candidate, CandidatePipeline.candidate_id == Candidate.id
    ).where(not_deleted(TestAssignment))
    if since:
        since_dt = datetime.utcfromtimestamp(since / 1000)
        query = query.where(TestAssignment.created_at > since_dt)
    query = query.order_by(TestAssignment.created_at.desc())

    rows = db.exec(query).all()
    if not rows:
        return []

    test_ids = [t.id for t, _, _ in rows]
    counts = _comment_counts(db, "pipeline", [t.pipeline_id for t, _, _ in rows])

    results = []
    for test, pipeline, candidate in rows:
        results.append({
            "id": str(test.id),
            "title": test.title,
            "status": test.status,
            "token": test.token,
            "candidateName": candidate.name,
            "candidateId": candidate.id,
            "pipelineId": pipeline.id,
            "position": pipeline.position or "",
            "businessUnit": pipeline.business_unit or "",
            "deadline": test.deadline.isoformat() if test.deadline else "",
            "submittedAt": test.submitted_at.isoformat() if test.submitted_at else "",
            "commentCount": counts.get(pipeline.id, 0),
            "createdAt": int(test.created_at.timestamp() * 1000) if test.created_at else 0,
        })
    return results


def _hydrate_tasks(db: Session, since: int | None):
    from datetime import date as date_type

    query = select(Task).where(not_deleted(Task))
    if since:
        since_dt = datetime.utcfromtimestamp(since / 1000)
        query = query.where(Task.updated_at > since_dt)
    query = query.order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())

    tasks = db.exec(query).all()
    if not tasks:
        return []

    today = date_type.today().isoformat()
    results = []
    for t in tasks:
        entity_display = ""
        bu_name = ""
        if t.entity_type == "job":
            job = db.get(Job, t.entity_id)
            if job:
                bu = db.get(BusinessUnit, job.business_unit_id)
                bu_name = bu.name if bu else ""
                entity_display = f"{job.position} — {job.level}" + (f" — {bu_name}" if bu_name else "")
        elif t.entity_type == "pipeline":
            pipeline = db.get(CandidatePipeline, t.entity_id)
            if pipeline:
                candidate = db.get(Candidate, pipeline.candidate_id)
                job = db.get(Job, pipeline.job_id) if pipeline.job_id else None
                parts = []
                if candidate:
                    parts.append(candidate.name)
                if job:
                    parts.append(job.position)
                    bu = db.get(BusinessUnit, job.business_unit_id)
                    bu_name = bu.name if bu else ""
                entity_display = " — ".join(parts)

        is_overdue = bool(t.due_date and t.due_date < today and t.status in ("pending", "in_progress"))
        results.append({
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "dueDate": t.due_date or "",
            "assignedTo": t.assigned_to or "",
            "entityType": t.entity_type,
            "entityId": t.entity_id,
            "entityDisplay": entity_display,
            "buName": bu_name,
            "isOverdue": is_overdue,
            "updatedAt": int(t.updated_at.timestamp() * 1000) if t.updated_at else 0,
        })
    return results


_HYDRATE_DISPATCH = {
    "sessions": _hydrate_sessions,
    "jobs": _hydrate_jobs,
    "candidates": _hydrate_candidates,
    "review_batches": _hydrate_review_batches,
    "pipelines": _hydrate_pipelines,
    "tests": _hydrate_tests,
    "tasks": _hydrate_tasks,
}


@router.get("/hydrate")
async def hydrate(
    request: Request,
    table: str = Query("sessions"),
    since: int | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    handler = _HYDRATE_DISPATCH.get(table)
    if not handler:
        return []
    if table == "candidates":
        return handler(db, since, filters=dict(request.query_params))
    return handler(db, since)


@router.websocket("/ws")
async def websocket_sync(ws: WebSocket, tables: str = Query("sessions")):
    cookie = ws.cookies.get("session")
    if not cookie:
        await ws.close(code=4401)
        return
    from app.auth import get_username_from_cookie
    if not get_username_from_cookie(cookie):
        await ws.close(code=4401)
        return

    table_list = [t.strip() for t in tables.split(",") if t.strip()]
    if not table_list:
        table_list = ["sessions"]

    entry = await hub.connect(ws, table_list)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(entry)
