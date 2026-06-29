import json
import secrets
from datetime import datetime, timedelta

from fastmcp import FastMCP
from sqlmodel import Session, select, create_engine

from app.database import DATABASE_URL
from app.models import InterviewSession, SessionInterviewer, Response
from app.nocodb import fetch_candidate

mcp = FastMCP("Interview Form Summarizer")

engine = create_engine(DATABASE_URL, echo=False)


def _get_db():
    return Session(engine)


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
        query = select(InterviewSession).order_by(InterviewSession.created_at.desc())
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
                "candidate_name": s.snapshot.get("name", ""),
                "job_title": s.job_title,
                "status": s.status,
                "progress": f"{completed}/{total}",
                "created_at": s.created_at.isoformat(),
            })
        return results


@mcp.tool()
async def generate_recruitment_report(bu_name: str | None = None, level: str | None = None, period_days: int | None = None) -> str:
    """Generate an LLM-powered recruitment general report as standalone HTML. Optionally filter by business unit name, level, or period (days back)."""
    from app.models import BusinessUnit, not_deleted
    from app.reports import collect_general_data
    from app.llm import generate_report
    from app.routes.reports import _render_report, _save_report

    with _get_db() as db:
        bu_ids = None
        if bu_name:
            bu = db.exec(select(BusinessUnit).where(BusinessUnit.name == bu_name)).first()
            if bu:
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
