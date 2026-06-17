import os
from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./interview.db")
engine = create_engine(DATABASE_URL, echo=False)


def create_tables():
    from app.models import AdminUser, Candidate, CandidatePipeline, InterviewSession, SessionInterviewer, Response, ResponseScore, Setting, Template, TemplateSection  # noqa
    SQLModel.metadata.create_all(engine)
    from app.seed import seed_templates
    seed_templates(engine)


def get_session():
    with Session(engine) as session:
        yield session
