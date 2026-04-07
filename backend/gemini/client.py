"""
gemini/client.py
----------------
Shared Gemini API wrapper for KineticAI.
Uses the current google-genai SDK (replaces deprecated google-generativeai).
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from typing import Any

from google import genai
from google.genai import types


def _client():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key or key == "your_gemini_api_key_here":
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Add it to your .env file and restart the server."
        )
    return genai.Client(api_key=key)


def _extract_json(text: str) -> Any:
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    start = min((text.find(c) for c in ["{", "["] if text.find(c) != -1), default=-1)
    if start == -1:
        raise ValueError(f"No JSON found in Gemini response: {text[:200]}")
    open_char  = text[start]
    close_char = "}" if open_char == "{" else "]"
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == open_char:  depth += 1
        if ch == close_char: depth -= 1
        if depth == 0:
            return json.loads(text[start : i + 1])
    raise ValueError("Unbalanced JSON in Gemini response.")


VALID_MUSCLES = [
    "biceps","triceps","forearms","chest","abs",
    "front_delts","side_delts","rear_delts","traps","lats",
    "spinal_erectors","glutes","hamstrings","quads","calves",
]
VALID_INTENSITIES = ["primary","secondary"]


def detect_muscles(exercise_name: str) -> dict:
    """
    Ask Gemini which muscles an exercise targets and at what intensity.

    Returns:
        {
            "exercise": "Barbell Squat",
            "muscles": [
                { "muscle": "quads",           "intensity": "primary"   },
                { "muscle": "glutes",          "intensity": "primary"   },
                { "muscle": "hamstrings",      "intensity": "secondary" },
                { "muscle": "spinal_erectors", "intensity": "secondary" },
                { "muscle": "calves",          "intensity": "tertiary"  }
            ]
        }
    """
    valid_list = ", ".join(VALID_MUSCLES)
    prompt = textwrap.dedent(f"""
        You are a certified strength and conditioning coach.
        For the exercise "{exercise_name}", identify which muscles it targets
        and classify each by activation intensity.

        Use ONLY these muscle names (exact spelling):
        {valid_list}

        Use ONLY these intensity levels:
        - "primary"   : the main mover(s)
        - "secondary" : significantly activated but not the primary focus
        Return ONLY a JSON object in this exact format, no other text:
        {{
            "exercise": "{exercise_name}",
            "muscles": [
                {{"muscle": "<muscle_name>", "intensity": "<primary|secondary>"}},
                ...
            ]
        }}

        Rules:
        - Include at least 1 primary muscle.
        - Include all meaningfully activated muscles.
        - Do not include muscles that are not activated by this exercise.
        - Do not include any text outside the JSON.
    """).strip()

    client   = _client()
    response = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
    result   = _extract_json(response.text)

    muscles, seen = [], set()
    for entry in result.get("muscles", []):
        m = entry.get("muscle", "").lower().strip()
        i = entry.get("intensity", "").lower().strip()
        if m in VALID_MUSCLES and i in VALID_INTENSITIES and m not in seen:
            muscles.append({"muscle": m, "intensity": i})
            seen.add(m)

    if not muscles:
        raise ValueError(
            f"Gemini returned no valid muscles for '{exercise_name}'. "
            "Please check the exercise name and try again."
        )

    return {"exercise": exercise_name, "muscles": muscles}


def evaluate_workouts(workout_data: dict) -> dict:
    """
    Send the user's 7-day workout history to Gemini and get back a full
    evaluation with score, grade, categories, suggestions, and narrative.
    """
    valid_muscles = ", ".join(VALID_MUSCLES)

    prompt = textwrap.dedent(f"""
        You are an expert personal trainer and exercise scientist analysing
        a user's training week. Provide a thorough, honest evaluation.

        === TRAINING DATA (past 7 days) ===
        {json.dumps(workout_data, indent=2)}

        === MUSCLE RECOVERY STATUS ===
        The "muscle_volume_summary" field in the training data contains a
        recovery status for each muscle that was trained this week:
          "red"    — recently overworked, needs full rest before training again
          "yellow" — partially recovered, can be trained lightly if needed
          "green"  — fully recovered or untrained, ready to be prioritised

        Any muscle NOT appearing in muscle_volume_summary is implicitly "green"
        (untrained this week) and should be treated as fully available.

        === YOUR TASK ===
        Evaluate the training week across four categories:
        1. balance    — push/pull/legs ratio, upper/lower balance, antagonist pairs
        2. frequency  — per-muscle training frequency, back-to-back risks
        3. rest       — rest day count, consecutive training streaks, session length
        4. volume     — overtraining risk, intensity distribution, exercise density

        Also consider the detected training split and adherence to it.

        Score each category 0-100. Compute a weighted overall score:
          balance=35%, frequency=25%, rest=22%, volume=18%

        Provide up to 5 workout suggestions following these strict rules:
        - ONLY suggest muscle groups with status "green" or that are absent from
          muscle_volume_summary (i.e. untrained and fully fresh).
        - NEVER include a muscle with status "red" in any suggestion's muscle_groups.
        - Muscles with status "yellow" may appear only as minor/supporting muscles,
          not as the primary focus of a suggestion.
        - Prioritise muscles that are "green" and have NOT been trained at all this
          week — these are the most important gaps to fill.
        - Each suggestion must have a descriptive name, list target muscle groups
          using ONLY: {valid_muscles}, explain why it is recommended given the
          recovery data, and have priority: "high", "medium", or "low".
        - Set priority "high" for suggestions that address a clear muscle group gap
          (untrained green muscles), "medium" for balance improvements, "low" for
          optional accessory work.

        Write a 2-4 sentence plain English narrative: week summary,
        biggest strength, most important thing to improve based on recovery status.

        Return ONLY valid JSON, no other text:
        {{
            "overall_score": <0-100>,
            "grade": "<A|B|C|D|F>",
            "narrative": "<2-4 sentence summary>",
            "categories": {{
                "balance":   {{ "score": <0-100>, "findings": ["<finding>", ...] }},
                "frequency": {{ "score": <0-100>, "findings": ["<finding>", ...] }},
                "rest":      {{ "score": <0-100>, "findings": ["<finding>", ...] }},
                "volume":    {{ "score": <0-100>, "findings": ["<finding>", ...] }}
            }},
            "suggestions": [
                {{
                    "name":          "<workout name>",
                    "muscle_groups": ["<muscle>", ...],
                    "reason":        "<why recommended>",
                    "priority":      "<high|medium|low>"
                }}
            ]
        }}
    """).strip()

    client   = _client()
    response = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
    result   = _extract_json(response.text)

    score = max(0.0, min(100.0, float(result.get("overall_score", 0))))
    grade = result.get("grade", "F")
    if grade not in ("A","B","C","D","F"):
        grade = _score_to_grade(score)

    categories = {}
    for cat in ("balance","frequency","rest","volume"):
        raw = result.get("categories", {}).get(cat, {})
        categories[cat] = {
            "score":    max(0.0, min(100.0, float(raw.get("score", 0)))),
            "findings": [str(f) for f in raw.get("findings", [])],
        }

    suggestions = []
    for s in result.get("suggestions", [])[:5]:
        muscles  = [m for m in s.get("muscle_groups", []) if m in VALID_MUSCLES]
        priority = s.get("priority","medium")
        if priority not in ("high","medium","low"): priority = "medium"
        suggestions.append({
            "name":          str(s.get("name","")),
            "muscle_groups": muscles,
            "reason":        str(s.get("reason","")),
            "priority":      priority,
        })

    return {
        "overall_score": round(score, 1),
        "grade":         grade,
        "narrative":     str(result.get("narrative","")),
        "categories":    categories,
        "suggestions":   suggestions,
    }


def _score_to_grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"
