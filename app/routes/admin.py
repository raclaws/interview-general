import json
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import AdminUser, InterviewSession, Response
from app.nocodb import search_candidates, fetch_candidate
from app.llm import generate_summary, get_llm_config, set_setting, DEFAULT_SYSTEM_PROMPT

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
    return _render(request, "dashboard.html", {"sessions": sessions, "admin": admin})


@router.get("/session/new", response_class=HTMLResponse)
async def session_new_form(request: Request, admin: AdminUser = Depends(get_current_admin)):
    return _render(request, "session_new.html", {"admin": admin})


@router.post("/session/new")
async def session_new_submit(
    request: Request,
    candidate_id: int = Form(None),
    job_title: str = Form(...),
    round: str = Form(...),
    interviewer_name: str = Form(...),
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

    token = _generate_token()
    session = InterviewSession(
        token=token,
        candidate_id=candidate_id,
        candidate_snapshot=json.dumps(snapshot),
        job_title=job_title,
        round=round,
        interviewer_name=interviewer_name,
        interview_date=interview_date if interview_date.strip() else None,
        show_salary=show_salary.lower() in ("on", "true", "1", "yes"),
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(session)
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
    response = db.exec(
        select(Response).where(Response.session_id == session.id)
    ).first()
    return _render(request, "session_detail.html", {"session": session, "response": response, "admin": admin})


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
    response = db.exec(
        select(Response).where(Response.session_id == session.id)
    ).first()
    if not response:
        return RedirectResponse(f"/session/{session_id}", status_code=303)

    snapshot = session.snapshot
    summary = await generate_summary(
        candidate_name=snapshot.get("name", "Unknown"),
        job_title=session.job_title,
        q1=response.q1,
        q2=response.q2,
        q3=response.q3,
        q4=response.q4,
        q5=response.q5,
        free_text=response.free_text,
    )
    response.summary = summary
    db.add(response)
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
    response = db.exec(
        select(Response).where(Response.session_id == session.id)
    ).first()
    return _render(request, "session_edit.html", {"session": session, "response": response, "admin": admin})


@router.post("/session/{session_id}/edit")
async def session_edit_submit(
    request: Request,
    session_id: int,
    job_title: str = Form(...),
    round: str = Form(...),
    interviewer_name: str = Form(...),
    interview_date: str = Form(""),
    show_salary: str = Form(""),
    edit_q1: int = Form(None),
    edit_q2: int = Form(None),
    edit_q3: int = Form(None),
    edit_q4: int = Form(None),
    edit_q5: str = Form(None),
    edit_free_text: str = Form(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    session = db.get(InterviewSession, session_id)
    if not session:
        return HTMLResponse("Not found", status_code=404)

    session.job_title = job_title
    session.round = round
    session.interviewer_name = interviewer_name
    session.interview_date = interview_date if interview_date.strip() else None
    session.show_salary = show_salary.lower() in ("on", "true", "1", "yes")
    db.add(session)

    # Update response if submitted and edit fields provided
    if edit_q1 is not None:
        response = db.exec(
            select(Response).where(Response.session_id == session.id)
        ).first()
        if response:
            response.q1 = edit_q1
            response.q2 = edit_q2
            response.q3 = edit_q3
            response.q4 = edit_q4
            response.q5 = edit_q5.lower() in ("yes", "true", "1") if edit_q5 else response.q5
            if edit_free_text is not None:
                response.free_text = edit_free_text if edit_free_text.strip() else None
            response.summary = ""  # Invalidate cached summary
            db.add(response)

    db.commit()
    return RedirectResponse(f"/session/{session_id}", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, admin: AdminUser = Depends(get_current_admin)):
    base_url, api_key, model, system_prompt = get_llm_config()
    # Mask API key for display
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
    # Only update API key if not all asterisks (user didn't change it)
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
