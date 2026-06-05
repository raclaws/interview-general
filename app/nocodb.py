import os
import httpx
from dotenv import load_dotenv

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


async def search_candidates(query: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _records_url(),
            headers=_headers(),
            params={
                "where": f"(Full-Name,like,%{query}%)",
                "fields": "Id,Full-Name,Current Formal Positions",
                "limit": 20,
            },
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        records = data.get("list", [])
        return [
            {
                "id": r.get("Id"),
                "name": r.get("Full-Name", ""),
                "position": r.get("Current Formal Positions", ""),
            }
            for r in records
        ]


async def fetch_candidate(row_id: int) -> dict | None:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_records_url()}/{row_id}",
            headers=_headers(),
        )
        if resp.status_code != 200:
            return None
        record = resp.json()
        snapshot = {}
        for noco_field, key in FIELD_MAPPING.items():
            snapshot[key] = record.get(noco_field, "")
        snapshot["id"] = record.get("Id")
        return snapshot
