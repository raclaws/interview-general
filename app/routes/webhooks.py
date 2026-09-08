from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from app.database import engine
from app.models import Candidate, Setting


router = APIRouter(prefix="/api/webhooks")


# --- Neon webhook ---


def _get_neon_webhook_secret() -> str | None:
    with Session(engine) as db:
        setting = db.exec(select(Setting).where(Setting.key == "neon_webhook_secret")).first()
        return setting.value if setting else None


@router.post("/candidates")
async def neon_webhook(request: Request):
    """Receive candidate events from CF Worker (Neon pipeline).
    
    Auth: Authorization: Bearer {secret}
    Payload: { event, data: { external_id, name, email, ... } }
    Events: candidate.created, candidate.updated, candidate.deleted
    """
    secret = _get_neon_webhook_secret()
    if not secret:
        return JSONResponse({"status": "error", "message": "webhook secret not configured"}, status_code=403)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer ") or auth_header[7:] != secret:
        return JSONResponse({"status": "error", "message": "unauthorized"}, status_code=401)

    body = await request.json()
    event_type = body.get("event", "")
    data = body.get("data", {})

    if not data:
        return JSONResponse({"status": "error", "message": "missing data field"}, status_code=400)

    external_id = data.get("external_id")
    email = (data.get("email") or "").strip()

    if event_type in ("candidate.created", "candidate.updated"):
        if not external_id:
            return JSONResponse({"status": "error", "message": "missing required field: external_id"}, status_code=422)
        if not email:
            return JSONResponse({"status": "error", "message": "missing required field: email"}, status_code=422)

        from app.neon import upsert_candidate_from_neon
        snapshot = {
            "external_id": external_id,
            "name": data.get("name", ""),
            "email": email,
            "phone": data.get("phone", ""),
            "current_position": data.get("current_position", ""),
            "yoe": data.get("yoe", ""),
            "languages": data.get("languages", ""),
            "cloud": data.get("cloud", ""),
            "tools": data.get("tools", ""),
            "working_arrangement": data.get("working_arrangement", ""),
            "current_salary": data.get("current_salary", ""),
            "expected_salary": data.get("expected_salary", ""),
            "notice_period": data.get("notice_period", ""),
            "cv_link": data.get("cv_link", ""),
        }
        # Check if candidate already exists to determine action
        with Session(engine) as db:
            existing = db.exec(select(Candidate).where(Candidate.email == email)).first()
        action = "updated" if existing else "created"
        candidate = upsert_candidate_from_neon(snapshot, external_id)
        return JSONResponse({
            "status": "ok",
            "action": action,
            "candidate_id": candidate.id,
        })

    elif event_type == "candidate.deleted":
        if not external_id:
            return JSONResponse({"status": "error", "message": "missing required field: external_id"}, status_code=422)

        with Session(engine) as db:
            candidate = db.exec(
                select(Candidate).where(Candidate.external_id == external_id)
            ).first()
            if candidate:
                candidate.nocodb_deleted = True
                candidate.updated_at = datetime.utcnow()
                db.add(candidate)
                db.commit()
                return JSONResponse({
                    "status": "ok",
                    "action": "deleted",
                    "candidate_id": candidate.id,
                })

        return JSONResponse({"status": "ok", "action": "deleted", "candidate_id": None})

    else:
        return JSONResponse({"status": "error", "message": f"unknown event type: {event_type}"}, status_code=400)
