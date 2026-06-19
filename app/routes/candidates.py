import json as json_mod
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, col
from sqlalchemy import func, case

from app.database import get_session
from app.auth import get_current_admin
from app.models import (
    AdminUser, Candidate, CandidatePipeline, InterviewSession,
    SessionInterviewer, Template, TemplateSection, Response, ResponseScore, PipelineScore,
    PIPELINE_STAGES, HR_DIMENSIONS, CULTURE_DIMENSIONS, DRIVE_DREAM_OPTIONS,
)
from app.routes.admin import POSITIONS, BUSINESS_UNITS

router = APIRouter()


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _pipeline_partial_context(db: Session, candidate_id: int) -> dict:
    """Build full context needed by partials/pipeline_list.html."""
    candidate = db.get(Candidate, candidate_id)
    pipelines = db.exec(
        select(CandidatePipeline)
        .where(CandidatePipeline.candidate_id == candidate_id)
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
        .where(InterviewSession.candidate_id == candidate_id)
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

    return {
        "pipelines": pipelines,
        "candidate": candidate,
        "stages": PIPELINE_STAGES,
        "pipeline_scores": pipeline_scores,
        "pipeline_sessions": pipeline_sessions,
    }


@router.get("/candidates", response_class=HTMLResponse)
async def candidates_list(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    from sqlalchemy import literal_column
    from sqlalchemy.orm import aliased

    candidates = db.exec(
        select(Candidate).order_by(Candidate.updated_at.desc())
    ).all()
    candidate_ids = [c.id for c in candidates]

    # Pipeline counts + stages in one query
    pipeline_rows = db.exec(
        select(
            CandidatePipeline.candidate_id,
            func.count(CandidatePipeline.id).label("pipeline_count"),
            func.group_concat(CandidatePipeline.stage).label("stages_csv"),
        )
        .where(CandidatePipeline.candidate_id.in_(candidate_ids))
        .group_by(CandidatePipeline.candidate_id)
    ).all() if candidate_ids else []
    pipeline_map = {r[0]: {"count": r[1], "stages_csv": r[2] or ""} for r in pipeline_rows}

    # Session counts per candidate
    session_rows = db.exec(
        select(
            InterviewSession.candidate_id,
            func.count(InterviewSession.id).label("session_count"),
        )
        .where(InterviewSession.candidate_id.in_(candidate_ids))
        .group_by(InterviewSession.candidate_id)
    ).all() if candidate_ids else []
    session_map = {r[0]: r[1] for r in session_rows}

    # Latest activity: max of candidate.updated_at, pipeline.updated_at, session.created_at
    pipeline_latest = db.exec(
        select(
            CandidatePipeline.candidate_id,
            func.max(CandidatePipeline.updated_at).label("latest"),
        )
        .where(CandidatePipeline.candidate_id.in_(candidate_ids))
        .group_by(CandidatePipeline.candidate_id)
    ).all() if candidate_ids else []
    pipeline_latest_map = {r[0]: r[1] for r in pipeline_latest}

    session_latest = db.exec(
        select(
            InterviewSession.candidate_id,
            func.max(InterviewSession.created_at).label("latest"),
        )
        .where(InterviewSession.candidate_id.in_(candidate_ids))
        .group_by(InterviewSession.candidate_id)
    ).all() if candidate_ids else []
    session_latest_map = {r[0]: r[1] for r in session_latest}

    candidate_data = []
    for c in candidates:
        p_info = pipeline_map.get(c.id, {"count": 0, "stages_csv": ""})
        s_count = session_map.get(c.id, 0)
        stages = [s for s in p_info["stages_csv"].split(",") if s] if p_info["stages_csv"] else []

        dates = [c.updated_at]
        if c.id in pipeline_latest_map and pipeline_latest_map[c.id]:
            dates.append(pipeline_latest_map[c.id])
        if c.id in session_latest_map and session_latest_map[c.id]:
            dates.append(session_latest_map[c.id])
        latest_activity = max(dates)

        candidate_data.append({
            "candidate": c,
            "pipeline_count": p_info["count"],
            "session_count": s_count,
            "stages": stages,
            "latest_activity": latest_activity,
        })
    return _render(request, "candidates_list.html", {
        "candidate_data": candidate_data,
        "admin": admin,
        "stages": PIPELINE_STAGES,
    })


@router.get("/candidate/{candidate_id}", response_class=HTMLResponse)
async def candidate_detail(
    request: Request,
    candidate_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    pipelines = db.exec(
        select(CandidatePipeline)
        .where(CandidatePipeline.candidate_id == candidate.id)
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()

    pipeline_scores = {}
    for p in pipelines:
        # Compute scores from completed sessions
        p_sessions = db.exec(
            select(InterviewSession).where(
                InterviewSession.pipeline_id == p.id,
                InterviewSession.status == "completed",
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
        .where(InterviewSession.candidate_id == candidate.id)
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
        "positions": POSITIONS,
        "business_units": BUSINESS_UNITS,
        "templates": templates,
    })


@router.get("/candidate/{candidate_id}/edit", response_class=HTMLResponse)
async def candidate_edit_form(
    request: Request,
    candidate_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)
    return _render(request, "candidate_edit.html", {"candidate": candidate, "admin": admin})


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
    candidate.updated_at = datetime.utcnow()
    db.add(candidate)
    db.commit()
    return RedirectResponse(f"/candidate/{candidate_id}", status_code=303)


@router.post("/candidate/{candidate_id}/pipeline")
async def pipeline_create(
    request: Request,
    candidate_id: int,
    position: str = Form(""),
    business_unit: str = Form(""),
    stage: str = Form("screening"),
    notes: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return HTMLResponse("Not found", status_code=404)

    pos = position.strip() or None
    bu = business_unit.strip() or None

    # Auto-generate display_name: Position MMYY #N — BU
    mmyy = datetime.utcnow().strftime("%m%y")
    existing = db.exec(
        select(CandidatePipeline).where(
            CandidatePipeline.candidate_id == candidate.id,
            CandidatePipeline.position == pos,
            CandidatePipeline.business_unit == bu,
        )
    ).all()
    same_month = [p for p in existing if p.created_at.strftime("%m%y") == mmyy]
    seq = len(same_month) + 1
    display_name = f"{pos or 'N/A'} {mmyy} #{seq} — {bu or 'N/A'}"

    pipeline = CandidatePipeline(
        candidate_id=candidate.id,
        display_name=display_name,
        position=pos,
        business_unit=bu,
        stage=stage if stage in PIPELINE_STAGES else "screening",
        notes=notes.strip() or None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(pipeline)
    db.commit()

    if request.headers.get("HX-Request"):
        db.refresh(pipeline)
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
        pipeline.stage = stage
        pipeline.updated_at = datetime.utcnow()
        db.add(pipeline)
        db.commit()

    if request.headers.get("HX-Request"):
        return _render(request, "partials/pipeline_list.html", _pipeline_partial_context(db, candidate_id))

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

    db.delete(pipeline)
    db.commit()

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
    # Batch query 1: all pipelines joined with candidate
    results = db.exec(
        select(CandidatePipeline, Candidate)
        .join(Candidate, CandidatePipeline.candidate_id == Candidate.id)
        .order_by(CandidatePipeline.updated_at.desc())
    ).all()

    # Batch query 2: session counts grouped by pipeline_id
    session_counts_rows = db.exec(
        select(
            InterviewSession.pipeline_id,
            func.count(SessionInterviewer.id).label("total"),
            func.sum(case((SessionInterviewer.status == "completed", 1), else_=0)).label("completed"),
        )
        .join(SessionInterviewer, SessionInterviewer.session_id == InterviewSession.id)
        .where(InterviewSession.pipeline_id != None)
        .group_by(InterviewSession.pipeline_id)
    ).all()
    session_counts = {row[0]: {"total": row[1], "completed": int(row[2] or 0)} for row in session_counts_rows}

    # Batch query 3: scores from PipelineScore table
    all_scores = db.exec(select(PipelineScore)).all()
    scores_map = {s.pipeline_id: s for s in all_scores}

    pipeline_data = []
    bus_set = set()
    for pipeline, candidate in results:
        sc = scores_map.get(pipeline.id)
        hr_avg = round(sc.hr_total / 3, 1) if sc and sc.hr_total else 0
        culture_avg = round(sc.culture_total / 4, 1) if sc and sc.culture_total else 0
        counts = session_counts.get(pipeline.id, {"total": 0, "completed": 0})
        if pipeline.business_unit:
            bus_set.add(pipeline.business_unit)
        pipeline_data.append({
            "pipeline": pipeline,
            "candidate": candidate,
            "session_count": counts,
            "scores": {"hr_avg": hr_avg, "culture_avg": culture_avg},
        })

    return _render(request, "pipelines_list.html", {
        "pipeline_data": pipeline_data,
        "admin": admin,
        "stages": PIPELINE_STAGES,
        "business_units": sorted(bus_set),
    })


# --- CLA-20: Pipeline Detail Page ---

def _pipeline_detail_context(db: Session, pipeline: CandidatePipeline, candidate: Candidate):
    """Build context for pipeline detail page."""
    sessions = db.exec(
        select(InterviewSession)
        .where(InterviewSession.pipeline_id == pipeline.id)
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

    # Scores: per-interviewer breakdown
    hr_data = []
    culture_data = []
    completed_sessions = [s for s in sessions if s.status == "completed"]

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

    for session in completed_sessions:
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
        "stages": PIPELINE_STAGES,
    }


@router.get("/pipeline/{pipeline_id}", response_class=HTMLResponse)
async def pipeline_detail(
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

    ctx = _pipeline_detail_context(db, pipeline, candidate)
    ctx["admin"] = admin
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
        pipeline.stage = stage
        pipeline.updated_at = datetime.utcnow()
        db.add(pipeline)
        db.commit()

    if request.headers.get("HX-Request"):
        options = "".join(
            f'<option value="{s}" {"selected" if s == pipeline.stage else ""}>{s.replace("_", " ").title()}</option>'
            for s in PIPELINE_STAGES
        )
        return HTMLResponse(
            f'<select name="stage" onchange="this.form.requestSubmit()" class="inline-select">{options}</select>',
            headers={"HX-Trigger": "toast:Stage updated"},
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

    db.delete(pipeline)
    db.commit()

    return RedirectResponse("/pipelines", status_code=303)
