"""Data collectors for LLM report generation."""
from datetime import datetime, timedelta
from sqlmodel import Session, select, func, col

from app.models import (
    Job, BusinessUnit, Candidate, CandidatePipeline, InterviewSession,
    SessionInterviewer, Response, ResponseScore, Template, TemplateSection,
    TestAssignment, Comment, not_deleted, PIPELINE_STAGES,
)
from app.helpers import compute_pipeline_scores


def collect_general_data(db: Session, bu_ids: list[int] | None = None, level: str | None = None, since: datetime | None = None) -> dict:
    job_query = select(Job).where(not_deleted(Job), Job.title != "_Unassigned")
    if bu_ids:
        job_query = job_query.where(col(Job.business_unit_id).in_(bu_ids))
    if level:
        job_query = job_query.where(Job.level == level)
    jobs = db.exec(job_query).all()
    job_ids = [j.id for j in jobs]

    bus = {bu.id: bu.name for bu in db.exec(select(BusinessUnit)).all()}

    pipelines = db.exec(
        select(CandidatePipeline).where(
            col(CandidatePipeline.job_id).in_(job_ids) if job_ids else CandidatePipeline.id > 0,
            not_deleted(CandidatePipeline),
        )
    ).all()

    if since:
        pipelines = [p for p in pipelines if p.created_at >= since]

    stage_counts = {}
    for p in pipelines:
        stage_counts[p.stage] = stage_counts.get(p.stage, 0) + 1

    now = datetime.utcnow()
    days_per_stage = {}
    stale_count = 0
    for p in pipelines:
        days = (now - p.updated_at).days
        if days > 14:
            stale_count += 1
        if p.stage not in days_per_stage:
            days_per_stage[p.stage] = []
        days_per_stage[p.stage].append((now - p.created_at).days)

    avg_days = {stage: round(sum(ds) / len(ds), 1) for stage, ds in days_per_stage.items() if ds}

    open_jobs = [j for j in jobs if j.status == "open"]
    bu_breakdown = {}
    for j in open_jobs:
        bu_name = bus.get(j.business_unit_id, "Unknown")
        if bu_name not in bu_breakdown:
            bu_breakdown[bu_name] = {"jobs": 0, "headcount": 0, "filled": 0}
        bu_breakdown[bu_name]["jobs"] += 1
        bu_breakdown[bu_name]["headcount"] += j.headcount

    for p in pipelines:
        if p.stage == "hired" and p.job_id:
            job = next((j for j in jobs if j.id == p.job_id), None)
            if job:
                bu_name = bus.get(job.business_unit_id, "Unknown")
                if bu_name in bu_breakdown:
                    bu_breakdown[bu_name]["filled"] += 1

    ended = [p for p in pipelines if p.stage in ("hired", "rejected", "withdrawn")]
    hired = [p for p in pipelines if p.stage == "hired"]
    hire_rate = round(len(hired) / len(ended) * 100, 1) if ended else 0

    sessions_q = select(InterviewSession).where(not_deleted(InterviewSession), InterviewSession.status == "completed")
    if since:
        sessions_q = sessions_q.where(InterviewSession.created_at >= since)
    completed_sessions = len(db.exec(sessions_q).all())

    tests_q = select(TestAssignment).where(not_deleted(TestAssignment))
    if since:
        tests_q = tests_q.where(TestAssignment.created_at >= since)
    tests = db.exec(tests_q).all()
    tests_assigned = len(tests)
    tests_submitted = len([t for t in tests if t.status == "submitted"])

    return {
        "report_type": "general",
        "generated_at": now.isoformat(),
        "period": f"Since {since.strftime('%Y-%m-%d')}" if since else "All time",
        "open_jobs": len(open_jobs),
        "total_jobs": len(jobs),
        "total_pipelines": len(pipelines),
        "stage_distribution": stage_counts,
        "avg_days_per_stage": avg_days,
        "hire_rate_pct": hire_rate,
        "stale_pipelines": stale_count,
        "bu_breakdown": bu_breakdown,
        "completed_sessions": completed_sessions,
        "tests_assigned": tests_assigned,
        "tests_submitted": tests_submitted,
    }


