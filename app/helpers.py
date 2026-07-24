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


def compute_fit(db, pipeline, job, candidate):
    """Compute fit insights for a candidate × job pair.
    Returns dict with salary_fit, notice_fit, criteria_coverage, r1_gate."""
    from sqlmodel import select
    from app.models import JobCriteria, CriteriaScore, SessionInterviewer, InterviewSession, not_deleted
    import re

    fit = {}

    # Salary fit
    if job.salary_range_min and job.salary_range_max and candidate.expected_salary:
        try:
            expected = int(re.sub(r"[^\d]", "", str(candidate.expected_salary)))
            if expected > 0:
                if expected < job.salary_range_min:
                    delta = round((job.salary_range_min - expected) / job.salary_range_min * 100)
                    fit["salary"] = {"status": "UNDER_BUDGET", "delta": -delta, "label": f"{delta}% under min"}
                elif expected > job.salary_range_max:
                    delta = round((expected - job.salary_range_max) / job.salary_range_max * 100)
                    fit["salary"] = {"status": "OVER_BUDGET", "delta": delta, "label": f"{delta}% over max"}
                else:
                    fit["salary"] = {"status": "WITHIN", "delta": 0, "label": "Within range"}
        except (ValueError, TypeError):
            pass

    # Notice fit
    if candidate.notice_period and job.target_date:
        notice_days = 0
        np_lower = (candidate.notice_period or "").lower()
        if "asap" in np_lower or "immediate" in np_lower:
            notice_days = 0
        elif "1 month" in np_lower or "< 1 month" in np_lower:
            notice_days = 30
        elif "2 month" in np_lower:
            notice_days = 60
        elif "3 month" in np_lower or "> 1 month" in np_lower:
            notice_days = 45
        from datetime import datetime, timedelta
        try:
            target = datetime.strptime(job.target_date, "%Y-%m-%d")
            available = datetime.utcnow() + timedelta(days=notice_days)
            if available <= target:
                fit["notice"] = {"status": "ON_TIME", "label": "Can start in time"}
            else:
                weeks_late = max(1, (available - target).days // 7)
                fit["notice"] = {"status": "LATE", "label": f"~{weeks_late} week{'s' if weeks_late > 1 else ''} late"}
        except (ValueError, TypeError):
            pass

    # Criteria coverage + R1 gate
    criteria = db.exec(
        select(JobCriteria).where(JobCriteria.job_id == job.id, not_deleted(JobCriteria))
    ).all()
    if criteria:
        # Get all session_interviewer_ids for this pipeline
        sessions = db.exec(
            select(InterviewSession).where(InterviewSession.pipeline_id == pipeline.id, not_deleted(InterviewSession))
        ).all()
        iv_ids = []
        for s in sessions:
            ivs = db.exec(select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)).all()
            iv_ids.extend([iv.id for iv in ivs])

        scores = {}
        if iv_ids:
            all_scores = db.exec(
                select(CriteriaScore).where(CriteriaScore.session_interviewer_id.in_(iv_ids))
            ).all()
            for sc in all_scores:
                if sc.criteria_id not in scores or sc.value > scores[sc.criteria_id]:
                    scores[sc.criteria_id] = sc.value

        r1_criteria = [c for c in criteria if c.tier == "r1"]
        r2_criteria = [c for c in criteria if c.tier == "r2"]
        assessed = [c for c in criteria if c.id in scores]

        r1_pass = all(scores.get(c.id, -1) >= 1 for c in r1_criteria) if r1_criteria else True
        r1_assessed = all(c.id in scores for c in r1_criteria) if r1_criteria else True

        fit["criteria"] = {
            "total": len(criteria),
            "assessed": len(assessed),
            "r1_total": len(r1_criteria),
            "r1_pass": r1_pass and r1_assessed,
            "r1_incomplete": not r1_assessed,
            "scores": {c.id: {"label": c.label, "tier": c.tier, "value": scores.get(c.id)} for c in criteria},
        }

    return fit
