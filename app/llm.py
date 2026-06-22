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
