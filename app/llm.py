import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
from sqlmodel import Session, select

from app.database import engine
from app.models import Setting, TemplateSection

load_dotenv()

DEFAULT_SYSTEM_PROMPT = """You are a senior talent advisor writing a concise candidate brief for a hiring decision. You do not summarize — you interpret.

You will receive:
- Candidate name and role applied for
- Evaluator responses across defined dimensions
- Optional free text from evaluators

Your task:
1. Identify which dimensions cluster and which break from the cluster
2. Flag any meaningful contradictions across dimensions or evaluators
3. Write a 2-5 sentence verdict: what kind of operator this person is, where they would perform well, and what the risk or ceiling is

Rules:
- No bullet points. Prose only.
- Do not restate the scores. Interpret them.
- If free text is provided, fold it in only if it adds signal.
- If all scores cluster without variance and no free text adds signal, state so briefly rather than manufacturing insight.
- Write as a senior colleague briefing a decision-maker, not as an HR system generating a report."""


def get_setting(key: str, fallback: str = "") -> str:
    with Session(engine) as db:
        setting = db.exec(select(Setting).where(Setting.key == key)).first()
        if setting and setting.value:
            return setting.value
    return os.getenv(key.upper(), fallback)


def set_setting(key: str, value: str):
    with Session(engine) as db:
        setting = db.exec(select(Setting).where(Setting.key == key)).first()
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
        db.add(setting)
        db.commit()


def get_llm_config() -> tuple[str, str, str, str]:
    base_url = get_setting("llm_base_url", "https://api.openai.com/v1")
    api_key = get_setting("llm_api_key", "")
    model = get_setting("llm_model", "gpt-4o")
    system_prompt = get_setting("llm_system_prompt", DEFAULT_SYSTEM_PROMPT)
    return base_url, api_key, model, system_prompt


def get_llm_params() -> tuple[float, int]:
    temperature = float(get_setting("llm_temperature", "0.3"))
    max_tokens = int(get_setting("llm_max_tokens", "700"))
    return temperature, max_tokens


def _build_dimensions_context(sections: list) -> str:
    lines = []
    for s in sections:
        if s.measurement_type == "rating_1_4":
            lines.append(f"- {s.title} (scale 1-4: {s.anchor_low} → {s.anchor_high})")
        elif s.measurement_type == "single_select":
            opts = s.options_list
            lines.append(f"- {s.title} (options: {', '.join(opts)})")
        elif s.measurement_type == "multi_select":
            opts = [o.split(" - ")[0] for o in s.options_list]
            lines.append(f"- {s.title} (multi-select, max {s.max_selections}: {', '.join(opts)})")
        elif s.measurement_type in ("short_text", "long_text"):
            lines.append(f"- {s.title} (free text)")
    return "\n".join(lines)


def _build_evaluator_block(sections: list, resp: dict) -> str:
    lines = [f"Evaluator: {resp['interviewer_name']}"]
    scores = resp.get("scores", {})
    for s in sections:
        val = scores.get(s.id, "")
        if val:
            lines.append(f"  {s.title}: {val}")
    if resp.get("free_text"):
        lines.append(f"  Notes: {resp['free_text']}")
    return "\n".join(lines)


async def generate_summary_dynamic(
    candidate_name: str,
    job_title: str,
    sections: list,
    responses_data: list[dict],
) -> str:
    base_url, api_key, model, system_prompt = get_llm_config()
    temperature, max_tokens = get_llm_params()
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    dimensions_context = _build_dimensions_context(sections)
    evaluator_blocks = []
    for resp in responses_data:
        evaluator_blocks.append(_build_evaluator_block(sections, resp))

    n_evaluators = len(responses_data)
    user_msg = f"""Candidate: {candidate_name}
Role: {job_title}
Number of evaluators: {n_evaluators}

Dimensions assessed:
{dimensions_context}

{"=" * 40}
{(chr(10) + "=" * 40 + chr(10)).join(evaluator_blocks)}
{"=" * 40}"""

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