def collect_pipeline_data(db: Session, pipeline_id: int) -> dict:
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return {"error": "Pipeline not found"}

    candidate = db.get(Candidate, pipeline.candidate_id)
    if not candidate:
        return {"error": "Candidate not found"}
    job = db.get(Job, pipeline.job_id) if pipeline.job_id else None
    bu = db.get(BusinessUnit, job.business_unit_id) if job else None

    sessions = db.exec(
        select(InterviewSession).where(
            InterviewSession.pipeline_id == pipeline_id, not_deleted(InterviewSession)
        ).order_by(InterviewSession.created_at)
    ).all()

    session_details = []
    for s in sessions:
        template = db.get(Template, s.template_id) if s.template_id else None
        interviewers = db.exec(
            select(SessionInterviewer).where(SessionInterviewer.session_id == s.id)
        ).all()
        iv_data = []
        for iv in interviewers:
            resp = db.exec(select(Response).where(Response.session_interviewer_id == iv.id)).first()
            scores_str = ""
            if resp:
                score_rows = db.exec(select(ResponseScore).where(ResponseScore.response_id == resp.id)).all()
                if score_rows and template:
                    sections = db.exec(select(TemplateSection).where(TemplateSection.template_id == template.id)).all()
                    sec_map = {sec.id: sec.title for sec in sections}
                    scores_str = "; ".join(f"{sec_map.get(sr.section_id, '?')}: {sr.value}" for sr in score_rows if sr.value)
            iv_data.append({
                "name": iv.interviewer_name,
                "status": iv.status,
                "scores": scores_str,
                "free_text": resp.free_text if resp else None,
            })
        session_details.append({
            "template": template.name if template else "—",
            "status": s.status,
            "date": s.interview_date or s.created_at.strftime("%Y-%m-%d"),
            "summary": s.aggregate_summary or None,
            "interviewers": iv_data,
        })

    tests = db.exec(
        select(TestAssignment).where(TestAssignment.pipeline_id == pipeline_id, not_deleted(TestAssignment))
    ).all()
    test_data = [{"title": t.title, "status": t.status, "deadline": t.deadline.strftime("%Y-%m-%d") if t.deadline else None} for t in tests]

    scores = compute_pipeline_scores(db, [pipeline_id])
    score_info = scores.get(pipeline_id, {"hr_avg": 0, "culture_avg": 0})

    activities = db.exec(
        select(Comment).where(Comment.entity_type == "pipeline", Comment.entity_id == pipeline_id)
        .order_by(Comment.created_at)
    ).all()
    timeline = [{"date": a.created_at.strftime("%Y-%m-%d"), "event": a.body} for a in activities]

    now = datetime.utcnow()
    return {
        "report_type": "pipeline",
        "generated_at": now.isoformat(),
        "candidate": {"name": candidate.name, "email": candidate.email, "position": candidate.current_position, "yoe": candidate.yoe, "skills": candidate.tools},
        "job": {"title": job.title, "position": job.position, "level": job.level, "bu": bu.name if bu else "—"} if job else None,
        "pipeline": {"stage": pipeline.stage, "days_in_pipeline": (now - pipeline.created_at).days, "created": pipeline.created_at.strftime("%Y-%m-%d")},
        "sessions": session_details,
        "tests": test_data,
        "scores": score_info,
        "timeline": timeline,
    }


def collect_job_data(db: Session, job_id: int, since: datetime | None = None) -> dict:
    job = db.get(Job, job_id)
    if not job:
        return {"error": "Job not found"}

    bu = db.get(BusinessUnit, job.business_unit_id)

    pipelines = db.exec(
        select(CandidatePipeline).where(CandidatePipeline.job_id == job_id, not_deleted(CandidatePipeline))
    ).all()
    if since:
        pipelines = [p for p in pipelines if p.created_at >= since]

    now = datetime.utcnow()
    scores = compute_pipeline_scores(db, [p.id for p in pipelines]) if pipelines else {}

    candidate_ids = [p.candidate_id for p in pipelines]
    candidates = {c.id: c for c in db.exec(select(Candidate).where(col(Candidate.id).in_(candidate_ids))).all()} if candidate_ids else {}

    pipeline_summaries = []
    for p in pipelines:
        c = candidates.get(p.candidate_id)
        sc = scores.get(p.id, {"hr_avg": 0, "culture_avg": 0})
        pipeline_summaries.append({
            "pipeline_id": p.id,
            "candidate": c.name if c else "—",
            "stage": p.stage,
            "days": (now - p.created_at).days,
            "hr_avg": sc["hr_avg"],
            "culture_avg": sc["culture_avg"],
            "total": round(sc["hr_avg"] + sc["culture_avg"], 1),
            "stale": (now - p.updated_at).days > 14,
        })

    hired = len([p for p in pipelines if p.stage == "hired"])

    return {
        "report_type": "job",
        "generated_at": now.isoformat(),
        "job": {
            "title": job.title, "position": job.position, "level": job.level,
            "bu": bu.name if bu else "—", "headcount": job.headcount,
            "recruiter": job.recruiter, "target_date": job.target_date,
            "status": job.status, "priority": job.priority,
        },
        "fill_progress": f"{hired}/{job.headcount}",
        "total_candidates": len(pipelines),
        "candidates": pipeline_summaries,
    }
