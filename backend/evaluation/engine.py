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

    # Use the user's stored body weight for bodyweight exercise substitution.
    bw_row = conn.execute(
        "SELECT body_weight_lbs FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    body_weight = (
        float(bw_row["body_weight_lbs"])
        if bw_row and bw_row["body_weight_lbs"]
        else BODYWEIGHT_NOMINAL_LBS
    )

    # ── Aggregate per-muscle stats ─────────────────────────────────────────
    muscle_sessions:    dict[str, list[str]] = {}
    muscle_volume:      dict[str, float]     = {}
    muscle_sets:        dict[str, int]       = {}
    muscle_rep_volume:  dict[str, int]       = {}  # sets × reps, no weight factor

    for ex in exercises:
        muscle    = ex["muscle"]
        intensity = ex["intensity"]
        mult      = INTENSITY_MULTIPLIERS.get(intensity, 1.0)
        eff_wt    = ex["weight_lbs"] if ex["weight_lbs"] > 0 else body_weight
        vol       = ex["sets"] * ex["reps"] * eff_wt * mult

        muscle_volume[muscle]     = muscle_volume.get(muscle, 0.0) + vol
        muscle_sets[muscle]       = muscle_sets.get(muscle, 0) + ex["sets"]
        muscle_rep_volume[muscle] = muscle_rep_volume.get(muscle, 0) + ex["sets"] * ex["reps"]
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
        "workouts":               workouts,
        "exercises":              exercises,
        "dates_worked":           dates_worked,
        "muscle_sessions":        muscle_sessions,
        "muscle_volume":          muscle_volume,
        "muscle_sets":            muscle_sets,
        "muscle_rep_volume":      muscle_rep_volume,
        "session_exercise_counts": session_exercise_counts,
        "push_volume":            push_volume,
        "pull_volume":            pull_volume,
        "leg_volume":             leg_volume,
        "core_volume":            core_volume,
        "upper_volume":           upper_volume,
        "lower_volume":           lower_volume,
        "total_workouts":         len(workouts),
        "max_duration":           max_duration,
        "max_exercises":          max_exercises,
        "body_weight":            body_weight,
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
    Balance score starts at 100; four deduction factors:

    Factor 1 (most important): Per-muscle weekly session frequency.
      Target is 2 sessions per muscle. Deductions are scaled by priority tier:
        HIGH (2.0x):   quads, chest, lats, hamstrings
        MEDIUM (1.0x): glutes, front_delts, rear_delts, traps, biceps, triceps
        LOW (0.5x):    calves, forearms, abs, spinal_erectors, side_delts
      Base deductions: 0 sessions→8, 1→3, 2→0, 3→2, 4→5, 5+→8

    Factor 2: Push/Pull/Legs balance by total SETS (not volume).
      push:pull ideal ratio 1:2–2:1; upper:lower ideal ratio 1:1–3:1.

    Factor 3: Antagonist pair session-count balance.
      Pairs: chest/lats, front_delts/rear_delts, quads/hamstrings, biceps/triceps.

    Factor 4: Core inclusion (abs / spinal_erectors).
    """
    _HIGH_PRIORITY   = {"quads", "chest", "lats", "hamstrings"}
    _MEDIUM_PRIORITY = {"glutes", "front_delts", "rear_delts", "traps", "biceps", "triceps"}
    _LOW_PRIORITY    = {"calves", "forearms", "abs", "spinal_erectors", "side_delts"}

    def _multiplier(muscle: str) -> float:
        if muscle in _HIGH_PRIORITY:   return 2.0
        if muscle in _MEDIUM_PRIORITY: return 1.0
        return 0.5

    def _session_deduction(sessions: int) -> float:
        return {0: 8.0, 1: 3.0, 2: 0.0, 3: 2.0, 4: 5.0}.get(sessions, 8.0)

    findings:   list[str] = []
    deductions: float     = 0.0

    muscle_sessions = data["muscle_sessions"]
    muscle_sets     = data["muscle_sets"]
    all_muscles     = (
        _HIGH_PRIORITY | _MEDIUM_PRIORITY | _LOW_PRIORITY
    )

    # ── Factor 1: Per-muscle frequency ────────────────────────────────────
    over_freq:  list[str] = []
    under_freq: list[str] = []
    absent_hi:  list[str] = []

    for muscle in all_muscles:
        sessions = len(muscle_sessions.get(muscle, []))
        base_ded = _session_deduction(sessions)
        mult     = _multiplier(muscle)
        deductions += base_ded * mult

        if sessions == 0 and muscle in _HIGH_PRIORITY:
            absent_hi.append(muscle)
        elif sessions == 1:
            under_freq.append(muscle)
        elif sessions >= 3:
            over_freq.append(muscle)

    if absent_hi:
        names = ", ".join(m.replace("_", " ") for m in absent_hi)
        findings.append(
            f"High-priority muscles not trained this week: {names}. "
            "These are primary compound movers — missing them costs the most balance points."
        )
    if under_freq:
        names = ", ".join(m.replace("_", " ") for m in under_freq)
        findings.append(
            f"Trained only once this week (target is 2×): {names}."
        )
    if over_freq:
        names = ", ".join(m.replace("_", " ") for m in over_freq)
        findings.append(
            f"Trained 3+ times this week (diminishing returns above 2×): {names}."
        )
    if not absent_hi and not under_freq:
        findings.append("All major muscles hit the 2× weekly target. ✓")

    # ── Factor 2: Push/Pull/Legs set ratio ───────────────────────────────
    def _sets(group: set) -> int:
        return sum(muscle_sets.get(m, 0) for m in group)

    push_sets  = _sets(PUSH_MUSCLES)
    pull_sets  = _sets(PULL_MUSCLES)
    leg_sets   = _sets(LEG_MUSCLES)
    upper_sets = push_sets + pull_sets

    pp = _ratio(push_sets, pull_sets)
    rp = _ratio(pull_sets, push_sets)
    ul = _ratio(upper_sets, leg_sets)

    if pp is not None and pp > 2.5:
        findings.append(
            f"Push sets ({push_sets}) are {pp:.1f}× pull sets ({pull_sets}) — "
            "add more rows, pull-downs, or face pulls."
        )
        deductions += 15
    elif pp is not None and pp > 2.0:
        findings.append(
            f"Push sets slightly exceed pull sets ({push_sets} vs {pull_sets}) — "
            "add some extra pulling work."
        )
        deductions += 8
    elif rp is not None and rp > 2.5:
        findings.append(
            f"Pull sets ({pull_sets}) are {rp:.1f}× push sets ({push_sets}) — "
            "add more pressing work."
        )
        deductions += 15
    elif rp is not None and rp > 2.0:
        findings.append(
            f"Pull sets slightly exceed push sets ({pull_sets} vs {push_sets}) — "
            "consider adding pressing work."
        )
        deductions += 8
    else:
        findings.append(
            f"Push/pull set balance is good ({push_sets} push / {pull_sets} pull). ✓"
        )

    if leg_sets == 0:
        findings.append("No leg sets this week — legs are completely absent.")
        deductions += 10
    elif ul is not None and ul > 4.0:
        findings.append(
            f"Upper-body sets ({upper_sets}) are {ul:.1f}× leg sets ({leg_sets}) — "
            "legs are severely under-trained."
        )
        deductions += 15
    elif ul is not None and ul > 3.0:
        findings.append(
            f"Upper-body sets ({upper_sets}) outpace leg sets ({leg_sets}) — "
            "try adding a dedicated leg session."
        )
        deductions += 8
    else:
        findings.append(
            f"Upper/lower set balance is reasonable ({upper_sets} upper / {leg_sets} legs). ✓"
        )

    # ── Factor 3: Antagonist pairs ────────────────────────────────────────
    for agonist, antagonist in ANTAGONIST_PAIRS:
        a_sess = len(muscle_sessions.get(agonist, []))
        b_sess = len(muscle_sessions.get(antagonist, []))
        if a_sess == 0 and b_sess == 0:
            continue
        if a_sess > 0 and b_sess == 0:
            findings.append(
                f"{agonist.replace('_', ' ').title()} trained but "
                f"{antagonist.replace('_', ' ').title()} completely absent — "
                "train its antagonist to prevent imbalances."
            )
            deductions += 12
        elif b_sess > 0 and a_sess == 0:
            findings.append(
                f"{antagonist.replace('_', ' ').title()} trained but "
                f"{agonist.replace('_', ' ').title()} completely absent — "
                "train its antagonist to prevent imbalances."
            )
            deductions += 12
        elif abs(a_sess - b_sess) >= 2:
            dominant   = agonist if a_sess > b_sess else antagonist
            weaker     = antagonist if a_sess > b_sess else agonist
            findings.append(
                f"{dominant.replace('_', ' ').title()} trained "
                f"{max(a_sess, b_sess)}× vs "
                f"{weaker.replace('_', ' ').title()} {min(a_sess, b_sess)}× — "
                "bring the antagonist closer to the same frequency."
            )
            deductions += 8

    # ── Factor 4: Core inclusion ──────────────────────────────────────────
    has_abs  = "abs" in muscle_sessions
    has_erec = "spinal_erectors" in muscle_sessions

    if not has_abs and not has_erec:
        findings.append(
            "No core work detected — add planks, dead bugs, or back extensions for stability."
        )
        deductions += 8
    elif not has_abs or not has_erec:
        missing = "abs" if not has_abs else "spinal erectors"
        findings.append(
            f"Core is partially trained — {missing} not hit this week."
        )
        deductions += 3

    score = max(0.0, 100.0 - deductions)
    return CategoryResult(score=score, findings=findings)


def _eval_consistency(conn: sqlite3.Connection, user_id: int) -> CategoryResult:
    """
    Consistency score starts at 100; three deduction factors across all history:

    Factor 1 (highest weight): Week-over-week training presence
      - Each missing past week: -8 (capped at -40)
      - Consecutive missing weeks ≥2: additional -5 per streak week beyond the first

    Factor 2: Session count vs. personal baseline
      Shortfall = avg_weekly_sessions − current_week_sessions
      - Shortfall 1: -5
      - Shortfall 2: -12
      - Shortfall 3+: -20

    Factor 3: Progressive overload trajectory
      - Each stagnating muscle: -4 (capped at -16)
      - Each regressing muscle: -6 (capped at -12)
      - 3+ muscles progressing: -5 reward
    """
    from evaluation.progressive_overload import analyse_overload
    from collections import defaultdict

    findings:   list[str] = []
    deductions: float     = 0.0
    today       = date.today()

    def _week_start(d: date) -> date:
        return d - timedelta(days=d.weekday())

    all_dates = conn.execute(
        "SELECT date FROM workouts WHERE user_id = ? ORDER BY date",
        (user_id,),
    ).fetchall()

    if not all_dates:
        findings.append("No workout history yet — start logging to build a consistency score.")
        return CategoryResult(score=100.0, findings=findings)

    current_week = _week_start(today)
    first_week   = _week_start(date.fromisoformat(all_dates[0]["date"]))

    week_sessions: dict[date, int] = defaultdict(int)
    for row in all_dates:
        week_sessions[_week_start(date.fromisoformat(row["date"]))] += 1

    past_weeks = []
    w = first_week
    while w < current_week:
        past_weeks.append(w)
        w += timedelta(weeks=1)

    weeks_tracked = len(past_weeks)

    if weeks_tracked < 2:
        findings.append("Less than 2 completed weeks of history — consistency tracking will improve with more data.")
        return CategoryResult(score=100.0, findings=findings)

    # ── Factor 1: Weekly presence ─────────────────────────────────────────
    weeks_active  = sum(1 for w in past_weeks if week_sessions[w] > 0)
    weeks_missing = weeks_tracked - weeks_active

    presence_ded = min(40.0, weeks_missing * 8.0)
    deductions  += presence_ded

    # Extra penalty for consecutive missing streaks
    streak = max_streak = 0
    for w in past_weeks:
        if week_sessions[w] == 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    if max_streak >= 2:
        deductions += (max_streak - 1) * 5

    if weeks_missing == 0:
        findings.append(f"Training every week across all {weeks_tracked} tracked weeks. ✓")
    elif weeks_missing == 1:
        findings.append(f"{weeks_active} of {weeks_tracked} past weeks had sessions (1 missed week).")
    else:
        findings.append(
            f"{weeks_active} of {weeks_tracked} past weeks had sessions "
            f"({weeks_missing} missed). "
            + (f"Longest gap: {max_streak} consecutive weeks without training." if max_streak >= 2 else "")
        )

    # ── Factor 2: Session baseline comparison ────────────────────────────
    avg_weekly           = (sum(week_sessions[w] for w in past_weeks) / weeks_tracked)
    current_week_count   = week_sessions.get(current_week, 0)
    shortfall            = avg_weekly - current_week_count

    if avg_weekly >= 1:
        if shortfall <= 0:
            findings.append(
                f"This week's session count ({current_week_count}) is at or above "
                f"your average of {avg_weekly:.1f} sessions/week. ✓"
            )
        elif shortfall < 2:
            findings.append(
                f"This week: {current_week_count} session(s) vs. your average of "
                f"{avg_weekly:.1f}/week — slightly below baseline."
            )
            deductions += 5
        elif shortfall < 3:
            findings.append(
                f"This week: {current_week_count} session(s) vs. your average of "
                f"{avg_weekly:.1f}/week — meaningfully below baseline."
            )
            deductions += 12
        else:
            findings.append(
                f"This week: {current_week_count} session(s) vs. your average of "
                f"{avg_weekly:.1f}/week — significantly below your normal cadence."
            )
            deductions += 20

    # ── Factor 3: Progressive overload ───────────────────────────────────
    overload = analyse_overload(conn, user_id)
    progressing = [s.muscle for s in overload.statuses if s.trend == "progressing"]
    stagnating  = [s.muscle for s in overload.statuses if s.trend == "stagnating"]
    regressing  = [s.muscle for s in overload.statuses if s.trend == "regressing"]

    if not overload.statuses:
        findings.append("Not enough multi-week history to assess progressive overload yet.")
    else:
        if progressing:
            names = ", ".join(m.replace("_", " ") for m in progressing)
            findings.append(f"Progressive overload on: {names}. ✓")
        if stagnating:
            names = ", ".join(m.replace("_", " ") for m in stagnating)
            findings.append(
                f"Volume has plateaued for: {names}. "
                "Add weight, an extra set, or reduce rest time to break the plateau."
            )
            deductions += min(16.0, len(stagnating) * 4.0)
        if regressing:
            names = ", ".join(m.replace("_", " ") for m in regressing)
            findings.append(
                f"Volume declining for: {names}. "
                "If not an intentional deload, review your recovery and load management."
            )
            deductions += min(12.0, len(regressing) * 6.0)
        if len(progressing) >= 3:
            deductions = max(0.0, deductions - 5.0)

    score = max(0.0, 100.0 - deductions)
    return CategoryResult(score=score, findings=findings)


def _eval_rest(data: dict) -> CategoryResult:
    """
    Rest score starts at 100; three deduction factors:

    Factor 1 (highest weight): Weekly rest day count
      Ideal range: 1–3 rest days. Split context:
        PPL → 1 rest day is appropriate
        Upper/Lower → 2–3 rest days is appropriate
      - 0 rest days: -40
      - 1 rest day: no penalty (valid for high-frequency splits)
      - 2–3 rest days: no penalty (ideal for most splits)
      - 4 rest days: -5 (mild; over-rest beats under-rest)
      - 5+ rest days: -10 per extra day above 4

    Factor 2: Per-muscle inter-session gap
      Ideal: 2–3 days between same-muscle sessions.
      - 0 days (back-to-back): -15 per muscle
      - 1 day: -8 per muscle (still insufficient)
      - 2–3 days: no penalty
      - 4+ days: -3 per muscle (slight over-rest)

    Factor 3: Major category absence (chronic over-rest)
      - 5 per major category (push/pull/legs) with zero sessions this week
    """
    findings: list[str] = []
    deductions = 0.0

    total_days      = FATIGUE_WINDOW_DAYS
    dates_worked    = data["dates_worked"]
    rest_days       = total_days - len(dates_worked)
    total_workouts  = data["total_workouts"]
    muscle_sessions = data["muscle_sessions"]

    if total_workouts == 0:
        findings.append("No workouts logged this week — no fatigue to evaluate.")
        return CategoryResult(score=100.0, findings=findings)

    # ── Factor 1: Weekly rest day count ────────────────────────────────────
    if rest_days == 0:
        findings.append(
            "No rest days this week — training every day significantly increases "
            "injury risk and impairs recovery. At least 1 rest day is essential."
        )
        deductions += 40
    elif rest_days == 1:
        findings.append(
            "1 rest day this week — appropriate for high-frequency splits (e.g. PPL). "
            "Ensure each muscle has 2–3 days of recovery between sessions. ✓"
        )
    elif rest_days <= 3:
        findings.append(
            f"{rest_days} rest days this week — within the ideal range for most training splits. ✓"
        )
    elif rest_days == 4:
        findings.append(
            "4 rest days this week — leaning toward over-rest. "
            "Over-rest is better than under-rest, but check that no muscle groups are being chronically skipped."
        )
        deductions += 5
    else:
        findings.append(
            f"{rest_days} rest days this week — significantly under-training. "
            "Aim for 1–3 rest days to maintain training stimulus."
        )
        deductions += 10 + (rest_days - 5) * 10

    # ── Factor 2: Per-muscle inter-session rest ─────────────────────────────
    under_rested: list[str] = []
    over_rested:  list[str] = []

    for muscle, session_dates in muscle_sessions.items():
        sorted_dates = sorted(session_dates)
        for i in range(1, len(sorted_dates)):
            d1  = date.fromisoformat(sorted_dates[i - 1])
            d2  = date.fromisoformat(sorted_dates[i])
            gap = (d2 - d1).days
            if gap == 0:
                if muscle not in under_rested:
                    under_rested.append(muscle)
                deductions += 15
            elif gap == 1:
                if muscle not in under_rested:
                    under_rested.append(muscle)
                deductions += 8
            elif gap >= 4:
                if muscle not in over_rested:
                    over_rested.append(muscle)
                deductions += 3

    if under_rested:
        names = ", ".join(m.replace("_", " ") for m in under_rested)
        findings.append(
            f"Insufficient rest before re-training: {names}. "
            "Allow 2–3 days of recovery between sessions for the same muscle group."
        )
    else:
        findings.append("All muscle groups have adequate rest between sessions. ✓")

    if over_rested:
        names = ", ".join(m.replace("_", " ") for m in over_rested)
        findings.append(
            f"Extended gap (4+ days) between sessions for: {names}. "
            "Occasional over-rest is fine, but if this repeats week over week it may indicate chronic skipping."
        )

    # ── Factor 3: Major category absence ────────────────────────────────────
    trained = set(muscle_sessions.keys())
    absent: list[str] = []
    if not (trained & PUSH_MUSCLES): absent.append("push muscles")
    if not (trained & PULL_MUSCLES): absent.append("pull muscles")
    if not (trained & LEG_MUSCLES):  absent.append("leg muscles")

    if absent:
        names = ", ".join(absent)
        findings.append(
            f"No sessions for: {names} this week. "
            "If this pattern repeats across weeks it signals chronic over-rest for those muscle groups."
        )
        deductions += len(absent) * 5

    score = max(0.0, 100.0 - deductions)
    return CategoryResult(score=score, findings=findings)


def _eval_volume(data: dict) -> CategoryResult:
    """
    Volume score starts at 100; four deduction factors:

    Factor 1 (highest weight): Per-muscle weekly rep volume (sets × reps, no weight).
      Baseline: 1–3 exercises × 2–4 sets × 5–10 reps per session, ×2 sessions/week.
      - < 20 reps (trained but under-stimulated): -4 per muscle
      - 20–240 reps: ideal, no deduction
      - 241–360 reps: yellow — elevated, -5 per muscle
      - > 360 reps: red — excessive, -15 per muscle scaling up (cap -25 per muscle)

    Factor 2: Intensity distribution across sessions.
      - >70% high intensity: -10, scaling toward -20 near 100%
      - 100% low/moderate with 3+ sessions: -8

    Factor 3: Exercise density per session.
      - Any session > 12 exercises: -8
      - Any session with only 1 exercise: -4

    Factor 4: Session duration.
      - Any session > 150 min: -10
      - Any session > 120 min: -6
    """
    from constants import REP_VOL_UNDERTRAINED, REP_VOL_IDEAL_MAX, REP_VOL_YELLOW

    findings:   list[str] = []
    deductions: float     = 0.0

    mrv             = data["muscle_rep_volume"]
    muscle_sessions = data["muscle_sessions"]

    # ── Factor 1: Per-muscle rep volume ───────────────────────────────────
    undertrained: list[str] = []
    yellow_vol:   list[str] = []
    red_vol:      list[str] = []

    for muscle in muscle_sessions:  # only muscles that were actually trained
        reps = mrv.get(muscle, 0)
        if reps < REP_VOL_UNDERTRAINED:
            undertrained.append(muscle)
            deductions += 4
        elif reps > REP_VOL_YELLOW:
            red_vol.append(muscle)
            excess = reps - REP_VOL_YELLOW
            deductions += min(25, 15 + (excess / REP_VOL_YELLOW) * 10)
        elif reps > REP_VOL_IDEAL_MAX:
            yellow_vol.append(muscle)
            deductions += 5

    if red_vol:
        names = ", ".join(m.replace("_", " ") for m in red_vol)
        findings.append(
            f"Excessive rep volume for: {names} — well above the weekly threshold. "
            "Consider reducing sets, exercises, or adding a deload."
        )
    if yellow_vol:
        names = ", ".join(m.replace("_", " ") for m in yellow_vol)
        findings.append(
            f"Elevated rep volume for: {names}. "
            "These muscles are well-worked — ensure adequate recovery before the next session."
        )
    if undertrained:
        names = ", ".join(m.replace("_", " ") for m in undertrained)
        findings.append(
            f"Very low rep volume for: {names} (under 20 total reps this week). "
            "Add at least 2 working sets to provide a meaningful training stimulus."
        )
    if not red_vol and not yellow_vol and not undertrained:
        findings.append("All trained muscles are within the ideal weekly rep volume range. ✓")

    # ── Factor 2: Intensity distribution ─────────────────────────────────
    workouts    = data["workouts"]
    intensities = [w["intensity"] for w in workouts]
    total       = len(intensities)

    if total > 0:
        high_pct = intensities.count("high") / total
        if high_pct > 0.7:
            findings.append(
                f"{int(high_pct * 100)}% of sessions this week were high intensity — "
                "mix in moderate or low intensity sessions to manage accumulated fatigue."
            )
            deductions += min(20, 10 + (high_pct - 0.7) * 33)
        elif high_pct == 0 and total >= 3:
            findings.append(
                "No high-intensity sessions this week — "
                "at least one high-effort session helps drive adaptation."
            )
            deductions += 8
        else:
            findings.append("Intensity distribution across sessions is well-mixed. ✓")

    # ── Factor 3: Exercise density per session ────────────────────────────
    session_ex = data["session_exercise_counts"]
    dense   = [wid for wid, cnt in session_ex.items() if cnt > MAX_EXERCISES_PER_SESSION]
    sparse  = [wid for wid, cnt in session_ex.items() if cnt == 1]

    if dense:
        findings.append(
            f"{len(dense)} session(s) exceeded {MAX_EXERCISES_PER_SESSION} exercises — "
            "high exercise counts often signal junk volume rather than productive work."
        )
        deductions += len(dense) * 8
    if sparse:
        findings.append(
            f"{len(sparse)} session(s) contained only 1 exercise — "
            "aim for at least 2–3 exercises per session for a complete stimulus."
        )
        deductions += len(sparse) * 4
    if not dense and not sparse:
        findings.append("Exercise density per session is within a healthy range. ✓")

    # ── Factor 4: Session duration ────────────────────────────────────────
    long_sessions = [w["duration_mins"] for w in workouts if w["duration_mins"] > 120]
    if long_sessions:
        worst = max(long_sessions)
        if worst > 150:
            findings.append(
                f"A session lasted {worst} minutes — beyond 150 min, "
                "returns diminish sharply. Tighten rest periods or split into two sessions."
            )
            deductions += 10
        else:
            findings.append(
                f"A session ran {worst} minutes — just over the 2-hour mark. "
                "Monitor for signs of accumulated fatigue."
            )
            deductions += 6

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

    # Compute body-weight-scaled thresholds for suggestion filtering
    from constants import RED_VOLUME_THRESHOLD, YELLOW_VOLUME_THRESHOLD
    bw_scale         = data["body_weight"] / 150.0
    effective_red    = RED_VOLUME_THRESHOLD    * bw_scale
    effective_yellow = YELLOW_VOLUME_THRESHOLD * bw_scale

    # Build suggestions from needed categories
    seen_names: set[str] = set()
    for tag, reason in category_need:
        for name, muscles, cat in _WORKOUT_LIBRARY:
            if cat == tag and name not in seen_names:
                # Skip if any of these muscles are already overloaded (red)
                if all(mv.get(m, 0) < effective_red for m in muscles):
                    suggestions.append(WorkoutSuggestion(
                        name=name,
                        muscle_groups=muscles,
                        reason=reason,
                        priority="high" if tag in ("legs", "pull") else "medium",
                    ))
                    seen_names.add(name)
                    break

    # ── Suggest active recovery if 0 rest days and high volume ────────────
    high_vol_muscles = [m for m, v in mv.items() if v >= effective_yellow]
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
    balance_res     = _eval_balance(data)
    consistency_res = _eval_consistency(conn, user_id)
    rest_res        = _eval_rest(data)
    vol_res         = _eval_volume(data)

    categories = {
        "balance":     balance_res,
        "consistency": consistency_res,
        "rest":        rest_res,
        "volume":      vol_res,
    }

    # ── Weighted overall score ─────────────────────────────────────────────
    overall = sum(
        categories[cat].score * weight
        for cat, weight in SCORE_WEIGHTS.items()
    )

    # ── Suggestions ────────────────────────────────────────────────────────
    suggestions = _build_suggestions(data, balance_res, consistency_res, rest_res, vol_res)

    return EvaluationResult(
        overall_score=overall,
        grade=_grade(overall),
        categories=categories,
        suggestions=suggestions,
    )
