import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session, select
from jinja2 import Environment, FileSystemLoader

from app.database import get_session
from app.auth import get_current_admin
from app.models import AdminUser, Job, BusinessUnit, CandidatePipeline, Candidate, ManagedLevel, not_deleted
from app.reports import collect_general_data, collect_pipeline_data, collect_job_data
from app.llm import generate_report

router = APIRouter(prefix="/reports")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = BASE_DIR / "static" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

_report_env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates" / "reports")), autoescape=True)


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _render_report(template_name: str, data: dict, llm: dict) -> str:
    template = _report_env.get_template(template_name)
    return template.render(data=data, llm=llm, generated_date=datetime.utcnow().strftime("%b %d, %Y"))


def _save_report(report_type: str, entity_id: str, html: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{report_type}_{entity_id}_{ts}.html"
    path = REPORTS_DIR / filename
    path.write_text(html, encoding="utf-8")
    return filename


@router.get("/general")
@router.get("/pipeline/{pipeline_id}")
@router.get("/job/{job_id}")
async def report_post_only_redirect(request: Request, pipeline_id: int = 0, job_id: int = 0):
    return RedirectResponse("/reports", status_code=303)


@router.get("", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    bus = db.exec(select(BusinessUnit).where(BusinessUnit.is_active == True).order_by(BusinessUnit.name)).all()
    levels = db.exec(select(ManagedLevel).order_by(ManagedLevel.order)).all()
    jobs = db.exec(select(Job).where(Job.status == "open", Job.title != "_Unassigned", not_deleted(Job)).order_by(Job.title)).all()
    pipelines = db.exec(
        select(CandidatePipeline, Candidate)
        .join(Candidate, CandidatePipeline.candidate_id == Candidate.id)
        .where(not_deleted(CandidatePipeline))
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()
    pipeline_options = [{"id": p.id, "label": f"{c.name} — {p.display_name or p.position or '—'}"} for p, c in pipelines]

    return _render(request, "reports.html", {
        "admin": admin,
        "bus": bus,
        "levels": levels,
        "jobs": jobs,
        "pipeline_options": pipeline_options,
    })


@router.post("/general", response_class=HTMLResponse)
async def report_general(
    request: Request,
    bu_ids: str = Form(""),
    level: str = Form(""),
    period: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    bu_list = [int(x) for x in bu_ids.split(",") if x.strip()] if bu_ids.strip() else None
    since = None
    if period:
        days = {"7d": 7, "30d": 30, "90d": 90}.get(period)
        if days:
            since = datetime.utcnow() - timedelta(days=days)

    try:
        data = collect_general_data(db, bu_ids=bu_list, level=level or None, since=since)
        llm = await generate_report("general", data)
        html = _render_report("general.html", data, llm)
        filename = _save_report("general", "all", html)
        return _render(request, "partials/report_result.html", {"filename": filename})
    except Exception as e:
        return HTMLResponse(
            f'<div class="detail-section"><div class="form-error">Report generation failed: {str(e)}</div></div>',
        )


@router.post("/pipeline/{pipeline_id}", response_class=HTMLResponse)
async def report_pipeline(
    request: Request,
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    try:
        data = collect_pipeline_data(db, pipeline_id)
        if data.get("error"):
            return HTMLResponse(f'<div class="form-error">{data["error"]}</div>')
        llm = await generate_report("pipeline", data)
        html = _render_report("pipeline.html", data, llm)
        filename = _save_report("pipeline", str(pipeline_id), html)
        return _render(request, "partials/report_result.html", {"filename": filename})
    except Exception as e:
        return HTMLResponse(
            f'<div class="detail-section"><div class="form-error">Report generation failed: {str(e)}</div></div>',
        )


@router.post("/job/{job_id}", response_class=HTMLResponse)
async def report_job(
    request: Request,
    job_id: int,
    period: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    since = None
    if period:
        days = {"7d": 7, "30d": 30, "90d": 90}.get(period)
        if days:
            since = datetime.utcnow() - timedelta(days=days)

    try:
        data = collect_job_data(db, job_id, since=since)
        if data.get("error"):
            return HTMLResponse(f'<div class="form-error">{data["error"]}</div>')
        llm = await generate_report("job", data)
        html = _render_report("job.html", data, llm)
        filename = _save_report("job", str(job_id), html)
        return _render(request, "partials/report_result.html", {"filename": filename})
    except Exception as e:
        return HTMLResponse(
            f'<div class="detail-section"><div class="form-error">Report generation failed: {str(e)}</div></div>',
        )
