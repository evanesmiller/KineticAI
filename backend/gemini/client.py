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
                { "muscle": "hamstrings",      "intensity": "secondary" }
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

        === USER PROFILE & RELATIVE STRENGTH ===
        The "user_profile" field contains the user's body weight and height.
        The "notable_lifts" list shows the peak weight achieved for each loaded
        exercise this week, expressed as a ratio of body weight ("bw_ratio").
        Use these guidelines for context:
          bw_ratio < 0.5   — beginner range for most lifts
          bw_ratio 0.5–1.0 — developing strength, common for upper body
          bw_ratio >= 1.0  — lifting at or above body weight; solid milestone
          bw_ratio >= 1.5  — strong for compound lower body lifts
          bw_ratio >= 2.0  — advanced, especially for deadlifts/squats
        "exceeds_bodyweight": true means the user moved more than their own body
        weight on that exercise — acknowledge this as a strength achievement in
        the narrative where relevant. If body_weight_lbs is null, skip relative
        strength commentary.

        === YOUR TASK ===
        Evaluate the training week across four categories:
        1. balance    — see detailed scoring rules below (starts at 100, deductions applied)
        2. consistency — see detailed scoring rules below (starts at 100, deductions applied)
        3. rest       — see detailed scoring rules below (starts at 100, deductions applied)
        4. volume     — overtraining risk, intensity distribution, exercise density

        Also consider the detected training split and adherence to it.

        Score each category 0-100. Compute a weighted overall score:
          overall_score = balance×0.35 + consistency×0.25 + rest×0.22 + volume×0.18

        Grade the overall score using these exact thresholds:
          90-100 → A  (near-perfect, hit all guidelines with minor room to improve)
          70-89  → B  (solid week, a few clear areas to address)
          50-69  → C  (decent effort, notable gaps to fix)
          25-49  → D  (met one or two requirements, neglected the rest)
          0-24   → F  (failed to meet the requirements)

        === BALANCE CATEGORY SCORING RULES ===
        Score starts at 100. Apply the following deductions:

        FACTOR 1 — Per-muscle weekly session frequency (most important factor):
        Target: every muscle should be trained 2 times per week.
        Use muscle_volume_summary[muscle].sessions for the session count.
        Muscles absent from muscle_volume_summary have 0 sessions.

        Muscle priority tiers — higher-priority muscles carry a larger multiplier
        because they are primary compound movers whose absence has wider impact:
          HIGH priority (2.0× multiplier): quads, chest, lats, hamstrings
          MEDIUM priority (1.0× multiplier): glutes, front_delts, rear_delts, traps, biceps, triceps
          LOW priority (0.5× multiplier): calves, forearms, abs, spinal_erectors, side_delts

        Base deductions per muscle (multiply each by the tier multiplier above):
          0 sessions → deduct 8 × multiplier (significant gap for high-priority muscles)
          1 session  → deduct 3 × multiplier (acceptable but sub-optimal)
          2 sessions → no deduction (ideal)
          3 sessions → deduct 2 × multiplier (slight over-frequency)
          4 sessions → deduct 5 × multiplier
          5+ sessions → deduct 8 × multiplier (overuse; compound penalties apply)

        Secondary-muscle credit: compound exercises stimulate secondary muscles.
        If a high-priority muscle (e.g. hamstrings) was not directly trained but was
        clearly a significant secondary mover of exercises performed that week
        (e.g. Romanian deadlifts hitting hamstrings, squats hitting glutes), reduce
        the "0 sessions" deduction by 50% for that muscle. Use your knowledge of
        compound exercise mechanics to apply this credit.

        FACTOR 2 — Push / Pull / Legs category balance (count SETS, not volume):
        Sum total sets per category from workouts[].exercises[].sets × muscle_group:
          push muscles: chest, front_delts, side_delts, triceps
          pull muscles: lats, rear_delts, traps, biceps, forearms
          leg muscles : quads, hamstrings, glutes, calves

        Ideal ratios by total sets:
          push : pull  → between 1:2 and 2:1 (balanced pressing and pulling)
          upper (push+pull) : lower (legs) → between 1:1 and 3:1

        Deductions:
          push:pull > 2.5:1 or < 1:2.5 → deduct 15 (significant imbalance)
          push:pull > 2:1   or < 1:2   → deduct 8
          upper:lower > 4:1            → deduct 15 (legs severely neglected)
          upper:lower > 3:1            → deduct 8
          legs completely absent (0 sets) → deduct an additional 10 on top of ratio penalty

        FACTOR 3 — Antagonist pair balance (by session count):
        Check these pairs. Use sessions count from muscle_volume_summary:
          chest ↔ lats         (horizontal push vs. pull)
          front_delts ↔ rear_delts  (anterior vs. posterior shoulder)
          quads ↔ hamstrings   (knee extension vs. flexion)
          biceps ↔ triceps     (elbow flexion vs. extension)

        Deductions per pair:
          One muscle trained, antagonist completely absent       → deduct 12
          One muscle trained 2+ more sessions than its antagonist → deduct 8
          Sessions within 1 of each other                        → no deduction ✓

        FACTOR 4 — Core inclusion:
          abs and spinal_erectors both absent → deduct 8
          Only one of the two absent          → deduct 3

        ZERO-SESSION OVERRIDE: If the workouts array is empty or contains no exercises,
        the balance score is 0. Do not apply individual factor deductions in this case.

        In balance findings, use at most 4 bullet points total. Be concise:
          • Muscle gaps: list only muscles that are absent (0×) or under-trained (1×),
            grouped as one line per priority tier — skip tiers with no issues.
            Format: "HIGH: Lats (0×), Hamstrings (1×) | MED: Chest, Triceps (0×)"
            If secondary-muscle credit reduced a deduction, append "(SC credit)" inline.
          • Push:Pull X:Y — one-sentence verdict. Include upper:lower only if it triggered a deduction.
          • Antagonist violations: list all affected pairs on one line, e.g. "Chest↔Lats, Biceps↔Triceps"
          • One closing note: either a positive observation if balance is solid, or the single most impactful fix.
          Omit any bullet if it has nothing to report.

        === CONSISTENCY CATEGORY SCORING RULES ===
        Score starts at 100. Use the "consistency_history" field in the training data.

        CRITICAL: The "workouts" array only covers the past 7 days — it is NOT a full history.
        Do NOT compute weeks_active, weeks_missing, avg_weekly_sessions, or any other
        historical metric yourself from the workouts array. All historical values are
        pre-computed in consistency_history — read those exact numbers directly.

        FACTOR 1 — Week-over-week training presence (highest weight):
        Use consistency_history.weeks_tracked (completed ISO weeks since first workout)
        and consistency_history.weeks_missing (weeks with zero sessions logged).

        Deductions:
          - Each missing week: −8 (total capped at −50 from this factor)
          - max_consecutive_missing_weeks ≥ 2: additional −5 per consecutive week beyond the first
          - If weeks_tracked < 2: insufficient history — apply no deductions and note it

        FACTOR 2 — Session count vs. personal baseline:
        Compare consistency_history.current_week_sessions to
        consistency_history.avg_weekly_sessions (mean sessions per past week, including missing ones).
        Shortfall = avg_weekly_sessions − current_week_sessions (only penalise if positive).

        Deductions:
          - Shortfall of 1 session below average: −5
          - Shortfall of 2 sessions below average: −15
          - Shortfall of 3+ sessions below average: −30
          - At or above average: no deduction ✓
          - If avg_weekly_sessions < 1 (very new user): note it, skip this factor

        FACTOR 3 — Progressive overload trajectory:
        Use consistency_history.overload_summary which contains muscle lists by trend:
          progressing — volume/weight improving week-over-week ✓
          stagnating  — flat for 2+ consecutive trained weeks
          regressing  — volume/weight declining
          new         — muscle only seen in one calendar week so far (no trend yet)

        Deductions:
          - Each stagnating muscle: −5 (total capped at −20 from this factor)
          - Each regressing muscle: −8 (total capped at −20 from this factor)
          - 3 or more muscles progressing: reduce total deductions by 5 (reward) ✓
          - Muscles in "new" list have no trend yet — mention them briefly, apply no deduction
          - If progressing/stagnating/regressing are ALL empty AND new is also empty: note insufficient history, apply no deductions

        In consistency findings, use at most 4 bullet points total. Be concise:
          • Presence: "X/Y weeks active" — note any consecutive missing weeks inline if relevant.
          • Baseline: "N sessions this week vs. avg M" — one-sentence verdict.
          • Overload: list progressing/stagnating/regressing muscles on one line each; omit any group that is empty.
          • One closing note: strong positive if solid, or the single highest-impact fix if not.
          Omit any bullet if it has nothing to report.

        === REST CATEGORY SCORING RULES ===
        The rest score starts at 100. Apply the following deductions:

        FACTOR 1 — Weekly rest day count (HIGHEST WEIGHT factor in rest score):
        Ideal range is 1–3 rest days per week. Training split context matters:
          • PPL (Push/Pull/Legs) splits typically train 5-6 days → 1 rest day is appropriate
          • Upper/Lower splits typically train 4 days → 2-3 rest days is appropriate
          • Full Body splits typically train 3 days → 3-4 rest days is appropriate
        Deductions:
          - 0 rest days → deduct 40 (training every day is a serious overuse risk)
          - 1 rest day  → no deduction if split supports it (PPL/high-frequency); deduct 10 otherwise
          - 2–3 rest days → no deduction (optimal range for most splits)
          - 4 rest days → deduct 5 (mild; over-rest is better than under-rest)
          - 5+ rest days → deduct 15 per extra day above 4 (significant under-training)
            e.g. 5 days = −15, 6 days = −30, 7 days (full week off) = −45

        FACTOR 2 — Same-muscle inter-session rest (within the 7-day window):
        Compute the gap in days between consecutive sessions that trained the same muscle.
        Ideal gap: 2–3 days. Deductions per muscle group violation:
          - 0 days (back-to-back same muscle) → deduct 15
          - 1 day between same-muscle sessions → deduct 8 (still insufficient recovery)
          - 2–3 days → no deduction (ideal recovery window)
          - 4+ days → deduct 3 (slight over-rest; generally acceptable, mild concern)
        NOTE: over-rest is always preferable to under-rest unless it becomes chronic.

        FACTOR 3 — Persistent muscle group absence (chronic over-rest):
        If a major training category (push muscles, pull muscles, or leg muscles) had ZERO
        sessions this week, flag it as potential chronic skipping. This matters because
        week-over-week absence of a muscle category indicates a structural problem, not just
        a recovery choice. Deduct 5 per absent major category.
        Cross-reference the detected training split: if the split implies that category should
        have been trained this week (e.g. PPL user skipping legs entirely), increase concern.

        In rest findings, use at most 4 bullet points total. Be concise:
          • Rest days: "N rest days — [ideal/too few/too many] for [detected split]." One sentence.
          • Under-rested muscles (if any): list on one line with gaps, e.g. "Quads (0d gap), Lats (1d gap)"
          • Absent categories / over-rested muscles (if any): one line, flag chronic skipping only if pattern is clear.
          • One closing note: positive if well-managed, or the single most important fix if not.
          Omit any bullet if it has nothing to report.

        === VOLUME CATEGORY SCORING RULES ===
        Score starts at 100. Apply the following deductions.
        Compute per-muscle rep volume as SUM(sets × reps) across all exercises for that
        muscle in the workouts array. Do NOT factor in weight — a beginner and an advanced
        lifter are evaluated equally on rep/set workload.

        Baseline: hypertrophy norms are 1–3 exercises × 2–4 sets × 5–10 reps per muscle
        per session. With 2 sessions/week (ideal frequency), the weekly ceiling is
        3 exercises × 4 sets × 10 reps × 2 sessions = 240 total reps per muscle.

        ZERO-SESSION OVERRIDE: If there are 0 training sessions this week (workouts array
        is empty), the volume score is 0. Do not apply any factor deductions in this case.

        FACTOR 1 — Per-muscle weekly rep volume (highest weight):
        Only evaluate muscles that were actually trained this week.
          < 20 reps  → deduct 4 (trained but barely any stimulus)
          20–240     → no deduction (ideal range) ✓
          241–360    → deduct 5 per muscle (elevated — approaching overuse)
          > 360      → deduct 15 per muscle, scaling up proportionally (cap −25 per muscle)

        FACTOR 2 — Intensity distribution across sessions:
        Use the "intensity" field on each workout ("low", "moderate", "high").
          >70% high intensity → deduct 10, scaling toward −20 as it approaches 100%
          100% low or moderate with 3+ sessions → deduct 8 (no real training stress applied)
          Reasonable mix → no deduction ✓

        FACTOR 3 — Exercise density per session:
        Count exercises per session from workouts[].exercises.
        Both compound and isolation exercises are valid — only flag extremes.
          Any session with more than 12 exercises → deduct 8 (junk volume territory)
          Any session with only 1 exercise → deduct 4 (likely incomplete)
          Within normal range → no deduction ✓

        FACTOR 4 — Session duration:
        Use duration_mins on each workout.
          Any session > 150 min → deduct 10
          Any session > 120 min → deduct 6
          All sessions ≤ 120 min → no deduction ✓

        In volume findings, use at most 4 bullet points total. Be concise:
          • Rep volume: list only muscles outside the ideal range on one line each —
            "Under (<20 reps): X, Y | Yellow (241–360): Z | Red (>360): W". Omit zones with no issues.
          • Intensity: one-sentence verdict, e.g. "80% high intensity — elevated fatigue risk."
          • Density/duration flags (if any): note offending sessions briefly on one line.
          • One closing note: positive if volume is well-managed, or the single most important fix.
          Omit any bullet if it has nothing to report.

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

        Write a 2-4 sentence plain English narrative: week summary, biggest
        strength (referencing relative strength from notable_lifts if available),
        and the most important thing to improve based on recovery status.

        Return ONLY valid JSON, no other text:
        {{
            "overall_score": <0-100>,
            "grade": "<A|B|C|D|F>",
            "narrative": "<2-4 sentence summary>",
            "categories": {{
                "balance":     {{ "score": <0-100>, "findings": ["<finding>", ...] }},
                "consistency": {{ "score": <0-100>, "findings": ["<finding>", ...] }},
                "rest":        {{ "score": <0-100>, "findings": ["<finding>", ...] }},
                "volume":      {{ "score": <0-100>, "findings": ["<finding>", ...] }}
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

    categories = {}
    for cat in ("balance","consistency","rest","volume"):
        raw = result.get("categories", {}).get(cat, {})
        categories[cat] = {
            "score":    max(0.0, min(100.0, float(raw.get("score", 0)))),
            "findings": [str(f) for f in raw.get("findings", [])],
        }

    weights = {"balance": 0.35, "consistency": 0.25, "rest": 0.22, "volume": 0.18}
    score = round(sum(categories[c]["score"] * w for c, w in weights.items()), 1)
    grade = _score_to_grade(score)

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
    if score >= 70: return "B"
    if score >= 50: return "C"
    if score >= 25: return "D"
    return "F"
