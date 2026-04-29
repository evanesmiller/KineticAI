"""
evaluation/progressive_overload.py
-----------------------------------
Tracks week-over-week volume and peak weight trends per muscle group
across all available history.

Detects:
  - Consistent progression   (volume or weight increasing week over week)
  - Stagnation               (no meaningful change for 2+ weeks)
  - Regression               (volume or weight decreasing)
  - Insufficient history     (fewer than 2 weeks of data — skip gracefully)
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from constants import BODYWEIGHT_NOMINAL_LBS, INTENSITY_MULTIPLIERS, MUSCLE_GROUPS


# Minimum % change in weekly volume to count as "meaningful progression"
PROGRESSION_THRESHOLD = 0.05   # 5%
REGRESSION_THRESHOLD  = -0.08  # -8% — small drops are noise, flag larger ones
STAGNATION_WEEKS      = 2      # flag if no progression for this many consecutive weeks


@dataclass
class MuscleOverloadStatus:
    muscle:       str
    trend:        str           # 'progressing' | 'stagnating' | 'regressing' | 'new'
    weeks_flat:   int = 0       # consecutive weeks without meaningful increase
    pct_change:   Optional[float] = None   # week-over-week % change (latest vs prior)
    peak_weight:  Optional[float] = None   # highest single-rep weight seen all-time
    note:         str = ""


@dataclass
class OverloadResult:
    statuses:  List[MuscleOverloadStatus] = field(default_factory=list)
    findings:  List[str]                  = field(default_factory=list)
    score:     float = 100.0   # bonus/penalty applied to overall score

    def to_dict(self) -> dict:
        return {
            "score":    round(self.score, 1),
            "findings": self.findings,
            "muscles": [
                {
                    "muscle":      s.muscle,
                    "trend":       s.trend,
                    "weeks_flat":  s.weeks_flat,
                    "pct_change":  round(s.pct_change, 1) if s.pct_change is not None else None,
                    "peak_weight": s.peak_weight,
                    "note":        s.note,
                }
                for s in self.statuses
            ],
        }


def _iso_week_start(d: date) -> date:
    """Return the Monday of the ISO week containing d."""
    return d - timedelta(days=d.weekday())


def analyse_overload(conn: sqlite3.Connection, user_id: int) -> OverloadResult:
    """
    Fetch all historical exercise data, bucket by ISO week, and compute
    week-over-week volume trends per muscle group.
    """
    rows = conn.execute(
        """
        SELECT e.sets, e.reps, e.weight_lbs, mg.name AS muscle,
               w.intensity, w.date
        FROM   exercises e
        JOIN   muscle_groups mg ON mg.id = e.muscle_group_id
        JOIN   workouts w       ON w.id  = e.workout_id
        WHERE  w.user_id = ?
        ORDER  BY w.date
        """,
        (user_id,),
    ).fetchall()

    if not rows:
        return OverloadResult(
            findings=["No workout history found — start logging to track progress."],
            score=100.0,
        )

    # Use the user's stored body weight for bodyweight exercise substitution.
    bw_row = conn.execute(
        "SELECT body_weight_lbs FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    body_weight = (
        float(bw_row["body_weight_lbs"])
        if bw_row and bw_row["body_weight_lbs"]
        else BODYWEIGHT_NOMINAL_LBS
    )

    # ── Bucket volume and peak weight by (muscle, week_start) ─────────────
    weekly_volume: Dict[str, Dict[date, float]] = defaultdict(dict)
    weekly_peak:   Dict[str, Dict[date, float]] = defaultdict(dict)

    for row in rows:
        muscle    = row["muscle"]
        d         = date.fromisoformat(row["date"])
        week      = _iso_week_start(d)
        mult      = INTENSITY_MULTIPLIERS.get(row["intensity"], 1.0)
        eff_wt    = row["weight_lbs"] if row["weight_lbs"] > 0 else body_weight
        vol       = row["sets"] * row["reps"] * eff_wt * mult

        weekly_volume[muscle][week] = weekly_volume[muscle].get(week, 0.0) + vol
        weekly_peak[muscle][week]   = max(weekly_peak[muscle].get(week, 0.0), eff_wt)

    # ── Determine all weeks in history ────────────────────────────────────
    all_weeks = sorted({
        _iso_week_start(date.fromisoformat(r["date"])) for r in rows
    })
    total_weeks = len(all_weeks)

    if total_weeks < 2:
        return OverloadResult(
            findings=["Need at least 2 weeks of data to assess progressive overload."],
            score=100.0,
        )

    # ── Analyse each trained muscle ────────────────────────────────────────
    statuses:    List[MuscleOverloadStatus] = []
    findings:    List[str]                  = []
    score_delta: float                      = 0.0

    trained_muscles = [m for m in MUSCLE_GROUPS if m in weekly_volume]

    for muscle in trained_muscles:
        vols  = weekly_volume[muscle]
        peaks = weekly_peak[muscle]

        # Only look at weeks this muscle was actually trained
        muscle_weeks = sorted(w for w in all_weeks if w in vols)

        if len(muscle_weeks) < 2:
            statuses.append(MuscleOverloadStatus(
                muscle=muscle, trend="new",
                note="Only trained in one week — need more history.",
            ))
            continue

        # Compare last two trained weeks
        prev_week = muscle_weeks[-2]
        last_week = muscle_weeks[-1]

        prev_vol  = vols[prev_week]
        last_vol  = vols[last_week]
        pct       = (last_vol - prev_vol) / prev_vol if prev_vol > 0 else 0.0

        peak_wt = max(peaks.values())

        # Count consecutive stagnant weeks
        weeks_flat = 0
        for i in range(len(muscle_weeks) - 1, 0, -1):
            w_curr = muscle_weeks[i]
            w_prev = muscle_weeks[i - 1]
            v_curr = vols[w_curr]
            v_prev = vols[w_prev]
            change = (v_curr - v_prev) / v_prev if v_prev > 0 else 0.0
            if abs(change) < PROGRESSION_THRESHOLD:
                weeks_flat += 1
            else:
                break

        # Classify trend
        if pct >= PROGRESSION_THRESHOLD:
            trend = "progressing"
            note  = f"Volume up {pct * 100:.1f}% vs previous trained week."
        elif pct <= REGRESSION_THRESHOLD:
            trend = "regressing"
            note  = f"Volume down {abs(pct) * 100:.1f}% vs previous trained week."
            score_delta -= 5
        elif weeks_flat >= STAGNATION_WEEKS:
            trend = "stagnating"
            note  = f"Volume unchanged for {weeks_flat} consecutive trained weeks."
            score_delta -= 8
        else:
            trend = "stagnating"
            note  = "Volume similar to previous week — consider adding load or sets."

        statuses.append(MuscleOverloadStatus(
            muscle=muscle,
            trend=trend,
            weeks_flat=weeks_flat,
            pct_change=round(pct * 100, 1),
            peak_weight=peak_wt,
            note=note,
        ))

    # ── Build human-readable findings ─────────────────────────────────────
    progressing = [s.muscle for s in statuses if s.trend == "progressing"]
    stagnating  = [s.muscle for s in statuses if s.trend == "stagnating"]
    regressing  = [s.muscle for s in statuses if s.trend == "regressing"]

    if progressing:
        names = ", ".join(m.replace("_", " ") for m in progressing)
        findings.append(f"Progressive overload detected for: {names}. Keep it up! ✓")

    if stagnating:
        names = ", ".join(m.replace("_", " ") for m in stagnating)
        findings.append(
            f"Volume has plateaued for: {names}. "
            "Try adding weight, an extra set, or reducing rest time to break the plateau."
        )

    if regressing:
        names = ", ".join(m.replace("_", " ") for m in regressing)
        findings.append(
            f"Volume has decreased for: {names}. "
            "This may be intentional (deload) — if not, check your recovery."
        )

    if not statuses:
        findings.append("Not enough history to assess progressive overload yet.")

    # ── Relative-strength milestones ──────────────────────────────────────
    # Only shown when the user has set their body weight. We check each muscle's
    # all-time peak weight against the body weight and emit milestone findings.
    # Thresholds are intentionally generous — they should feel like achievements.
    BW_MILESTONES = [
        (2.0, "elite territory"),
        (1.5, "very strong"),
        (1.0, "above body weight — a solid milestone"),
    ]

    for status in statuses:
        if status.peak_weight is None:
            continue
        ratio = status.peak_weight / body_weight
        muscle_label = status.muscle.replace("_", " ")
        # Find the highest milestone this muscle has reached
        for threshold, label in BW_MILESTONES:
            if ratio >= threshold:
                findings.append(
                    f"Your peak {muscle_label} lift is {ratio:.2f}× body weight "
                    f"({status.peak_weight:.0f} lbs) — {label}. ✓"
                )
                break  # only report the highest milestone per muscle

    final_score = max(0.0, min(100.0, 100.0 + score_delta))
    return OverloadResult(statuses=statuses, findings=findings, score=final_score)
