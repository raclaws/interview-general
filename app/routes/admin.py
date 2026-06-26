import json
import secrets
import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, func, col

from app.database import get_session
from app.auth import get_current_admin
from app.models import AdminUser, Candidate, CandidatePipeline, InterviewSession, SessionInterviewer, Response, ResponseScore, Template, TemplateSection, PIPELINE_ENDED_STAGES, TableView, Comment
from app.nocodb import search_candidates, fetch_candidate
from app.llm import generate_summary_dynamic, get_llm_config, set_setting, DEFAULT_SYSTEM_PROMPT
from app.routes.sync import hub as sync_hub
from app.activity import record_activity
from app.helpers import render_gone

router = APIRouter()


POSITIONS = [
    "Data Analyst", "Data Engineer", "Data Scientist",
    "Machine Learning Engineer / AI Engineer", "Data Quality Control",
    "Data Governance", "Fullstack Developer", "QA Engineer",
    "Project Manager", "CRM StrategistC", "CRM Operation",
    "CRM Assistant", "Account Manager", "Business Analyst",
    "Digital Marketing", "Design Graphic", "Other"
]

BUSINESS_UNITS = ["Markethac", "APEX", "EXONIA", "1011", "R&D", "Group Support", "LUPIN"]


def _generate_token() -> str:
    return secrets.token_urlsafe(16)


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    from app.models import Job, TestAssignment

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    week_ago = datetime.utcnow() - timedelta(days=7)
    stale_cutoff = datetime.utcnow() - timedelta(days=14)

    # Stats
    open_jobs = db.exec(select(func.count(Job.id)).where(Job.status == "open")).one()
    active_pipelines = db.exec(
        select(func.count(CandidatePipeline.id)).where(
            col(CandidatePipeline.stage).notin_(PIPELINE_ENDED_STAGES)
        )
    ).one()
    pending_sessions = db.exec(
        select(func.count(InterviewSession.id)).where(InterviewSession.status == "pending")
    ).one()
    completed_this_week = db.exec(
        select(func.count(InterviewSession.id)).where(
            InterviewSession.status == "completed",
            col(InterviewSession.created_at) >= week_ago,
        )
    ).one()

    # Attention: overdue interviews
    overdue_sessions = db.exec(
        select(InterviewSession).where(
            InterviewSession.status == "pending",
            col(InterviewSession.interview_date) < today_str,
            col(InterviewSession.interview_date).isnot(None),
        ).order_by(InterviewSession.interview_date).limit(5)
    ).all()

    # Attention: tests past deadline
    overdue_tests = db.exec(
        select(TestAssignment).where(
            TestAssignment.status.in_(["pending", "opened"]),
            col(TestAssignment.deadline).isnot(None),
            col(TestAssignment.deadline) < datetime.utcnow(),
        ).limit(5)
    ).all()

    # Attention: stale pipelines (non-terminal, not updated in 14+ days)
    stale_pipelines = db.exec(
        select(CandidatePipeline).where(
            col(CandidatePipeline.stage).notin_(PIPELINE_ENDED_STAGES),
            col(CandidatePipeline.updated_at) < stale_cutoff,
        ).order_by(CandidatePipeline.updated_at).limit(5)
    ).all()
    stale_candidates = {}
    if stale_pipelines:
        cids = [p.candidate_id for p in stale_pipelines]
        candidates = db.exec(select(Candidate).where(col(Candidate.id).in_(cids))).all()
        stale_candidates = {c.id: c.name for c in candidates}

    # Upcoming interviews
    upcoming_sessions = db.exec(
        select(InterviewSession).where(
            InterviewSession.status == "pending",
            col(InterviewSession.interview_date) >= today_str,
        ).order_by(InterviewSession.interview_date).limit(10)
    ).all()
    upcoming = []
    for s in upcoming_sessions:
        interviewers = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        upcoming.append({"session": s, "interviewers": interviewers})

    # Recent activity (last 5 pipeline updates)
    recent_pipelines = db.exec(
        select(CandidatePipeline).order_by(col(CandidatePipeline.updated_at).desc()).limit(5)
    ).all()
    recent_activity = []
    if recent_pipelines:
        cids = [p.candidate_id for p in recent_pipelines]
        candidates = db.exec(select(Candidate).where(col(Candidate.id).in_(cids))).all()
        cmap = {c.id: c.name for c in candidates}
        for p in recent_pipelines:
            recent_activity.append({
                "name": cmap.get(p.candidate_id, "—"),
                "stage": p.stage,
                "display_name": p.display_name or "—",
                "updated_at": p.updated_at,
                "pipeline_id": p.id,
            })

    return _render(request, "dashboard.html", {
        "admin": admin,
        "open_jobs": open_jobs,
        "active_pipelines": active_pipelines,
        "pending_sessions": pending_sessions,
        "completed_this_week": completed_this_week,
        "overdue_sessions": overdue_sessions,
        "overdue_tests": overdue_tests,
        "stale_pipelines": stale_pipelines,
        "stale_candidates": stale_candidates,
        "upcoming": upcoming,
        "recent_activity": recent_activity,
    })


