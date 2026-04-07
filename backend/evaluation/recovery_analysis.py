"""
evaluation/recovery_analysis.py
---------------------------------
Analyses recovery patterns across all historical workout data,
looking for chronic under-recovery that a single-week snapshot
would miss.

Detects:
  - Chronic same-muscle back-to-back patterns (repeated across multiple weeks)
  - Persistent lack of rest days week over week
  - Weeks with zero rest days (training every day)
  - Consistently high intensity with no deload signals
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Set

from constants import FATIGUE_WINDOW_DAYS, INTENSITY_MULTIPLIERS


# A week is "rest-deficient" if it has fewer than this many rest days
REST_DEFICIENT_THRESHOLD = 2

# Flag if this many or more consecutive weeks are rest-deficient
CHRONIC_REST_DEFICIENT_WEEKS = 2

# Flag if same muscle is trained on back-to-back days in this many weeks
CHRONIC_BTB_WEEKS = 2


@dataclass
class RecoveryResult:
    findings: List[str] = field(default_factory=list)
    score:    float     = 100.0   # penalty-based

    def to_dict(self) -> dict:
        return {
            "score":    round(self.score, 1),
            "findings": self.findings,
        }


def _iso_week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def analyse_recovery(conn: sqlite3.Connection, user_id: int) -> RecoveryResult:
    """
    Scan all historical workouts and flag chronic recovery issues.
    """
    workout_rows = conn.execute(
        """
        SELECT id, date, intensity
        FROM   workouts
        WHERE  user_id = ?
        ORDER  BY date
        """,
        (user_id,),
    ).fetchall()

    if not workout_rows:
        return RecoveryResult(
            findings=["No workout history found."],
            score=100.0,
        )

    exercise_rows = conn.execute(
        """
        SELECT e.workout_id, mg.name AS muscle
        FROM   exercises e
        JOIN   muscle_groups mg ON mg.id = e.muscle_group_id
        JOIN   workouts w       ON w.id  = e.workout_id
        WHERE  w.user_id = ?
        """,
        (user_id,),
    ).fetchall()

    # ── Build per-workout metadata ─────────────────────────────────────────
    workout_date:    Dict[int, date]      = {}
    workout_muscles: Dict[int, Set[str]]  = defaultdict(set)
    workout_intensity: Dict[int, str]     = {}

    for row in workout_rows:
        wid = row["id"]
        workout_date[wid]      = date.fromisoformat(row["date"])
        workout_intensity[wid] = row["intensity"]

    for row in exercise_rows:
        workout_muscles[row["workout_id"]].add(row["muscle"])

    # ── Group workouts by ISO week ─────────────────────────────────────────
    weeks: Dict[date, List[int]] = defaultdict(list)
    for wid, d in workout_date.items():
        weeks[_iso_week_start(d)].append(wid)

    sorted_weeks = sorted(weeks.keys())
    total_weeks  = len(sorted_weeks)

    findings:    List[str] = []
    score_delta: float     = 0.0

    # ── Per-week rest day count ────────────────────────────────────────────
    rest_deficient_count = 0
    zero_rest_weeks      = 0

    for week_start in sorted_weeks:
        workout_ids    = weeks[week_start]
        days_with_work = {workout_date[wid] for wid in workout_ids}
        rest_days      = FATIGUE_WINDOW_DAYS - len(days_with_work)

        if rest_days == 0:
            zero_rest_weeks += 1
        if rest_days < REST_DEFICIENT_THRESHOLD:
            rest_deficient_count += 1
        else:
            rest_deficient_count = 0  # reset streak

        if rest_deficient_count >= CHRONIC_REST_DEFICIENT_WEEKS:
            findings.append(
                f"{rest_deficient_count} consecutive weeks with fewer than "
                f"{REST_DEFICIENT_THRESHOLD} rest days detected. "
                "Chronic under-recovery can stall progress and increase injury risk."
            )
            score_delta -= min(20, rest_deficient_count * 5)
            rest_deficient_count = 0  # report once per streak

    if zero_rest_weeks > 0:
        findings.append(
            f"{zero_rest_weeks} week(s) where you trained every single day. "
            "At minimum one full rest day per week is strongly recommended."
        )
        score_delta -= min(15, zero_rest_weeks * 5)

    # ── Chronic same-muscle back-to-back ───────────────────────────────────
    # For each muscle, count weeks where it was trained on consecutive days
    muscle_btb_weeks: Dict[str, int] = defaultdict(int)

    for week_start, workout_ids in weeks.items():
        # Group workouts this week by date
        day_muscles: Dict[date, Set[str]] = defaultdict(set)
        for wid in workout_ids:
            day_muscles[workout_date[wid]].update(workout_muscles[wid])

        sorted_days = sorted(day_muscles.keys())
        for i in range(1, len(sorted_days)):
            gap = (sorted_days[i] - sorted_days[i - 1]).days
            if gap == 1:
                shared = day_muscles[sorted_days[i - 1]] & day_muscles[sorted_days[i]]
                for muscle in shared:
                    muscle_btb_weeks[muscle] += 1

    chronic_btb = [
        m for m, count in muscle_btb_weeks.items()
        if count >= CHRONIC_BTB_WEEKS
    ]
    if chronic_btb:
        names = ", ".join(m.replace("_", " ") for m in sorted(chronic_btb))
        findings.append(
            f"Chronically training back-to-back days for: {names}. "
            "This pattern has appeared across multiple weeks — "
            "build in at least one day of rest between sessions for these muscles."
        )
        score_delta -= min(20, len(chronic_btb) * 4)

    # ── High-intensity overuse across weeks ───────────────────────────────
    all_intensities = [workout_intensity[wid] for wid in workout_date]
    if all_intensities:
        high_pct = all_intensities.count("high") / len(all_intensities)
        if high_pct > 0.75 and total_weeks >= 3:
            findings.append(
                f"{int(high_pct * 100)}% of all your sessions have been high intensity. "
                "Consider periodising with moderate and low intensity weeks "
                "to manage cumulative fatigue."
            )
            score_delta -= min(15, (high_pct - 0.75) * 60)

    # ── Positive feedback if recovery looks good ───────────────────────────
    if not findings:
        findings.append(
            "No chronic recovery issues detected across your full training history. ✓"
        )

    final_score = max(0.0, min(100.0, 100.0 + score_delta))
    return RecoveryResult(findings=findings, score=final_score)
