import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from sqlmodel import Session, select

from app.database import engine
from app.models import Candidate

load_dotenv()

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")

_pool = None
_pool_lock = asyncio.Lock()

NEON_TIMEOUT = 10.0

# Neon table uses snake_case column names matching the Candidate model.
# Query selects all candidate fields.
CANDIDATE_COLUMNS = [
    "id", "name", "email", "phone", "current_position", "yoe",
    "languages", "cloud", "tools", "working_arrangement",
    "current_salary", "expected_salary", "notice_period", "cv_link",
]

CANDIDATE_SELECT = ", ".join(CANDIDATE_COLUMNS)


async def _get_pool():
    """Lazily create and return the asyncpg connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        if not NEON_DATABASE_URL:
            return None
        import asyncpg
        _pool = await asyncpg.create_pool(
            dsn=NEON_DATABASE_URL,
            min_size=1,
            max_size=3,
            command_timeout=NEON_TIMEOUT,
        )
        return _pool


async def close_pool():
    """Close the asyncpg connection pool. Call on app shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _row_to_dict(row: dict) -> dict:
    """Convert a database row dict to the snapshot format expected by upsert logic."""
    return {
        "external_id": row.get("id"),
        "name": row.get("name") or "",
        "email": row.get("email") or "",
        "phone": row.get("phone") or "",
        "current_position": row.get("current_position") or "",
        "yoe": row.get("yoe") or "",
        "languages": row.get("languages") or "",
        "cloud": row.get("cloud") or "",
        "tools": row.get("tools") or "",
        "working_arrangement": row.get("working_arrangement") or "",
        "current_salary": row.get("current_salary") or "",
        "expected_salary": row.get("expected_salary") or "",
        "notice_period": row.get("notice_period") or "",
        "cv_link": row.get("cv_link") or "",
    }


async def search_candidates(query: str) -> list[dict]:
    """Search candidates in Neon by name or email."""
    pool = await _get_pool()
    if not pool:
        return [{"_error": "Neon not configured — set NEON_DATABASE_URL"}]

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {CANDIDATE_SELECT} FROM candidates "
                "WHERE name ILIKE $1 OR email ILIKE $1 "
                "ORDER BY name LIMIT 20",
                f"%{query}%",
            )
            return [
                {
                    "id": r["id"],
                    "name": r["name"] or "",
                    "position": r["current_position"] or "",
                    "email": r["email"] or "",
                }
                for r in rows
            ]
    except Exception as e:
        return [{"_error": f"Neon error: {str(e)[:100]}"}]


async def fetch_candidate(external_id: int) -> dict | None:
    """Fetch a single candidate from Neon by ID."""
    pool = await _get_pool()
    if not pool:
        return {"_error": "Neon not configured — set NEON_DATABASE_URL"}

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {CANDIDATE_SELECT} FROM candidates WHERE id = $1",
                external_id,
            )
            if not row:
                return {"_error": f"Candidate {external_id} not found in Neon"}
            return _row_to_dict(dict(row))
    except Exception as e:
        return {"_error": f"Neon error: {str(e)[:100]}"}


def upsert_candidate_from_neon(snapshot: dict, external_id: int) -> Candidate:
    """Create or update a local Candidate record from Neon data."""
    email = (snapshot.get("email") or "").strip()
    if not email:
        email = f"neon_{external_id}@placeholder.local"

    with Session(engine) as db:
        candidate = db.exec(select(Candidate).where(Candidate.email == email)).first()
        if candidate:
            candidate.name = snapshot.get("name") or candidate.name
            candidate.phone = snapshot.get("phone") or candidate.phone
            candidate.external_id = external_id
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
                external_id=external_id,
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


async def bulk_import_candidates() -> dict:
    """Import all candidates from Neon into the local SQLite database."""
    pool = await _get_pool()
    if not pool:
        return {"error": "Neon not configured — set NEON_DATABASE_URL"}

    created = 0
    updated = 0
    skipped = 0

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {CANDIDATE_SELECT} FROM candidates ORDER BY id"
            )

        # Pre-load existing emails for fast lookup
        with Session(engine) as db:
            existing_emails = set(
                r[0] for r in db.exec(select(Candidate.email)).all() if r[0]
            )

        for row in rows:
            external_id = row["id"]
            snapshot = _row_to_dict(dict(row))

            email = (snapshot.get("email") or "").strip()
            if not email:
                skipped += 1
                continue

            if email in existing_emails:
                updated += 1
            else:
                created += 1
                existing_emails.add(email)

            upsert_candidate_from_neon(snapshot, external_id)

    except Exception as e:
        return {"error": f"Import error: {str(e)[:200]}", "created": created, "updated": updated, "skipped": skipped}

    return {"created": created, "updated": updated, "skipped": skipped, "total": created + updated}
