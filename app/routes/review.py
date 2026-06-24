from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import ReviewBatch, ReviewScore, TestAssignment, CandidatePipeline, Candidate

router = APIRouter()


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _get_batch(token: str, db: Session):
    return db.exec(
        select(ReviewBatch).where(ReviewBatch.token == token)
    ).first()


def _get_review_data(batch: ReviewBatch, db: Session):
    """Find all test assignments matching this batch's position+BU."""
    pipelines = db.exec(
        select(CandidatePipeline).where(
            CandidatePipeline.position == batch.position,
            CandidatePipeline.business_unit == batch.business_unit,
        )
    ).all()

    rows = []
    for p in pipelines:
        candidate = db.get(Candidate, p.candidate_id)
        if not candidate:
            continue
        assignments = db.exec(
            select(TestAssignment).where(
                TestAssignment.pipeline_id == p.id,
            )
        ).all()
        for a in assignments:
            score = db.exec(
                select(ReviewScore).where(
                    ReviewScore.review_batch_id == batch.id,
                    ReviewScore.test_assignment_id == a.id,
                )
            ).first()
            rows.append({
                "candidate": candidate,
                "assignment": a,
                "pipeline": p,
                "score": score,
            })

    return rows


@router.get("/r/{token}", response_class=HTMLResponse)
async def review_portal(request: Request, token: str, db: Session = Depends(get_session)):
    batch = _get_batch(token, db)
    if not batch:
        return HTMLResponse("Invalid or expired link.", status_code=404)

    rows = _get_review_data(batch, db)
    scored = len([r for r in rows if r["score"] and r["score"].submitted_at])

    return _render(request, "review_portal.html", {
        "batch": batch,
        "rows": rows,
        "scored": scored,
        "total": len(rows),
        "token": token,
    })


@router.get("/r/{token}/score/{assignment_id}", response_class=HTMLResponse)
async def review_score_form(
    request: Request,
    token: str,
    assignment_id: int,
    db: Session = Depends(get_session),
):
    batch = _get_batch(token, db)
    if not batch:
        return HTMLResponse("Invalid link.", status_code=404)

    assignment = db.get(TestAssignment, assignment_id)
    if not assignment:
        return HTMLResponse("Not found.", status_code=404)

    score = db.exec(
        select(ReviewScore).where(
            ReviewScore.review_batch_id == batch.id,
            ReviewScore.test_assignment_id == assignment_id,
        )
    ).first()

    pipeline = db.get(CandidatePipeline, assignment.pipeline_id)
    candidate = db.get(Candidate, pipeline.candidate_id) if pipeline else None

    return _render(request, "partials/review_score_form.html", {
        "batch": batch,
        "assignment": assignment,
        "candidate": candidate,
        "score": score,
        "token": token,
    })


@router.post("/r/{token}/score/{assignment_id}", response_class=HTMLResponse)
async def review_score_submit(
    request: Request,
    token: str,
    assignment_id: int,
    grade: str = Form(""),
    qualitative: str = Form(""),
    verdict: str = Form(""),
    db: Session = Depends(get_session),
):
    batch = _get_batch(token, db)
    if not batch:
        return HTMLResponse("Invalid link.", status_code=404)

    score = db.exec(
        select(ReviewScore).where(
            ReviewScore.review_batch_id == batch.id,
            ReviewScore.test_assignment_id == assignment_id,
        )
    ).first()

    if score:
        score.grade = grade or None
        score.qualitative = qualitative or None
        score.verdict = verdict or None
        score.submitted_at = datetime.utcnow()
    else:
        score = ReviewScore(
            review_batch_id=batch.id,
            test_assignment_id=assignment_id,
            grade=grade or None,
            qualitative=qualitative or None,
            verdict=verdict or None,
            submitted_at=datetime.utcnow(),
        )

    db.add(score)
    db.commit()

    # Return updated row partial for HTMX swap
    pipeline = db.get(CandidatePipeline, db.get(TestAssignment, assignment_id).pipeline_id)
    candidate = db.get(Candidate, pipeline.candidate_id) if pipeline else None

    return _render(request, "partials/review_row.html", {
        "candidate": candidate,
        "assignment": db.get(TestAssignment, assignment_id),
        "score": score,
        "token": token,
        "batch": batch,
    })
