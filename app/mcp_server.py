import json
import secrets
from datetime import datetime, timedelta

from fastmcp import FastMCP
from sqlmodel import Session, select, create_engine

from app.database import DATABASE_URL
from app.models import (
    InterviewSession, SessionInterviewer, Response, BusinessUnit, Job,
    Candidate, CandidatePipeline, Task, not_deleted,
)
from app.nocodb import fetch_candidate

mcp = FastMCP("INS ATS")

engine = create_engine(DATABASE_URL, echo=False)


def _get_db():
    return Session(engine)


# --- Sessions ---

@mcp.tool()
async def create_session(candidate_id: int, job_title: str, interviewer_names: list[str]) -> dict:
    """Create a new interview session with multiple interviewers and return shareable URLs."""
    snapshot = await fetch_candidate(candidate_id)
    if not snapshot:
        return {"error": "Candidate not found"}

    with _get_db() as db:
        session = InterviewSession(
            candidate_id=candidate_id,
            candidate_snapshot=json.dumps(snapshot),
            job_title=job_title,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        interviewers = []
        for name in interviewer_names:
            token = secrets.token_urlsafe(16)
            iv = SessionInterviewer(
                session_id=session.id,
                interviewer_name=name,
                token=token,
                status="pending",
            )
            db.add(iv)
            interviewers.append({"name": name, "token": token, "url": f"/i/{token}"})
        db.commit()

        return {
            "session_id": session.id,
            "candidate": snapshot.get("name", ""),
            "interviewers": interviewers,
        }


@mcp.tool()
async def get_session(session_id: int) -> dict:
    """Get session details including status, all interviewer scores, and aggregate summary."""
    with _get_db() as db:
        session = db.get(InterviewSession, session_id)
        if not session:
            return {"error": "Session not found"}

        interviewers = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == session.id)
        ).all()

        result = {
            "id": session.id,
            "candidate": session.snapshot,
            "job_title": session.job_title,
            "status": session.status,
            "aggregate_summary": session.aggregate_summary,
            "created_at": session.created_at.isoformat(),
            "interviewers": [],
        }

        for iv in interviewers:
            iv_data = {
                "name": iv.interviewer_name,
                "status": iv.status,
                "token": iv.token,
            }
            response = db.exec(
                select(Response).where(Response.session_interviewer_id == iv.id)
            ).first()
            if response:
                iv_data["scores"] = {
                    "q1": response.q1,
                    "q2": response.q2,
                    "q3": response.q3,
                    "q4": response.q4,
                    "q5": response.q5,
                }
                iv_data["free_text"] = response.free_text
                iv_data["submitted_at"] = response.submitted_at.isoformat()
            result["interviewers"].append(iv_data)

        return result


@mcp.tool()
async def list_sessions(candidate_id: int | None = None) -> list[dict]:
    """List all interview sessions, optionally filtered by candidate ID."""
    with _get_db() as db:
        query = select(InterviewSession).where(not_deleted(InterviewSession)).order_by(InterviewSession.created_at.desc())
        if candidate_id is not None:
            query = query.where(InterviewSession.candidate_id == candidate_id)
        sessions = db.exec(query).all()
        results = []
        for s in sessions:
            interviewers = db.exec(
                select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
            ).all()
            total = len(interviewers)
            completed = len([iv for iv in interviewers if iv.status == "completed"])
            results.append({
                "id": s.id,
                "candidate_name": s.snapshot.get("name", "") if isinstance(s.snapshot, dict) else "",
                "job_title": s.job_title,
                "status": s.status,
                "progress": f"{completed}/{total}",
                "created_at": s.created_at.isoformat(),
            })
        return results


# --- Jobs ---

