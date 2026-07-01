from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from app.database import engine
from app.models import Candidate, Setting
from app.nocodb import FIELD_MAPPING, NOCODB_TABLE_ID, upsert_candidate_from_nocodb

router = APIRouter(prefix="/api/webhooks")


def _get_webhook_secret() -> str | None:
    with Session(engine) as db:
        setting = db.exec(select(Setting).where(Setting.key == "nocodb_webhook_secret")).first()
        return setting.value if setting else None


@router.post("/nocodb")
async def nocodb_webhook(request: Request):
    secret = _get_webhook_secret()
    if not secret:
        return JSONResponse({"error": "webhook secret not configured"}, status_code=403)
    header_secret = request.headers.get("X-Webhook-Secret", "")
    if header_secret != secret:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    body = await request.json()
    event_type = body.get("type", "")
    data = body.get("data", {})

    table_id = data.get("table_id", "")
    if NOCODB_TABLE_ID and table_id != NOCODB_TABLE_ID:
        return JSONResponse({"status": "ignored", "reason": "table_id mismatch"})

    rows = data.get("rows", [])
    if not rows:
        return JSONResponse({"status": "ok", "processed": 0})

    processed = 0

    if event_type in ("records.after.insert", "records.after.update"):
        for row in rows:
            nocodb_id = row.get("Id")
            if not nocodb_id:
                continue
            snapshot = {}
            for noco_field, key in FIELD_MAPPING.items():
                snapshot[key] = row.get(noco_field, "")
            email = (snapshot.get("email") or "").strip()
            if not email:
                continue
            upsert_candidate_from_nocodb(snapshot, nocodb_id)
            processed += 1

    elif event_type == "records.after.delete":
        with Session(engine) as db:
            for row in rows:
                nocodb_id = row.get("Id")
                if not nocodb_id:
                    continue
                candidate = db.exec(
                    select(Candidate).where(Candidate.nocodb_id == nocodb_id)
                ).first()
                if candidate:
                    candidate.nocodb_deleted = True
                    candidate.updated_at = datetime.utcnow()
                    db.add(candidate)
                    processed += 1
            db.commit()

    return JSONResponse({"status": "ok", "processed": processed})
