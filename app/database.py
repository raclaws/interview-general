import os
from sqlmodel import SQLModel, create_engine, Session
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
    from app.models import AdminUser, Candidate, CandidatePipeline, InterviewSession, SessionInterviewer, Response, ResponseScore, Setting, Template, TemplateSection, PipelineScore, TableView, TestAssignment, ReviewBatch, ReviewScore, BusinessUnit, Job, ManagedPosition, ManagedLevel, ManagedJobType  # noqa
    SQLModel.metadata.create_all(engine)
    _migrate()
    from app.seed import seed_templates
    seed_templates(engine)
    from app.seed import seed_managed_data
    seed_managed_data(engine)
    from app.seed import migrate_legacy_job_ids
    migrate_legacy_job_ids(engine)


def get_session():
    with Session(engine) as session:
        yield session
