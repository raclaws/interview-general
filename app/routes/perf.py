"""
Performance logging endpoint.
Both /sessions and /sessions-v2 post timing metrics here.
Stored as JSONL for easy analysis.
"""

import json
import time
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/perf")

LOG_PATH = Path(__file__).resolve().parent.parent / "perf.jsonl"


@router.post("/log")
async def log_perf(request: Request):
    body = await request.json()
    entry = {
        "ts": int(time.time() * 1000),
        "iso": datetime.utcnow().isoformat(),
        "page": body.get("page", "unknown"),
        "metrics": body.get("metrics", {}),
        "userAgent": request.headers.get("user-agent", ""),
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return JSONResponse({"ok": True})


@router.get("/report")
async def perf_report():
    """Return last 100 entries for analysis."""
    if not LOG_PATH.exists():
        return {"entries": [], "summary": "No perf data yet."}

    lines = LOG_PATH.read_text().strip().split("\n")
    entries = [json.loads(l) for l in lines[-100:]]

    # Compute summaries per page
    pages: dict = {}
    for e in entries:
        page = e["page"]
        if page not in pages:
            pages[page] = {"count": 0, "metrics": {}}
        pages[page]["count"] += 1
        for key, val in e.get("metrics", {}).items():
            if isinstance(val, (int, float)):
                if key not in pages[page]["metrics"]:
                    pages[page]["metrics"][key] = []
                pages[page]["metrics"][key].append(val)

    summary = {}
    for page, data in pages.items():
        summary[page] = {"samples": data["count"], "avg": {}}
        for key, values in data["metrics"].items():
            summary[page]["avg"][key] = round(sum(values) / len(values), 2)

    return {"entries": entries[-20:], "summary": summary}
