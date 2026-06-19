import json
import secrets
from datetime import datetime

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


if __name__ == "__main__":
    from app.database import create_tables
    create_tables()
    mcp.run(transport="sse")
