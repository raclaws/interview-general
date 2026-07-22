"""Salary benchmark API + page route."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session, select
from collections import defaultdict
import statistics

from app.database import get_session
from app.auth import get_current_admin
from app.models import AdminUser, CandidateSignal

router = APIRouter()


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("/api/salary-stats")
async def salary_stats(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    sigs = db.exec(select(CandidateSignal).where(
        CandidateSignal.salary_label != "",
        CandidateSignal.salary_label != "NO_INPUT",
        CandidateSignal.salary_label != "INSUFFICIENT_DATA",
        CandidateSignal.percentile.isnot(None),
    )).all()

    buckets = defaultdict(list)
    for s in sigs:
        if not s.role_bucket or s.role_bucket == "UNKNOWN":
            continue
        key = (s.role_bucket, s.years_band or "unknown")
        buckets[key].append({
            "percentile": s.percentile,
            "label": s.salary_label,
            "category": s.company_category or "",
        })

    results = []
    for (role, band), items in sorted(buckets.items()):
        pcts = [i["percentile"] for i in items]
        labels = defaultdict(int)
        categories = defaultdict(int)
        for i in items:
            labels[i["label"]] += 1
            if i["category"]:
                categories[i["category"]] += 1

        results.append({
            "role": role,
            "band": band,
            "count": len(items),
            "p25": round(statistics.quantiles(pcts, n=4)[0], 1) if len(pcts) >= 4 else None,
            "p50": round(statistics.median(pcts), 1) if pcts else None,
            "p75": round(statistics.quantiles(pcts, n=4)[2], 1) if len(pcts) >= 4 else None,
            "distribution": dict(labels),
            "categories": dict(categories),
        })

    roles = sorted(set(r["role"] for r in results))
    bands = ["0-1yr", "1-3yr", "3-5yr", "5-8yr", "8yr+"]

    return JSONResponse({"buckets": results, "roles": roles, "bands": bands})


@router.get("/benchmark", response_class=HTMLResponse)
async def benchmark_page(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
):
    return _render(request, "benchmark.html", {"admin": admin})
