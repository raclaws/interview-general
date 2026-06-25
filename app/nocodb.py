import os
import httpx
from datetime import datetime
from dotenv import load_dotenv
from sqlmodel import Session, select

from app.database import engine
from app.models import Candidate

load_dotenv()

NOCODB_BASE_URL = os.getenv("NOCODB_BASE_URL", "")
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY", "")
NOCODB_TABLE_ID = os.getenv("NOCODB_TABLE_ID", "mqf1wqf4abbaqtx")
NOCODB_BASE_ID = os.getenv("NOCODB_BASE_ID", "pj16ynf0v7ds1mh")

FIELD_MAPPING = {
    "Full-Name": "name",
    "Phone Number": "phone",
    "Email": "email",
    "Current Formal Positions": "current_position",
    "Total Years of Experience": "yoe",
    "Programming Language (professionally used)": "languages",
    "Cloud Expertise": "cloud",
    "Other professional related tools used": "tools",
    "Working arrangement preferences": "working_arrangement",
    "(Full-time) Current Salary (Nett in IDR)": "current_salary",
    "(Full-time) Expected Salary (Nett in IDR)": "expected_salary",
    "(Full-time) Notice Period": "notice_period",
    "Upload CV": "cv_link",
}


def _headers() -> dict:
    return {"xc-token": NOCODB_API_KEY}


def _base_url() -> str:
    url = NOCODB_BASE_URL.rstrip("/")
    if not url.startswith("http"):
        url = f"https://{url}"
    return url


def _records_url() -> str:
    return f"{_base_url()}/api/v1/db/data/noco/{NOCODB_BASE_ID}/{NOCODB_TABLE_ID}"


NOCODB_TIMEOUT = 10.0


async def search_candidates(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=NOCODB_TIMEOUT) as client:
            resp = await client.get(
                _records_url(),
                headers=_headers(),
                params={
                    "where": f"(Full-Name,like,%{query}%)",
                    "fields": "Id,Full-Name,Current Formal Positions,Email",
                    "limit": 20,
                },
            )
            if resp.status_code != 200:
                return [{"_error": f"NocoDB returned {resp.status_code}"}]
            data = resp.json()
            records = data.get("list", [])
            return [
                {
                    "id": r.get("Id"),
                    "name": r.get("Full-Name", ""),
                    "position": r.get("Current Formal Positions", ""),
                    "email": r.get("Email", ""),
                }
                for r in records
            ]
    except httpx.TimeoutException:
        return [{"_error": "NocoDB request timed out"}]
    except httpx.ConnectError:
        return [{"_error": "Cannot connect to NocoDB"}]
    except Exception as e:
        return [{"_error": f"NocoDB error: {str(e)[:100]}"}]


async def fetch_candidate(row_id: int) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=NOCODB_TIMEOUT) as client:
            resp = await client.get(
                f"{_records_url()}/{row_id}",
                headers=_headers(),
            )
            if resp.status_code != 200:
                return {"_error": f"NocoDB returned {resp.status_code}"}
            record = resp.json()
            snapshot = {}
            for noco_field, key in FIELD_MAPPING.items():
                snapshot[key] = record.get(noco_field, "")
            snapshot["id"] = record.get("Id")
            return snapshot
    except httpx.TimeoutException:
        return {"_error": "NocoDB request timed out"}
    except httpx.ConnectError:
        return {"_error": "Cannot connect to NocoDB"}
    except Exception as e:
        return {"_error": f"NocoDB error: {str(e)[:100]}"}


def upsert_candidate_from_nocodb(snapshot: dict, nocodb_id: int) -> Candidate:
    """Create or update a local Candidate record from NocoDB data."""
    email = (snapshot.get("email") or "").strip()
    if not email:
        email = f"nocodb_{nocodb_id}@placeholder.local"

    with Session(engine) as db:
        candidate = db.exec(select(Candidate).where(Candidate.email == email)).first()
        if candidate:
            candidate.name = snapshot.get("name") or candidate.name
            candidate.phone = snapshot.get("phone") or candidate.phone
            candidate.nocodb_id = nocodb_id
            candidate.current_position = snapshot.get("current_position") or candidate.current_position
            candidate.yoe = snapshot.get("yoe") or candidate.yoe
            candidate.languages = snapshot.get("languages") or candidate.languages
            candidate.cloud = snapshot.get("cloud") or candidate.cloud
            candidate.tools = snapshot.get("tools") or candidate.tools
            candidate.working_arrangement = snapshot.get("working_arrangement") or candidate.working_arrangement
            candidate.current_salary = snapshot.get("current_salary") or candidate.current_salary
            candidate.expected_salary = snapshot.get("expected_salary") or candidate.expected_salary
            candidate.notice_period = snapshot.get("notice_period") or candidate.notice_period
            candidate.cv_link = snapshot.get("cv_link") or candidate.cv_link
            candidate.updated_at = datetime.utcnow()
        else:
            candidate = Candidate(
                name=snapshot.get("name", ""),
                email=email,
                phone=snapshot.get("phone", ""),
                nocodb_id=nocodb_id,
                current_position=snapshot.get("current_position", ""),
                yoe=snapshot.get("yoe", ""),
                languages=snapshot.get("languages", ""),
                cloud=snapshot.get("cloud", ""),
                tools=snapshot.get("tools", ""),
                working_arrangement=snapshot.get("working_arrangement", ""),
                current_salary=snapshot.get("current_salary", ""),
                expected_salary=snapshot.get("expected_salary", ""),
                notice_period=snapshot.get("notice_period", ""),
                cv_link=snapshot.get("cv_link", ""),
            )
            db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate


def upsert_candidate_manual(name: str, email: str, **kwargs) -> Candidate:
    """Create or update a local Candidate record from manual entry."""
    with Session(engine) as db:
        candidate = db.exec(select(Candidate).where(Candidate.email == email)).first()
        if candidate:
            candidate.name = name
            for key, val in kwargs.items():
                if val and hasattr(candidate, key):
                    setattr(candidate, key, val)
            candidate.updated_at = datetime.utcnow()
        else:
            candidate = Candidate(name=name, email=email, **kwargs)
            db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate


def search_local_candidates(query: str) -> list[dict]:
    """Search candidates already in the local DB."""
    with Session(engine) as db:
        candidates = db.exec(
            select(Candidate).where(
                Candidate.name.ilike(f"%{query}%") | Candidate.email.ilike(f"%{query}%")
            ).limit(20)
        ).all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "position": c.current_position or "",
                "source": "local",
            }
            for c in candidates
        ]
