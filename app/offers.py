"""Offer letter salary calculations and generation helpers."""
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).resolve().parent.parent
OFFERS_DIR = BASE_DIR / "static" / "offers"
OFFERS_DIR.mkdir(parents=True, exist_ok=True)

_offer_env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates" / "offers")), autoescape=True)


def calc_salary(amount: int) -> dict:
    """Calculate salary breakdown from net offering amount."""
    if amount > 13_400_000:
        gapok = int(amount * 0.75)
        tunjangan_jabatan = amount - gapok
    elif amount < 10_000_000:
        gapok = amount
        tunjangan_jabatan = 0
    else:
        gapok = 10_000_000
        tunjangan_jabatan = amount - 10_000_000
    return {"gapok": gapok, "tunjangan_jabatan": tunjangan_jabatan}


def calc_tunjangan_rj(amount: int) -> int:
    """Calculate tunjangan rawat jalan tier."""
    if amount >= 20_000_000:
        return 20_000_000
    elif amount >= 12_000_000:
        return 12_000_000
    return amount


def calc_bpjs_tk(gapok: int) -> int:
    """Calculate BPJS TK employee contribution (3% of gapok)."""
    return int(gapok * 0.03)


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
    salary = calc_salary(offering_amount)
    tunjangan_rj = calc_tunjangan_rj(offering_amount)
    bpjs_amount = calc_bpjs_tk(salary["gapok"]) if bpjs_tk else 0

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
        post_salary = calc_salary(post_probation_amount)
        post_bpjs = calc_bpjs_tk(post_salary["gapok"]) if bpjs_tk else 0
        data["post_probation"] = {
            "amount": format_idr(post_probation_amount),
            "gapok": format_idr(post_salary["gapok"]),
            "tunjangan_jabatan": format_idr(post_salary["tunjangan_jabatan"]),
            "bpjs_amount": format_idr(post_bpjs),
        }

    return data
