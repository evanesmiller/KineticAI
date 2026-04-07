"""
evaluation/engine.py
--------------------
Rule-based workout evaluation engine.

Analyses a user's rolling 7-day workout history across four categories:
  1. Muscle group balance   (35%) — push/pull/legs ratio, antagonist pairs,
                                    upper/lower balance
  2. Workout frequency      (25%) — per-muscle weekly session counts
  3. Rest day sufficiency   (22%) — rest between same-muscle sessions,
                                    total rest days in the week
  4. Weekly volume          (18%) — overtraining detection, intensity
                                    factorization

Returns an EvaluationResult containing:
  - overall score (0–100)
  - per-category scores
  - list of plain-English findings (warnings + positive feedback)
  - list of workout suggestions (exercise name + muscle groups targeted)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

from constants import (
    ANTAGONIST_MAX_RATIO,
    ANTAGONIST_PAIRS,
    BODYWEIGHT_NOMINAL_LBS,
    CORE_MUSCLES,
    FATIGUE_WINDOW_DAYS,
    INTENSITY_MULTIPLIERS,
    LEG_MUSCLES,
    MAX_EXERCISES_PER_SESSION,
    MAX_WEEKLY_SESSIONS,
    MAX_WORKOUT_DURATION_MINS,
    MIN_REST_DAYS_BETWEEN_SESSIONS,
    PULL_MUSCLES,
    PUSH_MUSCLES,
    PUSH_PULL_MAX_RATIO,
    SCORE_WEIGHTS,
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WorkoutSuggestion:
    """
    A single recommended workout the user should consider doing.

    Attributes:
        name            : Short description of the workout/exercise.
        muscle_groups   : Muscles it targets (used by frontend to highlight).
        reason          : Why this is being suggested.
        priority        : 'high' | 'medium' | 'low'
    """
    name:          str
    muscle_groups: List[str]
    reason:        str
    priority:      str = "medium"


@dataclass
class CategoryResult:
    """Score and findings for one evaluation category."""
    score:    float          # 0.0 – 100.0
    findings: List[str] = field(default_factory=list)  # plain-English messages


@dataclass
class EvaluationResult:
    """Full result returned by evaluate()."""
    overall_score:   float
    grade:           str                        # A / B / C / D / F
    categories:      dict[str, CategoryResult]
    suggestions:     List[WorkoutSuggestion]
    evaluation_date: date = field(default_factory=date.today)
    window_days:     int  = FATIGUE_WINDOW_DAYS

    def to_dict(self) -> dict:
        return {
            "overall_score":   round(self.overall_score, 1),
            "grade":           self.grade,
            "evaluation_date": self.evaluation_date.isoformat(),
            "window_days":     self.window_days,
            "categories": {
                name: {
                    "score":    round(cat.score, 1),
                    "findings": cat.findings,
                }
                for name, cat in self.categories.items()
            },
            "suggestions": [
                {
                    "name":          s.name,
                    "muscle_groups": s.muscle_groups,
                    "reason":        s.reason,
                    "priority":      s.priority,
                }
                for s in self.suggestions
            ],
        }


# ---------------------------------------------------------------------------
# Internal data helpers
# ---------------------------------------------------------------------------

def _fetch_window_data(
    conn: sqlite3.Connection,
    user_id: int,
    cutoff: date,
) -> dict:
    """
    Pull all workout + exercise data for the evaluation window into
    convenient in-memory structures so we only hit the DB once.

    Returns a dict with:
        workouts        : list of workout rows (sqlite3.Row)
        exercises       : list of exercise rows joined with muscle name
        dates_worked    : set of date strings that had at least one workout
        muscle_sessions : { muscle_name: [date_str, ...] }
        muscle_volume   : { muscle_name: float }   (intensity-weighted)
        muscle_sets     : { muscle_name: int }
        push_volume     : float
        pull_volume     : float
        leg_volume      : float
        core_volume     : float
        upper_volume    : float   (push + pull)
        lower_volume    : float   (legs)
        total_workouts  : int
        max_duration    : int     (minutes, longest single session)
        max_exercises   : int     (exercises in busiest session)
    """
    cutoff_str = cutoff.isoformat()

    workouts = conn.execute(
        """
        SELECT id, date, duration_mins, intensity
        FROM   workouts
        WHERE  user_id = ? AND date >= ?
        ORDER  BY date
        """,
        (user_id, cutoff_str),
    ).fetchall()

    exercises = conn.execute(
        """
        SELECT e.workout_id, e.sets, e.reps, e.weight_lbs,
               mg.name AS muscle, w.intensity, w.date
        FROM   exercises e
        JOIN   muscle_groups mg ON mg.id = e.muscle_group_id
        JOIN   workouts w       ON w.id  = e.workout_id
        WHERE  w.user_id = ? AND w.date >= ?
        """,
        (user_id, cutoff_str),
    ).fetchall()

    # ── Aggregate per-muscle stats ─────────────────────────────────────────
    muscle_sessions: dict[str, list[str]] = {}
    muscle_volume:   dict[str, float]     = {}
    muscle_sets:     dict[str, int]       = {}

    for ex in exercises:
        muscle    = ex["muscle"]
        intensity = ex["intensity"]
        mult      = INTENSITY_MULTIPLIERS.get(intensity, 1.0)
        eff_wt    = ex["weight_lbs"] if ex["weight_lbs"] > 0 else BODYWEIGHT_NOMINAL_LBS
        vol       = ex["sets"] * ex["reps"] * eff_wt * mult

        muscle_volume[muscle]   = muscle_volume.get(muscle, 0.0) + vol
        muscle_sets[muscle]     = muscle_sets.get(muscle, 0) + ex["sets"]
        muscle_sessions.setdefault(muscle, [])
        if ex["date"] not in muscle_sessions[muscle]:
            muscle_sessions[muscle].append(ex["date"])

    # ── Category volumes ───────────────────────────────────────────────────
    def _sum_volume(group: set[str]) -> float:
        return sum(muscle_volume.get(m, 0.0) for m in group)

    push_volume  = _sum_volume(PUSH_MUSCLES)
    pull_volume  = _sum_volume(PULL_MUSCLES)
    leg_volume   = _sum_volume(LEG_MUSCLES)
    core_volume  = _sum_volume(CORE_MUSCLES)
    upper_volume = push_volume + pull_volume
    lower_volume = leg_volume

    # ── Per-session stats ─────────────────────────────────────────────────
    session_exercise_counts: dict[int, int] = {}
    for ex in exercises:
        wid = ex["workout_id"]
        session_exercise_counts[wid] = session_exercise_counts.get(wid, 0) + 1

    max_exercises = max(session_exercise_counts.values(), default=0)
    max_duration  = max((w["duration_mins"] for w in workouts), default=0)
    dates_worked  = {w["date"] for w in workouts}

    return {
        "workouts":        workouts,
        "exercises":       exercises,
        "dates_worked":    dates_worked,
        "muscle_sessions": muscle_sessions,
        "muscle_volume":   muscle_volume,
        "muscle_sets":     muscle_sets,
        "push_volume":     push_volume,
        "pull_volume":     pull_volume,
        "leg_volume":      leg_volume,
        "core_volume":     core_volume,
        "upper_volume":    upper_volume,
        "lower_volume":    lower_volume,
        "total_workouts":  len(workouts),
        "max_duration":    max_duration,
        "max_exercises":   max_exercises,
    }


def _ratio(a: float, b: float) -> Optional[float]:
    """Return a/b, or None if b is zero."""
    return (a / b) if b > 0 else None


def _grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


# ---------------------------------------------------------------------------
# Rule category evaluators
# Each returns a CategoryResult (score 0–100 + findings list).
# ---------------------------------------------------------------------------

def _eval_balance(data: dict) -> CategoryResult:
    """
    Evaluate muscle group balance:
      - Push : pull volume ratio
      - Upper : lower volume ratio
      - Individual antagonist pair imbalances
      - Whether legs/core were trained at all
    """
    findings: list[str] = []
    deductions = 0.0

    push_vol  = data["push_volume"]
    pull_vol  = data["pull_volume"]
    upper_vol = data["upper_volume"]
    lower_vol = data["lower_volume"]
    mv        = data["muscle_volume"]

    # ── Push : pull ────────────────────────────────────────────────────────
    pp_ratio = _ratio(push_vol, pull_vol)
    rp_ratio = _ratio(pull_vol, push_vol)

    if pp_ratio is None and pull_vol == 0 and push_vol == 0:
        findings.append("No upper-body work detected this week.")
        deductions += 20
    elif pp_ratio is not None and pp_ratio > PUSH_PULL_MAX_RATIO:
        findings.append(
            f"Push volume is {pp_ratio:.1f}× your pull volume — "
            "add more rows, pull-downs, or face pulls to balance your shoulders."
        )
        deductions += min(25, (pp_ratio - PUSH_PULL_MAX_RATIO) * 8)
    elif rp_ratio is not None and rp_ratio > PUSH_PULL_MAX_RATIO:
        findings.append(
            f"Pull volume is {rp_ratio:.1f}× your push volume — "
            "consider adding pressing work to balance your chest and shoulders."
        )
        deductions += min(20, (rp_ratio - PUSH_PULL_MAX_RATIO) * 8)
    else:
        findings.append("Push/pull volume is well balanced. ✓")

    # ── Upper : lower ──────────────────────────────────────────────────────
    ul_ratio = _ratio(upper_vol, lower_vol)
    lu_ratio = _ratio(lower_vol, upper_vol)

    if upper_vol == 0 and lower_vol == 0:
        pass  # already flagged above
    elif lower_vol == 0:
        findings.append("No leg work detected this week — don't skip leg day!")
        deductions += 15
    elif upper_vol == 0:
        findings.append("No upper-body work detected this week.")
        deductions += 15
    elif ul_ratio is not None and ul_ratio > 3.0:
        findings.append(
            f"Upper-body volume is {ul_ratio:.1f}× your lower-body volume — "
            "try adding a dedicated leg session."
        )
        deductions += min(15, (ul_ratio - 3.0) * 5)
    elif lu_ratio is not None and lu_ratio > 3.0:
        findings.append(
            f"Lower-body volume is {lu_ratio:.1f}× your upper-body volume — "
            "balance it out with some upper-body work."
        )
        deductions += min(10, (lu_ratio - 3.0) * 5)
    else:
        findings.append("Upper/lower body volume is well balanced. ✓")

    # ── Antagonist pairs ───────────────────────────────────────────────────
    for agonist, antagonist in ANTAGONIST_PAIRS:
        a_vol = mv.get(agonist, 0.0)
        b_vol = mv.get(antagonist, 0.0)
        if a_vol == 0 and b_vol == 0:
            continue
        ratio = _ratio(a_vol, b_vol)
        inv   = _ratio(b_vol, a_vol)
        if ratio is not None and ratio > ANTAGONIST_MAX_RATIO:
            findings.append(
                f"{agonist.replace('_', ' ').title()} volume is "
                f"{ratio:.1f}× {antagonist.replace('_', ' ').title()} — "
                "consider training the weaker side more."
            )
            deductions += min(10, (ratio - ANTAGONIST_MAX_RATIO) * 4)
        elif inv is not None and inv > ANTAGONIST_MAX_RATIO:
            findings.append(
                f"{antagonist.replace('_', ' ').title()} volume is "
                f"{inv:.1f}× {agonist.replace('_', ' ').title()} — "
                "consider training the weaker side more."
            )
            deductions += min(10, (inv - ANTAGONIST_MAX_RATIO) * 4)

    # ── Core ───────────────────────────────────────────────────────────────
    if data["core_volume"] == 0:
        findings.append(
            "No core work (abs / spinal erectors) detected — "
            "add planks, dead bugs, or back extensions for stability."
        )
        deductions += 5

    score = max(0.0, 100.0 - deductions)
    return CategoryResult(score=score, findings=findings)


def _eval_frequency(data: dict) -> CategoryResult:
    """
    Evaluate per-muscle weekly training frequency:
      - Flag muscles trained too frequently (> MAX_WEEKLY_SESSIONS)
      - Flag muscles with back-to-back sessions (< MIN_REST_DAYS_BETWEEN_SESSIONS)
      - Reward consistent frequency across major groups
    """
    findings: list[str] = []
    deductions = 0.0
    muscle_sessions = data["muscle_sessions"]

    overworked = []
    back_to_back = []

    for muscle, session_dates in muscle_sessions.items():
        count = len(session_dates)

        # Too many sessions
        if count > MAX_WEEKLY_SESSIONS:
            overworked.append(muscle)
            deductions += min(15, (count - MAX_WEEKLY_SESSIONS) * 6)

        # Back-to-back days
        sorted_dates = sorted(session_dates)
        for i in range(1, len(sorted_dates)):
            d1 = date.fromisoformat(sorted_dates[i - 1])
            d2 = date.fromisoformat(sorted_dates[i])
            gap = (d2 - d1).days
            if gap < (MIN_REST_DAYS_BETWEEN_SESSIONS + 1):
                if muscle not in back_to_back:
                    back_to_back.append(muscle)
                deductions += 8

    if overworked:
        names = ", ".join(m.replace("_", " ") for m in overworked)
        findings.append(
            f"These muscles were trained more than {MAX_WEEKLY_SESSIONS}× "
            f"this week: {names}. Consider adding rest to avoid overuse injuries."
        )
    else:
        findings.append("No muscles are being overtrained in frequency. ✓")

    if back_to_back:
        names = ", ".join(m.replace("_", " ") for m in back_to_back)
        findings.append(
            f"Back-to-back training detected for: {names}. "
            "Allow at least one rest day between sessions for the same muscle."
        )
    else:
        findings.append("Adequate rest between same-muscle sessions. ✓")

    # Reward training all major groups at least once
    major_groups = PUSH_MUSCLES | PULL_MUSCLES | LEG_MUSCLES
    trained = set(muscle_sessions.keys())
    untrained_major = major_groups - trained
    if not untrained_major:
        findings.append("All major muscle groups were trained at least once. ✓")
    else:
        names = ", ".join(m.replace("_", " ") for m in sorted(untrained_major))
        findings.append(f"Major muscles not trained this week: {names}.")
        deductions += min(20, len(untrained_major) * 4)

    score = max(0.0, 100.0 - deductions)
    return CategoryResult(score=score, findings=findings)


def _eval_rest(data: dict) -> CategoryResult:
    """
    Evaluate rest day sufficiency:
      - Count total rest days in the 7-day window
      - Flag if fewer than 2 rest days
      - Detect consecutive training days (no rest at all mid-week)
    """
    findings: list[str] = []
    deductions = 0.0

    total_days     = FATIGUE_WINDOW_DAYS
    dates_worked   = data["dates_worked"]
    rest_days      = total_days - len(dates_worked)
    total_workouts = data["total_workouts"]

    # ── Rest day count ─────────────────────────────────────────────────────
    if total_workouts == 0:
        findings.append("No workouts logged this week — no fatigue to evaluate.")
        return CategoryResult(score=100.0, findings=findings)

    if rest_days >= 3:
        findings.append(f"{rest_days} rest days this week — well recovered. ✓")
    elif rest_days == 2:
        findings.append(f"{rest_days} rest days this week — adequate recovery.")
    elif rest_days == 1:
        findings.append(
            "Only 1 rest day this week. Most athletes benefit from at least 2 "
            "full rest days to allow systemic recovery."
        )
        deductions += 20
    else:
        findings.append(
            "No rest days detected this week! Training every day significantly "
            "increases injury risk and impairs progress."
        )
        deductions += 40

    # ── Consecutive training days ──────────────────────────────────────────
    sorted_dates = sorted(date.fromisoformat(d) for d in dates_worked)
    max_streak = streak = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 1

    if max_streak >= 5:
        findings.append(
            f"You trained {max_streak} consecutive days — consider breaking "
            "this up with a rest day to prevent accumulated fatigue."
        )
        deductions += min(25, (max_streak - 4) * 8)
    elif max_streak >= 3:
        findings.append(
            f"You had a {max_streak}-day training streak. "
            "This is manageable, but watch for signs of fatigue."
        )
        deductions += (max_streak - 2) * 5

    # ── Session duration ───────────────────────────────────────────────────
    if data["max_duration"] > MAX_WORKOUT_DURATION_MINS:
        findings.append(
            f"One or more sessions exceeded {MAX_WORKOUT_DURATION_MINS} minutes "
            f"({data['max_duration']} min). Shorter, focused sessions are "
            "generally more effective and less taxing."
        )
        deductions += 10

    score = max(0.0, 100.0 - deductions)
    return CategoryResult(score=score, findings=findings)


def _eval_volume(data: dict) -> CategoryResult:
    """
    Evaluate weekly volume and overtraining risk:
      - Per-muscle intensity-weighted volume vs red/yellow thresholds
      - Flag excessive exercises per session
      - Reward appropriate volume distribution
    """
    from constants import RED_VOLUME_THRESHOLD, YELLOW_VOLUME_THRESHOLD

    findings: list[str] = []
    deductions = 0.0
    mv = data["muscle_volume"]

    overloaded  = []
    high_volume = []

    for muscle, vol in mv.items():
        if vol >= RED_VOLUME_THRESHOLD:
            overloaded.append(muscle)
            deductions += min(20, ((vol - RED_VOLUME_THRESHOLD) / RED_VOLUME_THRESHOLD) * 15)
        elif vol >= YELLOW_VOLUME_THRESHOLD:
            high_volume.append(muscle)

    if overloaded:
        names = ", ".join(m.replace("_", " ") for m in overloaded)
        findings.append(
            f"High overtraining risk detected for: {names}. "
            "Volume is well above recommended weekly thresholds — "
            "plan deload days or reduce load."
        )
    else:
        findings.append("No muscles are showing overtraining-level volume. ✓")

    if high_volume:
        names = ", ".join(m.replace("_", " ") for m in high_volume)
        findings.append(
            f"Elevated volume for: {names}. "
            "These muscles are well-worked — ensure adequate rest before the next session."
        )

    # ── Exercise density per session ───────────────────────────────────────
    if data["max_exercises"] > MAX_EXERCISES_PER_SESSION:
        findings.append(
            f"One session had {data['max_exercises']} exercises — "
            f"more than the recommended maximum of {MAX_EXERCISES_PER_SESSION}. "
            "Focus on compound lifts and limit accessory work."
        )
        deductions += 10
    else:
        findings.append("Exercise volume per session is within healthy range. ✓")

    # ── Intensity distribution ─────────────────────────────────────────────
    workouts    = data["workouts"]
    intensities = [w["intensity"] for w in workouts]
    high_count  = intensities.count("high")
    total       = len(intensities)

    if total > 0:
        high_pct = high_count / total
        if high_pct > 0.7:
            findings.append(
                f"{int(high_pct * 100)}% of your sessions this week were high intensity. "
                "Mix in moderate and low intensity sessions for sustainable progress."
            )
            deductions += min(15, (high_pct - 0.7) * 50)
        elif high_pct < 0.2 and total >= 3:
            findings.append(
                "All sessions this week were low or moderate intensity. "
                "Including at least one high-intensity session can accelerate progress."
            )

    score = max(0.0, 100.0 - deductions)
    return CategoryResult(score=score, findings=findings)


# ---------------------------------------------------------------------------
# Suggestion engine
# ---------------------------------------------------------------------------

# Workout templates: name -> (muscle_groups, category_tag)
_WORKOUT_LIBRARY = [
    # Push
    ("Chest & Triceps (Bench Focus)",
     ["chest", "triceps", "front_delts"], "push"),
    ("Overhead Press & Lateral Raises",
     ["front_delts", "side_delts", "triceps"], "push"),
    ("Push Day (Compound)",
     ["chest", "front_delts", "triceps"], "push"),

    # Pull
    ("Back & Biceps (Row Focus)",
     ["lats", "biceps", "rear_delts", "traps"], "pull"),
    ("Pull Day (Compound)",
     ["lats", "rear_delts", "traps", "biceps", "forearms"], "pull"),
    ("Face Pulls & Rear Delt Flyes",
     ["rear_delts", "traps"], "pull"),

    # Legs
    ("Quad-Dominant Leg Day",
     ["quads", "glutes", "calves"], "legs"),
    ("Posterior Chain Focus",
     ["hamstrings", "glutes", "spinal_erectors"], "legs"),
    ("Full Leg Day",
     ["quads", "hamstrings", "glutes", "calves"], "legs"),

    # Core
    ("Core Stability Session",
     ["abs", "spinal_erectors"], "core"),
    ("Ab Circuit",
     ["abs"], "core"),

    # Full body
    ("Full Body Compound Day",
     ["quads", "chest", "lats", "abs"], "full"),
    ("Upper Body (Push + Pull)",
     ["chest", "lats", "front_delts", "rear_delts", "biceps", "triceps"], "upper"),
]


def _build_suggestions(
    data:        dict,
    balance_res: CategoryResult,
    freq_res:    CategoryResult,
    rest_res:    CategoryResult,
    vol_res:     CategoryResult,
) -> List[WorkoutSuggestion]:
    """
    Generate prioritised workout suggestions based on evaluation findings.
    """
    suggestions: List[WorkoutSuggestion] = []
    trained     = set(data["muscle_sessions"].keys())
    mv          = data["muscle_volume"]
    rest_days   = FATIGUE_WINDOW_DAYS - len(data["dates_worked"])

    # ── No workouts yet ────────────────────────────────────────────────────
    if data["total_workouts"] == 0:
        suggestions.append(WorkoutSuggestion(
            name="Full Body Compound Day",
            muscle_groups=["quads", "chest", "lats", "abs"],
            reason="Start your week with a full-body session to build a baseline.",
            priority="high",
        ))
        return suggestions

    # ── If overdue for rest ────────────────────────────────────────────────
    if rest_days == 0:
        suggestions.append(WorkoutSuggestion(
            name="Active Recovery / Rest Day",
            muscle_groups=[],
            reason="You have trained every day this week. A rest day is strongly recommended.",
            priority="high",
        ))
        return suggestions

    # ── Find untrained or under-trained muscles ────────────────────────────
    all_major     = PUSH_MUSCLES | PULL_MUSCLES | LEG_MUSCLES | CORE_MUSCLES
    untrained     = all_major - trained
    push_vol      = data["push_volume"]
    pull_vol      = data["pull_volume"]
    leg_vol       = data["leg_volume"]
    core_vol      = data["core_volume"]

    # Determine most needed category
    category_need = []
    if not (PUSH_MUSCLES & trained):
        category_need.append(("push",  "No push muscles trained yet this week."))
    if not (PULL_MUSCLES & trained):
        category_need.append(("pull",  "No pull muscles trained yet this week."))
    if not (LEG_MUSCLES  & trained):
        category_need.append(("legs",  "Legs have not been trained this week."))
    if not (CORE_MUSCLES & trained):
        category_need.append(("core",  "Core has not been trained this week."))

    # Push/pull imbalance
    pp = _ratio(push_vol, pull_vol)
    rp = _ratio(pull_vol, push_vol)
    if pp is not None and pp > PUSH_PULL_MAX_RATIO:
        category_need.append(("pull", f"Push volume is {pp:.1f}× pull — add pulling work."))
    elif rp is not None and rp > PUSH_PULL_MAX_RATIO:
        category_need.append(("push", f"Pull volume is {rp:.1f}× push — add pressing work."))

    # Upper/lower imbalance
    ul = _ratio(push_vol + pull_vol, leg_vol)
    if ul is not None and ul > 3.0:
        category_need.append(("legs", "Upper-body dominates — prioritise a leg session."))

    # Build suggestions from needed categories
    seen_names: set[str] = set()
    for tag, reason in category_need:
        for name, muscles, cat in _WORKOUT_LIBRARY:
            if cat == tag and name not in seen_names:
                # Skip if any of these muscles are already overloaded (red)
                from constants import RED_VOLUME_THRESHOLD
                if all(mv.get(m, 0) < RED_VOLUME_THRESHOLD for m in muscles):
                    suggestions.append(WorkoutSuggestion(
                        name=name,
                        muscle_groups=muscles,
                        reason=reason,
                        priority="high" if tag in ("legs", "pull") else "medium",
                    ))
                    seen_names.add(name)
                    break

    # ── Suggest active recovery if 0 rest days and high volume ────────────
    from constants import YELLOW_VOLUME_THRESHOLD
    high_vol_muscles = [m for m, v in mv.items() if v >= YELLOW_VOLUME_THRESHOLD]
    if len(high_vol_muscles) >= 3 and rest_days <= 1:
        suggestions.append(WorkoutSuggestion(
            name="Active Recovery Session",
            muscle_groups=[],
            reason=(
                f"{len(high_vol_muscles)} muscle groups are at high volume. "
                "Light cardio or mobility work will aid recovery."
            ),
            priority="medium",
        ))

    # ── If suggestions are empty, give a maintenance suggestion ───────────
    if not suggestions:
        suggestions.append(WorkoutSuggestion(
            name="Full Body Maintenance Session",
            muscle_groups=["chest", "lats", "quads", "abs"],
            reason="Your training is well-balanced — keep up the good work with a full-body session.",
            priority="low",
        ))

    return suggestions[:5]  # cap at 5 suggestions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(conn: sqlite3.Connection, user_id: int) -> EvaluationResult:
    """
    Run the full evaluation for a user's rolling 7-day training window.

    Args:
        conn    : Active SQLite connection.
        user_id : The user to evaluate.

    Returns:
        EvaluationResult with overall score, category breakdowns,
        and prioritised workout suggestions.
    """
    cutoff = date.today() - timedelta(days=FATIGUE_WINDOW_DAYS)
    data   = _fetch_window_data(conn, user_id, cutoff)

    # ── Run all four rule categories ───────────────────────────────────────
    balance_res  = _eval_balance(data)
    freq_res     = _eval_frequency(data)
    rest_res     = _eval_rest(data)
    vol_res      = _eval_volume(data)

    categories = {
        "balance":   balance_res,
        "frequency": freq_res,
        "rest":      rest_res,
        "volume":    vol_res,
    }

    # ── Weighted overall score ─────────────────────────────────────────────
    overall = sum(
        categories[cat].score * weight
        for cat, weight in SCORE_WEIGHTS.items()
    )

    # ── Suggestions ────────────────────────────────────────────────────────
    suggestions = _build_suggestions(data, balance_res, freq_res, rest_res, vol_res)

    return EvaluationResult(
        overall_score=overall,
        grade=_grade(overall),
        categories=categories,
        suggestions=suggestions,
    )
