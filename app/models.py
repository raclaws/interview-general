import json
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class AdminUser(SQLModel, table=True):
    __tablename__ = "admin_users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str


class InterviewSession(SQLModel, table=True):
    __tablename__ = "sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    candidate_id: Optional[int] = Field(default=None)
    candidate_snapshot: str  # JSON string
    job_title: str
    round: str
    interview_date: Optional[str] = Field(default=None)
    show_salary: bool = Field(default=False)
    status: str = Field(default="pending")
    aggregate_summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def snapshot(self) -> dict:
        return json.loads(self.candidate_snapshot)


class SessionInterviewer(SQLModel, table=True):
    __tablename__ = "session_interviewers"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessions.id")
    interviewer_name: str
    token: str = Field(unique=True, index=True)
    status: str = Field(default="pending")


class Response(SQLModel, table=True):
    __tablename__ = "responses"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_interviewer_id: int = Field(foreign_key="session_interviewers.id")
    q1: int
    q2: int
    q3: int
    q4: int
    q5: bool
    free_text: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    summary: str = ""


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: str = ""
