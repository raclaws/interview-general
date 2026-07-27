from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Candidate, CandidatePipeline, CandidateSignal, Job,
    InterviewSession, SessionInterviewer, Response, ResponseScore, Template, TemplateSection,
    not_deleted,
)

router = APIRouter()


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("/s/{token}", response_class=HTMLResponse)
async def shared_candidate_view(
    request: Request,
    token: str,
    db: Session = Depends(get_session),
):
    candidate = db.exec(
        select(Candidate).where(Candidate.share_token == token)
    ).first()
    hide_salary = True

    if not candidate:
        candidate = db.exec(
            select(Candidate).where(Candidate.share_token_full == token)
        ).first()
        hide_salary = False

    if not candidate:
        return HTMLResponse("<h1>Link expired or invalid</h1>", status_code=404)

    signal = db.exec(
        select(CandidateSignal).where(CandidateSignal.candidate_id == candidate.id)
    ).first()

    pipelines = db.exec(
        select(CandidatePipeline)
        .where(CandidatePipeline.candidate_id == candidate.id, not_deleted(CandidatePipeline))
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()

    pipeline_jobs = {}
    pipeline_sessions = {}
    for p in pipelines:
        if p.job_id:
            job = db.get(Job, p.job_id)
            if job:
                pipeline_jobs[p.id] = job

        sessions = db.exec(
            select(InterviewSession)
            .where(InterviewSession.pipeline_id == p.id, not_deleted(InterviewSession))
            .order_by(InterviewSession.created_at.desc())
        ).all()

        sess_list = []
        for s in sessions:
            template = db.get(Template, s.template_id) if s.template_id else None
            interviewers = db.exec(
                select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
            ).all()
            # Response links through SessionInterviewer, not directly to session
            responses_data = []
            for iv in interviewers:
                resp = db.exec(
                    select(Response).where(Response.session_interviewer_id == iv.id)
                ).first()
                if resp:
                    raw_scores = db.exec(
                        select(ResponseScore).where(ResponseScore.response_id == resp.id)
                    ).all()
                    scores = []
                    long_texts = {}
                    for rs in raw_scores:
                        section = db.get(TemplateSection, rs.section_id)
                        if section:
                            if section.measurement_type == "long_text" and rs.value:
                                long_texts[section.title] = rs.value
                            else:
                                scores.append({
                                    "dimension": section.title,
                                    "score": rs.value,
                                })
                        else:
                            scores.append({
                                "dimension": f"Section {rs.section_id}",
                                "score": rs.value,
                            })
                    responses_data.append({
                        "interviewer_name": iv.interviewer_name,
                        "scores": scores,
                        "notes": resp.free_text or "",
                        "long_texts": long_texts,
                    })

            sess_list.append({
                "session": s,
                "template": template,
                "interviewers": interviewers,
                "responses": responses_data,
            })
        pipeline_sessions[p.id] = sess_list

    # Compute fit per pipeline
    from app.helpers import compute_fit
    pipeline_fits = {}
    for p in pipelines:
        if p.job_id and p.id in pipeline_jobs:
            pipeline_fits[p.id] = compute_fit(db, p, pipeline_jobs[p.id], candidate)

    return _render(request, "share/candidate.html", {
        "candidate": candidate,
        "signal": signal,
        "pipelines": pipelines,
        "pipeline_jobs": pipeline_jobs,
        "pipeline_sessions": pipeline_sessions,
        "pipeline_fits": pipeline_fits,
        "hide_salary": hide_salary,
    })


def _build_pipeline_share_data(db: Session, pipeline: CandidatePipeline, hide_salary: bool):
    """Build data for pipeline share view."""
    candidate = db.get(Candidate, pipeline.candidate_id)
    job = db.get(Job, pipeline.job_id) if pipeline.job_id else None

    signal = db.exec(
        select(CandidateSignal).where(CandidateSignal.candidate_id == candidate.id)
    ).first() if candidate else None

    sessions = db.exec(
        select(InterviewSession)
        .where(InterviewSession.pipeline_id == pipeline.id, not_deleted(InterviewSession))
        .order_by(InterviewSession.created_at.desc())
    ).all()

    sess_list = []
    for s in sessions:
        template = db.get(Template, s.template_id) if s.template_id else None
        interviewers = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        responses_data = []
        for iv in interviewers:
            resp = db.exec(
                select(Response).where(Response.session_interviewer_id == iv.id)
            ).first()
            if resp:
                raw_scores = db.exec(
                    select(ResponseScore).where(ResponseScore.response_id == resp.id)
                ).all()
                scores = []
                long_texts = {}
                for rs in raw_scores:
                    section = db.get(TemplateSection, rs.section_id)
                    if section:
                        if section.measurement_type == "long_text" and rs.value:
                            long_texts[section.title] = rs.value
                        else:
                            scores.append({
                                "dimension": section.title,
                                "score": rs.value,
                            })
                    else:
                        scores.append({
                            "dimension": f"Section {rs.section_id}",
                            "score": rs.value,
                        })
                responses_data.append({
                    "interviewer_name": iv.interviewer_name,
                    "scores": scores,
                    "notes": resp.free_text or "",
                    "long_texts": long_texts,
                })

        sess_list.append({
            "session": s,
            "template": template,
            "interviewers": interviewers,
            "responses": responses_data,
        })

    from app.helpers import compute_fit
    fit = compute_fit(db, pipeline, job, candidate) if job and candidate else {}

    return {
        "pipeline": pipeline,
        "candidate": candidate,
        "job": job,
        "signal": signal,
        "sessions": sess_list,
        "fit": fit,
        "hide_salary": hide_salary,
    }


@router.get("/p/{token}", response_class=HTMLResponse)
async def shared_pipeline_view(
    request: Request,
    token: str,
    db: Session = Depends(get_session),
):
    pipeline = db.exec(
        select(CandidatePipeline).where(CandidatePipeline.share_token == token, not_deleted(CandidatePipeline))
    ).first()
    hide_salary = True

    if not pipeline:
        pipeline = db.exec(
            select(CandidatePipeline).where(CandidatePipeline.share_token_full == token, not_deleted(CandidatePipeline))
        ).first()
        hide_salary = False

    if not pipeline:
        return HTMLResponse("<h1>Link expired or invalid</h1>", status_code=404)

    data = _build_pipeline_share_data(db, pipeline, hide_salary)
    return _render(request, "share/pipeline.html", data)
