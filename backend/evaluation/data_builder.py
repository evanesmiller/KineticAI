"""
evaluation/data_builder.py
--------------------------
Builds the structured workout summary dict that gets sent to Gemini
for evaluation. Keeps all DB querying out of the Gemini client so
the client stays pure (prompt + API call only).
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List

from constants import (
    BODYWEIGHT_NOMINAL_LBS,
    CORE_MUSCLES,
    FATIGUE_WINDOW_DAYS,
    INTENSITY_MULTIPLIERS,
    LEG_MUSCLES,
    PULL_MUSCLES,
    PUSH_MUSCLES,
)
from evaluation.split_detector import analyse_split


def build_evaluation_data(conn: sqlite3.Connection, user_id: int) -> dict:
    """
    Query the past 7 days of workouts and return a structured dict
    ready to be serialised into the Gemini prompt.

    Structure:
    {
        "evaluation_date": "2026-03-25",
        "window_days": 7,
        "total_workouts": int,
        "rest_days": int,
        "training_split": { "detected": str, "adherence_pct": float },
        "workouts": [
            {
                "date": "YYYY-MM-DD",
                "duration_mins": int,
                "intensity": str,
                "notes": str | null,
                "exercises": [
                    {
                        "name": str,
                        "muscle_group": str,
                        "sets": int,
                        "reps": int,
                        "weight_lbs": float,
                        "weighted_volume": float
                    }
                ],
                "muscle_groups_trained": [str, ...]
            }
        ],
        "muscle_volume_summary": {
            "<muscle>": {
                "weighted_volume": float,
                "sessions": int,
                "status": "red"|"yellow"|"green"
            }
        },
        "category_volumes": {
            "push": float,
            "pull": float,
            "legs": float,
            "core": float
        }
    }
    """
    today      = date.today()
    cutoff     = today - timedelta(days=FATIGUE_WINDOW_DAYS)
    cutoff_str = cutoff.isoformat()

    # ── Fetch workouts ─────────────────────────────────────────────────────
    workout_rows = conn.execute(
        """
        SELECT id, date, duration_mins, intensity, notes
        FROM   workouts
        WHERE  user_id = ? AND date >= ?
        ORDER  BY date
        """,
        (user_id, cutoff_str),
    ).fetchall()

    # ── Fetch exercises for those workouts ────────────────────────────────
    if not workout_rows:
        split = analyse_split(conn, user_id)
        return {
            "evaluation_date":      today.isoformat(),
            "window_days":          FATIGUE_WINDOW_DAYS,
            "total_workouts":       0,
            "rest_days":            FATIGUE_WINDOW_DAYS,
            "training_split":       {"detected": split.detected_split, "adherence_pct": split.adherence_score},
            "workouts":             [],
            "muscle_volume_summary": {},
            "category_volumes":     {"push": 0, "pull": 0, "legs": 0, "core": 0},
        }

    workout_ids = [w["id"] for w in workout_rows]
    ex_rows = conn.execute(
        f"""
        SELECT e.workout_id, e.name, e.sets, e.reps, e.weight_lbs,
               mg.name AS muscle, w.intensity
        FROM   exercises e
        JOIN   muscle_groups mg ON mg.id = e.muscle_group_id
        JOIN   workouts w       ON w.id  = e.workout_id
        WHERE  e.workout_id IN ({','.join('?'*len(workout_ids))})
        ORDER  BY e.id
        """,
        workout_ids,
    ).fetchall()

    # Group exercises by workout_id
    ex_by_workout: Dict[int, list] = defaultdict(list)
    for ex in ex_rows:
        mult   = INTENSITY_MULTIPLIERS.get(ex["intensity"], 1.0)
        eff_wt = ex["weight_lbs"] if ex["weight_lbs"] > 0 else BODYWEIGHT_NOMINAL_LBS
        vol    = ex["sets"] * ex["reps"] * eff_wt * mult
        ex_by_workout[ex["workout_id"]].append({
            "name":            ex["name"],
            "muscle_group":    ex["muscle"],
            "sets":            ex["sets"],
            "reps":            ex["reps"],
            "weight_lbs":      ex["weight_lbs"],
            "weighted_volume": round(vol, 1),
        })

    # ── Build workout list ─────────────────────────────────────────────────
    dates_worked = set()
    workouts_out = []
    muscle_volume:   Dict[str, float] = defaultdict(float)
    muscle_sessions: Dict[str, set]   = defaultdict(set)

    for w in workout_rows:
        wid      = w["id"]
        w_date   = w["date"]
        exercises = ex_by_workout.get(wid, [])
        muscles_this_workout = list({ex["muscle_group"] for ex in exercises})

        dates_worked.add(w_date)

        for ex in exercises:
            m = ex["muscle_group"]
            muscle_volume[m]    += ex["weighted_volume"]
            muscle_sessions[m].add(w_date)

        workouts_out.append({
            "date":                w_date,
            "duration_mins":       w["duration_mins"],
            "intensity":           w["intensity"],
            "notes":               w["notes"],
            "exercises":           exercises,
            "muscle_groups_trained": muscles_this_workout,
        })

    # ── Muscle volume summary with fatigue status ─────────────────────────
    from constants import RED_VOLUME_THRESHOLD, YELLOW_VOLUME_THRESHOLD, RED_SESSION_THRESHOLD, YELLOW_SESSION_THRESHOLD
    muscle_summary = {}
    for muscle, vol in muscle_volume.items():
        sessions = len(muscle_sessions[muscle])
        if vol >= RED_VOLUME_THRESHOLD or sessions >= RED_SESSION_THRESHOLD:
            status = "red"
        elif vol >= YELLOW_VOLUME_THRESHOLD or sessions >= YELLOW_SESSION_THRESHOLD:
            status = "yellow"
        else:
            status = "green"
        muscle_summary[muscle] = {
            "weighted_volume": round(vol, 1),
            "sessions":        sessions,
            "status":          status,
        }

    # ── Category volumes ───────────────────────────────────────────────────
    def _cat_vol(group):
        return round(sum(muscle_volume.get(m, 0) for m in group), 1)

    category_volumes = {
        "push": _cat_vol(PUSH_MUSCLES),
        "pull": _cat_vol(PULL_MUSCLES),
        "legs": _cat_vol(LEG_MUSCLES),
        "core": _cat_vol(CORE_MUSCLES),
    }

    rest_days = FATIGUE_WINDOW_DAYS - len(dates_worked)

    # ── Split detection (uses full history) ───────────────────────────────
    split = analyse_split(conn, user_id)

    return {
        "evaluation_date":       today.isoformat(),
        "window_days":           FATIGUE_WINDOW_DAYS,
        "total_workouts":        len(workouts_out),
        "rest_days":             rest_days,
        "training_split":        {
            "detected":      split.detected_split,
            "adherence_pct": split.adherence_score,
        },
        "workouts":              workouts_out,
        "muscle_volume_summary": muscle_summary,
        "category_volumes":      category_volumes,
    }
