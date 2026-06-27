import asyncio
import json as json_mod
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response as FastAPIResponse
from sqlmodel import Session, select, col
from sqlalchemy import func, case

from app.database import get_session
from app.auth import get_current_admin
from app.models import (
    AdminUser, Candidate, CandidatePipeline, InterviewSession,
    SessionInterviewer, Template, TemplateSection, Response, ResponseScore, PipelineScore,
    PIPELINE_STAGES, HR_DIMENSIONS, CULTURE_DIMENSIONS, DRIVE_DREAM_OPTIONS, TableView,
    TestAssignment, ReviewBatch, ReviewScore, Job, BusinessUnit, Comment, not_deleted,
)
from app.routes.sync import hub as sync_hub
from app.activity import record_activity
from app.helpers import render_gone

router = APIRouter()


def _candidate_broadcast(candidate: Candidate, db: Session) -> dict:
    pipelines = db.exec(
        select(CandidatePipeline).where(CandidatePipeline.candidate_id == candidate.id, not_deleted(CandidatePipeline))
    ).all()
    stages = list(set(p.stage for p in pipelines if p.stage))
    session_count = db.exec(
        select(func.count(InterviewSession.id)).where(InterviewSession.candidate_id == candidate.id, not_deleted(InterviewSession))
    ).one()
    return {
        "id": str(candidate.id),
        "name": candidate.name,
        "email": candidate.email or "",
        "currentPosition": candidate.current_position or "",
        "stages": ",".join(stages),
        "pipelineCount": len(pipelines),
        "sessionCount": session_count,
        "updatedAt": int(candidate.updated_at.timestamp() * 1000) if candidate.updated_at else 0,
    }


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _pipeline_partial_context(db: Session, candidate_id: int) -> dict:
    """Build full context needed by partials/pipeline_list.html."""
    candidate = db.get(Candidate, candidate_id)
    pipelines = db.exec(
        select(CandidatePipeline)
        .where(CandidatePipeline.candidate_id == candidate_id, not_deleted(CandidatePipeline))
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()

    # Cache template sections to avoid re-querying per interviewer
    _template_sections_cache = {}

    def get_template_sections(template_id):
        if template_id not in _template_sections_cache:
            _template_sections_cache[template_id] = db.exec(
                select(TemplateSection).where(TemplateSection.template_id == template_id)
            ).all()
        return _template_sections_cache[template_id]

    pipeline_scores = {}
    for p in pipelines:
        p_sessions = db.exec(
            select(InterviewSession).where(
                InterviewSession.pipeline_id == p.id,
                InterviewSession.status == "completed",
                not_deleted(InterviewSession),
            )
        ).all()
        hr_total = 0
        culture_total = 0
        hr_count = 0
        culture_count = 0
        for s in p_sessions:
            template = db.get(Template, s.template_id) if s.template_id else None
            if not template:
                continue
            is_hr = template.name == "HR Interview"
            is_culture = template.name == "Culture Alignment"
            if not is_hr and not is_culture:
                continue
            ivs = db.exec(
                select(SessionInterviewer).where(
                    SessionInterviewer.session_id == s.id,
                    SessionInterviewer.status == "completed",
                )
            ).all()
            for iv in ivs:
                resp = db.exec(select(Response).where(Response.session_interviewer_id == iv.id)).first()
                if not resp:
                    continue
                scores = db.exec(select(ResponseScore).where(ResponseScore.response_id == resp.id)).all()
                sections = get_template_sections(template.id)
                section_map = {sec.id: sec for sec in sections}
                iv_total = 0
                for sr in scores:
                    sec = section_map.get(sr.section_id)
                    if sec and sec.measurement_type == "rating_1_4" and sr.value:
                        try:
                            iv_total += int(sr.value)
                        except ValueError:
                            pass
                if is_hr:
                    hr_total += iv_total
                    hr_count += 1
                elif is_culture:
                    culture_total += iv_total
                    culture_count += 1
        pipeline_scores[p.id] = {
            "hr_avg": round(hr_total / hr_count, 1) if hr_count else 0,
            "culture_avg": round(culture_total / culture_count, 1) if culture_count else 0,
        }

    pipeline_sessions = {}
    sessions = db.exec(
        select(InterviewSession)
        .where(InterviewSession.candidate_id == candidate_id, not_deleted(InterviewSession))
        .order_by(InterviewSession.created_at.desc())
    ).all()
    for s in sessions:
        ivs = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        total = len(ivs)
        completed = len([i for i in ivs if i.status == "completed"])
        entry = {"session": s, "total": total, "completed": completed}
        pid = s.pipeline_id or 0
        pipeline_sessions.setdefault(pid, []).append(entry)

    pipeline_tests = {}
    for p in pipelines:
        tests = db.exec(
            select(TestAssignment).where(
                TestAssignment.pipeline_id == p.id,
                not_deleted(TestAssignment),
            )
        ).all()
        submitted = len([t for t in tests if t.status == "submitted"])
        pipeline_tests[p.id] = {"total": len(tests), "submitted": submitted}

    return {
        "pipelines": pipelines,
        "candidate": candidate,
        "stages": PIPELINE_STAGES,
        "pipeline_scores": pipeline_scores,
        "pipeline_sessions": pipeline_sessions,
        "pipeline_tests": pipeline_tests,
    }


@router.get("/candidates", response_class=HTMLResponse)
async def candidates_list(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
):
    return _render(request, "candidates_list.html", {"admin": admin})


@router.get("/candidate/new", response_class=HTMLResponse)
async def candidate_new_form(
    request: Request,
    next: str = None,
    admin: AdminUser = Depends(get_current_admin),
):
    return _render(request, "candidate_new.html", {"admin": admin, "next": next})


@router.post("/candidate/new")
async def candidate_new_submit(
    request: Request,
    mode: str = Form("manual"),
    candidate_id: int = Form(None),
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    current_position: str = Form(""),
    yoe: str = Form(""),
    languages: str = Form(""),
    cloud: str = Form(""),
    tools: str = Form(""),
    working_arrangement: str = Form(""),
    current_salary: str = Form(""),
    expected_salary: str = Form(""),
    notice_period: str = Form(""),
    cv_link: str = Form(""),
    next: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    if mode == "nocodb" and candidate_id:
        existing = db.get(Candidate, candidate_id)
        if not existing:
            return _render(request, "candidate_new.html", {
                "admin": admin,
                "error": "Candidate not found.",
            })
        return RedirectResponse(next or f"/candidate/{existing.id}", status_code=303)

    if mode == "nocodb_import" and candidate_id:
        from app.nocodb import fetch_candidate
        snapshot = await fetch_candidate(candidate_id)
        if not snapshot or snapshot.get("_error") or not snapshot.get("email"):
            error_msg = snapshot.get("_error", "Candidate not found in NocoDB.") if snapshot else "Candidate not found in NocoDB."
            return _render(request, "candidate_new.html", {
                "admin": admin,
                "error": error_msg,
            })
        from app.nocodb import upsert_candidate_from_nocodb
        candidate = upsert_candidate_from_nocodb(snapshot, candidate_id)
        asyncio.create_task(sync_hub.broadcast("candidates", "insert", str(candidate.id), _candidate_broadcast(candidate, db)))
        return RedirectResponse(next or f"/candidate/{candidate.id}", status_code=303)

    if not name.strip() or not email.strip():
        return _render(request, "candidate_new.html", {
            "admin": admin,
            "error": "Name and email are required.",
        })

    existing = db.exec(select(Candidate).where(Candidate.email == email.strip())).first()
    if existing:
        return _render(request, "candidate_new.html", {
            "admin": admin,
            "error": f"A candidate with email '{email.strip()}' already exists. <a href='/candidate/{existing.id}'>View {existing.name}</a>",
        })

    candidate = Candidate(
        name=name.strip(),
        email=email.strip(),
        phone=phone.strip() or None,
        current_position=current_position.strip() or None,
        yoe=yoe.strip() or None,
        languages=languages.strip() or None,
        cloud=cloud.strip() or None,
        tools=tools.strip() or None,
        working_arrangement=working_arrangement.strip() or None,
        current_salary=current_salary.strip() or None,
        expected_salary=expected_salary.strip() or None,
        notice_period=notice_period.strip() or None,
        cv_link=cv_link.strip() or None,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    asyncio.create_task(sync_hub.broadcast("candidates", "insert", str(candidate.id), _candidate_broadcast(candidate, db)))

    return RedirectResponse(next or f"/candidate/{candidate.id}", status_code=303)


@router.get("/candidate/{candidate_id}", response_class=HTMLResponse)
async def candidate_detail(
    request: Request,
    candidate_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return render_gone(request, "Candidate", "/candidates", "Candidates")

    pipelines = db.exec(
        select(CandidatePipeline)
        .where(CandidatePipeline.candidate_id == candidate.id, not_deleted(CandidatePipeline))
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()

    pipeline_scores = {}
    for p in pipelines:
        # Compute scores from completed sessions
        p_sessions = db.exec(
            select(InterviewSession).where(
                InterviewSession.pipeline_id == p.id,
                InterviewSession.status == "completed",
                not_deleted(InterviewSession),
            )
        ).all()
        hr_total = 0
        culture_total = 0
        hr_count = 0
        culture_count = 0
        for s in p_sessions:
            template = db.get(Template, s.template_id) if s.template_id else None
            if not template:
                continue
            is_hr = template.name == "HR Interview"
            is_culture = template.name == "Culture Alignment"
            if not is_hr and not is_culture:
                continue
            ivs = db.exec(
                select(SessionInterviewer).where(
                    SessionInterviewer.session_id == s.id,
                    SessionInterviewer.status == "completed",
                )
            ).all()
            for iv in ivs:
                resp = db.exec(select(Response).where(Response.session_interviewer_id == iv.id)).first()
                if not resp:
                    continue
                scores = db.exec(select(ResponseScore).where(ResponseScore.response_id == resp.id)).all()
                sections = db.exec(select(TemplateSection).where(TemplateSection.template_id == template.id)).all()
                section_map = {sec.id: sec for sec in sections}
                iv_total = 0
                for sr in scores:
                    sec = section_map.get(sr.section_id)
                    if sec and sec.measurement_type == "rating_1_4" and sr.value:
                        try:
                            iv_total += int(sr.value)
                        except ValueError:
                            pass
                if is_hr:
                    hr_total += iv_total
                    hr_count += 1
                elif is_culture:
                    culture_total += iv_total
                    culture_count += 1
        pipeline_scores[p.id] = {
            "hr_avg": round(hr_total / hr_count, 1) if hr_count else 0,
            "culture_avg": round(culture_total / culture_count, 1) if culture_count else 0,
        }

    sessions = db.exec(
        select(InterviewSession)
        .where(InterviewSession.candidate_id == candidate.id, not_deleted(InterviewSession))
        .order_by(InterviewSession.created_at.desc())
    ).all()

    # Group sessions by pipeline_id
    pipeline_sessions = {}
    for s in sessions:
        ivs = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        total = len(ivs)
        completed = len([i for i in ivs if i.status == "completed"])
        template = db.get(Template, s.template_id) if s.template_id else None
        entry = {
            "session": s,
            "total": total,
            "completed": completed,
            "template": template,
            "interviewers": [iv.interviewer_name for iv in ivs],
        }
        pid = s.pipeline_id or 0
        pipeline_sessions.setdefault(pid, []).append(entry)

    templates = db.exec(select(Template).order_by(Template.name)).all()

    return _render(request, "candidate_detail.html", {
        "candidate": candidate,
        "pipelines": pipelines,
        "pipeline_scores": pipeline_scores,
        "pipeline_sessions": pipeline_sessions,
        "admin": admin,
        "stages": PIPELINE_STAGES,
        "jobs": db.exec(select(Job).where(Job.status == "open", Job.title != "_Unassigned", not_deleted(Job)).order_by(Job.title)).all(),
        "templates": templates,
        "trail": db.exec(
            select(Comment).where(Comment.entity_type == "candidate", Comment.entity_id == candidate_id).order_by(Comment.created_at)
        ).all(),
    })


@router.get("/candidate/{candidate_id}/edit", response_class=HTMLResponse)
async def candidate_edit_form(
    request: Request,
    candidate_id: int,
    next: str = None,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)
    return _render(request, "candidate_edit.html", {"candidate": candidate, "admin": admin, "next": next or f"/candidate/{candidate_id}"})


@router.post("/candidate/{candidate_id}/edit")
async def candidate_edit_submit(
    request: Request,
    candidate_id: int,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    current_position: str = Form(""),
    yoe: str = Form(""),
    languages: str = Form(""),
    cloud: str = Form(""),
    tools: str = Form(""),
    working_arrangement: str = Form(""),
    current_salary: str = Form(""),
    expected_salary: str = Form(""),
    notice_period: str = Form(""),
    cv_link: str = Form(""),
    next: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    candidate.name = name.strip()
    candidate.email = email.strip()
    candidate.phone = phone.strip() or None
    candidate.current_position = current_position.strip() or None
    candidate.yoe = yoe.strip() or None
    candidate.languages = languages.strip() or None
    candidate.cloud = cloud.strip() or None
    candidate.tools = tools.strip() or None
    candidate.working_arrangement = working_arrangement.strip() or None
    candidate.current_salary = current_salary.strip() or None
    candidate.expected_salary = expected_salary.strip() or None
    candidate.notice_period = notice_period.strip() or None
    candidate.cv_link = cv_link.strip() or None
    candidate.updated_at = datetime.utcnow()
    db.add(candidate)
    db.commit()
    return RedirectResponse(next or f"/candidate/{candidate_id}", status_code=303)


@router.post("/candidate/{candidate_id}/pipeline")
async def pipeline_create(
    request: Request,
    candidate_id: int,
    job_id: int = Form(...),
    stage: str = Form("screening"),
    notes: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return render_gone(request, "Candidate", "/candidates", "Candidates")

    job = db.get(Job, job_id)
    if not job:
        if request.headers.get("HX-Request"):
            return HTMLResponse('<div class="form-error">This job no longer exists. It may have been deleted by another user.</div>')
        return render_gone(request, "Job", "/jobs", "Jobs")

    bu = db.get(BusinessUnit, job.business_unit_id)
    pos = job.position
    bu_name = bu.name if bu else "N/A"

    # Block duplicate active pipeline for same job
    from app.models import PIPELINE_ENDED_STAGES
    active_dup = db.exec(
        select(CandidatePipeline).where(
            CandidatePipeline.candidate_id == candidate.id,
            CandidatePipeline.job_id == job_id,
            CandidatePipeline.stage.notin_(PIPELINE_ENDED_STAGES),
            not_deleted(CandidatePipeline),
        )
    ).first()
    if active_dup:
        if request.headers.get("HX-Request"):
            return HTMLResponse(f'<div class="form-error">An active pipeline for this job already exists.</div>')
        return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)

    # Auto-generate display_name from job title
    mmyy = datetime.utcnow().strftime("%m%y")
    existing = db.exec(
        select(CandidatePipeline).where(
            CandidatePipeline.candidate_id == candidate.id,
            CandidatePipeline.job_id == job_id,
            not_deleted(CandidatePipeline),
        )
    ).all()
    same_month = [p for p in existing if p.created_at.strftime("%m%y") == mmyy]
    seq = len(same_month) + 1
    display_name = f"{pos} {mmyy} #{seq} — {bu_name}"

    pipeline = CandidatePipeline(
        candidate_id=candidate.id,
        job_id=job_id,
        display_name=display_name,
        position=pos,
        business_unit=bu_name,
        stage=stage if stage in PIPELINE_STAGES else "screening",
        notes=notes.strip() or None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    record_activity(db, "pipeline", pipeline.id, f"Pipeline created — {display_name}", pipeline_id=pipeline.id)
    db.commit()

    if request.headers.get("HX-Request"):
        return _render(request, "partials/pipeline_list.html", _pipeline_partial_context(db, candidate_id))

    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.post("/candidate/{candidate_id}/pipeline/{pipeline_id}/stage")
async def pipeline_update_stage(
    request: Request,
    candidate_id: int,
    pipeline_id: int,
    stage: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline or pipeline.candidate_id != candidate_id:
        return HTMLResponse("Not found", status_code=404)

    if stage in PIPELINE_STAGES:
        old_stage = pipeline.stage
        pipeline.stage = stage
        pipeline.updated_at = datetime.utcnow()
        record_activity(db, "pipeline", pipeline_id, f"Stage changed from {old_stage.replace('_', ' ')} to {stage.replace('_', ' ')}", pipeline_id=pipeline_id)
        db.add(pipeline)
        db.commit()

    # Auto-close check
    toast_msg = "Stage updated"
    if stage == "hired" and pipeline.job_id:
        job = db.get(Job, pipeline.job_id)
        if job and job.status == "open":
            filled = len(db.exec(
                select(CandidatePipeline).where(
                    CandidatePipeline.job_id == job.id,
                    CandidatePipeline.stage == "hired",
                    not_deleted(CandidatePipeline),
                )
            ).all())
            if filled >= job.headcount:
                toast_msg = f"Stage updated — Job \"{job.title}\" reached headcount ({filled}/{job.headcount})"

    if request.headers.get("HX-Request"):
        resp = _render(request, "partials/pipeline_list.html", _pipeline_partial_context(db, candidate_id))
        resp.headers["HX-Trigger"] = f"toast:{toast_msg}"
        return resp

    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.post("/candidate/{candidate_id}/pipeline/{pipeline_id}/notes")
async def pipeline_update_notes(
    request: Request,
    candidate_id: int,
    pipeline_id: int,
    notes: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline or pipeline.candidate_id != candidate_id:
        return HTMLResponse("Not found", status_code=404)

    pipeline.notes = notes.strip() or None
    pipeline.updated_at = datetime.utcnow()
    db.add(pipeline)
    db.commit()

    if request.headers.get("HX-Request"):
        return _render(request, "partials/pipeline_list.html", _pipeline_partial_context(db, candidate_id))

    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.get("/candidate/{candidate_id}/pipeline/{pipeline_id}/delete")
async def pipeline_delete_redirect(request: Request, candidate_id: int, pipeline_id: int):
    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.post("/candidate/{candidate_id}/pipeline/{pipeline_id}/delete")
async def pipeline_delete(
    request: Request,
    candidate_id: int,
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline or pipeline.candidate_id != candidate_id:
        return HTMLResponse("Not found", status_code=404)

    # Detach sessions linked to this pipeline before deleting
    linked_sessions = db.exec(
        select(InterviewSession).where(InterviewSession.pipeline_id == pipeline_id)
    ).all()
    for s in linked_sessions:
        s.pipeline_id = None
        db.add(s)

    record_activity(db, "pipeline", pipeline_id, f"Pipeline deleted — {pipeline.display_name or '—'}", pipeline_id=pipeline_id)
    pipeline.deleted_at = datetime.utcnow()
    db.add(pipeline)
    db.commit()

    asyncio.create_task(sync_hub.broadcast("pipelines", "delete", str(pipeline_id)))

    if request.headers.get("HX-Request"):
        return _render(request, "partials/pipeline_list.html", _pipeline_partial_context(db, candidate_id))

    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.get("/candidate/{candidate_id}/pipeline/{pipeline_id}/score", response_class=HTMLResponse)
async def pipeline_score_view(
    request: Request,
    candidate_id: int,
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not candidate or not pipeline or pipeline.candidate_id != candidate_id:
        return HTMLResponse("Not found", status_code=404)

    # Map section titles to dimension keys
    HR_TITLE_MAP = {
        "Ownership with Accountability": "ownership_accountability",
        "Maturity & Growth Mindset": "maturity_growth",
        "Supportive & Collaborative": "supportive_collaborative",
    }
    CULTURE_TITLE_MAP = {
        "Execution Excellence": "execution_excellence",
        "Learn Fast, Adapt Faster": "learn_adapt",
        "Impact Over Activity": "impact_over_activity",
        "Clarity & Structured Thinking": "clarity_structured",
    }

    # Find all completed sessions for this pipeline
    sessions = db.exec(
        select(InterviewSession).where(
            InterviewSession.pipeline_id == pipeline_id,
            InterviewSession.status == "completed",
            not_deleted(InterviewSession),
        )
    ).all()

    # Collect per-interviewer scores
    hr_data = []  # [{name, scores: {key: val}, drive_dream: []}]
    culture_data = []

    for session in sessions:
        template = db.get(Template, session.template_id) if session.template_id else None
        if not template:
            continue

        sections = db.exec(
            select(TemplateSection).where(TemplateSection.template_id == template.id)
        ).all()
        section_map = {s.id: s for s in sections}

        interviewers = db.exec(
            select(SessionInterviewer).where(
                SessionInterviewer.session_id == session.id,
                SessionInterviewer.status == "completed",
            )
        ).all()

        is_hr = template.name == "HR Interview"
        is_culture = template.name == "Culture Alignment"

        for iv in interviewers:
            response = db.exec(
                select(Response).where(Response.session_interviewer_id == iv.id)
            ).first()
            if not response:
                continue

            score_rows = db.exec(
                select(ResponseScore).where(ResponseScore.response_id == response.id)
            ).all()

            scores = {}
            drive_dream = []
            for sr in score_rows:
                section = section_map.get(sr.section_id)
                if not section:
                    continue

                title_map = HR_TITLE_MAP if is_hr else CULTURE_TITLE_MAP if is_culture else {}
                dim_key = title_map.get(section.title)

                if dim_key and sr.value:
                    try:
                        scores[dim_key] = int(sr.value)
                    except ValueError:
                        pass

                if section.title == "Drive & Dream" and sr.value:
                    drive_dream = [v.strip() for v in sr.value.split(",") if v.strip()]

            entry = {
                "name": iv.interviewer_name,
                "scores": scores,
                "drive_dream": drive_dream,
                "free_text": response.free_text,
            }

            if is_hr:
                hr_data.append(entry)
            elif is_culture:
                culture_data.append(entry)

    # Compute averages
    def compute_avg(data_list, dimensions):
        avg = {}
        for dim in dimensions:
            values = [d["scores"].get(dim["key"], 0) for d in data_list if d["scores"].get(dim["key"])]
            avg[dim["key"]] = round(sum(values) / len(values), 1) if values else 0
        return avg

    hr_avg = compute_avg(hr_data, HR_DIMENSIONS)
    culture_avg = compute_avg(culture_data, CULTURE_DIMENSIONS)
    hr_total = sum(hr_avg.values())
    culture_total = sum(culture_avg.values())

    return _render(request, "pipeline_score.html", {
        "candidate": candidate,
        "pipeline": pipeline,
        "hr_dimensions": HR_DIMENSIONS,
        "culture_dimensions": CULTURE_DIMENSIONS,
        "drive_dream_options": DRIVE_DREAM_OPTIONS,
        "hr_data": hr_data,
        "culture_data": culture_data,
        "hr_avg": hr_avg,
        "culture_avg": culture_avg,
        "hr_total": hr_total,
        "culture_total": culture_total,
        "admin": admin,
    })


# --- CLA-19: Pipeline List Page ---

@router.get("/pipelines", response_class=HTMLResponse)
async def pipelines_list(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    bus = db.exec(select(BusinessUnit).where(BusinessUnit.is_active == True)).all()
    bu_names = sorted(b.name for b in bus)
    return _render(request, "pipelines_list.html", {"admin": admin, "bu_names": bu_names})


@router.get("/pipeline/new", response_class=HTMLResponse)
async def pipeline_new_form(
    request: Request,
    candidate_id: int = None,
    job_id: int = None,
    next: str = None,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidates = db.exec(select(Candidate).order_by(Candidate.name)).all()
    jobs = db.exec(select(Job).where(Job.status == "open").where(not_deleted(Job)).order_by(Job.title)).all()
    return _render(request, "pipeline_new.html", {
        "admin": admin,
        "candidates": candidates,
        "jobs": jobs,
        "stages": PIPELINE_STAGES[:4],
        "prefill_candidate_id": candidate_id,
        "prefill_job_id": job_id,
        "next": next,
    })


@router.post("/pipeline/new")
async def pipeline_new_submit(
    request: Request,
    candidate_id: int = Form(...),
    job_id: int = Form(...),
    stage: str = Form("screening"),
    notes: str = Form(""),
    next: str = Form(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return render_gone(request, "Candidate", "/candidates", "Candidates")

    job = db.get(Job, job_id)
    if not job:
        return render_gone(request, "Job", "/jobs", "Jobs")

    bu = db.get(BusinessUnit, job.business_unit_id)
    pos = job.position
    bu_name = bu.name if bu else "N/A"

    from app.models import PIPELINE_ENDED_STAGES
    active_dup = db.exec(
        select(CandidatePipeline).where(
            CandidatePipeline.candidate_id == candidate.id,
            CandidatePipeline.job_id == job_id,
            CandidatePipeline.stage.notin_(PIPELINE_ENDED_STAGES),
            not_deleted(CandidatePipeline),
        )
    ).first()
    if active_dup:
        return RedirectResponse(f"/pipeline/new?candidate_id={candidate_id}&job_id={job_id}", status_code=303)

    mmyy = datetime.utcnow().strftime("%m%y")
    existing = db.exec(
        select(CandidatePipeline).where(
            CandidatePipeline.candidate_id == candidate.id,
            CandidatePipeline.job_id == job_id,
            not_deleted(CandidatePipeline),
        )
    ).all()
    same_month = [p for p in existing if p.created_at.strftime("%m%y") == mmyy]
    seq = len(same_month) + 1
    display_name = f"{pos} {mmyy} #{seq} — {bu_name}"

    pipeline = CandidatePipeline(
        candidate_id=candidate.id,
        job_id=job_id,
        display_name=display_name,
        position=pos,
        business_unit=bu_name,
        stage=stage if stage in PIPELINE_STAGES else "screening",
        notes=notes.strip() or None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    record_activity(db, "pipeline", pipeline.id, f"Pipeline created — {display_name}", pipeline_id=pipeline.id)
    db.commit()

    asyncio.ensure_future(sync_hub.broadcast("pipelines", "insert", str(pipeline.id), {"id": pipeline.id}))
    return RedirectResponse(next or f"/pipeline/{pipeline.id}", status_code=303)


@router.get("/test/new", response_class=HTMLResponse)
async def test_new_form(
    request: Request,
    pipeline_id: int = None,
    next: str = None,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from app.models import PIPELINE_ENDED_STAGES
    results = db.exec(
        select(CandidatePipeline, Candidate).join(Candidate, CandidatePipeline.candidate_id == Candidate.id)
        .where(CandidatePipeline.stage.notin_(PIPELINE_ENDED_STAGES))
        .where(not_deleted(CandidatePipeline))
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()
    pipelines = [{"pipeline": p, "candidate": c} for p, c in results]

    return _render(request, "test_new.html", {
        "admin": admin,
        "pipelines": pipelines,
        "prefill_pipeline_id": pipeline_id,
        "today": datetime.utcnow().strftime("%Y-%m-%d"),
        "next": next,
    })


@router.post("/test/new")
async def test_new_submit(
    request: Request,
    pipeline_id: int = Form(...),
    title: str = Form(...),
    external_url: str = Form(...),
    instructions: str = Form(""),
    time_limit: int = Form(None),
    max_upload_size: int = Form(25),
    deadline: str = Form(None),
    expiry: str = Form(None),
    next: str = Form(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    import secrets

    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline or pipeline.deleted_at:
        return render_gone(request, "Pipeline", "/pipelines", "Pipelines")

    token = secrets.token_urlsafe(16)
    password = secrets.token_urlsafe(6)[:8]
    deadline_dt = datetime.fromisoformat(deadline) if deadline else None
    expiry_dt = datetime.fromisoformat(expiry) if expiry else None

    assignment = TestAssignment(
        pipeline_id=pipeline.id,
        title=title.strip(),
        external_url=external_url.strip(),
        instructions=instructions.strip() or None,
        time_limit=time_limit,
        max_upload_size=max_upload_size,
        deadline=deadline_dt,
        expiry=expiry_dt,
        token=token,
        password=password,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    record_activity(db, "test", assignment.id, f"Test assigned — {title.strip()}", pipeline_id=pipeline.id)
    db.commit()

    asyncio.ensure_future(sync_hub.broadcast("tests", "insert", str(assignment.id), {"id": assignment.id}))
    return RedirectResponse(next or f"/pipeline/{pipeline.id}", status_code=303)


# --- CLA-20: Pipeline Detail Page ---

def _annotate_test_assignments(assignments):
    """Add is_late flag to each test assignment for template rendering."""
    from datetime import timedelta
    result = []
    for a in assignments:
        deadline = a.deadline
        if not deadline and a.time_limit:
            deadline = a.created_at + timedelta(days=a.time_limit)
        is_late = (
            a.status == "submitted"
            and a.submitted_at is not None
            and deadline is not None
            and a.submitted_at > deadline
        )
        a.__dict__["is_late"] = is_late
        result.append(a)
    return result


def _pipeline_detail_context(db: Session, pipeline: CandidatePipeline, candidate: Candidate):
    """Build context for pipeline detail page."""
    sessions = db.exec(
        select(InterviewSession)
        .where(InterviewSession.pipeline_id == pipeline.id, not_deleted(InterviewSession))
        .order_by(InterviewSession.created_at.desc())
    ).all()

    session_data = []
    for s in sessions:
        ivs = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        total = len(ivs)
        completed = len([i for i in ivs if i.status == "completed"])
        template = db.get(Template, s.template_id) if s.template_id else None
        session_data.append({"session": s, "total": total, "completed": completed, "template": template, "interviewers": [iv.interviewer_name for iv in ivs]})

    # Scores: per-interviewer breakdown (include partial — any session with at least one submitted response)
    hr_data = []
    culture_data = []
    scored_sessions = [s for s in sessions if s.status in ("completed", "pending")]

    HR_TITLE_MAP = {
        "Ownership with Accountability": "ownership_accountability",
        "Maturity & Growth Mindset": "maturity_growth",
        "Supportive & Collaborative": "supportive_collaborative",
    }
    CULTURE_TITLE_MAP = {
        "Execution Excellence": "execution_excellence",
        "Learn Fast, Adapt Faster": "learn_adapt",
        "Impact Over Activity": "impact_over_activity",
        "Clarity & Structured Thinking": "clarity_structured",
    }

    for session in scored_sessions:
        template = db.get(Template, session.template_id) if session.template_id else None
        if not template:
            continue
        is_hr = template.name == "HR Interview"
        is_culture = template.name == "Culture Alignment"
        if not is_hr and not is_culture:
            continue

        sections = db.exec(
            select(TemplateSection).where(TemplateSection.template_id == template.id)
        ).all()
        section_map = {sec.id: sec for sec in sections}

        interviewers = db.exec(
            select(SessionInterviewer).where(
                SessionInterviewer.session_id == session.id,
                SessionInterviewer.status == "completed",
            )
        ).all()

        for iv in interviewers:
            response = db.exec(
                select(Response).where(Response.session_interviewer_id == iv.id)
            ).first()
            if not response:
                continue
            score_rows = db.exec(
                select(ResponseScore).where(ResponseScore.response_id == response.id)
            ).all()

            scores = {}
            drive_dream = []
            title_map = HR_TITLE_MAP if is_hr else CULTURE_TITLE_MAP
            for sr in score_rows:
                section = section_map.get(sr.section_id)
                if not section:
                    continue
                dim_key = title_map.get(section.title)
                if dim_key and sr.value:
                    try:
                        scores[dim_key] = int(sr.value)
                    except ValueError:
                        pass
                if section.title == "Drive & Dream" and sr.value:
                    drive_dream = [v.strip() for v in sr.value.split(",") if v.strip()]

            entry = {"name": iv.interviewer_name, "scores": scores, "drive_dream": drive_dream}
            if is_hr:
                hr_data.append(entry)
            elif is_culture:
                culture_data.append(entry)

    def compute_avg(data_list, dimensions):
        avg = {}
        for dim in dimensions:
            values = [d["scores"].get(dim["key"], 0) for d in data_list if d["scores"].get(dim["key"])]
            avg[dim["key"]] = round(sum(values) / len(values), 1) if values else 0
        return avg

    hr_avg = compute_avg(hr_data, HR_DIMENSIONS)
    culture_avg = compute_avg(culture_data, CULTURE_DIMENSIONS)

    # Scorecard completion status
    hr_sessions = [s for s in scored_sessions if db.get(Template, s.template_id) and db.get(Template, s.template_id).name == "HR Interview"]
    culture_sessions = [s for s in scored_sessions if db.get(Template, s.template_id) and db.get(Template, s.template_id).name == "Culture Alignment"]

    def session_completion(session_list):
        total_ivs = 0
        completed_ivs = 0
        for s in session_list:
            ivs = db.exec(select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)).all()
            total_ivs += len(ivs)
            completed_ivs += len([i for i in ivs if i.status == "completed"])
        return completed_ivs, total_ivs

    hr_completed_ivs, hr_total_ivs = session_completion(hr_sessions)
    culture_completed_ivs, culture_total_ivs = session_completion(culture_sessions)

    return {
        "pipeline": pipeline,
        "candidate": candidate,
        "session_data": session_data,
        "hr_data": hr_data,
        "culture_data": culture_data,
        "hr_avg": hr_avg,
        "culture_avg": culture_avg,
        "hr_total": sum(hr_avg.values()),
        "culture_total": sum(culture_avg.values()),
        "hr_dimensions": HR_DIMENSIONS,
        "culture_dimensions": CULTURE_DIMENSIONS,
        "hr_completion": f"{hr_completed_ivs}/{hr_total_ivs}",
        "hr_partial": hr_total_ivs > 0 and hr_completed_ivs < hr_total_ivs,
        "culture_completion": f"{culture_completed_ivs}/{culture_total_ivs}",
        "culture_partial": culture_total_ivs > 0 and culture_completed_ivs < culture_total_ivs,
        "stages": PIPELINE_STAGES,
        "test_assignments": _annotate_test_assignments(db.exec(
            select(TestAssignment)
            .where(TestAssignment.pipeline_id == pipeline.id, not_deleted(TestAssignment))
            .order_by(TestAssignment.created_at.desc())
        ).all()),
    }


@router.get("/pipeline/{pipeline_id}", response_class=HTMLResponse)
async def pipeline_detail(
    request: Request,
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline or pipeline.deleted_at:
        return render_gone(request, "Pipeline", "/pipelines", "Pipelines")
    candidate = db.get(Candidate, pipeline.candidate_id)
    if not candidate:
        return render_gone(request, "Pipeline", "/pipelines", "Pipelines")

    ctx = _pipeline_detail_context(db, pipeline, candidate)
    ctx["admin"] = admin
    ctx["job"] = db.get(Job, pipeline.job_id) if pipeline.job_id else None
    ctx["trail"] = db.exec(
        select(Comment).where(Comment.entity_type == "pipeline", Comment.entity_id == pipeline_id).order_by(Comment.created_at)
    ).all()
    return _render(request, "pipeline_detail.html", ctx)


@router.post("/pipeline/{pipeline_id}/stage")
async def pipeline_detail_update_stage(
    request: Request,
    pipeline_id: int,
    stage: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return HTMLResponse("Not found", status_code=404)

    if stage in PIPELINE_STAGES:
        old_stage = pipeline.stage
        pipeline.stage = stage
        pipeline.updated_at = datetime.utcnow()
        record_activity(db, "pipeline", pipeline_id, f"Stage changed from {old_stage.replace('_', ' ')} to {stage.replace('_', ' ')}", pipeline_id=pipeline_id)
        db.add(pipeline)
        db.commit()

    if request.headers.get("HX-Request"):
        options = "".join(
            f'<option value="{s}" {"selected" if s == pipeline.stage else ""}>{s.replace("_", " ").title()}</option>'
            for s in PIPELINE_STAGES
        )
        select_html = (
            f'<select name="stage" hx-post="/pipeline/{pipeline_id}/stage" '
            f'hx-target="this" hx-swap="outerHTML" hx-push-url="false" hx-trigger="change" '
            f'hx-disinherit="*" onclick="event.stopPropagation()" class="inline-select">{options}</select>'
        )

        # Auto-close prompt: check if job headcount is met
        toast_msg = "Stage updated"
        close_prompt = ""
        if stage == "hired" and pipeline.job_id:
            job = db.get(Job, pipeline.job_id)
            if job and job.status == "open":
                filled = len(db.exec(
                    select(CandidatePipeline).where(
                        CandidatePipeline.job_id == job.id,
                        CandidatePipeline.stage == "hired",
                    )
                ).all())
                if filled >= job.headcount:
                    close_prompt = (
                        f'<div class="toast-prompt" id="close-prompt">'
                        f'<p>Job "{job.title}" reached headcount ({filled}/{job.headcount}). Close this job?</p>'
                        f'<form method="post" action="/job/{job.id}/close" hx-post="/job/{job.id}/close" style="display:inline;">'
                        f'<button type="submit" class="btn" style="font-size:0.8rem;">Close Job</button></form>'
                        f' <button class="btn-ghost" style="font-size:0.8rem;" onclick="this.closest(\'.toast-prompt\').remove()">Keep Open</button>'
                        f'</div>'
                    )
                    toast_msg = "Stage updated — headcount reached"

        return HTMLResponse(
            select_html + close_prompt,
            headers={"HX-Trigger": f"toast:{toast_msg}"},
        )

    return RedirectResponse(f"/pipeline/{pipeline_id}", status_code=303)


@router.post("/pipeline/{pipeline_id}/notes")
async def pipeline_detail_update_notes(
    request: Request,
    pipeline_id: int,
    notes: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return HTMLResponse("Not found", status_code=404)

    pipeline.notes = notes.strip() or None
    pipeline.updated_at = datetime.utcnow()
    db.add(pipeline)
    db.commit()

    return RedirectResponse(f"/pipeline/{pipeline_id}", status_code=303)


@router.post("/pipeline/{pipeline_id}/delete")
async def pipeline_detail_delete(
    request: Request,
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return HTMLResponse("Not found", status_code=404)

    linked_sessions = db.exec(
        select(InterviewSession).where(InterviewSession.pipeline_id == pipeline_id)
    ).all()
    for s in linked_sessions:
        s.pipeline_id = None
        db.add(s)

    record_activity(db, "pipeline", pipeline_id, f"Pipeline deleted — {pipeline.display_name or '—'}", pipeline_id=pipeline_id)
    pipeline.deleted_at = datetime.utcnow()
    db.add(pipeline)
    db.commit()

    asyncio.create_task(sync_hub.broadcast("pipelines", "delete", str(pipeline_id)))

    if request.headers.get("HX-Request"):
        resp = HTMLResponse("")
        current_path = request.headers.get("HX-Current-URL", "").split("?")[0].rstrip("/")
        if current_path.endswith(f"/pipeline/{pipeline_id}"):
            resp.headers["HX-Redirect"] = "/pipelines"
        resp.headers["HX-Trigger"] = json_mod.dumps({"undoable-delete": {"type": "pipeline", "id": str(pipeline_id), "label": pipeline.display_name or "pipeline"}})
        return resp

    return RedirectResponse("/pipelines", status_code=303)


@router.get("/pipeline/{pipeline_id}/assign-test", response_class=HTMLResponse)
async def assign_test_form(
    request: Request,
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return HTMLResponse("Not found", status_code=404)
    candidate = db.get(Candidate, pipeline.candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    return _render(request, "test_assign.html", {
        "admin": admin,
        "pipeline": pipeline,
        "candidate": candidate,
        "today": datetime.utcnow().strftime("%Y-%m-%d"),
    })


@router.post("/pipeline/{pipeline_id}/assign-test")
async def assign_test_submit(
    request: Request,
    pipeline_id: int,
    title: str = Form(...),
    external_url: str = Form(...),
    instructions: str = Form(""),
    time_limit: int = Form(None),
    deadline: str = Form(""),
    expiry: str = Form(""),
    max_upload_size: int = Form(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    import secrets
    from datetime import datetime as dt

    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return render_gone(request, "Pipeline", "/pipelines", "Pipelines")

    # Dup check: same URL already assigned to this pipeline
    existing_test = db.exec(
        select(TestAssignment).where(
            TestAssignment.pipeline_id == pipeline_id,
            TestAssignment.external_url == external_url.strip(),
            TestAssignment.status != "cancelled",
            not_deleted(TestAssignment),
        )
    ).first()
    if existing_test:
        return HTMLResponse(
            f'<div class="form-error">This test URL is already assigned to this pipeline (status: {existing_test.status}).</div>',
            status_code=400,
        )

    token = secrets.token_urlsafe(16)
    password = secrets.token_urlsafe(6)[:8]

    deadline_dt = dt.fromisoformat(deadline) if deadline else None
    expiry_dt = dt.fromisoformat(expiry) if expiry else None

    assignment = TestAssignment(
        pipeline_id=pipeline_id,
        title=title,
        external_url=external_url,
        instructions=instructions or None,
        time_limit=min(365, max(1, time_limit)) if time_limit and time_limit > 0 else None,
        deadline=deadline_dt,
        expiry=expiry_dt,
        max_upload_size=min(100, max(1, max_upload_size)) if max_upload_size and max_upload_size > 0 else 25,
        token=token,
        password=password,
        status="pending",
    )
    db.add(assignment)
    db.commit()
    record_activity(db, "pipeline", pipeline_id, f"Test assigned — {title}", pipeline_id=pipeline_id)
    db.commit()

    asyncio.create_task(sync_hub.broadcast("tests", "insert", str(assignment.id), {
        "id": str(assignment.id), "title": assignment.title, "status": assignment.status,
        "token": assignment.token, "pipelineId": pipeline_id,
    }))

    return RedirectResponse(f"/pipeline/{pipeline_id}", status_code=303)


@router.post("/pipeline/{pipeline_id}/test/{test_id}/cancel")
async def cancel_test_assignment(
    request: Request,
    pipeline_id: int,
    test_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    assignment = db.get(TestAssignment, test_id)
    if not assignment or assignment.pipeline_id != pipeline_id:
        return HTMLResponse("Not found", status_code=404)

    if assignment.status in ("pending", "opened"):
        assignment.status = "cancelled"
        db.add(assignment)
        db.commit()
        asyncio.create_task(sync_hub.broadcast("tests", "update", str(test_id), {"id": str(test_id), "status": "cancelled"}))

    if request.headers.get("HX-Request"):
        return HTMLResponse("", headers={"HX-Trigger": "toast:Test cancelled"})

    return RedirectResponse(f"/pipeline/{pipeline_id}", status_code=303)


@router.post("/pipeline/{pipeline_id}/test/{test_id}/delete")
async def delete_test_assignment(
    request: Request,
    pipeline_id: int,
    test_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    assignment = db.get(TestAssignment, test_id)
    if not assignment or assignment.pipeline_id != pipeline_id:
        return HTMLResponse("Not found", status_code=404)

    assignment.deleted_at = datetime.utcnow()
    db.add(assignment)
    db.commit()
    asyncio.create_task(sync_hub.broadcast("tests", "delete", str(test_id)))

    if request.headers.get("HX-Request"):
        resp = HTMLResponse("")
        resp.headers["HX-Trigger"] = json_mod.dumps({"undoable-delete": {"type": "test", "id": str(test_id), "label": assignment.title}, "toast": {"message": "Test deleted", "severity": ""}})
        return resp

    return RedirectResponse(f"/pipeline/{pipeline_id}", status_code=303)


# --- Review Batch endpoints ---


@router.get("/review-batch/new", response_class=HTMLResponse)
async def review_batch_new_form(
    request: Request,
    job_id: str = "",
    next: str = None,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    jobs = db.exec(select(Job).where(Job.status == "open", Job.title != "_Unassigned", not_deleted(Job)).order_by(Job.title)).all()
    return _render(request, "review_batch_new.html", {
        "admin": admin,
        "jobs": jobs,
        "prefill_job_id": int(job_id) if job_id else None,
        "next": next,
    })


@router.post("/review-batch/new")
async def review_batch_new_submit(
    request: Request,
    reviewer_name: str = Form(...),
    job_id: int = Form(...),
    confirm: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    import secrets

    job = db.get(Job, job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)

    bu = db.get(BusinessUnit, job.business_unit_id)

    # Check for existing batches with same job
    existing = db.exec(
        select(ReviewBatch).where(ReviewBatch.job_id == job_id)
    ).all()

    if existing and confirm != "yes":
        jobs = db.exec(select(Job).where(Job.status == "open", Job.title != "_Unassigned", not_deleted(Job)).order_by(Job.title)).all()
        return _render(request, "review_batch_new.html", {
            "admin": admin,
            "jobs": jobs,
            "prefill_job_id": job_id,
            "prefill_reviewer": reviewer_name,
            "existing_batches": existing,
        })

    token = secrets.token_urlsafe(16)
    batch = ReviewBatch(
        token=token,
        reviewer_name=reviewer_name,
        job_id=job_id,
        position=job.position,
        business_unit=bu.name if bu else "",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    return _render(request, "review_batch_created.html", {
        "admin": admin,
        "batch": batch,
        "link": f"{request.base_url}r/{token}",
    })


@router.get("/review-batches", response_class=HTMLResponse)
async def review_batches_list(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
):
    return _render(request, "review_batches_list.html", {"admin": admin})


# --- Export endpoints ---


@router.get("/pipeline/{pipeline_id}/export/pdf")
async def pipeline_export_pdf(
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from app.export import render_pdf

    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return HTMLResponse("Not found", status_code=404)
    candidate = db.get(Candidate, pipeline.candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    ctx = _pipeline_detail_context(db, pipeline, candidate)
    ctx["now"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    pdf_bytes = render_pdf("export/pipeline_pdf.html", ctx)

    filename = f"pipeline_{candidate.name.replace(' ', '_')}_{pipeline.position or 'export'}.pdf"
    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pipeline/{pipeline_id}/export/csv")
async def pipeline_export_csv(
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from app.export import pipeline_csv

    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return HTMLResponse("Not found", status_code=404)
    candidate = db.get(Candidate, pipeline.candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    ctx = _pipeline_detail_context(db, pipeline, candidate)
    csv_content = pipeline_csv(pipeline, candidate, ctx["session_data"], ctx.get("test_assignments"))

    filename = f"pipeline_{candidate.name.replace(' ', '_')}_{pipeline.position or 'export'}.csv"
    return FastAPIResponse(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pipeline/{pipeline_id}/score/export/pdf")
async def scorecard_export_pdf(
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from app.export import render_pdf

    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return HTMLResponse("Not found", status_code=404)
    candidate = db.get(Candidate, pipeline.candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    ctx = _pipeline_detail_context(db, pipeline, candidate)
    ctx["now"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    pdf_bytes = render_pdf("export/scorecard_pdf.html", ctx)

    filename = f"scorecard_{candidate.name.replace(' ', '_')}_{pipeline.position or 'export'}.pdf"
    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pipeline/{pipeline_id}/score/export/csv")
async def scorecard_export_csv(
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from app.export import scorecard_csv

    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return HTMLResponse("Not found", status_code=404)
    candidate = db.get(Candidate, pipeline.candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    ctx = _pipeline_detail_context(db, pipeline, candidate)
    csv_content = scorecard_csv(
        ctx["hr_data"], ctx["culture_data"],
        ctx["hr_dimensions"], ctx["culture_dimensions"],
        ctx["hr_avg"], ctx["culture_avg"],
        candidate, pipeline,
    )

    filename = f"scorecard_{candidate.name.replace(' ', '_')}_{pipeline.position or 'export'}.csv"
    return FastAPIResponse(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )