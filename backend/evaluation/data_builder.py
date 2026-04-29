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
from evaluation.progressive_overload import analyse_overload


def _build_consistency_data(conn: sqlite3.Connection, user_id: int) -> dict:
    """
    Build historical consistency metrics used by the Consistency scoring category.

    Returns a dict containing:
      weeks_tracked                 — completed ISO weeks since first workout
      weeks_active                  — weeks with ≥1 session
      weeks_missing                 — weeks with 0 sessions
      max_consecutive_missing_weeks — longest streak of absent weeks
      missing_weeks_before_current  — gap (in weeks) immediately before this week
      avg_weekly_sessions           — mean sessions per week across all past weeks
      current_week_sessions         — sessions logged in the current ISO week
      overload_summary              — progressive overload trend lists per muscle
    """
    today = date.today()

    all_workout_dates = conn.execute(
        "SELECT date FROM workouts WHERE user_id = ? ORDER BY date",
        (user_id,),
    ).fetchall()

    empty = {
        "weeks_tracked": 0,
        "weeks_active": 0,
        "weeks_missing": 0,
        "max_consecutive_missing_weeks": 0,
        "missing_weeks_before_current": 0,
        "avg_weekly_sessions": 0.0,
        "current_week_sessions": 0,
        "overload_summary": {"progressing": [], "stagnating": [], "regressing": []},
    }
    if not all_workout_dates:
        return empty

    def _week_start(d: date) -> date:
        return d - timedelta(days=d.weekday())

    current_week = _week_start(today)
    first_week   = _week_start(date.fromisoformat(all_workout_dates[0]["date"]))

    # Per-week session counts
    week_sessions: dict[date, int] = defaultdict(int)
    for row in all_workout_dates:
        week_sessions[_week_start(date.fromisoformat(row["date"]))] += 1

    # Completed past weeks only (exclude the current in-progress week)
    past_weeks: list[date] = []
    w = first_week
    while w < current_week:
        past_weeks.append(w)
        w += timedelta(weeks=1)

    weeks_tracked = len(past_weeks)
    weeks_active  = sum(1 for w in past_weeks if week_sessions[w] > 0)
    weeks_missing = weeks_tracked - weeks_active

    # Longest consecutive missing-week streak
    max_missing_streak = streak = 0
    for w in past_weeks:
        if week_sessions[w] == 0:
            streak += 1
            max_missing_streak = max(max_missing_streak, streak)
        else:
            streak = 0

    # Missing weeks immediately before the current week (recent gap)
    missing_before_current = 0
    for w in reversed(past_weeks):
        if week_sessions[w] == 0:
            missing_before_current += 1
        else:
            break

    avg_weekly = (
        round(sum(week_sessions[w] for w in past_weeks) / weeks_tracked, 1)
        if weeks_tracked > 0 else 0.0
    )

    current_week_sessions = week_sessions.get(current_week, 0)

    # Reuse existing progressive overload analyser for trend data
    overload = analyse_overload(conn, user_id)
    overload_summary = {
        "progressing": [s.muscle for s in overload.statuses if s.trend == "progressing"],
        "stagnating":  [s.muscle for s in overload.statuses if s.trend == "stagnating"],
        "regressing":  [s.muscle for s in overload.statuses if s.trend == "regressing"],
        "new":         [s.muscle for s in overload.statuses if s.trend == "new"],
    }

    return {
        "weeks_tracked":                weeks_tracked,
        "weeks_active":                 weeks_active,
        "weeks_missing":                weeks_missing,
        "max_consecutive_missing_weeks": max_missing_streak,
        "missing_weeks_before_current": missing_before_current,
        "avg_weekly_sessions":          avg_weekly,
        "current_week_sessions":        current_week_sessions,
        "overload_summary":             overload_summary,
    }


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

    # ── Fetch user profile ─────────────────────────────────────────────────
    profile_row = conn.execute(
        "SELECT body_weight_lbs, height_in FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    body_weight = (
        float(profile_row["body_weight_lbs"])
        if profile_row and profile_row["body_weight_lbs"]
        else BODYWEIGHT_NOMINAL_LBS
    )
    height_in = (
        float(profile_row["height_in"])
        if profile_row and profile_row["height_in"]
        else None
    )

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
            "consistency_history":  _build_consistency_data(conn, user_id),
            "user_profile":         {
                "body_weight_lbs": profile_row["body_weight_lbs"] if profile_row else None,
                "height_in":       height_in,
                "notable_lifts":   [],
            },
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

    # Group exercises by workout_id; also track peak weight per exercise name
    # for the notable lifts summary sent to Gemini.
    ex_by_workout: Dict[int, list] = defaultdict(list)
    peak_by_exercise: Dict[str, dict] = {}   # name -> {weight_lbs, muscle}

    for ex in ex_rows:
        mult   = INTENSITY_MULTIPLIERS.get(ex["intensity"], 1.0)
        eff_wt = ex["weight_lbs"] if ex["weight_lbs"] > 0 else body_weight
        vol    = ex["sets"] * ex["reps"] * eff_wt * mult
        ex_by_workout[ex["workout_id"]].append({
            "name":            ex["name"],
            "muscle_group":    ex["muscle"],
            "sets":            ex["sets"],
            "reps":            ex["reps"],
            "weight_lbs":      ex["weight_lbs"],
            "weighted_volume": round(vol, 1),
        })
        # Track peak weight for loaded exercises only (skip bodyweight entries)
        if ex["weight_lbs"] > 0:
            prev = peak_by_exercise.get(ex["name"])
            if prev is None or ex["weight_lbs"] > prev["weight_lbs"]:
                peak_by_exercise[ex["name"]] = {
                    "weight_lbs": ex["weight_lbs"],
                    "muscle":     ex["muscle"],
                }

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
    bw_scale         = body_weight / 150.0
    effective_red    = RED_VOLUME_THRESHOLD    * bw_scale
    effective_yellow = YELLOW_VOLUME_THRESHOLD * bw_scale

    muscle_summary = {}
    for muscle, vol in muscle_volume.items():
        sessions = len(muscle_sessions[muscle])
        if vol >= effective_red or sessions >= RED_SESSION_THRESHOLD:
            status = "red"
        elif vol >= effective_yellow or sessions >= YELLOW_SESSION_THRESHOLD:
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

    # ── User profile + notable lifts ───────────────────────────────────────
    # Notable lifts: all loaded exercises sorted by body-weight ratio (highest
    # first). Gives Gemini the context to make relative-strength observations.
    user_bw = profile_row["body_weight_lbs"] if profile_row else None
    notable_lifts = []
    if user_bw:
        for name, info in peak_by_exercise.items():
            bw_ratio = round(info["weight_lbs"] / user_bw, 2)
            notable_lifts.append({
                "exercise":         name,
                "muscle":           info["muscle"],
                "peak_weight_lbs":  info["weight_lbs"],
                "bw_ratio":         bw_ratio,
                "exceeds_bodyweight": info["weight_lbs"] >= user_bw,
            })
        notable_lifts.sort(key=lambda x: x["bw_ratio"], reverse=True)

    user_profile = {
        "body_weight_lbs": user_bw,
        "height_in":       height_in,
        "notable_lifts":   notable_lifts[:10],
    }

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
        "consistency_history":   _build_consistency_data(conn, user_id),
        "user_profile":          user_profile,
    }
