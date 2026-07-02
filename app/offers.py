"""Offer letter salary calculations and generation helpers."""
import json
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session, select

from app.database import engine
from app.models import Setting

BASE_DIR = Path(__file__).resolve().parent.parent
OFFERS_DIR = BASE_DIR / "static" / "offers"
OFFERS_DIR.mkdir(parents=True, exist_ok=True)

_offer_env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates" / "offers")), autoescape=True)

DEFAULT_OFFER_CONFIG = {
    "gapok": {"method": "pct", "value": 0.75, "of": "offering"},
    "gapok_floor": {"method": "fixed", "value": 10_000_000},
    "gapok_floor_threshold": {"method": "fixed", "value": 13_400_000},
    "tunjangan_rj_tier3": {"method": "fixed", "value": 20_000_000},
    "tunjangan_rj_tier2": {"method": "fixed", "value": 12_000_000},
    "bpjs_tk": {"method": "pct", "value": 0.03, "of": "gapok"},
}


def get_offer_config() -> dict:
    """Load offer calc config from Settings, fallback to defaults."""
    with Session(engine) as db:
        setting = db.exec(select(Setting).where(Setting.key == "offer_config")).first()
        if setting and setting.value:
            try:
                stored = json.loads(setting.value)
                merged = {}
                for key, default in DEFAULT_OFFER_CONFIG.items():
                    if key in stored:
                        if isinstance(stored[key], dict):
                            merged[key] = {**default, **stored[key]}
                        else:
                            merged[key] = {**default, "value": stored[key]}
                    else:
                        merged[key] = default
                return merged
            except (json.JSONDecodeError, TypeError):
                pass
    return {k: v.copy() for k, v in DEFAULT_OFFER_CONFIG.items()}


def save_offer_config(config: dict):
    """Save offer calc config to Settings."""
    with Session(engine) as db:
        setting = db.exec(select(Setting).where(Setting.key == "offer_config")).first()
        if setting:
            setting.value = json.dumps(config)
        else:
            db.add(Setting(key="offer_config", value=json.dumps(config)))
        db.commit()


def _resolve_factor(cfg_entry: dict, reference: int) -> int:
    """Resolve a config factor to an absolute value given a reference amount."""
    if cfg_entry["method"] == "pct":
        return int(reference * float(cfg_entry["value"]))
    return int(cfg_entry["value"])


def calc_salary(amount: int, config: dict = None) -> dict:
    """Calculate salary breakdown from net offering amount."""
    cfg = config or get_offer_config()
    threshold = _resolve_factor(cfg["gapok_floor_threshold"], amount)
    floor = _resolve_factor(cfg["gapok_floor"], amount)
    gapok_resolved = _resolve_factor(cfg["gapok"], amount)

    if amount > threshold:
        gapok = gapok_resolved
        tunjangan_jabatan = amount - gapok
    elif amount < floor:
        gapok = amount
        tunjangan_jabatan = 0
    else:
        gapok = floor
        tunjangan_jabatan = amount - floor
    return {"gapok": gapok, "tunjangan_jabatan": tunjangan_jabatan}


def calc_tunjangan_rj(amount: int, config: dict = None) -> int:
    """Calculate tunjangan rawat jalan tier."""
    cfg = config or get_offer_config()
    tier3 = _resolve_factor(cfg["tunjangan_rj_tier3"], amount)
    tier2 = _resolve_factor(cfg["tunjangan_rj_tier2"], amount)

    if amount >= tier3:
        return tier3
    elif amount >= tier2:
        return tier2
    return amount


def calc_bpjs_tk(gapok: int, config: dict = None) -> int:
    """Calculate BPJS TK employee contribution."""
    cfg = config or get_offer_config()
    bpjs_entry = cfg["bpjs_tk"]
    return _resolve_factor(bpjs_entry, gapok)


def format_idr(amount: int) -> str:
    """Format integer as IDR string with thousand separators."""
    return f"{amount:,.0f}".replace(",", ".")


def generate_offer_html(data: dict) -> str:
    """Render offer letter HTML from data dict."""
    template = _offer_env.get_template("letter.html")
    return template.render(**data)


def save_offer(pipeline_id: int, html: str) -> tuple[str, str]:
    """Save HTML and generate PDF. Returns (html_filename, pdf_filename)."""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    html_filename = f"offer_{pipeline_id}_{ts}.html"
    pdf_filename = f"offer_{pipeline_id}_{ts}.pdf"

    html_path = OFFERS_DIR / html_filename
    html_path.write_text(html, encoding="utf-8")

    pdf_path = OFFERS_DIR / pdf_filename
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(pdf_path))
    except Exception:
        pdf_filename = ""

    return html_filename, pdf_filename


def build_offer_data(
    candidate_name: str,
    job_title: str,
    business_unit: str,
    offering_amount: int,
    bpjs_tk: bool = False,
    probation_change: bool = False,
    post_probation_amount: int | None = None,
    start_date: str = "tbc",
    metode_kerja: str = "Hybrid – Jakarta (3 hari WFO, 2 hari WFH)",
) -> dict:
    """Build the full data dict for template rendering."""
    cfg = get_offer_config()
    salary = calc_salary(offering_amount, cfg)
    tunjangan_rj = calc_tunjangan_rj(offering_amount, cfg)
    bpjs_amount = calc_bpjs_tk(salary["gapok"], cfg) if bpjs_tk else 0

    data = {
        "candidate_name": candidate_name,
        "job_title": job_title,
        "business_unit": business_unit,
        "offering_amount": format_idr(offering_amount),
        "gapok": format_idr(salary["gapok"]),
        "tunjangan_jabatan": format_idr(salary["tunjangan_jabatan"]),
        "tunjangan_rj": format_idr(tunjangan_rj),
        "bpjs_tk": bpjs_tk,
        "bpjs_amount": format_idr(bpjs_amount),
        "probation_change": probation_change,
        "start_date": start_date or "tbc",
        "metode_kerja": metode_kerja,
        "generated_date": datetime.utcnow().strftime("%Y-%m-%d"),
    }

    if probation_change and post_probation_amount:
        post_salary = calc_salary(post_probation_amount, cfg)
        post_bpjs = calc_bpjs_tk(post_salary["gapok"], cfg) if bpjs_tk else 0
        data["post_probation"] = {
            "amount": format_idr(post_probation_amount),
            "gapok": format_idr(post_salary["gapok"]),
            "tunjangan_jabatan": format_idr(post_salary["tunjangan_jabatan"]),
            "bpjs_amount": format_idr(post_bpjs),
        }

    return data
