import os
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import TestAssignment

router = APIRouter()

UPLOAD_DIR = os.path.join("static", "uploads", "tests")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _get_assignment(token: str, db: Session):
    return db.exec(
        select(TestAssignment).where(TestAssignment.token == token)
    ).first()


def _is_expired(assignment: TestAssignment) -> bool:
    now = datetime.utcnow()
    if assignment.expiry and now > assignment.expiry:
        return True
    return False


def _is_past_deadline(assignment: TestAssignment) -> bool:
    now = datetime.utcnow()
    if assignment.deadline and now > assignment.deadline:
        return True
    return False


@router.get("/t/{token}", response_class=HTMLResponse)
async def test_password_page(request: Request, token: str, db: Session = Depends(get_session)):
    assignment = _get_assignment(token, db)
    if not assignment:
        return HTMLResponse("Invalid or expired link.", status_code=404)
    if _is_expired(assignment):
        return _render(request, "test_expired.html", {"assignment": assignment})
    if assignment.status == "submitted":
        return RedirectResponse(f"/t/{token}/done", status_code=303)

    return _render(request, "test_password.html", {"token": token, "error": None})


@router.post("/t/{token}/auth", response_class=HTMLResponse)
async def test_auth(
    request: Request,
    token: str,
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    assignment = _get_assignment(token, db)
    if not assignment:
        return HTMLResponse("Invalid or expired link.", status_code=404)
    if _is_expired(assignment):
        return _render(request, "test_expired.html", {"assignment": assignment})

    if password != assignment.password:
        return _render(request, "test_password.html", {"token": token, "error": "Incorrect password. Please try again."})

    return RedirectResponse(f"/t/{token}/test?key={password}", status_code=303)


@router.get("/t/{token}/test", response_class=HTMLResponse)
async def test_portal(request: Request, token: str, key: str = "", db: Session = Depends(get_session)):
    assignment = _get_assignment(token, db)
    if not assignment:
        return HTMLResponse("Invalid or expired link.", status_code=404)
    if key != assignment.password:
        return RedirectResponse(f"/t/{token}", status_code=303)
    if _is_expired(assignment):
        return _render(request, "test_expired.html", {"assignment": assignment})
    if assignment.status == "submitted":
        return RedirectResponse(f"/t/{token}/done", status_code=303)

    if assignment.status == "pending":
        assignment.status = "opened"
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

    return _render(request, "test_portal.html", {
        "assignment": assignment,
        "token": token,
        "key": key,
        "past_deadline": _is_past_deadline(assignment),
    })


@router.post("/t/{token}/submit")
async def test_submit(
    request: Request,
    token: str,
    key: str = Form(""),
    submission_url: str = Form(""),
    file: UploadFile = File(None),
    db: Session = Depends(get_session),
):
    assignment = _get_assignment(token, db)
    if not assignment:
        return HTMLResponse("Invalid or expired link.", status_code=404)
    if key != assignment.password:
        return RedirectResponse(f"/t/{token}", status_code=303)
    if _is_expired(assignment):
        return _render(request, "test_expired.html", {"assignment": assignment})
    if assignment.status == "submitted":
        return RedirectResponse(f"/t/{token}/done", status_code=303)

    if file and file.filename:
        if assignment.max_upload_size:
            contents = await file.read()
            if len(contents) > assignment.max_upload_size * 1024 * 1024:
                return _render(request, "test_portal.html", {
                    "assignment": assignment,
                    "token": token,
                    "key": key,
                    "past_deadline": _is_past_deadline(assignment),
                    "error": f"File exceeds maximum size of {assignment.max_upload_size} MB.",
                })
            save_path = os.path.join(UPLOAD_DIR, f"{token}_{file.filename}")
            with open(save_path, "wb") as f:
                f.write(contents)
        else:
            save_path = os.path.join(UPLOAD_DIR, f"{token}_{file.filename}")
            with open(save_path, "wb") as f:
                while chunk := await file.read(1024 * 1024):
                    f.write(chunk)
        assignment.submission_url = save_path
    elif submission_url:
        assignment.submission_url = submission_url
    else:
        return _render(request, "test_portal.html", {
            "assignment": assignment,
            "token": token,
            "key": key,
            "past_deadline": _is_past_deadline(assignment),
            "error": "Please upload a file or provide a submission link.",
        })

    assignment.status = "submitted"
    assignment.submitted_at = datetime.utcnow()
    db.add(assignment)
    db.commit()

    return RedirectResponse(f"/t/{token}/done", status_code=303)


@router.get("/t/{token}/done", response_class=HTMLResponse)
async def test_done(request: Request, token: str, db: Session = Depends(get_session)):
    assignment = _get_assignment(token, db)
    if not assignment:
        return HTMLResponse("Invalid or expired link.", status_code=404)

    return _render(request, "test_done.html", {"assignment": assignment})
