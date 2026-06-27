from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, col, func

from app.database import get_session
from app.auth import get_current_admin
from app.models import (
    AdminUser, BusinessUnit, ManagedPosition, ManagedLevel, ManagedJobType, Job, not_deleted,
)

router = APIRouter(prefix="/settings")


def _render(request: Request, name: str, context: dict = None):
    ctx = context or {}
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _job_usage_counts(db: Session, field: str) -> dict:
    """Count active jobs per distinct value of a field (position, level, job_type)."""
    col_attr = getattr(Job, field)
    rows = db.exec(
        select(col_attr, func.count(Job.id))
        .where(not_deleted(Job))
        .group_by(col_attr)
    ).all()
    return {val: count for val, count in rows if val}


# --- Business Units ---


@router.get("/business-units", response_class=HTMLResponse)
async def settings_bu(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    bus = db.exec(select(BusinessUnit).order_by(BusinessUnit.name)).all()
    ctx = {"admin": admin, "business_units": bus, "active_tab": "business-units"}
    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return _render(request, "settings_bu.html", ctx)
    return _render(request, "settings_layout.html", {**ctx, "tab_content": "settings_bu.html"})


@router.post("/business-units", response_class=HTMLResponse)
async def settings_bu_create(
    request: Request,
    name: str = Form(...),
    head: str = Form(""),
    default_recruiter: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    existing = db.exec(select(BusinessUnit).where(BusinessUnit.name == name.strip())).first()
    if existing:
        return HTMLResponse('', status_code=422, headers={"HX-Reswap": "none", "HX-Trigger": '{"toast":{"value":"Business unit already exists","severity":"error"}}'})

    bu = BusinessUnit(
        name=name.strip(),
        head=head.strip() or None,
        default_recruiter=default_recruiter.strip() or None,
    )
    db.add(bu)
    db.commit()

    bus = db.exec(select(BusinessUnit).order_by(BusinessUnit.name)).all()
    return _render(request, "settings_bu.html", {"admin": admin, "business_units": bus, "active_tab": "business-units"})


@router.post("/business-units/{bu_id}", response_class=HTMLResponse)
async def settings_bu_update(
    request: Request,
    bu_id: int,
    name: str = Form(...),
    head: str = Form(""),
    default_recruiter: str = Form(""),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    bu = db.get(BusinessUnit, bu_id)
    if not bu:
        return HTMLResponse("Not found", status_code=404)

    bu.name = name.strip()
    bu.head = head.strip() or None
    bu.default_recruiter = default_recruiter.strip() or None
    db.add(bu)
    db.commit()

    bus = db.exec(select(BusinessUnit).order_by(BusinessUnit.name)).all()
    return _render(request, "settings_bu.html", {"admin": admin, "business_units": bus, "active_tab": "business-units"})


@router.post("/business-units/{bu_id}/deactivate", response_class=HTMLResponse)
async def settings_bu_deactivate(
    request: Request,
    bu_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    bu = db.get(BusinessUnit, bu_id)
    if not bu:
        return HTMLResponse("Not found", status_code=404)

    active_jobs = db.exec(
        select(Job).where(Job.business_unit_id == bu_id, Job.status == "open", not_deleted(Job))
    ).all()
    if active_jobs:
        return HTMLResponse('', status_code=422, headers={"HX-Reswap": "none", "HX-Trigger": f'{{"toast":{{"value":"Cannot deactivate — {len(active_jobs)} active job(s) reference this BU","severity":"error"}}}}'})

    bu.is_active = not bu.is_active
    db.add(bu)
    db.commit()

    bus = db.exec(select(BusinessUnit).order_by(BusinessUnit.name)).all()
    return _render(request, "settings_bu.html", {"admin": admin, "business_units": bus, "active_tab": "business-units"})


# --- Managed Positions ---


@router.get("/positions", response_class=HTMLResponse)
async def settings_positions(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    items = db.exec(select(ManagedPosition).order_by(ManagedPosition.order)).all()
    usage = _job_usage_counts(db, "position")
    ctx = {"admin": admin, "items": items, "active_tab": "positions", "list_type": "positions", "label_field": "title", "usage": usage}
    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return _render(request, "settings_list.html", ctx)
    return _render(request, "settings_layout.html", {**ctx, "tab_content": "settings_list.html"})


@router.post("/positions", response_class=HTMLResponse)
async def settings_positions_add(
    request: Request,
    value: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    existing = db.exec(select(ManagedPosition).where(ManagedPosition.title == value.strip())).first()
    if existing:
        return HTMLResponse('', status_code=422, headers={"HX-Reswap": "none", "HX-Trigger": '{"toast":{"value":"Already exists","severity":"error"}}'})

    max_order = db.exec(select(ManagedPosition).order_by(ManagedPosition.order.desc())).first()
    order = (max_order.order + 1) if max_order else 0
    db.add(ManagedPosition(title=value.strip(), order=order))
    db.commit()

    items = db.exec(select(ManagedPosition).order_by(ManagedPosition.order)).all()
    usage = _job_usage_counts(db, "position")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "positions", "list_type": "positions", "label_field": "title", "usage": usage})


@router.post("/positions/{item_id}/delete", response_class=HTMLResponse)
async def settings_positions_delete(
    request: Request,
    item_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    item = db.get(ManagedPosition, item_id)
    if item:
        db.delete(item)
        db.commit()

    items = db.exec(select(ManagedPosition).order_by(ManagedPosition.order)).all()
    usage = _job_usage_counts(db, "position")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "positions", "list_type": "positions", "label_field": "title", "usage": usage})


@router.post("/positions/{item_id}/edit", response_class=HTMLResponse)
async def settings_positions_edit(
    request: Request,
    item_id: int,
    value: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    item = db.get(ManagedPosition, item_id)
    if item:
        item.title = value.strip()
        db.add(item)
        db.commit()

    items = db.exec(select(ManagedPosition).order_by(ManagedPosition.order)).all()
    usage = _job_usage_counts(db, "position")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "positions", "list_type": "positions", "label_field": "title", "usage": usage})


# --- Managed Levels ---


@router.get("/levels", response_class=HTMLResponse)
async def settings_levels(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    items = db.exec(select(ManagedLevel).order_by(ManagedLevel.order)).all()
    usage = _job_usage_counts(db, "level")
    ctx = {"admin": admin, "items": items, "active_tab": "levels", "list_type": "levels", "label_field": "label", "usage": usage}
    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return _render(request, "settings_list.html", ctx)
    return _render(request, "settings_layout.html", {**ctx, "tab_content": "settings_list.html"})


@router.post("/levels", response_class=HTMLResponse)
async def settings_levels_add(
    request: Request,
    value: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    existing = db.exec(select(ManagedLevel).where(ManagedLevel.label == value.strip())).first()
    if existing:
        return HTMLResponse('', status_code=422, headers={"HX-Reswap": "none", "HX-Trigger": '{"toast":{"value":"Already exists","severity":"error"}}'})

    max_order = db.exec(select(ManagedLevel).order_by(ManagedLevel.order.desc())).first()
    order = (max_order.order + 1) if max_order else 0
    db.add(ManagedLevel(label=value.strip(), order=order))
    db.commit()

    items = db.exec(select(ManagedLevel).order_by(ManagedLevel.order)).all()
    usage = _job_usage_counts(db, "level")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "levels", "list_type": "levels", "label_field": "label", "usage": usage})


@router.post("/levels/{item_id}/delete", response_class=HTMLResponse)
async def settings_levels_delete(
    request: Request,
    item_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    item = db.get(ManagedLevel, item_id)
    if item:
        db.delete(item)
        db.commit()

    items = db.exec(select(ManagedLevel).order_by(ManagedLevel.order)).all()
    usage = _job_usage_counts(db, "level")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "levels", "list_type": "levels", "label_field": "label", "usage": usage})


@router.post("/levels/{item_id}/edit", response_class=HTMLResponse)
async def settings_levels_edit(
    request: Request,
    item_id: int,
    value: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    item = db.get(ManagedLevel, item_id)
    if item:
        item.label = value.strip()
        db.add(item)
        db.commit()

    items = db.exec(select(ManagedLevel).order_by(ManagedLevel.order)).all()
    usage = _job_usage_counts(db, "level")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "levels", "list_type": "levels", "label_field": "label", "usage": usage})


