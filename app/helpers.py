"""Shared view helpers."""
from fastapi import Request


def render_gone(request: Request, entity_label: str, back_url: str, back_label: str):
    return request.app.state.templates.TemplateResponse(
        request, "gone.html",
        {"entity_label": entity_label, "back_url": back_url, "back_label": back_label},
        status_code=404,
    )


def compute_pipeline_scores(db, pipeline_ids):
    """Compute HR/Culture average scores for a list of pipeline IDs.
    Returns dict: {pipeline_id: {"hr_avg": float, "culture_avg": float}}
    """
    from sqlmodel import select
    from app.models import (
        InterviewSession, SessionInterviewer, Response, ResponseScore,
        Template, TemplateSection, not_deleted,
    )

    results = {}
    template_sections_cache = {}

    for pid in pipeline_ids:
        sessions = db.exec(
            select(InterviewSession).where(
                InterviewSession.pipeline_id == pid,
                InterviewSession.status == "completed",
                not_deleted(InterviewSession),
            )
        ).all()
        hr_total = 0
        culture_total = 0
        hr_count = 0
        culture_count = 0
        for s in sessions:
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
                if template.id not in template_sections_cache:
                    template_sections_cache[template.id] = db.exec(
                        select(TemplateSection).where(TemplateSection.template_id == template.id)
                    ).all()
                sections = template_sections_cache[template.id]
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
        results[pid] = {
            "hr_avg": round(hr_total / hr_count, 1) if hr_count else 0,
            "culture_avg": round(culture_total / culture_count, 1) if culture_count else 0,
        }
    return results
