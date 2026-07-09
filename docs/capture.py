"""
Docs screenshot capture script.
Requires: pip install playwright && playwright install chromium

Usage:
    1. Start the app: uvicorn app.main:app --port 8000
    2. Run: python docs/capture.py

Screenshots saved to static/docs/img/
"""
import os
import sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "docs", "img")
os.makedirs(OUT_DIR, exist_ok=True)

PAGES = [
    # (path, filename, wait_selector, description)
    # Home / navigation
    ("/", "sidebar-nav.png", ".sidebar-nav", "Sidebar navigation"),
    ("/login", "login.png", "button[type='submit']", "Login page"),

    # Jobs
    ("/jobs", "jobs-list.png", ".table-clean tbody tr", "Jobs list page"),
    ("/job/new", "job-form.png", ".form-card", "Job creation form"),

    # Candidates
    ("/candidates", "candidates-list.png", ".table-clean tbody tr", "Candidates list"),

    # Pipelines
    ("/pipelines", "pipelines-list.png", ".table-clean tbody tr", "Pipelines list"),

    # Tasks
    ("/tasks", "tasks-list.png", ".table-clean tbody tr", "Tasks list"),
    ("/tasks/new", "task-form.png", ".form-card", "Task creation form"),

    # Interview
    ("/sessions", "sessions-list.png", ".table-clean tbody tr", "Sessions list"),

    # Reports
    ("/reports", "reports.png", ".page-header", "Reports page"),

    # Settings
    ("/settings", "settings-llm.png", ".page-header", "Settings LLM tab"),
]

# Pages that need a specific job/pipeline ID — captured dynamically
DYNAMIC_PAGES = [
    # Will be resolved at runtime by finding first valid ID
    ("job_detail", "/job/{id}", "job-detail.png", ".detail-section"),
    ("pipeline_detail", "/pipeline/{id}", "pipeline-detail.png", ".detail-section"),
    ("session_detail", "/session/{id}", "session-detail.png", ".detail-section"),
    ("task_detail", "/tasks/{id}", "task-detail.png", ".detail-section"),
]


def capture(page, path, filename, wait_selector, full_page=True):
    url = BASE + path
    print(f"  > {path} ... ", end="", flush=True)
    try:
        page.goto(url, wait_until="networkidle")
        page.wait_for_selector(wait_selector, timeout=5000)
        page.wait_for_timeout(500)
        filepath = os.path.join(OUT_DIR, filename)
        page.screenshot(path=filepath, full_page=full_page)
        print(f"OK ({filename})")
        return True
    except Exception as e:
        print(f"SKIP ({e})")
        return False


def find_first_id(page, list_path, table="jobs"):
    """Navigate to a list page and extract the first row's href ID."""
    page.goto(BASE + list_path, wait_until="networkidle")
    try:
        page.wait_for_selector(".table-clean tbody tr", timeout=5000)
        row = page.query_selector(".clickable-row[data-href]")
        if row:
            href = row.get_attribute("data-href")
            return href.split("/")[-1] if href else None
    except Exception:
        pass
    return None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # Login
        print("Logging in...")
        page.goto(BASE + "/login")
        page.fill('[name="username"]', "admin")
        page.fill('[name="password"]', "admin")
        page.click('button[type="submit"]')
        page.wait_for_url("**/")
        print("  Logged in.\n")

        # Static pages
        print("Capturing static pages:")
        for path, filename, wait_sel, desc in PAGES:
            capture(page, path, filename, wait_sel)

        # Dynamic pages — find first valid ID
        print("\nCapturing dynamic pages:")
        job_id = find_first_id(page, "/jobs", "jobs")
        pipeline_id = find_first_id(page, "/pipelines", "pipelines")
        session_id = find_first_id(page, "/sessions", "sessions")
        task_id = find_first_id(page, "/tasks", "tasks")

        id_map = {
            "job_detail": job_id,
            "pipeline_detail": pipeline_id,
            "session_detail": session_id,
            "task_detail": task_id,
        }

        for key, path_tpl, filename, wait_sel in DYNAMIC_PAGES:
            entity_id = id_map.get(key)
            if entity_id:
                path = path_tpl.replace("{id}", str(entity_id))
                capture(page, path, filename, wait_sel)
            else:
                print(f"  > {path_tpl} ... SKIP (no {key} found)")

        # Job post form (if job exists)
        if job_id:
            capture(page, f"/job/{job_id}/post", "job-post-form.png", ".form-card")

        # Portal (try to find a BU with token)
        print("\nCapturing portal (if token exists):")
        try:
            page.goto(BASE + "/settings", wait_until="networkidle")
            # Look for portal link in page source
            content = page.content()
            import re
            match = re.search(r'/portal/([a-zA-Z0-9_-]+)', content)
            if match:
                token = match.group(1)
                capture(page, f"/portal/{token}", "portal-home.png", ".page-header")
            else:
                print("  No portal token found in settings.")
        except Exception as e:
            print(f"  Portal capture skipped: {e}")

        browser.close()
        print(f"\nDone. Screenshots saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
