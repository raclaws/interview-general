import json
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, func, col

from app.database import get_session
from app.auth import get_current_admin
from app.models import AdminUser, Candidate, CandidatePipeline, InterviewSession, SessionInterviewer, Response, ResponseScore, Template, TemplateSection, PIPELINE_ENDED_STAGES
from app.nocodb import search_candidates, fetch_candidate
from app.llm import generate_summary_dynamic, get_llm_config, set_setting, DEFAULT_SYSTEM_PROMPT

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
    total_sessions = db.exec(select(func.count(InterviewSession.id))).one()
    pending_sessions = db.exec(
        select(func.count(InterviewSession.id)).where(InterviewSession.status == "pending")
    ).one()
    week_ago = datetime.utcnow() - timedelta(days=7)
    completed_this_week = db.exec(
        select(func.count(InterviewSession.id)).where(
            InterviewSession.status == "completed",
            col(InterviewSession.created_at) >= week_ago,
        )
    ).one()
    active_candidates = db.exec(
        select(func.count(func.distinct(CandidatePipeline.candidate_id))).where(
            col(CandidatePipeline.stage).notin_(PIPELINE_ENDED_STAGES)
        )
    ).one()

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
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

    return _render(request, "dashboard.html", {
        "admin": admin,
        "total_sessions": total_sessions,
        "pending_sessions": pending_sessions,
        "completed_this_week": completed_this_week,
        "active_candidates": active_candidates,
        "upcoming": upcoming,
    })


@router.get("/sessions", response_class=HTMLResponse)
async def sessions_list(request: Request, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    sessions = db.exec(
        select(InterviewSession).order_by(InterviewSession.created_at.desc())
    ).all()
    session_data = []
    for s in sessions:
        interviewers = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        total = len(interviewers)
        completed = len([i for i in interviewers if i.status == "completed"])
        template = db.get(Template, s.template_id) if s.template_id else None
        pipeline = db.get(CandidatePipeline, s.pipeline_id) if s.pipeline_id else None
        session_data.append({"session": s, "interviewers": interviewers, "total": total, "completed": completed, "template": template, "pipeline": pipeline})
    return _render(request, "sessions_list.html", {"session_data": session_data, "admin": admin})


@router.get("/session/new", response_class=HTMLResponse)
async def session_new_form(request: Request, candidate_id: int = None, pipeline_id: int = None, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    templates = db.exec(select(Template).order_by(Template.name)).all()
    prefill_candidate = None
    prefill_pipeline = None
    if candidate_id:
        prefill_candidate = db.get(Candidate, candidate_id)
    if pipeline_id:
        prefill_pipeline = db.get(CandidatePipeline, pipeline_id)
    return _render(request, "session_new.html", {
        "admin": admin,
        "templates": templates,
        "positions": POSITIONS,
        "business_units": BUSINESS_UNITS,
        "prefill_candidate": prefill_candidate,
        "prefill_pipeline": prefill_pipeline,
        "prefill_pipeline_id": pipeline_id,
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
    position: str = Form(""),
    position_other: str = Form(""),
    business_unit: str = Form(""),
    entry_mode: str = Form("nocodb"),
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
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    is_htmx = request.headers.get("HX-Request") == "true"

    if entry_mode == "nocodb":
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

    # Handle "Other" position
    final_position = position_other.strip() if position == "Other" and position_other.strip() else position.strip()

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
        pos = final_position or None
        bu = business_unit.strip() if business_unit.strip() else None
        # Reuse existing active pipeline with same position + BU for this candidate
        pipeline_record = db.exec(
            select(CandidatePipeline).where(
                CandidatePipeline.candidate_id == candidate_record.id,
                CandidatePipeline.position == pos,
                CandidatePipeline.business_unit == bu,
                CandidatePipeline.stage.notin_(PIPELINE_ENDED_STAGES),
            )
        ).first()
        if not pipeline_record:
            mmyy = datetime.utcnow().strftime("%m%y")
            existing_pipelines = db.exec(
                select(CandidatePipeline).where(
                    CandidatePipeline.candidate_id == candidate_record.id,
                    CandidatePipeline.position == pos,
                    CandidatePipeline.business_unit == bu,
                )
            ).all()
            same_month = [p for p in existing_pipelines if p.created_at.strftime("%m%y") == mmyy]
            seq = len(same_month) + 1
            display_name = f"{pos or 'N/A'} {mmyy} #{seq} — {bu or 'N/A'}"

            pipeline_record = CandidatePipeline(
                candidate_id=candidate_record.id,
                display_name=display_name,
                position=pos,
                business_unit=bu,
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

    session = InterviewSession(
        template_id=template_id,
        candidate_id=candidate_record.id if candidate_record else None,
        pipeline_id=pipeline_record.id if pipeline_record else None,
        candidate_snapshot=json.dumps(snapshot),
        job_title=auto_title,
        position=final_position if final_position else None,
        business_unit=business_unit.strip() if business_unit.strip() else None,
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

    if is_htmx:
        return HTMLResponse("", headers={"HX-Redirect": f"/session/{session.id}"})
    return RedirectResponse("/sessions", status_code=303)


@router.get("/session/{session_id}", response_class=HTMLResponse)
async def session_detail(
    request: Request,
    session_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    session = db.get(InterviewSession, session_id)
    if not session:
        return HTMLResponse("Not found", status_code=404)

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

    return _render(request, "session_detail.html", {
        "session": session,
        "template": template,
        "sections": sections,
        "interviewer_data": interviewer_data,
        "pipeline": pipeline,
        "admin": admin,
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
        db.add(session)
        db.commit()
    if request.headers.get("HX-Request") == "true":
        return HTMLResponse(
            f'<span class="badge badge-cancelled">cancelled</span>',
            headers={"HX-Reswap": "innerHTML", "HX-Retarget": f"#status-{session_id}", "HX-Trigger": "toast:Session cancelled"},
        )
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
    if request.headers.get("HX-Request") == "true":
        return HTMLResponse("")
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
        "positions": POSITIONS,
        "business_units": BUSINESS_UNITS,
    })


@router.post("/session/{session_id}/edit")
async def session_edit_submit(
    request: Request,
    session_id: int,
    job_title: str = Form(...),
    interview_date: str = Form(""),
    show_salary: str = Form(""),
    position: str = Form(""),
    business_unit: str = Form(""),
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
    session.position = position.strip() if position.strip() else None
    session.business_unit = business_unit.strip() if business_unit.strip() else None
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
    return _render(request, "settings.html", {
        "admin": admin,
        "base_url": base_url,
        "api_key_masked": masked_key,
        "model": model,
        "system_prompt": system_prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
    })


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
async def api_candidates(q: str = ""):
    if len(q) < 2:
        return []
    results = await search_candidates(q)
    return results


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
