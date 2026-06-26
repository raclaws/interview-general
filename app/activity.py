"""
Activity trail helper — FK-walk propagation pattern.

Rule: record on the mutated entity + every ancestor reachable by walking up foreign keys.
Caller passes pipeline_id when available — this function does the walk mechanically.
"""
from datetime import datetime
from app.models import Comment, CandidatePipeline


def record_activity(db, source_type: str, source_id: int, body: str, pipeline_id: int | None = None):
    targets = [(source_type, source_id)]

    if pipeline_id:
        if source_type != "pipeline":
            targets.append(("pipeline", pipeline_id))
        pipeline = db.get(CandidatePipeline, pipeline_id)
        if pipeline:
            targets.append(("candidate", pipeline.candidate_id))
            if pipeline.job_id:
                targets.append(("job", pipeline.job_id))

    for entity_type, entity_id in targets:
        db.add(Comment(
            entity_type=entity_type,
            entity_id=entity_id,
            kind="activity",
            body=body,
            author="system",
        ))
    db.flush()
