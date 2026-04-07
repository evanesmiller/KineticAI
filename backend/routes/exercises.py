"""
routes/exercises.py
-------------------
Exercise read endpoints. Exercises are created as part of a workout
(POST /workouts) so there is no standalone create route here.

GET /workouts/<workout_id>/exercises          — list all exercises for a workout
GET /workouts/<workout_id>/exercises/<ex_id>  — get a single exercise
"""

from flask import Blueprint

from db.connection import get_db
from routes.utils import success, error, login_required

exercises_bp = Blueprint("exercises", __name__)


def _serialize(row) -> dict:
    return {
        "id":           row["id"],
        "workout_id":   row["workout_id"],
        "name":         row["name"],
        "muscle_group": row["muscle_group"],
        "sets":         row["sets"],
        "reps":         row["reps"],
        "weight_lbs":   row["weight_lbs"],
    }


def _assert_workout_owned(db, workout_id: int, user_id: int) -> bool:
    """Return True if the workout exists and belongs to user_id."""
    row = db.execute(
        "SELECT id FROM workouts WHERE id = ? AND user_id = ?",
        (workout_id, user_id),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# GET /workouts/<workout_id>/exercises
# ---------------------------------------------------------------------------
@exercises_bp.get("/workouts/<int:workout_id>/exercises")
@login_required
def list_exercises(user_id, workout_id):
    """
    Return all exercises for a given workout.

    Response 200:
        [ { id, workout_id, name, muscle_group, sets, reps, weight_lbs }, ... ]
    """
    db = get_db()

    if not _assert_workout_owned(db, workout_id, user_id):
        return error("Workout not found.", 404)

    rows = db.execute(
        """
        SELECT e.id, e.workout_id, e.name, e.sets, e.reps, e.weight_lbs,
               mg.name AS muscle_group
        FROM exercises e
        JOIN muscle_groups mg ON mg.id = e.muscle_group_id
        WHERE e.workout_id = ?
        ORDER BY e.id
        """,
        (workout_id,),
    ).fetchall()

    return success([_serialize(r) for r in rows])


# ---------------------------------------------------------------------------
# GET /workouts/<workout_id>/exercises/<exercise_id>
# ---------------------------------------------------------------------------
@exercises_bp.get("/workouts/<int:workout_id>/exercises/<int:exercise_id>")
@login_required
def get_exercise(user_id, workout_id, exercise_id):
    """Return a single exercise by ID."""
    db = get_db()

    if not _assert_workout_owned(db, workout_id, user_id):
        return error("Workout not found.", 404)

    row = db.execute(
        """
        SELECT e.id, e.workout_id, e.name, e.sets, e.reps, e.weight_lbs,
               mg.name AS muscle_group
        FROM exercises e
        JOIN muscle_groups mg ON mg.id = e.muscle_group_id
        WHERE e.workout_id = ? AND e.id = ?
        """,
        (workout_id, exercise_id),
    ).fetchone()

    if row is None:
        return error("Exercise not found.", 404)

    return success(_serialize(row))
