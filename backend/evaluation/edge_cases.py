"""
evaluation/edge_cases.py
-------------------------
Detects and gracefully handles training patterns that would otherwise
produce misleading scores or crash the engine.

Cases handled:
  - New user          : fewer than 3 total workouts logged
  - Empty week        : no workouts in the current 7-day window
  - Single-muscle focus : every session this week hits only one muscle group
  - Extreme sessions  : unusually long duration or very high exercise count
  - No-weight logging : user logs only bodyweight exercises (weight_lbs = 0)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List

from constants import (
    FATIGUE_WINDOW_DAYS,
    MAX_EXERCISES_PER_SESSION,
    MAX_WORKOUT_DURATION_MINS,
    MUSCLE_GROUPS,
)

# Thresholds
NEW_USER_WORKOUT_THRESHOLD    = 3     # fewer than this = new user
SINGLE_MUSCLE_SESSION_RATIO   = 0.75  # if this fraction of sessions are single-muscle
EXTREME_DURATION_MINS         = 150   # flag sessions longer than this
EXTREME_EXERCISE_COUNT        = 15    # flag sessions with more exercises than this


@dataclass
class EdgeCaseResult:
    is_new_user:          bool = False
    is_empty_week:        bool = False
    is_single_focus:      bool = False
    has_extreme_sessions: bool = False
    is_bodyweight_only:   bool = False
    findings:             List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "is_new_user":          self.is_new_user,
            "is_empty_week":        self.is_empty_week,
            "is_single_focus":      self.is_single_focus,
            "has_extreme_sessions": self.has_extreme_sessions,
            "is_bodyweight_only":   self.is_bodyweight_only,
            "findings":             self.findings,
        }


def detect_edge_cases(conn: sqlite3.Connection, user_id: int) -> EdgeCaseResult:
    """
    Run all edge case checks and return a summary.
    The engine calls this first; detected flags modify how results are presented.
    """
    result   = EdgeCaseResult()
    findings = result.findings
    cutoff   = (date.today() - timedelta(days=FATIGUE_WINDOW_DAYS)).isoformat()

    # ── Total workout count (all time) ─────────────────────────────────────
    total_all_time = conn.execute(
        "SELECT COUNT(*) AS cnt FROM workouts WHERE user_id = ?",
        (user_id,),
    ).fetchone()["cnt"]

    if total_all_time < NEW_USER_WORKOUT_THRESHOLD:
        result.is_new_user = True
        findings.append(
            f"Welcome! You have logged {total_all_time} workout(s) so far. "
            "Log at least 3 sessions to unlock full evaluation insights."
        )
        return result   # early exit — other checks aren't meaningful yet

    # ── Current week workouts ─────────────────────────────────────────────
    week_workouts = conn.execute(
        """
        SELECT id, duration_mins FROM workouts
        WHERE  user_id = ? AND date >= ?
        """,
        (user_id, cutoff),
    ).fetchall()

    if not week_workouts:
        result.is_empty_week = True
        findings.append(
            "No workouts logged in the past 7 days. "
            "Your muscles are fully recovered — time to get back at it!"
        )
        return result

    workout_ids = [w["id"] for w in week_workouts]

    # ── Extreme session detection ─────────────────────────────────────────
    extreme_sessions = []
    for w in week_workouts:
        if w["duration_mins"] > EXTREME_DURATION_MINS:
            extreme_sessions.append(
                f"{w['duration_mins']} min session (over {EXTREME_DURATION_MINS} min)"
            )

    ex_counts = conn.execute(
        f"""
        SELECT workout_id, COUNT(*) AS cnt
        FROM   exercises
        WHERE  workout_id IN ({','.join('?' * len(workout_ids))})
        GROUP  BY workout_id
        """,
        workout_ids,
    ).fetchall()

    for row in ex_counts:
        if row["cnt"] > EXTREME_EXERCISE_COUNT:
            extreme_sessions.append(
                f"{row['cnt']} exercises in one session (over {EXTREME_EXERCISE_COUNT})"
            )

    if extreme_sessions:
        result.has_extreme_sessions = True
        for desc in extreme_sessions:
            findings.append(
                f"Extreme session detected: {desc}. "
                "Very long or exercise-dense sessions may inflate volume scores "
                "and increase fatigue beyond what raw numbers suggest."
            )

    # ── Single-muscle-focus detection ─────────────────────────────────────
    if len(workout_ids) >= 2:
        per_workout_muscle_counts = conn.execute(
            f"""
            SELECT workout_id, COUNT(DISTINCT muscle_group_id) AS muscle_cnt
            FROM   exercises
            WHERE  workout_id IN ({','.join('?' * len(workout_ids))})
            GROUP  BY workout_id
            """,
            workout_ids,
        ).fetchall()

        single_muscle_sessions = sum(
            1 for row in per_workout_muscle_counts if row["muscle_cnt"] == 1
        )
        ratio = single_muscle_sessions / len(workout_ids)

        if ratio >= SINGLE_MUSCLE_SESSION_RATIO:
            result.is_single_focus = True
            findings.append(
                f"{single_muscle_sessions} of {len(workout_ids)} sessions this week "
                "targeted only a single muscle group. "
                "Consider compound movements to improve efficiency and balance."
            )

    # ── Bodyweight-only detection ─────────────────────────────────────────
    non_bw = conn.execute(
        f"""
        SELECT COUNT(*) AS cnt FROM exercises
        WHERE  workout_id IN ({','.join('?' * len(workout_ids))})
          AND  weight_lbs > 0
        """,
        workout_ids,
    ).fetchone()["cnt"]

    if non_bw == 0:
        result.is_bodyweight_only = True
        findings.append(
            "All exercises this week were logged as bodyweight (weight = 0). "
            "Volume scores use a nominal 100 lb substitute — "
            "log actual weights for more accurate tracking."
        )

    if not findings:
        findings.append("No edge cases detected in your current week's data. ✓")

    return result