@router.post("/levels/reorder", response_class=HTMLResponse)
async def settings_levels_reorder(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    form = await request.form()
    order_str = form.get("order", "")
    if order_str:
        ids = [int(x) for x in order_str.split(",") if x.strip()]
        for i, item_id in enumerate(ids):
            item = db.get(ManagedLevel, item_id)
            if item:
                item.order = i
                db.add(item)
        db.commit()

    items = db.exec(select(ManagedLevel).order_by(ManagedLevel.order)).all()
    usage = _job_usage_counts(db, "level")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "levels", "list_type": "levels", "label_field": "label", "usage": usage})


# --- Managed Job Types ---


@router.get("/job-types", response_class=HTMLResponse)
async def settings_job_types(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    items = db.exec(select(ManagedJobType).order_by(ManagedJobType.order)).all()
    usage = _job_usage_counts(db, "job_type")
    ctx = {"admin": admin, "items": items, "active_tab": "job-types", "list_type": "job-types", "label_field": "label", "usage": usage}
    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return _render(request, "settings_list.html", ctx)
    return _render(request, "settings_layout.html", {**ctx, "tab_content": "settings_list.html"})


@router.post("/job-types", response_class=HTMLResponse)
async def settings_job_types_add(
    request: Request,
    value: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    existing = db.exec(select(ManagedJobType).where(ManagedJobType.label == value.strip())).first()
    if existing:
        return HTMLResponse('', status_code=422, headers={"HX-Reswap": "none", "HX-Trigger": '{"toast":{"value":"Already exists","severity":"error"}}'})

    max_order = db.exec(select(ManagedJobType).order_by(ManagedJobType.order.desc())).first()
    order = (max_order.order + 1) if max_order else 0
    db.add(ManagedJobType(label=value.strip(), order=order))
    db.commit()

    items = db.exec(select(ManagedJobType).order_by(ManagedJobType.order)).all()
    usage = _job_usage_counts(db, "job_type")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "job-types", "list_type": "job-types", "label_field": "label", "usage": usage})


@router.post("/job-types/{item_id}/delete", response_class=HTMLResponse)
async def settings_job_types_delete(
    request: Request,
    item_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    item = db.get(ManagedJobType, item_id)
    if item:
        db.delete(item)
        db.commit()

    items = db.exec(select(ManagedJobType).order_by(ManagedJobType.order)).all()
    usage = _job_usage_counts(db, "job_type")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "job-types", "list_type": "job-types", "label_field": "label", "usage": usage})


@router.post("/job-types/{item_id}/edit", response_class=HTMLResponse)
async def settings_job_types_edit(
    request: Request,
    item_id: int,
    value: str = Form(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
):
    item = db.get(ManagedJobType, item_id)
    if item:
        item.label = value.strip()
        db.add(item)
        db.commit()

    items = db.exec(select(ManagedJobType).order_by(ManagedJobType.order)).all()
    usage = _job_usage_counts(db, "job_type")
    return _render(request, "settings_list.html", {"admin": admin, "items": items, "active_tab": "job-types", "list_type": "job-types", "label_field": "label", "usage": usage})
