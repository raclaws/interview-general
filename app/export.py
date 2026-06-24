import csv
import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


def render_pdf(template_name: str, context: dict) -> bytes:
    from weasyprint import HTML

    template = _env.get_template(template_name)
    html_string = template.render(**context)
    return HTML(string=html_string).write_pdf()


def pipeline_csv(pipeline, candidate, session_data, test_assignments=None) -> str:
    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM for Excel
    writer = csv.writer(buf)

    writer.writerow(["Pipeline Summary"])
    writer.writerow(["Candidate", candidate.name])
    writer.writerow(["Email", candidate.email or ""])
    writer.writerow(["Position", pipeline.position or ""])
    writer.writerow(["Business Unit", pipeline.business_unit or ""])
    writer.writerow(["Stage", pipeline.stage])
    writer.writerow(["Notes", pipeline.notes or ""])
    writer.writerow(["Updated", pipeline.updated_at.strftime("%Y-%m-%d %H:%M")])
    writer.writerow([])

    writer.writerow(["Sessions"])
    writer.writerow(["Template", "Interviewers", "Status", "Date", "Completed"])
    for item in session_data:
        s = item["session"]
        date_val = s.interview_date or s.created_at
        if hasattr(date_val, 'strftime'):
            date_str = date_val.strftime("%Y-%m-%d")
        else:
            date_str = str(date_val) if date_val else ""
        writer.writerow([
            item["template"].name if item["template"] else "",
            ", ".join(item["interviewers"]),
            s.status,
            date_str,
            f"{item['completed']}/{item['total']}",
        ])
    writer.writerow([])

    if test_assignments:
        writer.writerow(["Test Assignments"])
        writer.writerow(["Title", "URL", "Status", "Deadline"])
        for t in test_assignments:
            writer.writerow([
                t.title,
                t.external_url,
                t.status,
                t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else "",
            ])

    return buf.getvalue()


def scorecard_csv(hr_data, culture_data, hr_dimensions, culture_dimensions, hr_avg, culture_avg, candidate, pipeline) -> str:
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)

    writer.writerow(["Scorecard"])
    writer.writerow(["Candidate", candidate.name])
    writer.writerow(["Position", pipeline.position or ""])
    writer.writerow(["Business Unit", pipeline.business_unit or ""])
    writer.writerow([])

    if hr_data:
        writer.writerow(["HR Scores"])
        header = ["Interviewer"] + [d["label"] for d in hr_dimensions] + ["Total", "Drive & Dream"]
        writer.writerow(header)
        for entry in hr_data:
            row = [entry["name"]]
            total = 0
            for dim in hr_dimensions:
                val = entry["scores"].get(dim["key"], 0)
                row.append(val or "")
                total += val or 0
            row.append(total)
            row.append(", ".join(entry.get("drive_dream", [])))
            writer.writerow(row)
        avg_row = ["Average"]
        avg_total = 0
        for dim in hr_dimensions:
            val = hr_avg.get(dim["key"], 0)
            avg_row.append(val)
            avg_total += val
        avg_row.append(round(avg_total, 1))
        avg_row.append("")
        writer.writerow(avg_row)
        writer.writerow([])

    if culture_data:
        writer.writerow(["Culture Scores"])
        header = ["Interviewer"] + [d["label"] for d in culture_dimensions] + ["Total", "Drive & Dream"]
        writer.writerow(header)
        for entry in culture_data:
            row = [entry["name"]]
            total = 0
            for dim in culture_dimensions:
                val = entry["scores"].get(dim["key"], 0)
                row.append(val or "")
                total += val or 0
            row.append(total)
            row.append(", ".join(entry.get("drive_dream", [])))
            writer.writerow(row)
        avg_row = ["Average"]
        avg_total = 0
        for dim in culture_dimensions:
            val = culture_avg.get(dim["key"], 0)
            avg_row.append(val)
            avg_total += val
        avg_row.append(round(avg_total, 1))
        avg_row.append("")
        writer.writerow(avg_row)

    return buf.getvalue()
