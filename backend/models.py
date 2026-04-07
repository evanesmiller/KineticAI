"""
models.py
---------
Dataclass definitions for Exercise and Workout, plus the database
operations that persist them and keep muscle_fatigue_cache in sync.

All public functions accept a sqlite3.Connection so they can participate
in a caller-managed transaction — important for the workout + exercises +
fatigue update sequence that must succeed or fail atomically.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

from constants import (
    BODYWEIGHT_NOMINAL_LBS,
    FATIGUE_WINDOW_DAYS,
    INTENSITY_MULTIPLIERS,
    MUSCLE_GROUPS,
    RED_SESSION_THRESHOLD,
    RED_VOLUME_THRESHOLD,
    SECONDARY_FATIGUE_MULTIPLIER,
    YELLOW_SESSION_THRESHOLD,
    YELLOW_VOLUME_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Exercise:
    """
    A single exercise performed during a workout session.

    Attributes:
        name            : Human-readable exercise name (e.g. 'Barbell Squat').
        muscle_group    : Must match a name in the muscle_groups table.
        sets            : Number of sets performed.
        reps            : Number of repetitions per set.
        weight_lbs      : Load in pounds; use 0.0 for bodyweight exercises.
        id              : Populated after the record is inserted into the DB.
    """
    name:           str
    muscle_group:   str
    sets:           int
    reps:           int
    weight_lbs:     float
    id:             Optional[int] = field(default=None, repr=False)

    def __post_init__(self):
        if self.sets <= 0:
            raise ValueError("sets must be > 0")
        if self.reps <= 0:
            raise ValueError("reps must be > 0")
        if self.weight_lbs < 0:
            raise ValueError("weight_lbs must be >= 0")
        if self.muscle_group not in MUSCLE_GROUPS:
            raise ValueError(
                f"'{self.muscle_group}' is not a recognised muscle group. "
                f"Valid options: {MUSCLE_GROUPS}"
            )

    @property
    def effective_weight(self) -> float:
        """Returns BODYWEIGHT_NOMINAL_LBS when weight is 0 (bodyweight move)."""
        return self.weight_lbs if self.weight_lbs > 0 else BODYWEIGHT_NOMINAL_LBS

    @property
    def volume(self) -> float:
        """Raw volume: sets × reps × effective_weight."""
        return self.sets * self.reps * self.effective_weight


@dataclass
class Workout:
    """
    A single training session composed of one or more exercises.

    Attributes:
        user_id         : FK to users table.
        date            : Calendar date of the session (YYYY-MM-DD).
        duration_mins   : Session length in minutes.
        intensity       : 'low' | 'moderate' | 'high'.
        exercises       : List of Exercise objects performed in this session.
        notes           : Optional free-text notes.
        id              : Populated after the record is inserted into the DB.
    """
    user_id:        int
    date:           date
    duration_mins:  int
    intensity:      str
    exercises:      List[Exercise] = field(default_factory=list)
    notes:          Optional[str] = None
    id:             Optional[int] = field(default=None, repr=False)

    def __post_init__(self):
        if self.duration_mins <= 0:
            raise ValueError("duration_mins must be > 0")
        if self.intensity not in INTENSITY_MULTIPLIERS:
            raise ValueError(
                f"intensity must be one of {list(INTENSITY_MULTIPLIERS.keys())}"
            )

    @property
    def targeted_muscle_groups(self) -> List[str]:
        """Deduplicated list of muscle groups trained in this workout."""
        return list({ex.muscle_group for ex in self.exercises})


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_muscle_group_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM muscle_groups WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Muscle group '{name}' not found in database.")
    return row["id"]


# ---------------------------------------------------------------------------
# Core CRUD — Workout
# ---------------------------------------------------------------------------

def insert_workout(conn: sqlite3.Connection, workout: Workout) -> int:
    """
    Persist a Workout and all its Exercises in one atomic transaction.
    Also refreshes the muscle_fatigue_cache for every muscle group
    touched by this workout.

    Returns the newly created workout_id.
    """
    with conn:  # begins a transaction; commits on exit, rolls back on exception
        # 1. Insert the workout row
        cur = conn.execute(
            """
            INSERT INTO workouts (user_id, date, duration_mins, intensity, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                workout.user_id,
                workout.date.isoformat(),
                workout.duration_mins,
                workout.intensity,
                workout.notes,
            ),
        )
        workout_id = cur.lastrowid
        workout.id = workout_id

        # 2. Insert exercises and populate workout_muscle_groups junction table
        touched_muscles = set()
        for exercise in workout.exercises:
            mg_id = _get_muscle_group_id(conn, exercise.muscle_group)

            ex_cur = conn.execute(
                """
                INSERT INTO exercises
                    (workout_id, muscle_group_id, name, sets, reps, weight_lbs)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    workout_id,
                    mg_id,
                    exercise.name,
                    exercise.sets,
                    exercise.reps,
                    exercise.weight_lbs,
                ),
            )
            exercise.id = ex_cur.lastrowid
            touched_muscles.add(exercise.muscle_group)

        # 3. Upsert workout_muscle_groups junction rows
        for muscle in touched_muscles:
            mg_id = _get_muscle_group_id(conn, muscle)
            conn.execute(
                """
                INSERT OR IGNORE INTO workout_muscle_groups (workout_id, muscle_group_id)
                VALUES (?, ?)
                """,
                (workout_id, mg_id),
            )

        # 4. Refresh fatigue cache for every muscle touched by this workout
        for muscle in touched_muscles:
            refresh_muscle_fatigue(conn, workout.user_id, muscle)

    return workout_id


def get_workout(conn: sqlite3.Connection, workout_id: int) -> Optional[Workout]:
    """Fetch a single workout and its exercises by workout_id."""
    row = conn.execute(
        "SELECT * FROM workouts WHERE id = ?", (workout_id,)
    ).fetchone()
    if row is None:
        return None

    exercises = _fetch_exercises_for_workout(conn, workout_id)
    return Workout(
        id=row["id"],
        user_id=row["user_id"],
        date=date.fromisoformat(row["date"]),
        duration_mins=row["duration_mins"],
        intensity=row["intensity"],
        notes=row["notes"],
        exercises=exercises,
    )


def get_workouts_for_user(
    conn: sqlite3.Connection,
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Workout]:
    """
    Return all workouts for a user, optionally filtered to a date range.
    Results are ordered newest-first.
    """
    query = "SELECT * FROM workouts WHERE user_id = ?"
    params: list = [user_id]

    if start_date:
        query += " AND date >= ?"
        params.append(start_date.isoformat())
    if end_date:
        query += " AND date <= ?"
        params.append(end_date.isoformat())

    query += " ORDER BY date DESC"

    rows = conn.execute(query, params).fetchall()
    return [
        Workout(
            id=row["id"],
            user_id=row["user_id"],
            date=date.fromisoformat(row["date"]),
            duration_mins=row["duration_mins"],
            intensity=row["intensity"],
            notes=row["notes"],
            exercises=_fetch_exercises_for_workout(conn, row["id"]),
        )
        for row in rows
    ]


def delete_workout(conn: sqlite3.Connection, workout_id: int, user_id: int) -> bool:
    """
    Delete a workout (cascades to exercises + workout_muscle_groups).
    Refreshes the fatigue cache for all muscles that were part of the session.
    Returns True if a row was deleted.
    """
    # Capture which muscles were affected before deletion
    muscle_rows = conn.execute(
        """
        SELECT mg.name
        FROM workout_muscle_groups wmg
        JOIN muscle_groups mg ON mg.id = wmg.muscle_group_id
        WHERE wmg.workout_id = ?
        """,
        (workout_id,),
    ).fetchall()
    touched_muscles = [r["name"] for r in muscle_rows]

    with conn:
        cur = conn.execute(
            "DELETE FROM workouts WHERE id = ? AND user_id = ?",
            (workout_id, user_id),
        )
        deleted = cur.rowcount > 0

        if deleted:
            for muscle in touched_muscles:
                refresh_muscle_fatigue(conn, user_id, muscle)

    return deleted


# ---------------------------------------------------------------------------
# Exercise helpers
# ---------------------------------------------------------------------------

def _fetch_exercises_for_workout(
    conn: sqlite3.Connection, workout_id: int
) -> List[Exercise]:
    rows = conn.execute(
        """
        SELECT e.id, e.name, e.sets, e.reps, e.weight_lbs, mg.name AS muscle_group
        FROM exercises e
        JOIN muscle_groups mg ON mg.id = e.muscle_group_id
        WHERE e.workout_id = ?
        ORDER BY e.id
        """,
        (workout_id,),
    ).fetchall()
    return [
        Exercise(
            id=row["id"],
            name=row["name"],
            muscle_group=row["muscle_group"],
            sets=row["sets"],
            reps=row["reps"],
            weight_lbs=row["weight_lbs"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Fatigue cache
# ---------------------------------------------------------------------------

def refresh_muscle_fatigue(
    conn: sqlite3.Connection, user_id: int, muscle_group: str
) -> None:
    """
    Recompute the rolling 7-day fatigue score for one muscle group and
    upsert the result into muscle_fatigue_cache.

    Called automatically by insert_workout() and delete_workout().
    Can also be called manually to force a cache refresh.
    """
    mg_id = _get_muscle_group_id(conn, muscle_group)
    cutoff = (date.today() - timedelta(days=FATIGUE_WINDOW_DAYS)).isoformat()

    # Aggregate volume and session count for this muscle over the past 7 days.
    # Secondary exercises (name ends with " (secondary)") are discounted by
    # SECONDARY_FATIGUE_MULTIPLIER and excluded from the session count so they
    # don't drive the muscle to yellow/red on their own.
    agg = conn.execute(
        """
        SELECT
            COUNT(DISTINCT CASE
                WHEN e.name NOT LIKE '%(secondary)'
                THEN w.id END)                          AS weekly_sessions,
            COALESCE(SUM(
                e.sets * e.reps *
                CASE WHEN e.weight_lbs > 0 THEN e.weight_lbs
                     ELSE :bw END *
                CASE w.intensity
                    WHEN 'low'      THEN :low
                    WHEN 'moderate' THEN :mod
                    WHEN 'high'     THEN :high
                    ELSE 1.0 END *
                CASE WHEN e.name LIKE '%(secondary)'
                     THEN :sec ELSE 1.0 END
            ), 0.0)                                     AS weekly_volume
        FROM workouts w
        JOIN exercises e ON e.workout_id = w.id
        WHERE w.user_id        = :user_id
          AND e.muscle_group_id = :mg_id
          AND w.date            >= :cutoff
        """,
        {
            "user_id": user_id,
            "mg_id":   mg_id,
            "cutoff":  cutoff,
            "bw":      BODYWEIGHT_NOMINAL_LBS,
            "low":     INTENSITY_MULTIPLIERS["low"],
            "mod":     INTENSITY_MULTIPLIERS["moderate"],
            "high":    INTENSITY_MULTIPLIERS["high"],
            "sec":     SECONDARY_FATIGUE_MULTIPLIER,
        },
    ).fetchone()

    weekly_volume   = agg["weekly_volume"]
    weekly_sessions = agg["weekly_sessions"]

    # Determine highlight color
    if (weekly_volume >= RED_VOLUME_THRESHOLD or
            weekly_sessions >= RED_SESSION_THRESHOLD):
        color = "red"
    elif (weekly_volume >= YELLOW_VOLUME_THRESHOLD or
          weekly_sessions >= YELLOW_SESSION_THRESHOLD):
        color = "yellow"
    else:
        color = "green"

    conn.execute(
        """
        INSERT INTO muscle_fatigue_cache
            (user_id, muscle_group_id, weekly_volume, weekly_sessions, highlight_color, last_updated)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, muscle_group_id) DO UPDATE SET
            weekly_volume   = excluded.weekly_volume,
            weekly_sessions = excluded.weekly_sessions,
            highlight_color = excluded.highlight_color,
            last_updated    = excluded.last_updated
        """,
        (user_id, mg_id, weekly_volume, weekly_sessions, color),
    )


def get_muscle_highlight_map(
    conn: sqlite3.Connection, user_id: int
) -> dict[str, str]:
    """
    Return a dict mapping every canonical muscle group name to its
    current highlight color: 'red' | 'yellow' | 'green'.

    Muscles with no cache entry yet default to 'green' (unworked).
    This is the primary function the 3D model frontend will call.

    Example return value:
        {
            'biceps':         'red',
            'triceps':        'yellow',
            'forearms':       'green',
            ...
        }
    """
    rows = conn.execute(
        """
        SELECT mg.name, COALESCE(mfc.highlight_color, 'green') AS highlight_color
        FROM muscle_groups mg
        LEFT JOIN muscle_fatigue_cache mfc
               ON mfc.muscle_group_id = mg.id
              AND mfc.user_id = ?
        """,
        (user_id,),
    ).fetchall()
    return {row["name"]: row["highlight_color"] for row in rows}


def refresh_all_muscle_fatigue(conn: sqlite3.Connection, user_id: int) -> None:
    """
    Full cache rebuild for all 15 muscle groups.
    Useful on app startup or after bulk imports.
    """
    for muscle in MUSCLE_GROUPS:
        refresh_muscle_fatigue(conn, user_id, muscle)
