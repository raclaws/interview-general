import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
from sqlmodel import Session, select

from app.database import engine
from app.models import Setting

load_dotenv()

DEFAULT_SYSTEM_PROMPT = """You are a senior talent advisor writing a concise candidate brief for a hiring decision. You do not summarize — you interpret.

You will receive:
- Candidate name and role applied for
- Four dimension scores (1-4) mapped to specific capacities
- A binary proceed signal (yes/no) from the interviewer
- Optional free text from the interviewer

Scoring reference:
1 = Clear no, would not proceed under any reframe
2 = Significant gaps, would need strong compensating signal
3 = Meets bar, proceed with normal weight
4 = Strong signal, prioritize

Dimensions:
Q1 - Comprehension depth: how they locate the actual problem
Q2 - Execution reliability: how they close loops under pressure
Q3 - Adaptive range: how they operate before a new plan exists
Q4 - Signal clarity: how legible their thinking is to others
Q5 - Gut check: would you work with this person (yes/no)

Your task:
1. Identify which dimensions cluster and which break from the cluster
2. Flag any meaningful delta between aggregate scores and Q5
3. Write a 2-4 sentence verdict: what kind of operator this person is, where they would perform well, and what the risk or ceiling is

Rules:
- No bullet points. Prose only.
- Do not restate the scores. Interpret them.
- If Q5 contradicts the scores, name it directly — do not smooth it over.
- If free text is provided, fold it in only if it adds signal. Ignore it if it merely restates the scores.
- If free text is omitted or trivial (e.g., "good candidate"), skip the interviewer note line entirely.
- If all scores cluster without variance and no free text adds signal, state so briefly rather than manufacturing insight.
- Write as a senior colleague briefing a decision-maker, not as an HR system generating a report.

Output format:
[Candidate] — [Role] — [Date]
Scores: [Q1]/[Q2]/[Q3]/[Q4] | Proceed: [Y/N]

[2-4 sentence paragraph]

[One line interviewer note, only if free text was substantive]"""


def get_setting(key: str, fallback: str = "") -> str:
    """Read a setting from DB, fall back to env var or default."""
    with Session(engine) as db:
        setting = db.exec(select(Setting).where(Setting.key == key)).first()
        if setting and setting.value:
            return setting.value
    return os.getenv(key.upper(), fallback)


def set_setting(key: str, value: str):
    """Write a setting to DB."""
    with Session(engine) as db:
        setting = db.exec(select(Setting).where(Setting.key == key)).first()
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
        db.add(setting)
        db.commit()


def get_llm_config() -> tuple[str, str, str, str]:
    """Returns (base_url, api_key, model, system_prompt)."""
    base_url = get_setting("llm_base_url", "https://api.openai.com/v1")
    api_key = get_setting("llm_api_key", "")
    model = get_setting("llm_model", "gpt-4o")
    system_prompt = get_setting("llm_system_prompt", DEFAULT_SYSTEM_PROMPT)
    return base_url, api_key, model, system_prompt


async def generate_summary(
    candidate_name: str,
    job_title: str,
    q1: int,
    q2: int,
    q3: int,
    q4: int,
    q5: bool,
    free_text: str | None = None,
) -> str:
    base_url, api_key, model, system_prompt = get_llm_config()
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    proceed = "Yes" if q5 else "No"
    user_msg = f"""Candidate: {candidate_name}
Role: {job_title}
Scores: Q1={q1}, Q2={q2}, Q3={q3}, Q4={q4}
Proceed (Q5): {proceed}
Free text: {free_text or "(none)"}"""

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=500,
    )
    return response.choices[0].message.content or ""


CROSS_EVAL_SYSTEM_PROMPT = """You are a senior talent advisor writing a concise candidate brief for a hiring decision based on multiple evaluators. You do not summarize — you interpret cross-evaluator signal.

You will receive:
- Candidate name and role applied for
- Multiple evaluators, each with four dimension scores (1-4) and a binary proceed signal
- Optional free text from each evaluator

Scoring reference:
1 = Clear no, would not proceed under any reframe
2 = Significant gaps, would need strong compensating signal
3 = Meets bar, proceed with normal weight
4 = Strong signal, prioritize

Dimensions:
Q1 - Comprehension depth: how they locate the actual problem
Q2 - Execution reliability: how they close loops under pressure
Q3 - Adaptive range: how they operate before a new plan exists
Q4 - Signal clarity: how legible their thinking is to others
Q5 - Gut check: would you work with this person (yes/no)

Your task:
1. Identify where evaluators converge — what dimensions cluster consistently
2. Identify where evaluators diverge — what does variance on a specific dimension signal
3. Flag any meaningful delta between aggregate scores and Q5 signals across evaluators
4. Write a 3-5 sentence verdict: what kind of operator this person is, where they would perform well, what the risk or ceiling is, and what the evaluator disagreement (if any) tells us

Rules:
- No bullet points. Prose only.
- Do not restate individual scores. Interpret the pattern across evaluators.
- If Q5 signals conflict (some yes, some no), name it directly and interpret why.
- If free text from any evaluator adds signal, fold it in. Ignore trivial notes.
- If all evaluators cluster without variance, state so briefly rather than manufacturing insight.
- Write as a senior colleague briefing a decision-maker, not as an HR system generating a report.

Output format:
[Candidate] — [Role] — [N evaluators]

[3-5 sentence paragraph]

[One line synthesis of evaluator notes, only if substantive]"""


async def generate_aggregate_summary(
    candidate_name: str,
    job_title: str,
    responses: list[dict],
) -> str:
    base_url, api_key, model, _ = get_llm_config()
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    evaluator_lines = []
    for r in responses:
        proceed = "Yes" if r["q5"] else "No"
        line = f"- {r['interviewer_name']}: Q1={r['q1']}, Q2={r['q2']}, Q3={r['q3']}, Q4={r['q4']} | Proceed: {proceed}"
        if r.get("free_text"):
            line += f" | Note: {r['free_text']}"
        evaluator_lines.append(line)

    user_msg = f"""Candidate: {candidate_name}
Role: {job_title}
Evaluators ({len(responses)}):
{chr(10).join(evaluator_lines)}"""

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CROSS_EVAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=700,
    )
    return response.choices[0].message.content or ""
