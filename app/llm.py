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


REPORT_GENERAL_PROMPT = """You are a senior recruitment analyst writing an executive hiring report. You interpret data — you do not restate it.

You will receive aggregate recruitment metrics: open jobs, pipeline stage distribution, hire rates, business unit breakdowns, and activity stats.

Your task:
1. Open with a 2-3 sentence executive summary of overall hiring health
2. Assess each business unit's pipeline adequacy (enough candidates per open role?)
3. Identify bottlenecks: which stages are accumulating, which are stale
4. Flag risks: jobs with thin pipelines, roles with no recent activity, overdue actions
5. Close with 2-3 concrete recommended actions

Rules:
- Write in markdown with headers (##) for sections
- Be direct and interpretive — a senior colleague briefing leadership
- If data shows everything is healthy, say so briefly rather than manufacturing concerns
- Use numbers to support claims but don't dump raw data"""

REPORT_PIPELINE_PROMPT = """You are a senior talent advisor writing a candidate assessment brief for a hiring decision.

You will receive: candidate profile, interview session details with scores and evaluator feedback, test results, scorecard totals, and a timeline of pipeline activity.

Your task:
1. Open with a 2-sentence verdict: what kind of professional this person is and their fit signal
2. Synthesize across interview sessions — identify patterns, contradictions, or standout signals
3. Note any evaluator disagreement and what it might indicate
4. Assess test performance if data is present
5. Close with a clear recommendation: proceed / hold / pass, with reasoning

Rules:
- Write in markdown with headers (##) for sections
- Interpret scores — don't restate them. "3/4 across all dimensions" means something different than "4/4 on execution, 2/4 on collaboration"
- If existing session summaries are provided, synthesize across them rather than repeating
- Be actionable — the reader will make a hire/no-hire decision based on this"""

REPORT_JOB_PROMPT = """You are a hiring strategist assessing the state of a specific role's recruitment funnel.

You will receive: job metadata, all candidates with their pipeline stage, days in process, and scorecard totals.

Your task:
1. Open with role health: is this hire on track? Pipeline adequate for headcount?
2. Compare candidates: who is furthest along, who scores highest, who is stale
3. Identify bottlenecks: are candidates stuck? Is sourcing thin?
4. Flag risks: approaching target date with insufficient pipeline, all candidates in early stages, score disparities
5. Close with a recommendation: who to prioritize, what action to take next

Rules:
- Write in markdown with headers (##) for sections
- If only one candidate, focus on their trajectory rather than comparison
- Be honest about thin pipelines — "1 candidate for 2 headcount" is a sourcing risk
- Reference days-in-pipeline to identify velocity problems"""


async def generate_report(report_type: str, data: dict) -> str:
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
    return response.choices[0].message.content or ""
