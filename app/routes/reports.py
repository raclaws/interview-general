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
from app.models import AdminUser, Job, BusinessUnit, CandidatePipeline, Candidate, ManagedLevel, ReportHistory, not_deleted
from app.reports import collect_general_data, collect_pipeline_data, collect_job_data
from app.llm import generate_report, get_llm_config

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


def _toast_error(msg: str):
    trigger = json.dumps({"toast": {"value": msg, "severity": "error"}})
    return HTMLResponse('', status_code=422, headers={"HX-Reswap": "none", "HX-Trigger": trigger})


def _check_llm_config():
    _, api_key, model, _ = get_llm_config()
    if not api_key or api_key == "change-me":
        return "LLM API key not configured. Go to Settings → LLM to set it up."
    if not model:
        return "LLM model not configured. Go to Settings → LLM to set it up."
    return None


def _save_report(report_type: str, entity_id: str, html: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{report_type}_{entity_id}_{ts}.html"
    path = REPORTS_DIR / filename
    path.write_text(html, encoding="utf-8")
    return filename


def _record_history(db: Session, report_type: str, filename: str, filters: dict):
    entry = ReportHistory(
        report_type=report_type,
        filename=filename,
        filters=json.dumps(filters, default=str),
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()


def _purge_expired_history(db: Session):
    cutoff = datetime.utcnow() - timedelta(days=90)
    expired = db.exec(select(ReportHistory).where(ReportHistory.created_at < cutoff)).all()
    for entry in expired:
        filepath = REPORTS_DIR / entry.filename
        if filepath.exists():
            filepath.unlink()
        db.delete(entry)
    if expired:
        db.commit()


@router.get("/history", response_class=HTMLResponse)
async def report_history(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    _purge_expired_history(db)
    entries = db.exec(select(ReportHistory).order_by(ReportHistory.created_at.desc()).limit(50)).all()
    history = []
    for e in entries:
        try:
            filters = json.loads(e.filters) if e.filters else {}
        except (json.JSONDecodeError, TypeError):
            filters = {}
        history.append({
            "report_type": e.report_type,
            "filename": e.filename,
            "display": filters.get("display", "—"),
            "created_at": e.created_at,
        })
    return _render(request, "partials/report_history.html", {"entries": history})


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

    llm_err = _check_llm_config()
    if llm_err:
        return _toast_error(llm_err)

    try:
        data = collect_general_data(db, bu_ids=bu_list, level=level or None, since=since)
        if data["total_pipelines"] == 0 and data["open_jobs"] == 0:
            return _toast_error("No data to report — no open jobs or active pipelines found with these filters.")
        llm = await generate_report("general", data)
        html = _render_report("general.html", data, llm)
        filename = _save_report("general", "all", html)
        bu_label = "All BUs"
        if bu_list:
            bus = db.exec(select(BusinessUnit).where(BusinessUnit.id.in_(bu_list))).all()
            bu_label = ", ".join(b.name for b in bus) if bus else "All BUs"
        filters_display = f"BU: {bu_label} · Level: {level or 'All'} · Period: {period or 'All time'}"
        _record_history(db, "general", filename, {"display": filters_display})
        return _render(request, "partials/report_result.html", {"filename": filename})
    except Exception as e:
        return _toast_error(f"Report generation failed: {str(e)}")


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
            return _toast_error(data["error"])

        llm_err = _check_llm_config()
        if llm_err:
            return _toast_error(llm_err)

        if not data.get("sessions") and not data.get("tests"):
            return _toast_error("No interview or test data yet for this pipeline — nothing to analyze.")

        llm = await generate_report("pipeline", data)
        html = _render_report("pipeline.html", data, llm)
        filename = _save_report("pipeline", str(pipeline_id), html)
        candidate_name = data.get("candidate", {}).get("name", "—")
        job_title = data.get("job", {}).get("title", "—") if data.get("job") else "—"
        filters_display = f"Candidate: {candidate_name} · Job: {job_title}"
        _record_history(db, "pipeline", filename, {"display": filters_display})
        return _render(request, "partials/report_result.html", {"filename": filename})
    except Exception as e:
        return _toast_error(f"Report generation failed: {str(e)}")


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

    llm_err = _check_llm_config()
    if llm_err:
        return _toast_error(llm_err)

    try:
        data = collect_job_data(db, job_id, since=since)
        if data.get("error"):
            return _toast_error(data["error"])

        if not data.get("candidates"):
            return _toast_error("No candidates in pipeline for this job — nothing to analyze.")

        llm = await generate_report("job", data)
        html = _render_report("job.html", data, llm)
        filename = _save_report("job", str(job_id), html)
        job_title = data.get("job", {}).get("title", "—")
        filters_display = f"Job: {job_title} · Period: {period or 'All time'}"
        _record_history(db, "job", filename, {"display": filters_display})
        return _render(request, "partials/report_result.html", {"filename": filename})
    except Exception as e:
        return _toast_error(f"Report generation failed: {str(e)}")
