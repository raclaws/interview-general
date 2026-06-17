import json
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class AdminUser(SQLModel, table=True):
    __tablename__ = "admin_users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str


class Candidate(SQLModel, table=True):
    __tablename__ = "candidates"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    phone: Optional[str] = None
    nocodb_id: Optional[int] = None
    current_position: Optional[str] = None
    yoe: Optional[str] = None
    languages: Optional[str] = None
    cloud: Optional[str] = None
    tools: Optional[str] = None
    working_arrangement: Optional[str] = None
    current_salary: Optional[str] = None
    expected_salary: Optional[str] = None
    notice_period: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_snapshot(self) -> dict:
        return {
            "name": self.name,
            "phone": self.phone or "",
            "email": self.email,
            "current_position": self.current_position or "",
            "yoe": self.yoe or "",
            "languages": self.languages or "",
            "cloud": self.cloud or "",
            "tools": self.tools or "",
            "working_arrangement": self.working_arrangement or "",
            "current_salary": self.current_salary or "",
            "expected_salary": self.expected_salary or "",
            "notice_period": self.notice_period or "",
        }


PIPELINE_STAGES = [
    "screening",
    "test",
    "interview",
    "offer",
    "hired",
    "rejected",
    "withdrawn",
    "on_hold",
]


class CandidatePipeline(SQLModel, table=True):
    __tablename__ = "candidate_pipelines"

    id: Optional[int] = Field(default=None, primary_key=True)
    candidate_id: int = Field(foreign_key="candidates.id")
    business_unit: Optional[str] = None
    position: Optional[str] = None
    stage: str = Field(default="screening")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Template(SQLModel, table=True):
    __tablename__ = "templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TemplateSection(SQLModel, table=True):
    __tablename__ = "template_sections"

    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: int = Field(foreign_key="templates.id")
    order: int
    title: str
    description: Optional[str] = None
    measurement_type: str
    options: Optional[str] = None
    anchor_low: Optional[str] = None
    anchor_high: Optional[str] = None
    max_selections: Optional[int] = None
    required: bool = Field(default=True)
    condition_section_id: Optional[int] = None
    condition_value: Optional[str] = None

    @property
    def options_list(self) -> list[str]:
        if self.options:
            return json.loads(self.options)
        return []


class InterviewSession(SQLModel, table=True):
    __tablename__ = "sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: Optional[int] = Field(default=None, foreign_key="templates.id")
    candidate_id: Optional[int] = Field(default=None, foreign_key="candidates.id")
    pipeline_id: Optional[int] = Field(default=None, foreign_key="candidate_pipelines.id")
    candidate_snapshot: str  # JSON string — frozen at creation time
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
    free_text: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    summary: str = ""


class ResponseScore(SQLModel, table=True):
    __tablename__ = "response_scores"

    id: Optional[int] = Field(default=None, primary_key=True)
    response_id: int = Field(foreign_key="responses.id")
    section_id: int = Field(foreign_key="template_sections.id")
    value: str = ""


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: str = ""


DRIVE_DREAM_OPTIONS = [
    "Survival - Visi masa depan sangat samar atau tidak ada. Semua motivasi ekstrinsik.",
    "Growth - Excited cerita hal baru yang dipelajari mandiri. Punya roadmap pengembangan diri.",
    "Impact - Jawaban pencapaian selalu dalam bahasa dampak, ada angka atau before-after.",
    "Ambition - Visi masa depan sangat spesifik soal posisi dan title. Excited cerita pencapaian yang diakui orang lain.",
]

HR_DIMENSIONS = [
    {"key": "ownership_accountability", "label": "Ownership with Accountability"},
    {"key": "maturity_growth", "label": "Maturity & Growth Mindset"},
    {"key": "supportive_collaborative", "label": "Supportive & Collaborative"},
]

CULTURE_DIMENSIONS = [
    {"key": "execution_excellence", "label": "Execution Excellence"},
    {"key": "learn_adapt", "label": "Learn Fast, Adapt Faster"},
    {"key": "impact_over_activity", "label": "Impact Over Activity"},
    {"key": "clarity_structured", "label": "Clarity & Structured Thinking"},
]


class PipelineScore(SQLModel, table=True):
    __tablename__ = "pipeline_scores"

    id: Optional[int] = Field(default=None, primary_key=True)
    pipeline_id: int = Field(foreign_key="candidate_pipelines.id", unique=True)
    hr_scores: str = ""
    culture_scores: str = ""
    hr_drive_dream: str = ""
    culture_drive_dream: str = ""
    hr_notes: Optional[str] = None
    culture_notes: Optional[str] = None
    scored_by: Optional[str] = None
    scored_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def hr_scores_dict(self) -> dict:
        return json.loads(self.hr_scores) if self.hr_scores else {}

    @property
    def culture_scores_dict(self) -> dict:
        return json.loads(self.culture_scores) if self.culture_scores else {}

    @property
    def hr_total(self) -> int:
        return sum(int(v) for v in self.hr_scores_dict.values() if v)

    @property
    def culture_total(self) -> int:
        return sum(int(v) for v in self.culture_scores_dict.values() if v)