@router.get("/peek/{entity_type}/{entity_id}", response_class=HTMLResponse)
async def peek_panel(
    request: Request,
    entity_type: str,
    entity_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from app.models import Job, Comment, Candidate, TestAssignment

    trail = db.exec(
        select(Comment).where(
            Comment.entity_type == entity_type,
            Comment.entity_id == entity_id,
        ).order_by(Comment.created_at)
    ).all()

    title = ""
    summary = {}

    if entity_type == "pipeline":
        p = db.get(CandidatePipeline, entity_id)
        if not p:
            return HTMLResponse("Not found", status_code=404)
        c = db.get(Candidate, p.candidate_id)
        j = db.get(Job, p.job_id) if p.job_id else None
        title = c.name if c else "Pipeline"
        summary = {
            "Job": j.title if j else "—",
            "Stage": p.stage.replace("_", " ").title(),
            "Updated": p.updated_at.strftime("%b %d, %Y"),
        }
    elif entity_type == "job":
        j = db.get(Job, entity_id)
        if not j:
            return HTMLResponse("Not found", status_code=404)
        title = j.title
        summary = {
            "Status": j.status.title(),
            "Position": j.position,
            "Level": j.level,
            "Headcount": str(j.headcount),
        }
    elif entity_type == "session":
        s = db.get(InterviewSession, entity_id)
        if not s:
            return HTMLResponse("Not found", status_code=404)
        title = f"Session #{s.id}"
        summary = {
            "Candidate": s.snapshot.get("name", "—"),
            "Template": s.job_title or "—",
            "Status": s.status.title(),
            "Date": s.interview_date or "—",
        }
    elif entity_type == "candidate":
        c = db.get(Candidate, entity_id)
        if not c:
            return HTMLResponse("Not found", status_code=404)
        title = c.name
        summary = {
            "Email": c.email,
            "Position": c.current_position or "—",
            "Experience": c.yoe or "—",
        }
    else:
        return HTMLResponse("Invalid entity type", status_code=400)

    return _render(request, "partials/peek_panel.html", {
        "title": title,
        "summary": summary,
        "trail": trail,
        "entity_type": entity_type,
        "entity_id": entity_id,
    })


@router.post("/peek/{entity_type}/{entity_id}/comment", response_class=HTMLResponse)
async def peek_add_comment(
    request: Request,
    entity_type: str,
    entity_id: int,
    body: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from app.models import Comment

    if not body.strip():
        return HTMLResponse("")

    comment = Comment(
        entity_type=entity_type,
        entity_id=entity_id,
        kind="comment",
        body=body.strip(),
        author=admin.username,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return _render(request, "partials/trail_item.html", {"item": comment})


@router.get("/peek/{entity_type}/{entity_id}/version")
async def peek_version(
    entity_type: str,
    entity_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from app.models import Job
    from fastapi.responses import JSONResponse

    updated_at = None
    if entity_type == "pipeline":
        e = db.get(CandidatePipeline, entity_id)
        if e:
            updated_at = e.updated_at
    elif entity_type == "job":
        e = db.get(Job, entity_id)
        if e:
            updated_at = e.updated_at
    elif entity_type == "session":
        e = db.get(InterviewSession, entity_id)
        if e:
            updated_at = e.created_at
    elif entity_type == "candidate":
        e = db.get(Candidate, entity_id)
        if e:
            updated_at = e.updated_at

    ts = int(updated_at.timestamp() * 1000) if updated_at else 0
    return JSONResponse({"ts": ts})


@router.get("/sessions", response_class=HTMLResponse)
async def sessions_list(request: Request, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    templates = db.exec(select(Template)).all()
    template_names = sorted(set(t.name for t in templates))
    return _render(request, "sessions_list.html", {"admin": admin, "template_names": template_names})


@router.get("/tests", response_class=HTMLResponse)
async def tests_list(request: Request, admin: AdminUser = Depends(get_current_admin)):
    return _render(request, "tests_list.html", {"admin": admin})


@router.post("/views")
async def create_view(request: Request, page: str = Form(...), name: str = Form(...), config: str = Form(""), admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    view = TableView(page=page, name=name, config=config)
    db.add(view)
    db.commit()
    db.refresh(view)
    return HTMLResponse(f'<span class="view-pill" data-view-id="{view.id}" data-view-config=\'{view.config}\'>{view.name} <button type="button" class="view-del">×</button></span>')


@router.delete("/views/{view_id}")
async def delete_view(view_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    view = db.get(TableView, view_id)
    if view:
        db.delete(view)
        db.commit()
    return HTMLResponse("")


@router.get("/session/new", response_class=HTMLResponse)
async def session_new_form(request: Request, candidate_id: int = None, pipeline_id: int = None, next: str = None, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    templates = db.exec(select(Template).order_by(Template.name)).all()
    prefill_candidate = None
    prefill_pipeline = None
    prefill_job = None
    if candidate_id:
        prefill_candidate = db.get(Candidate, candidate_id)
    if pipeline_id:
        prefill_pipeline = db.get(CandidatePipeline, pipeline_id)
        if prefill_pipeline and prefill_pipeline.job_id:
            from app.models import Job
            prefill_job = db.get(Job, prefill_pipeline.job_id)
        if not prefill_candidate and prefill_pipeline:
            prefill_candidate = db.get(Candidate, prefill_pipeline.candidate_id)

    # If no pipeline context, provide a pipeline picker
    pipelines = []
    if not pipeline_id:
        from app.models import PIPELINE_ENDED_STAGES
        results = db.exec(
            select(CandidatePipeline, Candidate).join(Candidate, CandidatePipeline.candidate_id == Candidate.id)
            .where(CandidatePipeline.stage.notin_(PIPELINE_ENDED_STAGES))
            .order_by(CandidatePipeline.updated_at.desc())
        ).all()
        pipelines = [{"pipeline": p, "candidate": c} for p, c in results]

    return _render(request, "session_new.html", {
        "admin": admin,
        "templates": templates,
        "prefill_candidate": prefill_candidate,
        "prefill_pipeline": prefill_pipeline,
        "prefill_pipeline_id": pipeline_id,
        "prefill_job": prefill_job,
        "pipelines": pipelines,
        "next": next,
    })


@router.post("/session/new")
async def session_new_submit(
    request: Request,
    candidate_id: int = Form(None),
    pipeline_id: int = Form(None),
    job_title: str = Form(""),
    interviewer_names: str = Form(...),
    interview_date: str = Form(""),
    show_salary: str = Form(""),
    template_id: int = Form(...),
    entry_mode: str = Form("pipeline"),
    manual_name: str = Form(""),
    manual_email: str = Form(""),
    manual_position: str = Form(""),
    manual_yoe: str = Form(""),
    manual_languages: str = Form(""),
    manual_cloud: str = Form(""),
    manual_tools: str = Form(""),
    manual_working_arrangement: str = Form(""),
    manual_current_salary: str = Form(""),
    manual_expected_salary: str = Form(""),
    manual_notice_period: str = Form(""),
    manual_cv_link: str = Form(""),
    next: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    is_htmx = request.headers.get("HX-Request") == "true"

    if entry_mode == "pipeline":
        if not pipeline_id:
            if is_htmx:
                return HTMLResponse('<div class="form-error">Please select a pipeline.</div>')
            return RedirectResponse("/session/new?error=no_pipeline", status_code=303)
        pipeline_record = db.get(CandidatePipeline, pipeline_id)
        if not pipeline_record:
            if is_htmx:
                return HTMLResponse('<div class="form-error">Pipeline not found.</div>')
            return RedirectResponse("/session/new?error=pipeline_not_found", status_code=303)
        candidate_record = db.get(Candidate, pipeline_record.candidate_id)
        if not candidate_record:
            if is_htmx:
                return HTMLResponse('<div class="form-error">Candidate not found.</div>')
            return RedirectResponse("/session/new?error=candidate_not_found", status_code=303)
        snapshot = candidate_record.to_snapshot()
        candidate_id = candidate_record.id
        if not job_title.strip():
            job_title = snapshot.get("current_position", "")
    elif entry_mode == "nocodb":
        if not candidate_id:
            if is_htmx:
                return HTMLResponse('<div class="form-error">Please select a candidate.</div>')
            return RedirectResponse("/session/new?error=no_candidate_selected", status_code=303)
        snapshot = await fetch_candidate(candidate_id)
        if not snapshot:
            if is_htmx:
                return HTMLResponse('<div class="form-error">Candidate not found in NocoDB.</div>')
            return RedirectResponse("/session/new?error=candidate_not_found", status_code=303)
        # Pull job_title from snapshot if not provided
        if not job_title.strip():
            job_title = snapshot.get("current_position", "")
    else:
        if not manual_name.strip():
            if is_htmx:
                return HTMLResponse('<div class="form-error">Candidate name is required.</div>')
            return RedirectResponse("/session/new?error=name_required", status_code=303)
        snapshot = {
            "name": manual_name.strip(),
            "phone": "",
            "email": manual_email.strip(),
            "current_position": manual_position.strip(),
            "yoe": manual_yoe.strip(),
            "languages": manual_languages.strip(),
            "cloud": manual_cloud.strip(),
            "tools": manual_tools.strip(),
            "working_arrangement": manual_working_arrangement.strip(),
            "current_salary": manual_current_salary.strip(),
            "expected_salary": manual_expected_salary.strip(),
            "notice_period": manual_notice_period.strip(),
            "cv_link": manual_cv_link.strip(),
        }
        candidate_id = None

    if not snapshot or not snapshot.get("name", "").strip():
        if is_htmx:
            return HTMLResponse('<div class="form-error">Candidate information is required.</div>')
        return RedirectResponse("/session/new?error=no_candidate", status_code=303)

    if not interview_date.strip():
        if is_htmx:
            return HTMLResponse('<div class="form-error">Interview date is required.</div>')
        return RedirectResponse("/session/new?error=date_required", status_code=303)

    # Upsert candidate record
    candidate_record = None
    email = snapshot.get("email", "").strip()
    if email:
        candidate_record = db.exec(
            select(Candidate).where(Candidate.email == email)
        ).first()
    if candidate_record:
        candidate_record.name = snapshot.get("name", candidate_record.name)
        candidate_record.phone = snapshot.get("phone") or candidate_record.phone
        candidate_record.current_position = snapshot.get("current_position") or candidate_record.current_position
        candidate_record.yoe = snapshot.get("yoe") or candidate_record.yoe
        candidate_record.languages = snapshot.get("languages") or candidate_record.languages
        candidate_record.cloud = snapshot.get("cloud") or candidate_record.cloud
        candidate_record.tools = snapshot.get("tools") or candidate_record.tools
        candidate_record.working_arrangement = snapshot.get("working_arrangement") or candidate_record.working_arrangement
        candidate_record.current_salary = snapshot.get("current_salary") or candidate_record.current_salary
        candidate_record.expected_salary = snapshot.get("expected_salary") or candidate_record.expected_salary
        candidate_record.notice_period = snapshot.get("notice_period") or candidate_record.notice_period
        candidate_record.cv_link = snapshot.get("cv_link") or candidate_record.cv_link
        candidate_record.updated_at = datetime.utcnow()
        db.add(candidate_record)
        db.commit()
        db.refresh(candidate_record)
    elif snapshot.get("name", "").strip():
        candidate_record = Candidate(
            name=snapshot.get("name", "").strip(),
            email=email or f"{secrets.token_hex(4)}@placeholder.local",
            phone=snapshot.get("phone") or None,
            nocodb_id=candidate_id,
            current_position=snapshot.get("current_position") or None,
            yoe=snapshot.get("yoe") or None,
            languages=snapshot.get("languages") or None,
            cloud=snapshot.get("cloud") or None,
            tools=snapshot.get("tools") or None,
            working_arrangement=snapshot.get("working_arrangement") or None,
            current_salary=snapshot.get("current_salary") or None,
            expected_salary=snapshot.get("expected_salary") or None,
            notice_period=snapshot.get("notice_period") or None,
            cv_link=snapshot.get("cv_link") or None,
        )
        db.add(candidate_record)
        db.commit()
        db.refresh(candidate_record)

    # Create or link pipeline entry
    pipeline_record = None
    existing_sessions = []
    if pipeline_id:
        pipeline_record = db.get(CandidatePipeline, pipeline_id)
    elif candidate_record:
        # Reuse existing active pipeline for this candidate (first available)
        pipeline_record = db.exec(
            select(CandidatePipeline).where(
                CandidatePipeline.candidate_id == candidate_record.id,
                CandidatePipeline.stage.notin_(PIPELINE_ENDED_STAGES),
            )
        ).first()
        if not pipeline_record:
            pipeline_record = CandidatePipeline(
                candidate_id=candidate_record.id,
                display_name=f"{candidate_record.name} — interview",
                stage="interview",
            )
            db.add(pipeline_record)
            db.commit()
            db.refresh(pipeline_record)
        db.refresh(pipeline_record)

    # Validate session limits per pipeline
    if pipeline_record:
        existing_sessions = db.exec(
            select(InterviewSession).where(InterviewSession.pipeline_id == pipeline_record.id)
        ).all()
        if len(existing_sessions) >= 4:
            if is_htmx:
                return HTMLResponse('<div class="form-error">Maximum 4 sessions per pipeline reached.</div>')
            return RedirectResponse("/session/new?error=max_sessions_reached", status_code=303)
        hr_template = db.exec(select(Template).where(Template.name == "HR Interview")).first()
        if hr_template and template_id == hr_template.id:
            hr_existing = [s for s in existing_sessions if s.template_id == hr_template.id]
            if hr_existing:
                s = hr_existing[0]
                return _render(request, "session_hr_conflict.html", {
                    "admin": admin,
                    "existing_session": s,
                    "pipeline": pipeline_record,
                    "candidate_id": candidate_record.id if candidate_record else None,
                    "candidate_name": snapshot.get("name", "Unknown"),
                })

    names = [n.strip() for n in interviewer_names.split(",") if n.strip()]
    if not names:
        if is_htmx:
            return HTMLResponse('<div class="form-error">At least one interviewer name is required.</div>')
        return RedirectResponse("/session/new?error=no_interviewers", status_code=303)

    # Job title is plain — no auto-differentiation (pipeline name handles that)
    auto_title = job_title.strip() if job_title.strip() else "N/A"

    # Derive position/BU from pipeline's job if available
    final_position_val = None
    final_bu_val = None
    if pipeline_record and pipeline_record.job_id:
        from app.models import Job, BusinessUnit
        job = db.get(Job, pipeline_record.job_id)
        if job:
            auto_title = auto_title if auto_title != "N/A" else job.title
            final_position_val = job.position
            bu = db.get(BusinessUnit, job.business_unit_id)
            final_bu_val = bu.name if bu else None

    session = InterviewSession(
        template_id=template_id,
        candidate_id=candidate_record.id if candidate_record else None,
        pipeline_id=pipeline_record.id if pipeline_record else None,
        candidate_snapshot=json.dumps(snapshot),
        job_title=auto_title,
        position=final_position_val,
        business_unit=final_bu_val,
        interview_date=interview_date if interview_date.strip() else None,
        show_salary=show_salary.lower() in ("on", "true", "1", "yes"),
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    for name in names:
        interviewer = SessionInterviewer(
            session_id=session.id,
            interviewer_name=name,
            token=_generate_token(),
            status="pending",
        )
        db.add(interviewer)
    db.commit()

    # Activity trail
    template_name = db.get(Template, session.template_id).name if session.template_id else "—"
    record_activity(db, "session", session.id, f"Session created ({template_name})", pipeline_id=session.pipeline_id)
    db.commit()

    # Broadcast to sync clients
    interviewers = db.exec(select(SessionInterviewer).where(SessionInterviewer.session_id == session.id)).all()
    template = db.get(Template, session.template_id) if session.template_id else None
    pipeline = db.get(CandidatePipeline, session.pipeline_id) if session.pipeline_id else None
    from app.routes.sync import _serialize_session
    asyncio.create_task(sync_hub.broadcast("sessions", "insert", str(session.id), _serialize_session(session, interviewers, template, pipeline)))

    if is_htmx:
        redirect_to = next or f"/session/{session.id}"
        return HTMLResponse("", headers={"HX-Redirect": redirect_to})
    return RedirectResponse(next or f"/session/{session.id}", status_code=303)


@router.get("/session/{session_id}", response_class=HTMLResponse)
async def session_detail(
    request: Request,
    session_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    session = db.get(InterviewSession, session_id)
    if not session:
        return render_gone(request, "Session", "/sessions", "Interview")

    template = db.get(Template, session.template_id) if session.template_id else None
    sections = []
    if session.template_id:
        sections = db.exec(
            select(TemplateSection).where(TemplateSection.template_id == session.template_id).order_by(TemplateSection.order)
        ).all()

    interviewers = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.session_id == session.id)
    ).all()

    interviewer_data = []
    for iv in interviewers:
        response = db.exec(
            select(Response).where(Response.session_interviewer_id == iv.id)
        ).first()
        scores = {}
        if response:
            score_rows = db.exec(
                select(ResponseScore).where(ResponseScore.response_id == response.id)
            ).all()
            for sr in score_rows:
                scores[sr.section_id] = sr.value
        interviewer_data.append({"interviewer": iv, "response": response, "scores": scores})

    pipeline = db.get(CandidatePipeline, session.pipeline_id) if session.pipeline_id else None
    job = None
    if pipeline and pipeline.job_id:
        from app.models import Job
        job = db.get(Job, pipeline.job_id)

    return _render(request, "session_detail.html", {
        "session": session,
        "template": template,
        "sections": sections,
        "interviewer_data": interviewer_data,
        "pipeline": pipeline,
        "job": job,
        "admin": admin,
        "trail": db.exec(
            select(Comment).where(Comment.entity_type == "session", Comment.entity_id == session_id).order_by(Comment.created_at)
        ).all(),
    })


@router.post("/session/{session_id}/generate-summary")
async def generate_session_summary(
    request: Request,
    session_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    session = db.get(InterviewSession, session_id)
    if not session:
        return HTMLResponse("Not found", status_code=404)

    sections = []
    if session.template_id:
        sections = db.exec(
            select(TemplateSection).where(TemplateSection.template_id == session.template_id).order_by(TemplateSection.order)
        ).all()

    interviewers = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.session_id == session.id)
    ).all()

    responses_data = []
    for iv in interviewers:
        response = db.exec(
            select(Response).where(Response.session_interviewer_id == iv.id)
        ).first()
        if response:
            score_rows = db.exec(
                select(ResponseScore).where(ResponseScore.response_id == response.id)
            ).all()
            scores = {sr.section_id: sr.value for sr in score_rows}
            responses_data.append({
                "interviewer_name": iv.interviewer_name,
                "scores": scores,
                "free_text": response.free_text,
            })

    if not responses_data:
        return RedirectResponse(f"/session/{session_id}", status_code=303)

    snapshot = session.snapshot
    summary = await generate_summary_dynamic(
        candidate_name=snapshot.get("name", "Unknown"),
        job_title=session.job_title,
        sections=sections,
        responses_data=responses_data,
    )

    session.aggregate_summary = summary
    db.add(session)
    db.commit()

    # If HTMX request, return just the partial
    if request.headers.get("HX-Request"):
        return _render(request, "partials/summary_block.html", {"session": session})

    return RedirectResponse(f"/session/{session_id}", status_code=303)


@router.post("/session/{session_id}/cancel")
async def cancel_session(
    request: Request,
    session_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    session = db.get(InterviewSession, session_id)
    if not session:
        return HTMLResponse("Not found", status_code=404)
    if session.status == "pending":
        session.status = "cancelled"
        interviewers = db.exec(
            select(SessionInterviewer).where(
                SessionInterviewer.session_id == session_id,
                SessionInterviewer.status == "pending",
            )
        ).all()
        for iv in interviewers:
            iv.status = "cancelled"
            db.add(iv)
        record_activity(db, "session", session_id, "Session cancelled", pipeline_id=session.pipeline_id)
        db.add(session)
        db.commit()
        asyncio.create_task(sync_hub.broadcast("sessions", "update", str(session_id), {"status": "cancelled"}))
    if request.headers.get("HX-Request") == "true":
        resp = HTMLResponse("")
        resp.headers["HX-Trigger"] = json.dumps({"toast": {"message": "Session cancelled", "severity": "warning"}})
        resp.headers["HX-Refresh"] = "true"
        return resp
    return RedirectResponse(f"/session/{session_id}", status_code=303)


@router.post("/session/{session_id}/delete")
async def delete_session(
    request: Request,
    session_id: int,
    next: str = None,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    session = db.get(InterviewSession, session_id)
    if not session:
        return HTMLResponse("Not found", status_code=404)

    # Delete related responses and scores
    interviewers = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.session_id == session.id)
    ).all()
    for iv in interviewers:
        response = db.exec(
            select(Response).where(Response.session_interviewer_id == iv.id)
        ).first()
        if response:
            scores = db.exec(
                select(ResponseScore).where(ResponseScore.response_id == response.id)
            ).all()
            for s in scores:
                db.delete(s)
            db.delete(response)
        db.delete(iv)

    db.delete(session)
    db.commit()
    asyncio.create_task(sync_hub.broadcast("sessions", "delete", str(session_id)))
    if request.headers.get("HX-Request") == "true":
        resp = HTMLResponse("")
        current_path = request.headers.get("HX-Current-URL", "").split("?")[0].rstrip("/")
        if current_path.endswith(f"/session/{session_id}"):
            resp.headers["HX-Redirect"] = "/sessions"
        return resp
    return RedirectResponse(next or "/sessions", status_code=303)


@router.get("/session/{session_id}/edit", response_class=HTMLResponse)
async def session_edit_form(
    request: Request,
    session_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    session = db.get(InterviewSession, session_id)
    if not session:
        return HTMLResponse("Not found", status_code=404)
    interviewers = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.session_id == session.id)
    ).all()
    return _render(request, "session_edit.html", {
        "session": session,
        "interviewers": interviewers,
        "admin": admin,
    })


@router.post("/session/{session_id}/edit")
async def session_edit_submit(
    request: Request,
    session_id: int,
    job_title: str = Form(...),
    interview_date: str = Form(""),
    show_salary: str = Form(""),
    new_interviewers: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    session = db.get(InterviewSession, session_id)
    if not session:
        return HTMLResponse("Not found", status_code=404)

    session.job_title = job_title
    session.interview_date = interview_date if interview_date.strip() else None
    session.show_salary = show_salary.lower() in ("on", "true", "1", "yes")
    db.add(session)

    if new_interviewers.strip():
        names = [n.strip() for n in new_interviewers.split(",") if n.strip()]
        for name in names:
            interviewer = SessionInterviewer(
                session_id=session.id,
                interviewer_name=name,
                token=_generate_token(),
                status="pending",
            )
            db.add(interviewer)
        session.status = "pending"
        session.aggregate_summary = ""
        db.add(session)

    db.commit()
    return RedirectResponse(f"/session/{session_id}", status_code=303)


@router.get("/templates", response_class=HTMLResponse)
async def templates_list(request: Request, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    templates = db.exec(select(Template).order_by(Template.name)).all()
    template_data = []
    for t in templates:
        sections = db.exec(select(TemplateSection).where(TemplateSection.template_id == t.id)).all()
        template_data.append({"template": t, "section_count": len(sections)})
    return _render(request, "templates_list.html", {"template_data": template_data, "admin": admin})


@router.get("/templates/{template_id}", response_class=HTMLResponse)
async def template_detail(
    request: Request,
    template_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    template = db.get(Template, template_id)
    if not template:
        return HTMLResponse("Not found", status_code=404)
    sections = db.exec(
        select(TemplateSection).where(TemplateSection.template_id == template.id).order_by(TemplateSection.order)
    ).all()
    return _render(request, "template_detail.html", {"template": template, "sections": sections, "admin": admin})


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, admin: AdminUser = Depends(get_current_admin)):
    base_url, api_key, model, system_prompt = get_llm_config()
    from app.llm import get_llm_params
    temperature, max_tokens = get_llm_params()
    masked_key = ("*" * (len(api_key) - 4) + api_key[-4:]) if len(api_key) > 4 else "*" * len(api_key)
    ctx = {
        "admin": admin,
        "base_url": base_url,
        "api_key_masked": masked_key,
        "model": model,
        "system_prompt": system_prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "active_tab": "llm",
        "tab_content": "settings_llm.html",
    }
    if request.headers.get("HX-Request"):
        return _render(request, "settings_llm.html", ctx)
    return _render(request, "settings_layout.html", ctx)


@router.post("/settings")
async def settings_save(
    request: Request,
    llm_base_url: str = Form(...),
    llm_api_key: str = Form(""),
    llm_model: str = Form(...),
    llm_system_prompt: str = Form(...),
    llm_temperature: str = Form("0.3"),
    llm_max_tokens: str = Form("700"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    set_setting("llm_base_url", llm_base_url)
    if llm_api_key and not all(c == "*" for c in llm_api_key):
        set_setting("llm_api_key", llm_api_key)
    set_setting("llm_model", llm_model)
    set_setting("llm_system_prompt", llm_system_prompt)
    set_setting("llm_temperature", llm_temperature)
    set_setting("llm_max_tokens", llm_max_tokens)
    return RedirectResponse("/settings", status_code=303)


@router.get("/api/candidates")
async def api_candidates(q: str = "", db: Session = Depends(get_session)):
    if len(q) < 2:
        return []
    from app.models import Candidate
    candidates = db.exec(
        select(Candidate).where(
            Candidate.name.ilike(f"%{q}%") | Candidate.email.ilike(f"%{q}%")
        ).limit(10)
    ).all()
    return [{"id": c.id, "name": c.name, "email": c.email or ""} for c in candidates]


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return _render(request, "login.html", {"error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    from app.auth import verify_password, create_session_cookie, COOKIE_NAME

    admin = db.exec(select(AdminUser).where(AdminUser.username == username)).first()
    if not admin or not verify_password(password, admin.hashed_password):
        return _render(request, "login.html", {"error": "Invalid credentials"})
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(COOKIE_NAME, create_session_cookie(username), httponly=True)
    return response


@router.post("/logout")
async def logout():
    from app.auth import COOKIE_NAME

    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
