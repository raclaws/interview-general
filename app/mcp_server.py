import json
import secrets
from datetime import datetime

from fastmcp import FastMCP
from sqlmodel import Session, select, create_engine

from app.database import DATABASE_URL
from app.models import InterviewSession, Response
from app.nocodb import fetch_candidate

mcp = FastMCP("Interview Form Summarizer")

engine = create_engine(DATABASE_URL, echo=False)


def _get_db():
    return Session(engine)


@mcp.tool()
async def create_session(candidate_id: int, job_title: str, round: str, interviewer_name: str) -> dict:
    """Create a new interview session and return the shareable URL."""
    snapshot = await fetch_candidate(candidate_id)
    if not snapshot:
        return {"error": "Candidate not found"}

    token = secrets.token_urlsafe(16)
    session = InterviewSession(
        token=token,
        candidate_id=candidate_id,
        candidate_snapshot=json.dumps(snapshot),
        job_title=job_title,
        round=round,
        interviewer_name=interviewer_name,
        status="pending",
        created_at=datetime.utcnow(),
    )
    with _get_db() as db:
        db.add(session)
        db.commit()
        db.refresh(session)
        return {
            "session_id": session.id,
            "token": token,
            "url": f"/i/{token}",
            "candidate": snapshot.get("name", ""),
        }


@mcp.tool()
async def get_session(session_id: int) -> dict:
    """Get session details including status, scores, and summary."""
    with _get_db() as db:
        session = db.get(InterviewSession, session_id)
        if not session:
            return {"error": "Session not found"}

        result = {
            "id": session.id,
            "token": session.token,
            "candidate": session.snapshot,
            "job_title": session.job_title,
            "round": session.round,
            "interviewer_name": session.interviewer_name,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
        }

        if session.status == "completed":
            response = db.exec(
                select(Response).where(Response.session_id == session.id)
            ).first()
            if response:
                result["scores"] = {
                    "q1": response.q1,
                    "q2": response.q2,
                    "q3": response.q3,
                    "q4": response.q4,
                    "q5": response.q5,
                }
                result["summary"] = response.summary
                result["free_text"] = response.free_text
                result["submitted_at"] = response.submitted_at.isoformat()

        return result


@mcp.tool()
async def list_sessions(candidate_id: int | None = None) -> list[dict]:
    """List all interview sessions, optionally filtered by candidate ID."""
    with _get_db() as db:
        query = select(InterviewSession).order_by(InterviewSession.created_at.desc())
        if candidate_id is not None:
            query = query.where(InterviewSession.candidate_id == candidate_id)
        sessions = db.exec(query).all()
        return [
            {
                "id": s.id,
                "candidate_name": s.snapshot.get("name", ""),
                "job_title": s.job_title,
                "round": s.round,
                "interviewer_name": s.interviewer_name,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
            }
            for s in sessions
        ]


if __name__ == "__main__":
    from app.database import create_tables
    create_tables()
    mcp.run(transport="sse")
