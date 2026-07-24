from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import InterviewSession, SessionInterviewer, Response, ResponseScore, Template, TemplateSection

router = APIRouter()


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("/i/{token}", response_class=HTMLResponse)
async def interview_form(request: Request, token: str, db: Session = Depends(get_session)):
    interviewer = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.token == token)
    ).first()
    if not interviewer:
        return HTMLResponse("Invalid or expired link.", status_code=404)
    if interviewer.status == "completed":
        return RedirectResponse(f"/i/{token}/done", status_code=303)

    session = db.get(InterviewSession, interviewer.session_id)
    if not session:
        return HTMLResponse("This session is no longer available.", status_code=410)
    if session.status == "cancelled":
        return HTMLResponse("This session has been cancelled.", status_code=410)
    template = db.get(Template, session.template_id) if session.template_id else None
    sections = []
    if session.template_id:
        sections = db.exec(
            select(TemplateSection).where(TemplateSection.template_id == session.template_id).order_by(TemplateSection.order)
        ).all()

    # Load job criteria if session is linked to a pipeline with a job
    from app.models import CandidatePipeline, JobCriteria, not_deleted
    criteria = []
    if session.pipeline_id:
        pipeline = db.get(CandidatePipeline, session.pipeline_id)
        if pipeline and pipeline.job_id:
            criteria = db.exec(
                select(JobCriteria).where(JobCriteria.job_id == pipeline.job_id, not_deleted(JobCriteria)).order_by(JobCriteria.order)
            ).all()

    return _render(request, "interview_form.html", {
        "session": session,
        "interviewer": interviewer,
        "template": template,
        "sections": sections,
        "criteria": criteria,
    })


@router.post("/i/{token}")
async def interview_submit(
    request: Request,
    token: str,
    db: Session = Depends(get_session),
):
    interviewer = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.token == token)
    ).first()
    if not interviewer or interviewer.status == "completed":
        return HTMLResponse("This session has already been submitted.", status_code=400)

    session = db.get(InterviewSession, interviewer.session_id)
    if not session:
        return HTMLResponse("This session is no longer available.", status_code=410)
    if session.status == "cancelled":
        return HTMLResponse("This session has been cancelled.", status_code=410)
    sections = []
    if session.template_id:
        sections = db.exec(
            select(TemplateSection).where(TemplateSection.template_id == session.template_id).order_by(TemplateSection.order)
        ).all()

    form_data = await request.form()

    free_text = form_data.get("free_text", "")
    response = Response(
        session_interviewer_id=interviewer.id,
        free_text=free_text.strip() if free_text.strip() else None,
        submitted_at=datetime.utcnow(),
        summary="",
    )
    db.add(response)
    db.commit()
    db.refresh(response)

    for section in sections:
        key = f"section_{section.id}"
        if section.measurement_type == "multi_select":
            values = form_data.getlist(key)
            value = ",".join(values) if values else ""
        else:
            value = form_data.get(key, "")

        score = ResponseScore(
            response_id=response.id,
            section_id=section.id,
            value=value if value else "",
        )
        db.add(score)

    # Save criteria scores
    from app.models import CandidatePipeline, JobCriteria, CriteriaScore, not_deleted
    if session.pipeline_id:
        pipeline = db.get(CandidatePipeline, session.pipeline_id)
        if pipeline and pipeline.job_id:
            criteria = db.exec(
                select(JobCriteria).where(JobCriteria.job_id == pipeline.job_id, not_deleted(JobCriteria))
            ).all()
            for c in criteria:
                cval = form_data.get(f"criteria_{c.id}")
                if cval is not None and cval in ("0", "1", "2"):
                    db.add(CriteriaScore(
                        session_interviewer_id=interviewer.id,
                        criteria_id=c.id,
                        value=int(cval),
                    ))

    interviewer.status = "completed"
    db.add(interviewer)

    all_interviewers = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.session_id == session.id)
    ).all()
    if all(iv.status == "completed" for iv in all_interviewers):
        session.status = "completed"
        db.add(session)

    db.commit()
    return RedirectResponse(f"/i/{token}/done", status_code=303)


@router.get("/i/{token}/done", response_class=HTMLResponse)
async def interview_done(request: Request, token: str, db: Session = Depends(get_session)):
    interviewer = db.exec(
        select(SessionInterviewer).where(SessionInterviewer.token == token)
    ).first()
    if not interviewer:
        return HTMLResponse("Invalid link.", status_code=404)
    session = db.get(InterviewSession, interviewer.session_id)
    return _render(request, "interview_done.html", {"session": session})
