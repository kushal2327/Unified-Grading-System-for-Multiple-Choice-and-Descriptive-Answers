"""
apps/descriptive_grading/pipeline/llm_grader.py

Phase 2, Steps 5-7: build the grading prompt, call the configured LLM
(Ollama locally or OpenAI in the cloud), parse its JSON response, and
validate/clamp the awarded score.
"""
import json
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMGradingError(Exception):
    """Raised when the LLM fails to produce a usable graded response
    after retrying once, per the spec's re-prompt-once-then-flag rule."""
    pass


def build_prompt(question_text: str, rubric: str, total_marks: int,
                  student_answer: str, context_available: bool,
                  combined_context: str = "") -> str:
    """Build the grading prompt sent to the LLM."""

    if context_available:
        reference_section = f"""
Reference Material:
{combined_context}
"""
    else:
        reference_section = """
No reference material available. Grade based on rubric and general knowledge.
"""

    prompt = f"""You are an expert grading assistant.

Question: {question_text}

Rubric: {rubric}
{reference_section}
Student Answer:
{student_answer}

Instructions:
1. Evaluate the student answer against each rubric point
2. For each rubric point state: full / partial / none
3. Award marks based on the rubric
4. Write specific feedback on what was correct, what was missing, and what was partially correct
5. Justify the final mark clearly
6. Respond ONLY in this exact JSON format:
{{
  "marks": <integer>,
  "total": {total_marks},
  "feedback": "<specific written feedback>",
  "justification": {{
    "point1": {{"status": "full/partial/none", "marks": <integer>, "comment": "<why>"}},
    "point2": {{"status": "full/partial/none", "marks": <integer>, "comment": "<why>"}}
  }}
}}
7. marks must be between 0 and {total_marks}
8. Do not include any text outside the JSON
"""
    return prompt


def _extract_json(raw_response: str) -> dict:
    """
    Try to parse the LLM's raw response as JSON. LLMs sometimes wrap
    JSON in markdown code fences or add stray text around it, so we
    fall back to extracting the outermost {...} block before giving up.
    """
    text = raw_response.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("No JSON object found in LLM response")


def _call_ollama(prompt: str) -> str:
    response = requests.post(
        f"{settings.OLLAMA_HOST}/api/generate",
        json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"]


def _call_openai(prompt: str) -> str:
    import openai

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content


def call_llm(prompt: str) -> str:
    """Dispatch to the configured LLM provider."""
    if settings.LLM_PROVIDER == "openai":
        return _call_openai(prompt)
    return _call_ollama(prompt)


def grade_with_llm(prompt: str) -> dict:
    """
    Call the LLM and parse its JSON response, re-prompting once if
    parsing fails. Raises LLMGradingError if it still fails after retry
    (caller should flag the result reason="llm_invalid").
    """
    last_error = None
    for attempt in range(2):
        try:
            raw_response = call_llm(prompt)
            parsed = _extract_json(raw_response)

            if "marks" not in parsed or "feedback" not in parsed:
                raise ValueError("Missing required keys in LLM JSON response")

            return parsed
        except Exception as exc:  # noqa: BLE001 - deliberately broad; any failure -> retry/flag
            last_error = exc
            logger.warning("LLM grading attempt %d failed: %s", attempt + 1, exc)

    raise LLMGradingError(f"LLM failed to produce valid JSON after 2 attempts: {last_error}")


def validate_score(parsed_response: dict, total_marks: float) -> dict:
    """
    Validate marks are within [0, total_marks]. Clamps out-of-range
    scores and flags them.

    Returns: {"marks": float, "was_clamped": bool}
    """
    try:
        marks = float(parsed_response.get("marks", 0))
    except (TypeError, ValueError):
        marks = 0.0

    was_clamped = False
    if marks < 0:
        marks = 0.0
        was_clamped = True
    elif marks > total_marks:
        marks = float(total_marks)
        was_clamped = True

    return {"marks": marks, "was_clamped": was_clamped}
