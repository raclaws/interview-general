"""
Batch compute script: runs signal engine + CV parser on all cached candidates,
upserts results into candidate_signals table.

Usage: python -m scripts.compute_signals
Run from interview-general root directory.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "candidate-search"))

from sqlmodel import Session, select
from app.database import engine, create_tables
from app.models import Candidate, CandidateSignal

from signal_engine import run_engine, build_signal_map, normalize_salary
from cv_parser import parse_cv, summarize_cv
from credibility_layer import detect_employment_status

CV_CACHE = Path(__file__).resolve().parent.parent.parent / "candidate-search" / "cv_cache"


def load_records():
    path = CV_CACHE / "all_records.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cv_texts(records):
    texts = {}
    for r in records:
        rid = r.get("id", r.get("Id"))
        txt_path = CV_CACHE / f"{rid}.txt"
        if txt_path.exists():
            texts[rid] = txt_path.read_text(encoding="utf-8", errors="replace")
    return texts


def load_company_categories():
    path = CV_CACHE / "companies_categorized.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {item["name"]: item["category"] for item in data}


def resolve_candidate_category(cv_text: str, company_map: dict) -> str:
    """Determine company category from most recent employer in CV text."""
    if not cv_text:
        return ""
    from cv_parser import extract_timeline
    timeline = extract_timeline(cv_text)
    if not timeline:
        return ""
    latest_org = timeline[0].org
    if latest_org == "Unknown Org":
        return ""
    for company_name, category in company_map.items():
        if company_name.lower() in latest_org.lower() or latest_org.lower() in company_name.lower():
            return category
    return ""


def main():
    create_tables()
    print("Loading NocoDB records...")
    records = load_records()
    print(f"  {len(records)} records loaded")

    print("Loading CV texts...")
    cv_texts = load_cv_texts(records)
    print(f"  {len(cv_texts)} CV texts found")

    print("Loading company categories...")
    company_map = load_company_categories()
    print(f"  {len(company_map)} companies categorized")

    # Build per-record company category
    print("Resolving company categories per candidate...")
    company_categories = {}
    for r in records:
        rid = r.get("id", r.get("Id"))
        cv = cv_texts.get(rid, "")
        cat = resolve_candidate_category(cv, company_map)
        if cat:
            company_categories[rid] = cat

    print(f"  {len(company_categories)} candidates have company category")

    # Run signal engine (two-pass)
    print("Running signal engine...")
    outputs, store = run_engine(records, cv_texts=cv_texts, company_categories=company_categories)
    print(f"  {len(outputs)} outputs computed")

    # Parse CVs for searchable fields
    print("Parsing CVs for search index...")
    cv_signals = {}
    for rid, text in cv_texts.items():
        signals = parse_cv(text)
        cv_signals[rid] = signals

    # Build nocodb_id → candidate_id map from DB
    print("Matching to interview-general candidates...")
    with Session(engine) as db:
        candidates = db.exec(select(Candidate)).all()
        nocodb_map = {}
        for c in candidates:
            if c.nocodb_id:
                nocodb_map[c.nocodb_id] = c.id

        print(f"  {len(nocodb_map)} candidates have nocodb_id")

        # Upsert signals
        matched = 0
        for i, record in enumerate(records):
            rid = record.get("id", record.get("Id"))
            if rid not in nocodb_map:
                continue

            candidate_id = nocodb_map[rid]
            output = outputs[i]
            cv_sig = cv_signals.get(rid)

            # Build skills string
            skills_explicit = ""
            skills_contextual = ""
            domains = ""
            credentials = ""
            companies_str = ""
            latest_role = ""
            total_years = None
            trajectory = ""

            if cv_sig:
                skills_explicit = ",".join(sorted(cv_sig.skills_explicit))
                skills_contextual = ",".join(sorted(cv_sig.skills_contextual - cv_sig.skills_explicit))
                domains = ",".join(sorted(cv_sig.domains))
                credentials = ",".join(
                    c.institution.split(",")[0].strip()[:50]
                    for c in cv_sig.credentials[:5]
                )
                latest_role = cv_sig.latest_role
                total_years = cv_sig.total_years
                trajectory = cv_sig.title_trajectory
                # Companies from timeline
                orgs = [e.org for e in cv_sig.timeline if e.org != "Unknown Org"]
                companies_str = ",".join(orgs[:10])

            # Employment status
            f = record.get("fields", record)
            title_raw = f.get("Current Formal Positions", "")
            salary_signal = normalize_salary(f.get("(Full-time) Current Salary (Nett in IDR)", ""))
            salary_val = salary_signal.value if salary_signal.value else None
            emp_status = detect_employment_status(title_raw, salary_val)

            # Flags
            flags_data = []
            for flag in output.flags:
                flags_data.append({
                    "pattern": flag.pattern,
                    "a": flag.interpretation_a,
                    "b": flag.interpretation_b,
                })

            # Upsert
            existing = db.exec(
                select(CandidateSignal).where(CandidateSignal.candidate_id == candidate_id)
            ).first()

            data = dict(
                candidate_id=candidate_id,
                nocodb_id=rid,
                salary_label=output.salary_label.value,
                percentile=output.percentile,
                comparison_source=output._comparison_source,
                bucket_size=output._bucket_size,
                role_bucket=output.role_bucket,
                gate_status=output.gate_status.value,
                flag_count=len(output.flags),
                flags_json=json.dumps(flags_data),
                skills_explicit=skills_explicit,
                skills_contextual=skills_contextual,
                domains=domains,
                companies=companies_str,
                company_category=company_categories.get(rid, ""),
                credentials=credentials,
                latest_role=latest_role,
                total_years=total_years,
                trajectory=trajectory,
                employment_status=emp_status.value,
                computed_at=datetime.utcnow(),
            )

            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
            else:
                sig = CandidateSignal(**data)
                db.add(sig)

            matched += 1

        db.commit()
        print(f"  {matched} candidate signals upserted")
    print("Done.")


if __name__ == "__main__":
    main()
