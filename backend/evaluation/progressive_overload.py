"""
evaluation/progressive_overload.py
-----------------------------------
Tracks weight progression per muscle group across all available history.

For each muscle, finds the primary exercise with the highest peak weight,
then compares its most recent logged weight to the very first time it was
logged, showing how much the user has increased that lift over their
entire history.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from constants import BODYWEIGHT_NOMINAL_LBS, MUSCLE_GROUPS


_BW_THRESHOLDS = [
    (2.0, "elite territory"),
    (1.5, "very strong"),
    (1.0, "a solid milestone"),
]


@dataclass
class MuscleOverloadStatus:
    muscle:        str
    exercise_name: str = ""
    trend:         str = "new"        # 'progressing' | 'stagnating' | 'regressing' | 'new'
    pct_change:    Optional[float] = None   # (latest_weight - first_weight) / first_weight * 100
    first_weight:  Optional[float] = None  # weight the first time the exercise was logged
    peak_weight:   Optional[float] = None  # most recent logged weight for this exercise
    bw_ratio:      Optional[float] = None  # peak_weight / body_weight
    milestone:     str = ""                # "elite territory" | "very strong" | "a solid milestone" | ""
    note:          str = ""


@dataclass
class OverloadResult:
    statuses:  List[MuscleOverloadStatus] = field(default_factory=list)
    findings:  List[str]                  = field(default_factory=list)
    score:     float = 100.0

    def to_dict(self) -> dict:
        return {
            "score":    round(self.score, 1),
            "findings": self.findings,
            "muscles": [
                {
                    "muscle":         s.muscle,
                    "exercise_name":  s.exercise_name,
                    "trend":          s.trend,
                    "pct_change":     round(s.pct_change, 1) if s.pct_change is not None else None,
                    "first_weight":   s.first_weight,
                    "peak_weight":    s.peak_weight,
                    "bw_ratio":       s.bw_ratio,
                    "milestone":      s.milestone,
                    "note":           s.note,
                }
                for s in self.statuses
            ],
        }


def analyse_overload(conn: sqlite3.Connection, user_id: int) -> OverloadResult:
    """
    For each trained muscle group, find the weighted exercise with the
    highest peak weight. Compare the first logged weight for that exercise
    to the most recently logged weight, and compute the all-time % change.
    """
    rows = conn.execute(
        """
        SELECT e.name AS exercise_name, e.weight_lbs,
               mg.name AS muscle, w.date
        FROM   exercises e
        JOIN   muscle_groups mg ON mg.id = e.muscle_group_id
        JOIN   workouts w       ON w.id  = e.workout_id
        WHERE  w.user_id = ? AND e.weight_lbs > 0
          AND  e.name NOT LIKE '%(secondary)%'
        ORDER  BY w.date
        """,
        (user_id,),
    ).fetchall()

    if not rows:
        return OverloadResult(
            findings=["No weighted exercises logged yet — add weight to exercises to track progression."],
            score=100.0,
        )

    bw_row = conn.execute(
        "SELECT body_weight_lbs FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    body_weight = (
        float(bw_row["body_weight_lbs"])
        if bw_row and bw_row["body_weight_lbs"]
        else BODYWEIGHT_NOMINAL_LBS
    )

    # muscle -> exercise_name -> [(date, weight), ...]  (rows already sorted by date)
    muscle_exercises: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        clean = row["exercise_name"].replace(" (primary)", "").replace("(primary)", "").strip()
        muscle_exercises[row["muscle"]][clean].append(
            (row["date"], float(row["weight_lbs"]))
        )

    statuses:    List[MuscleOverloadStatus] = []
    score_delta: float                      = 0.0

    for muscle in MUSCLE_GROUPS:
        if muscle not in muscle_exercises:
            continue

        exercises = muscle_exercises[muscle]

        # Pick the exercise with the highest single-session weight for this muscle
        best_ex = max(exercises, key=lambda ex: max(w for _, w in exercises[ex]))
        entries = exercises[best_ex]   # already date-ordered (ORDER BY w.date above)

        first_weight  = entries[0][1]
        latest_weight = entries[-1][1]

        bw_ratio  = round(latest_weight / body_weight, 2) if body_weight > 0 else None
        milestone = ""
        for threshold, label in _BW_THRESHOLDS:
            if bw_ratio is not None and bw_ratio >= threshold:
                milestone = label
                break

        if len(entries) == 1:
            trend      = "new"
            pct_change = None
            note       = "Only logged once — keep training to track progression."
        else:
            pct_change = round((latest_weight - first_weight) / first_weight * 100, 1)
            if pct_change > 0:
                trend = "progressing"
                note  = f"{first_weight:.0f} → {latest_weight:.0f} lbs (+{pct_change}%)"
            elif pct_change < 0:
                trend = "regressing"
                note  = f"{first_weight:.0f} → {latest_weight:.0f} lbs ({pct_change}%)"
                score_delta -= 5
            else:
                trend = "stagnating"
                note  = f"Weight unchanged at {latest_weight:.0f} lbs across all sessions"
                score_delta -= 3

        statuses.append(MuscleOverloadStatus(
            muscle=muscle,
            exercise_name=best_ex,
            trend=trend,
            pct_change=pct_change,
            first_weight=first_weight,
            peak_weight=latest_weight,
            bw_ratio=bw_ratio,
            milestone=milestone,
            note=note,
        ))

    findings: List[str] = []
    progressing = [s for s in statuses if s.trend == "progressing"]
    stagnating  = [s for s in statuses if s.trend == "stagnating"]
    regressing  = [s for s in statuses if s.trend == "regressing"]

    if progressing:
        names = ", ".join(s.muscle.replace("_", " ") for s in progressing)
        findings.append(f"Increasing weight over time for: {names}. ✓")
    if stagnating:
        names = ", ".join(s.muscle.replace("_", " ") for s in stagnating)
        findings.append(f"Weight has stayed flat for: {names}. Try adding load.")
    if regressing:
        names = ", ".join(s.muscle.replace("_", " ") for s in regressing)
        findings.append(f"Weight has decreased for: {names}. Check your recovery.")

    return OverloadResult(
        statuses=statuses,
        findings=findings,
        score=max(0.0, min(100.0, 100.0 + score_delta)),
    )