@mcp.tool()
async def list_jobs(status: str | None = None, bu_name: str | None = None) -> list[dict]:
    """List all jobs, optionally filtered by status (open/closed) or business unit name."""
    with _get_db() as db:
        query = select(Job).where(not_deleted(Job), Job.title != "_Unassigned")
        if status:
            query = query.where(Job.status == status)
        if bu_name:
            bu = db.exec(select(BusinessUnit).where(BusinessUnit.name == bu_name)).first()
            if bu:
                query = query.where(Job.business_unit_id == bu.id)
        query = query.order_by(Job.updated_at.desc())
        jobs = db.exec(query).all()
        results = []
        for job in jobs:
            bu = db.get(BusinessUnit, job.business_unit_id)
            pipelines = db.exec(
                select(CandidatePipeline).where(
                    CandidatePipeline.job_id == job.id, not_deleted(CandidatePipeline)
                )
            ).all()
            filled = len([p for p in pipelines if p.stage == "hired"])
            results.append({
                "id": job.id,
                "title": job.title,
                "position": job.position,
                "level": job.level,
                "job_type": job.job_type,
                "status": job.status,
                "priority": job.priority,
                "business_unit": bu.name if bu else "",
                "recruiter": job.recruiter or "",
                "headcount": job.headcount,
                "filled": filled,
                "pipeline_count": len(pipelines),
                "target_date": job.target_date,
            })
        return results


@mcp.tool()
async def get_job(job_id: int) -> dict:
    """Get full job details by ID."""
    with _get_db() as db:
        job = db.get(Job, job_id)
        if not job or job.deleted_at:
            return {"error": "Job not found"}
        bu = db.get(BusinessUnit, job.business_unit_id)
        pipelines = db.exec(
            select(CandidatePipeline).where(
                CandidatePipeline.job_id == job.id, not_deleted(CandidatePipeline)
            )
        ).all()
        filled = len([p for p in pipelines if p.stage == "hired"])
        return {
            "id": job.id,
            "title": job.title,
            "position": job.position,
            "level": job.level,
            "job_type": job.job_type,
            "status": job.status,
            "priority": job.priority,
            "business_unit": bu.name if bu else "",
            "recruiter": job.recruiter or "",
            "backup_recruiter": job.backup_recruiter or "",
            "hiring_manager": job.hiring_manager or "",
            "headcount": job.headcount,
            "filled": filled,
            "salary_range_min": job.salary_range_min,
            "salary_range_max": job.salary_range_max,
            "target_date": job.target_date,
            "description": job.description or "",
            "notes": job.notes or "",
            "pipeline_count": len(pipelines),
            "pipelines": [{"id": p.id, "candidate_id": p.candidate_id, "stage": p.stage} for p in pipelines],
        }


# --- Pipelines ---

@mcp.tool()
async def list_pipelines(job_id: int | None = None, stage: str | None = None) -> list[dict]:
    """List candidate pipelines, optionally filtered by job ID or stage."""
    with _get_db() as db:
        query = select(CandidatePipeline).where(not_deleted(CandidatePipeline))
        if job_id:
            query = query.where(CandidatePipeline.job_id == job_id)
        if stage:
            query = query.where(CandidatePipeline.stage == stage)
        query = query.order_by(CandidatePipeline.updated_at.desc())
        pipelines = db.exec(query).all()
        results = []
        for p in pipelines:
            candidate = db.get(Candidate, p.candidate_id)
            job = db.get(Job, p.job_id) if p.job_id else None
            results.append({
                "id": p.id,
                "candidate_name": candidate.name if candidate else "",
                "candidate_id": p.candidate_id,
                "job_title": job.title if job else "",
                "job_id": p.job_id,
                "stage": p.stage,
                "display_name": p.display_name or "",
                "updated_at": p.updated_at.isoformat() if p.updated_at else "",
            })
        return results


