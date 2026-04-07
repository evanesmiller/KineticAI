"""
evaluation/split_detector.py
------------------------------
Analyses the composition of each workout session across all history
to classify the user's training split and score their adherence to it.

Supported splits (in detection priority order):
  PPL         — Push / Pull / Legs (3- or 6-day)
  Upper/Lower — Upper body and lower body alternating
  Full Body   — Most sessions hit all three categories
  Bro Split   — Dedicated single-muscle sessions (chest day, arm day, etc.)
  Unknown     — Pattern doesn't match any recognised split

Adherence score:
  How consistently does each session match the detected split's expected
  pattern? E.g. a PPL user who mixes push and pull muscles in the same
  session has low adherence.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Set, Tuple

from constants import CORE_MUSCLES, LEG_MUSCLES, PULL_MUSCLES, PUSH_MUSCLES


# ---------------------------------------------------------------------------
# Per-session muscle category classification
# ---------------------------------------------------------------------------

def _classify_session(muscles_trained: Set[str]) -> str:
    """
    Given the set of muscles trained in one session, return a category label.
    """
    has_push = bool(muscles_trained & PUSH_MUSCLES)
    has_pull = bool(muscles_trained & PULL_MUSCLES)
    has_legs = bool(muscles_trained & LEG_MUSCLES)

    active = sum([has_push, has_pull, has_legs])

    if active == 3:
        return "full_body"
    if has_push and has_pull and not has_legs:
        return "upper"
    if has_legs and not has_push and not has_pull:
        return "legs"
    if has_push and not has_pull and not has_legs:
        return "push"
    if has_pull and not has_push and not has_legs:
        return "pull"
    if has_legs and (has_push or has_pull):
        return "lower_mix"
    return "other"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SplitResult:
    detected_split:   str          # 'PPL' | 'Upper/Lower' | 'Full Body' | 'Bro Split' | 'Unknown'
    adherence_score:  float        # 0–100: how consistently they follow the split
    session_breakdown: Dict[str, int] = field(default_factory=dict)  # label -> count
    findings:         List[str]    = field(default_factory=list)
    total_sessions:   int          = 0

    def to_dict(self) -> dict:
        return {
            "detected_split":    self.detected_split,
            "adherence_score":   round(self.adherence_score, 1),
            "total_sessions":    self.total_sessions,
            "session_breakdown": self.session_breakdown,
            "findings":          self.findings,
        }


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

def _detect_split(label_counts: Counter, total: int) -> Tuple[str, float]:
    """
    Given session label counts, return (split_name, adherence_score).
    Adherence is the fraction of sessions that match the detected split's pattern.
    """
    if total == 0:
        return "Unknown", 0.0

    full_body_pct = label_counts.get("full_body", 0) / total
    push_pct      = label_counts.get("push", 0) / total
    pull_pct      = label_counts.get("pull", 0) / total
    legs_pct      = label_counts.get("legs", 0) / total
    upper_pct     = label_counts.get("upper", 0) / total
    lower_mix_pct = label_counts.get("lower_mix", 0) / total

    ppl_sessions   = label_counts.get("push", 0) + label_counts.get("pull", 0) + label_counts.get("legs", 0)
    upper_sessions = label_counts.get("upper", 0) + label_counts.get("legs", 0) + label_counts.get("lower_mix", 0)

    # Full Body: majority of sessions are full_body
    if full_body_pct >= 0.55:
        return "Full Body", round(full_body_pct * 100, 1)

    # PPL: push + pull + legs each make up a meaningful portion, no upper mixing
    if (push_pct >= 0.2 and pull_pct >= 0.2 and legs_pct >= 0.15
            and upper_pct < 0.2):
        adherence = (ppl_sessions / total) * 100
        return "PPL", round(adherence, 1)

    # Upper/Lower: upper + lower_mix/legs dominate, minimal isolated push/pull
    if (upper_pct >= 0.3 and (legs_pct + lower_mix_pct) >= 0.2
            and full_body_pct < 0.3):
        adherence = (upper_sessions / total) * 100
        return "Upper/Lower", round(adherence, 1)

    # Bro Split: mostly isolated push or pull sessions, rarely mixed
    if push_pct + pull_pct >= 0.6 and upper_pct < 0.2 and full_body_pct < 0.2:
        bro_sessions = label_counts.get("push", 0) + label_counts.get("pull", 0)
        return "Bro Split", round((bro_sessions / total) * 100, 1)

    # Fallback
    dominant = label_counts.most_common(1)[0][0] if label_counts else "other"
    return "Unknown", round((label_counts.get(dominant, 0) / total) * 100, 1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_split(conn: sqlite3.Connection, user_id: int) -> SplitResult:
    """
    Classify the user's training split based on all historical workouts
    and score how consistently they adhere to it.
    """
    # Fetch all workouts with their muscle groups
    workout_rows = conn.execute(
        """
        SELECT DISTINCT w.id, w.date
        FROM   workouts w
        WHERE  w.user_id = ?
        ORDER  BY w.date
        """,
        (user_id,),
    ).fetchall()

    if not workout_rows:
        return SplitResult(
            detected_split="Unknown",
            adherence_score=0.0,
            findings=["No workout history to analyse."],
        )

    # Build per-workout muscle sets
    workout_muscles: Dict[int, Set[str]] = defaultdict(set)
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

    for row in exercise_rows:
        workout_muscles[row["workout_id"]].add(row["muscle"])

    # Classify each session
    labels = [_classify_session(workout_muscles[w["id"]]) for w in workout_rows]
    label_counts = Counter(labels)
    total = len(labels)

    detected_split, adherence = _detect_split(label_counts, total)

    # ── Build findings ─────────────────────────────────────────────────────
    findings: List[str] = []

    findings.append(
        f"Detected training split: {detected_split} "
        f"(adherence: {adherence:.0f}% of {total} sessions)."
    )

    if adherence >= 80:
        findings.append(f"You are consistently following your {detected_split} split. ✓")
    elif adherence >= 60:
        findings.append(
            f"Moderate adherence to {detected_split}. "
            "Some sessions deviate from the expected pattern — "
            "try to keep session muscle groups more consistent."
        )
    else:
        findings.append(
            f"Low adherence to {detected_split} ({adherence:.0f}%). "
            "Your session composition varies a lot — consider sticking to a "
            "defined split for more predictable progress."
        )

    # Warn if legs are rarely a dedicated session
    legs_pct = label_counts.get("legs", 0) / total if total > 0 else 0
    if detected_split == "PPL" and legs_pct < 0.15:
        findings.append(
            "Leg sessions are underrepresented in your PPL split. "
            "Aim for roughly equal push, pull, and leg days."
        )

    # Warn about too many full-body sessions if PPL/Upper-Lower detected
    if detected_split in ("PPL", "Upper/Lower"):
        fb_count = label_counts.get("full_body", 0)
        if fb_count / total > 0.25:
            findings.append(
                f"{fb_count} full-body sessions detected alongside your {detected_split} split. "
                "Mixing splits can dilute training focus — consider staying consistent."
            )

    return SplitResult(
        detected_split=detected_split,
        adherence_score=adherence,
        session_breakdown=dict(label_counts),
        findings=findings,
        total_sessions=total,
    )
