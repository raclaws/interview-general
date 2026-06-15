import json
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import AdminUser, InterviewSession, SessionInterviewer, Response
from app.nocodb import search_candidates, fetch_candidate
from app.llm import generate_summary, generate_aggregate_summary, get_llm_config, set_setting, DEFAULT_SYSTEM_PROMPT

router = APIRouter()


def _generate_token() -> str:
    return secrets.token_urlsafe(16)


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
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
        session_data.append({"session": s, "interviewers": interviewers, "total": total, "completed": completed})
    return _render(request, "dashboard.html", {"session_data": session_data, "admin": admin})


@router.get("/session/new", response_class=HTMLResponse)
async def session_new_form(request: Request, admin: AdminUser = Depends(get_current_admin)):
    return _render(request, "session_new.html", {"admin": admin})


@router.post("/session/new")
async def session_new_submit(
    request: Request,
    candidate_id: int = Form(None),
    job_title: str = Form(...),
    round: str = Form(...),
    interviewer_names: str = Form(...),
    interview_date: str = Form(""),
    show_salary: str = Form(""),
    entry_mode: str = Form("nocodb"),
    manual_name: str = Form(""),
    manual_position: str = Form(""),
    manual_yoe: str = Form(""),
    manual_languages: str = Form(""),
    manual_cloud: str = Form(""),
    manual_tools: str = Form(""),
    manual_working_arrangement: str = Form(""),
    manual_current_salary: str = Form(""),
    manual_expected_salary: str = Form(""),
    manual_notice_period: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    if entry_mode == "nocodb":
        if not candidate_id:
            return RedirectResponse("/session/new?error=no_candidate_selected", status_code=303)
        snapshot = await fetch_candidate(candidate_id)
        if not snapshot:
            return RedirectResponse("/session/new?error=candidate_not_found", status_code=303)
    else:
        if not manual_name.strip():
            return RedirectResponse("/session/new?error=name_required", status_code=303)
        snapshot = {
            "name": manual_name.strip(),
            "phone": "",
            "email": "",
            "current_position": manual_position.strip(),
            "yoe": manual_yoe.strip(),
            "languages": manual_languages.strip(),
            "cloud": manual_cloud.strip(),
            "tools": manual_tools.strip(),
            "working_arrangement": manual_working_arrangement.strip(),
            "current_salary": manual_current_salary.strip(),
            "expected_salary": manual_expected_salary.strip(),
            "notice_period": manual_notice_period.strip(),
        }
        candidate_id = None

    # Parse interviewer names (comma-separated)
    names = [n.strip() for n in interviewer_names.split(",") if n.strip()]
    if not names:
        return RedirectResponse("/session/new?error=no_interviewers", status_code=303)

    session = InterviewSession(
        candidate_id=candidate_id,
        candidate_snapshot=json.dumps(snapshot),
        job_title=job_title,
        round=round,
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

    return RedirectResponse("/", status_code=303)


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
    interviewers = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.session_id == session.id)
    ).all()
    # Fetch responses for each interviewer
    interviewer_data = []
    for iv in interviewers:
        response = db.exec(
            select(Response).where(Response.session_interviewer_id == iv.id)
        ).first()
        interviewer_data.append({"interviewer": iv, "response": response})
    return _render(request, "session_detail.html", {
        "session": session,
        "interviewer_data": interviewer_data,
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

    interviewers = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.session_id == session.id)
    ).all()

    # Collect all responses
    responses_data = []
    for iv in interviewers:
        response = db.exec(
            select(Response).where(Response.session_interviewer_id == iv.id)
        ).first()
        if response:
            responses_data.append({
                "interviewer_name": iv.interviewer_name,
                "q1": response.q1,
                "q2": response.q2,
                "q3": response.q3,
                "q4": response.q4,
                "q5": response.q5,
                "free_text": response.free_text,
            })

    if not responses_data:
        return RedirectResponse(f"/session/{session_id}", status_code=303)

    snapshot = session.snapshot

    if len(responses_data) == 1:
        # Single evaluator — use original prompt
        r = responses_data[0]
        summary = await generate_summary(
            candidate_name=snapshot.get("name", "Unknown"),
            job_title=session.job_title,
            q1=r["q1"], q2=r["q2"], q3=r["q3"], q4=r["q4"],
            q5=r["q5"], free_text=r["free_text"],
        )
    else:
        # Multiple evaluators — cross-evaluator prompt
        summary = await generate_aggregate_summary(
            candidate_name=snapshot.get("name", "Unknown"),
            job_title=session.job_title,
            responses=responses_data,
        )

    session.aggregate_summary = summary
    db.add(session)
    db.commit()
    return RedirectResponse(f"/session/{session_id}", status_code=303)


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
    return _render(request, "session_edit.html", {"session": session, "interviewers": interviewers, "admin": admin})


@router.post("/session/{session_id}/edit")
async def session_edit_submit(
    request: Request,
    session_id: int,
    job_title: str = Form(...),
    round: str = Form(...),
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
    session.round = round
    session.interview_date = interview_date if interview_date.strip() else None
    session.show_salary = show_salary.lower() in ("on", "true", "1", "yes")
    db.add(session)

    # Add new interviewers if provided
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
        # Reset session status if adding new interviewers
        session.status = "pending"
        session.aggregate_summary = ""
        db.add(session)

    db.commit()
    return RedirectResponse(f"/session/{session_id}", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, admin: AdminUser = Depends(get_current_admin)):
    base_url, api_key, model, system_prompt = get_llm_config()
    masked_key = ("*" * (len(api_key) - 4) + api_key[-4:]) if len(api_key) > 4 else "*" * len(api_key)
    return _render(request, "settings.html", {
        "admin": admin,
        "base_url": base_url,
        "api_key_masked": masked_key,
        "model": model,
        "system_prompt": system_prompt,
    })


@router.post("/settings")
async def settings_save(
    request: Request,
    llm_base_url: str = Form(...),
    llm_api_key: str = Form(""),
    llm_model: str = Form(...),
    llm_system_prompt: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    set_setting("llm_base_url", llm_base_url)
    if llm_api_key and not all(c == "*" for c in llm_api_key):
        set_setting("llm_api_key", llm_api_key)
    set_setting("llm_model", llm_model)
    set_setting("llm_system_prompt", llm_system_prompt)
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
