from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.auth import get_current_admin
from app.models import AdminUser, CandidatePipeline, Candidate, Job, BusinessUnit, OfferLetter, not_deleted
from app.offers import build_offer_data, generate_offer_html, save_offer, OFFERS_DIR

router = APIRouter(prefix="/offers")


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


@router.get("/new/{pipeline_id}", response_class=HTMLResponse)
async def offer_form(
    request: Request,
    pipeline_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return RedirectResponse("/candidates", status_code=303)

    candidate = db.get(Candidate, pipeline.candidate_id)
    job = db.get(Job, pipeline.job_id) if pipeline.job_id else None
    bu = db.get(BusinessUnit, job.business_unit_id) if job else None

    existing = db.exec(
        select(OfferLetter).where(OfferLetter.pipeline_id == pipeline_id)
        .order_by(OfferLetter.created_at.desc())
    ).all()

    return _render(request, "offers/form.html", {
        "admin": admin,
        "pipeline": pipeline,
        "candidate": candidate,
        "job": job,
        "bu": bu,
        "existing_offers": existing,
    })


@router.post("/generate/{pipeline_id}", response_class=HTMLResponse)
async def offer_generate(
    request: Request,
    pipeline_id: int,
    offering_amount: int = Form(...),
    bpjs_tk: bool = Form(False),
    probation_change: bool = Form(False),
    post_probation_amount: int = Form(0),
    start_date: str = Form("tbc"),
    metode_kerja: str = Form("Hybrid – Jakarta (3 hari WFO, 2 hari WFH)"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    pipeline = db.get(CandidatePipeline, pipeline_id)
    if not pipeline:
        return HTMLResponse("Pipeline not found", status_code=404)

    candidate = db.get(Candidate, pipeline.candidate_id)
    job = db.get(Job, pipeline.job_id) if pipeline.job_id else None
    bu = db.get(BusinessUnit, job.business_unit_id) if job else None

    candidate_name = candidate.name if candidate else "—"
    job_title = job.position if job else "—"
    business_unit = bu.name if bu else "—"

    data = build_offer_data(
        candidate_name=candidate_name,
        job_title=job_title,
        business_unit=business_unit,
        offering_amount=offering_amount,
        bpjs_tk=bpjs_tk,
        probation_change=probation_change,
        post_probation_amount=post_probation_amount if probation_change else None,
        start_date=start_date,
        metode_kerja=metode_kerja,
    )

    html = generate_offer_html(data)
    html_filename, pdf_filename = save_offer(pipeline_id, html)

    offer = OfferLetter(
        pipeline_id=pipeline_id,
        candidate_name=candidate_name,
        job_title=job_title,
        business_unit=business_unit,
        offering_amount=offering_amount,
        post_probation_amount=post_probation_amount if probation_change else None,
        bpjs_tk=bpjs_tk,
        probation_change=probation_change,
        start_date=start_date,
        metode_kerja=metode_kerja,
        filename_html=html_filename,
        filename_pdf=pdf_filename,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)

    return _render(request, "offers/result.html", {"offer": offer})


@router.get("/{offer_id}/preview")
async def offer_preview(offer_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    offer = db.get(OfferLetter, offer_id)
    if not offer:
        return HTMLResponse("Not found", status_code=404)
    path = OFFERS_DIR / offer.filename_html
    if not path.exists():
        return HTMLResponse("File not found", status_code=404)
    return FileResponse(str(path), media_type="text/html")


@router.get("/{offer_id}/pdf")
async def offer_pdf(offer_id: int, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    offer = db.get(OfferLetter, offer_id)
    if not offer or not offer.filename_pdf:
        return HTMLResponse("Not found", status_code=404)
    path = OFFERS_DIR / offer.filename_pdf
    if not path.exists():
        return HTMLResponse("File not found", status_code=404)
    return FileResponse(str(path), media_type="application/pdf", filename=offer.filename_pdf)


@router.post("/{offer_id}/delete", response_class=HTMLResponse)
async def offer_delete(
    request: Request,
    offer_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    offer = db.get(OfferLetter, offer_id)
    if not offer:
        return HTMLResponse("", status_code=404)
    offer.status = "deleted"
    db.add(offer)
    db.commit()
    return HTMLResponse(f'''<tr style="opacity: 0.4;">
        <td>
            <div class="col-primary">Rp {offer.offering_amount:,.0f}<span class="badge" style="margin-left: 0.4rem; font-size: 0.65rem; background: var(--bg-muted); color: var(--text-muted);">deleted</span></div>
            <div class="row-meta">{offer.created_at.strftime("%d %b %Y, %H:%M")}{"" if not offer.bpjs_tk else " · BPJS"}{"" if not offer.probation_change else " · Probation change"}</div>
        </td>
        <td></td>
    </tr>'''.replace(",", "."))