@mcp.tool()
async def get_pipeline(pipeline_id: int) -> dict:
    """Get pipeline details by ID including candidate info and linked sessions."""
    with _get_db() as db:
        pipeline = db.get(CandidatePipeline, pipeline_id)
        if not pipeline or pipeline.deleted_at:
            return {"error": "Pipeline not found"}
        candidate = db.get(Candidate, pipeline.candidate_id)
        job = db.get(Job, pipeline.job_id) if pipeline.job_id else None
        sessions = db.exec(
            select(InterviewSession).where(
                InterviewSession.pipeline_id == pipeline_id, not_deleted(InterviewSession)
            )
        ).all()
        return {
            "id": pipeline.id,
            "candidate": {"id": candidate.id, "name": candidate.name, "email": candidate.email} if candidate else None,
            "job": {"id": job.id, "title": job.title, "position": job.position} if job else None,
            "stage": pipeline.stage,
            "display_name": pipeline.display_name or "",
            "notes": pipeline.notes or "",
            "sessions": [{"id": s.id, "status": s.status, "template_id": s.template_id} for s in sessions],
            "updated_at": pipeline.updated_at.isoformat() if pipeline.updated_at else "",
        }


# --- Candidates ---

@mcp.tool()
async def list_candidates(query: str | None = None, limit: int = 50) -> list[dict]:
    """List candidates, optionally filtered by name/email search. Returns max 50 results."""
    with _get_db() as db:
        q = select(Candidate).where(Candidate.nocodb_deleted == False)
        if query:
            q = q.where(Candidate.name.ilike(f"%{query}%") | Candidate.email.ilike(f"%{query}%"))
        q = q.order_by(Candidate.updated_at.desc()).limit(min(limit, 50))
        candidates = db.exec(q).all()
        return [{
            "id": c.id,
            "name": c.name,
            "email": c.email or "",
            "current_position": c.current_position or "",
            "phone": c.phone or "",
        } for c in candidates]


@mcp.tool()
async def get_candidate(candidate_id: int) -> dict:
    """Get full candidate details by ID including all pipeline stages."""
    with _get_db() as db:
        c = db.get(Candidate, candidate_id)
        if not c:
            return {"error": "Candidate not found"}
        pipelines = db.exec(
            select(CandidatePipeline).where(
                CandidatePipeline.candidate_id == c.id, not_deleted(CandidatePipeline)
            )
        ).all()
        return {
            "id": c.id,
            "name": c.name,
            "email": c.email or "",
            "phone": c.phone or "",
            "current_position": c.current_position or "",
            "yoe": c.yoe or "",
            "languages": c.languages or "",
            "tools": c.tools or "",
            "cv_link": c.cv_link or "",
            "pipelines": [{"id": p.id, "job_id": p.job_id, "stage": p.stage} for p in pipelines],
        }


# --- Tasks ---

@mcp.tool()
async def list_tasks(entity_type: str | None = None, entity_id: int | None = None, status: str | None = None) -> list[dict]:
    """List tasks, optionally filtered by entity (job/pipeline), entity_id, or status."""
    with _get_db() as db:
        query = select(Task).where(not_deleted(Task))
        if entity_type:
            query = query.where(Task.entity_type == entity_type)
        if entity_id:
            query = query.where(Task.entity_id == entity_id)
        if status:
            query = query.where(Task.status == status)
        query = query.order_by(Task.due_date.asc(), Task.created_at.desc())
        tasks = db.exec(query).all()
        return [{
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date,
            "assigned_to": t.assigned_to or "",
            "entity_type": t.entity_type,
            "entity_id": t.entity_id,
        } for t in tasks]


