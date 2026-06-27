"""Seed script: populates ~100 interview sessions for table component testing."""
import json
import secrets
import random
from datetime import datetime, timedelta

from sqlmodel import Session, select
from app.database import engine
from app.models import Candidate, InterviewSession, SessionInterviewer, Template, Job, CandidatePipeline

FIRST_NAMES = ["Alice", "Bob", "Carol", "David", "Eva", "Frank", "Grace", "Henry", "Iris", "Jack",
               "Kate", "Leo", "Mia", "Noah", "Olivia", "Paul", "Quinn", "Rita", "Sam", "Tina",
               "Uma", "Victor", "Wendy", "Xavier", "Yuki", "Zara"]
LAST_NAMES = ["Chen", "Kumar", "Zhang", "Park", "Smith", "Lee", "Kim", "Wu", "Patel", "Brown",
              "Johnson", "Garcia", "Tanaka", "Nguyen", "Das", "Lim", "Yamada", "Santos", "Ali", "Cho"]
POSITIONS = ["Data Analyst", "Data Engineer", "Data Scientist", "ML Engineer", "Fullstack Developer",
             "QA Engineer", "Project Manager", "Business Analyst", "Design Graphic", "CRM Strategist"]
BUS = ["Markethac", "APEX", "EXONIA", "1011", "R&D", "Group Support"]
STATUSES = ["pending", "pending", "pending", "completed", "completed", "cancelled"]


def seed_test_data():
    with Session(engine) as db:
        # Check if already seeded
        existing = db.exec(select(InterviewSession)).all()
        if len(existing) >= 50:
            print(f"Already have {len(existing)} sessions, skipping seed.")
            return

        # Get or create templates
        templates = db.exec(select(Template)).all()
        if not templates:
            print("No templates found. Run the app first to seed templates.")
            return
        template_ids = [t.id for t in templates]
        template_map = {t.id: t.name for t in templates}

        # Get existing jobs
        jobs = db.exec(select(Job)).all()

        # Create candidates
        candidates = []
        for i in range(40):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            email = f"{first.lower()}.{last.lower()}{i}@example.com"

            existing_c = db.exec(select(Candidate).where(Candidate.email == email)).first()
            if existing_c:
                candidates.append(existing_c)
                continue

            c = Candidate(
                name=f"{first} {last}",
                email=email,
                phone=f"+62 812 {random.randint(1000,9999)} {random.randint(1000,9999)}",
                current_position=random.choice(POSITIONS),
                yoe=f"{random.randint(1,12)} years",
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
            )
            db.add(c)
            db.flush()
            candidates.append(c)

        db.commit()

        # Create sessions
        count = 0
        for i in range(100):
            candidate = random.choice(candidates)
            template_id = random.choice(template_ids)
            status = random.choice(STATUSES)
            position = random.choice(POSITIONS)
            bu = random.choice(BUS)
            days_ago = random.randint(0, 60)
            created = datetime.utcnow() - timedelta(days=days_ago)

            snapshot = json.dumps({
                "name": candidate.name,
                "email": candidate.email,
                "phone": candidate.phone or "",
                "current_position": candidate.current_position or "",
                "yoe": candidate.yoe or "",
                "languages": "",
                "cloud": "",
                "tools": "",
                "working_arrangement": "",
                "current_salary": "",
                "expected_salary": "",
                "notice_period": "",
                "cv_link": "",
            })

            # Pick a job if available
            job_title = f"{position} - {bu}"
            pipeline_id = None
            if jobs:
                job = random.choice(jobs)
                job_title = job.title or job_title
                pipelines = db.exec(
                    select(CandidatePipeline).where(
                        CandidatePipeline.candidate_id == candidate.id,
                        CandidatePipeline.job_id == job.id,
                    )
                ).first()
                if pipelines:
                    pipeline_id = pipelines.id

            session = InterviewSession(
                template_id=template_id,
                candidate_id=candidate.id,
                pipeline_id=pipeline_id,
                candidate_snapshot=snapshot,
                job_title=job_title,
                position=position,
                business_unit=bu,
                interview_date=(created + timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d"),
                status=status,
                created_at=created,
            )
            db.add(session)
            db.flush()

            # Add 1-3 interviewers
            num_interviewers = random.randint(1, 3)
            for j in range(num_interviewers):
                interviewer = SessionInterviewer(
                    session_id=session.id,
                    interviewer_name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                    token=secrets.token_urlsafe(16),
                    status="completed" if status == "completed" else "pending",
                )
                db.add(interviewer)

            count += 1

        db.commit()
        print(f"Seeded {count} sessions with interviewers.")


if __name__ == "__main__":
    seed_test_data()