REPORT_GENERAL_PROMPT = """You are a senior recruitment analyst. You will receive aggregate hiring metrics as JSON.

Return ONLY valid JSON (no markdown, no explanation) with this exact schema:
{
  "executive_summary": "2-3 sentence overview of overall hiring health",
  "alerts": [
    {"severity": "red|amber|green|blue", "title": "short headline", "body": "1-2 sentence explanation"}
  ],
  "bu_assessments": {
    "BU Name": "one-line health statement"
  },
  "recommendations": ["actionable recommendation 1", "actionable recommendation 2"]
}

Rules:
- Max 4 alerts, prioritized: red (overdue/empty pipelines) > amber (due today/stale) > blue (informational) > green (positive)
- executive_summary: interpret, don't restate numbers
- bu_assessments: one entry per BU in the data
- recommendations: 2-3 concrete actions, imperative form
- If everything looks healthy, say so — don't manufacture concerns"""

REPORT_JOB_PROMPT = """You are a hiring strategist assessing a specific role's recruitment funnel. You will receive job metadata and candidate pipeline data as JSON.

Return ONLY valid JSON (no markdown, no explanation) with this exact schema:
{
  "executive_summary": "2-3 sentence role health overview",
  "alerts": [
    {"severity": "red|amber|green|blue", "title": "short headline", "body": "1-2 sentence explanation"}
  ],
  "candidate_narratives": {
    "<pipeline_id>": {"verdict": "1 sentence on this candidate", "next_action": "what to do next", "next_action_urgency": "red|amber|green|gray"}
  },
  "recommendations": ["actionable recommendation 1", "actionable recommendation 2"]
}

Rules:
- Max 4 alerts prioritized by severity
- candidate_narratives: one entry per candidate pipeline_id in the data. Verdict interprets their stage + score + velocity
- next_action_urgency: red=overdue, amber=due soon/stale, green=on track, gray=on hold/no action
- If only 1 candidate, focus on trajectory not comparison
- Flag thin pipelines honestly"""

REPORT_PIPELINE_PROMPT = """You are a senior talent advisor writing a candidate assessment. You will receive candidate profile, interview sessions with scores, test results, and timeline data as JSON.

Return ONLY valid JSON (no markdown, no explanation) with this exact schema:
{
  "verdict": "2-3 sentence assessment of who this person is and their fit signal",
  "strengths": ["strength 1", "strength 2"],
  "risks": ["risk or concern 1", "risk or concern 2"],
  "recommendation": "proceed|hold|pass",
  "recommendation_reasoning": "1-2 sentence justification"
}

Rules:
- verdict: interpret scores and feedback, don't restate them
- strengths/risks: 2-4 items each, concrete and specific
- recommendation: exactly one of proceed/hold/pass
- If scores cluster without variance, note that briefly rather than inventing differentiation
- Synthesize across multiple sessions if present — contradictions between evaluators are signal"""


async def generate_report(report_type: str, data: dict) -> dict:
    prompts = {
        "general": REPORT_GENERAL_PROMPT,
        "pipeline": REPORT_PIPELINE_PROMPT,
        "job": REPORT_JOB_PROMPT,
    }
    system_prompt = prompts.get(report_type, REPORT_GENERAL_PROMPT)
    base_url, api_key, model, _ = get_llm_config()
    temperature, max_tokens = get_llm_params()
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    import json as json_mod
    user_msg = json_mod.dumps(data, indent=2, default=str)

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=temperature,
        max_tokens=min(max_tokens * 2, 2000),
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json_mod.loads(raw)
    except json_mod.JSONDecodeError:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
        try:
            return json_mod.loads(clean)
        except json_mod.JSONDecodeError:
            return {"_raw": raw, "_error": "LLM returned invalid JSON"}