@mcp.tool()
async def create_task(title: str, entity_type: str, entity_id: int, priority: str = "none", due_date: str | None = None, assigned_to: str | None = None, description: str | None = None) -> dict:
    """Create a new task linked to a job or pipeline."""
    if entity_type not in ("job", "pipeline"):
        return {"error": "entity_type must be 'job' or 'pipeline'"}
    if priority not in ("none", "low", "medium", "high", "urgent"):
        priority = "none"

    with _get_db() as db:
        if entity_type == "job":
            entity = db.get(Job, entity_id)
            if not entity or entity.deleted_at:
                return {"error": "Job not found"}
        else:
            entity = db.get(CandidatePipeline, entity_id)
            if not entity or entity.deleted_at:
                return {"error": "Pipeline not found"}

        task = Task(
            title=title.strip(),
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            priority=priority,
            due_date=due_date,
            assigned_to=assigned_to,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return {"id": task.id, "title": task.title, "status": task.status}


@mcp.tool()
async def update_task(task_id: int, status: str | None = None, title: str | None = None, priority: str | None = None, due_date: str | None = None, assigned_to: str | None = None) -> dict:
    """Update a task's status, title, priority, due date, or assignee."""
    with _get_db() as db:
        task = db.get(Task, task_id)
        if not task or task.deleted_at:
            return {"error": "Task not found"}
        if status and status in ("pending", "in_progress", "done", "cancelled"):
            task.status = status
        if title:
            stripped = title.strip()
            if not stripped:
                return {"error": "Title cannot be empty"}
            task.title = stripped
        if priority and priority in ("none", "low", "medium", "high", "urgent"):
            task.priority = priority
        if due_date is not None:
            task.due_date = due_date or None
        if assigned_to is not None:
            task.assigned_to = assigned_to or None
        task.updated_at = datetime.utcnow()
        db.commit()
        return {"id": task.id, "title": task.title, "status": task.status, "updated": True}


# --- Reports ---

@mcp.tool()
async def generate_recruitment_report(bu_name: str | None = None, level: str | None = None, period_days: int | None = None) -> str:
    """Generate an LLM-powered recruitment general report as standalone HTML. Optionally filter by business unit name, level, or period (days back)."""
    from app.reports import collect_general_data
    from app.llm import generate_report
    from app.routes.reports import _render_report, _save_report

    with _get_db() as db:
        bu_ids = None
        if bu_name:
            bu = db.exec(select(BusinessUnit).where(BusinessUnit.name == bu_name)).first()
            if not bu:
                return f"Error: Business unit '{bu_name}' not found"
            bu_ids = [bu.id]

        since = None
        if period_days:
            since = datetime.utcnow() - timedelta(days=period_days)

        data = collect_general_data(db, bu_ids=bu_ids, level=level, since=since)
        llm = await generate_report("general", data)
        html = _render_report("general.html", data, llm)
        filename = _save_report("general", "all", html)
        return f"Report saved: static/reports/{filename}"


@mcp.tool()
async def generate_pipeline_report(pipeline_id: int) -> str:
    """Generate an LLM-powered candidate assessment report as standalone HTML for a specific pipeline."""
    from app.reports import collect_pipeline_data
    from app.llm import generate_report
    from app.routes.reports import _render_report, _save_report

    with _get_db() as db:
        data = collect_pipeline_data(db, pipeline_id)
        if data.get("error"):
            return f"Error: {data['error']}"
        llm = await generate_report("pipeline", data)
        html = _render_report("pipeline.html", data, llm)
        filename = _save_report("pipeline", str(pipeline_id), html)
        return f"Report saved: static/reports/{filename}"


@mcp.tool()
async def generate_job_report(job_id: int, period_days: int | None = None) -> str:
    """Generate an LLM-powered job role health report as standalone HTML."""
    from app.reports import collect_job_data
    from app.llm import generate_report
    from app.routes.reports import _render_report, _save_report

    since = None
    if period_days:
        since = datetime.utcnow() - timedelta(days=period_days)

    with _get_db() as db:
        data = collect_job_data(db, job_id, since=since)
        if data.get("error"):
            return f"Error: {data['error']}"
        llm = await generate_report("job", data)
        html = _render_report("job.html", data, llm)
        filename = _save_report("job", str(job_id), html)
        return f"Report saved: static/reports/{filename}"


if __name__ == "__main__":
    from app.database import create_tables
    create_tables()
    mcp.run(transport="sse")
