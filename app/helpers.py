"""Shared view helpers."""
from fastapi import Request


def render_gone(request: Request, entity_label: str, back_url: str, back_label: str):
    return request.app.state.templates.TemplateResponse(
        request, "gone.html",
        {"entity_label": entity_label, "back_url": back_url, "back_label": back_label},
        status_code=404,
    )
