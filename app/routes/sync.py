"""
Sync endpoints for real-time client sync engine.
Provides REST hydrate + WebSocket change stream.
"""

import asyncio
import json
import time
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import (
    InterviewSession, SessionInterviewer, Template, CandidatePipeline, AdminUser
)


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


def _serialize_session(s: InterviewSession, interviewers, template, pipeline) -> dict:
    snapshot = json.loads(s.candidate_snapshot) if s.candidate_snapshot else {}
    return {
        "id": str(s.id),
        "candidateName": snapshot.get("name", ""),
        "candidateId": s.candidate_id,
        "jobTitle": s.job_title,
        "status": s.status,
        "templateName": template.name if template else "",
        "templateId": s.template_id,
        "pipelineId": s.pipeline_id,
        "position": pipeline.position if pipeline else "",
        "businessUnit": pipeline.business_unit if pipeline else "",
        "interviewerCount": len(interviewers),
        "completedCount": len([i for i in interviewers if i.status == "completed"]),
        "interviewers": [{"name": i.interviewer_name, "token": i.token} for i in interviewers],
        "interviewDate": s.interview_date,
        "createdAt": int(s.created_at.timestamp() * 1000) if s.created_at else 0,
    }


@router.get("/hydrate")
async def hydrate(
    table: str = Query("sessions"),
    since: int | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    if table != "sessions":
        return []

    query = select(InterviewSession)
    if since:
        since_dt = datetime.utcfromtimestamp(since / 1000)
        query = query.where(InterviewSession.created_at > since_dt)
    query = query.order_by(InterviewSession.created_at.desc())

    sessions = db.exec(query).all()
    results = []
    for s in sessions:
        interviewers = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        template = db.get(Template, s.template_id) if s.template_id else None
        pipeline = db.get(CandidatePipeline, s.pipeline_id) if s.pipeline_id else None
        results.append(_serialize_session(s, interviewers, template, pipeline))

    return results


@router.websocket("/ws")
async def websocket_sync(ws: WebSocket, tables: str = Query("sessions")):
    table_list = [t.strip() for t in tables.split(",") if t.strip()]
    if not table_list:
        table_list = ["sessions"]

    entry = await hub.connect(ws, table_list)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(entry)
