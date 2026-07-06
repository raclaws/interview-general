import os
from datetime import datetime
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import text, inspect
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./interview.db")
engine = create_engine(DATABASE_URL, echo=False)


def _migrate():
    """Add missing columns to existing tables."""
    migrations = [
        ("sessions", "pipeline_id", "INTEGER"),
        ("sessions", "candidate_id", "INTEGER"),
        ("sessions", "position", "TEXT"),
        ("sessions", "business_unit", "TEXT"),
        ("candidate_pipelines", "display_name", "TEXT"),
        ("candidate_pipelines", "job_id", "INTEGER"),
        ("candidates", "cv_link", "TEXT"),
        ("review_batches", "job_id", "INTEGER"),
        ("sessions", "deleted_at", "TIMESTAMP"),
        ("candidate_pipelines", "deleted_at", "TIMESTAMP"),
        ("jobs", "deleted_at", "TIMESTAMP"),
        ("test_assignments", "deleted_at", "TIMESTAMP"),
        ("template_sections", "example_questions", "TEXT"),
        ("template_sections", "good_answer", "TEXT"),
        ("template_sections", "red_flags", "TEXT"),
        ("candidates", "nocodb_deleted", "BOOLEAN DEFAULT 0"),
        ("business_units", "portal_token", "TEXT"),
    ]
    with engine.connect() as conn:
        inspector = inspect(engine)
        for table, column, col_type in migrations:
            if table in inspector.get_table_names():
                existing = [c["name"] for c in inspector.get_columns(table)]
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        # Handle legacy 'round' column: make it nullable so model without round can INSERT
        if "sessions" in inspector.get_table_names():
            cols = {c["name"]: c for c in inspector.get_columns("sessions")}
            if "round" in cols:
                try:
                    conn.execute(text('ALTER TABLE sessions DROP COLUMN "round"'))
                except Exception:
                    # SQLite <3.35 can't DROP COLUMN; set a default instead
                    try:
                        conn.execute(text('UPDATE sessions SET "round" = 1 WHERE "round" IS NULL'))
                    except Exception:
                        pass
        conn.commit()


def create_tables():
    from app.models import AdminUser, Candidate, CandidatePipeline, InterviewSession, SessionInterviewer, Response, ResponseScore, Setting, Template, TemplateSection, PipelineScore, TableView, TestAssignment, ReviewBatch, ReviewScore, BusinessUnit, Job, ManagedPosition, ManagedLevel, ManagedJobType, Comment, ReportHistory, OfferLetter, ManpowerRequest  # noqa
    SQLModel.metadata.create_all(engine)
    _migrate()
    _purge_soft_deleted()
    from app.seed import seed_templates
    seed_templates(engine)
    from app.seed import seed_managed_data
    seed_managed_data(engine)
    from app.seed import migrate_legacy_job_ids
    migrate_legacy_job_ids(engine)
    from app.seed import backfill_section_guidance
    backfill_section_guidance(engine)


def _purge_soft_deleted():
    """Hard delete records soft-deleted more than 30 days ago."""
    from datetime import timedelta
    from app.models import CandidatePipeline, InterviewSession, Job, TestAssignment
    cutoff = datetime.utcnow() - timedelta(days=30)
    with Session(engine) as db:
        deleted_any = False
        for model in [TestAssignment, InterviewSession, CandidatePipeline, Job]:
            stale = db.exec(
                select(model).where(model.deleted_at.isnot(None), model.deleted_at < cutoff)
            ).all()
            for record in stale:
                db.delete(record)
                deleted_any = True
        if deleted_any:
            db.commit()


def get_session():
    with Session(engine) as session:
        yield session
