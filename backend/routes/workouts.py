"""
routes/workouts.py
------------------
Workout CRUD endpoints. All routes require authentication.

POST   /workouts          — log a new workout session
GET    /workouts          — list all workouts for the logged-in user
GET    /workouts/<id>     — get a single workout with its exercises
DELETE /workouts/<id>     — delete a workout
"""

from datetime import date as date_type
from flask import Blueprint, request

from db.connection import get_db
from models import Exercise, Workout, insert_workout, get_workout, get_workouts_for_user, delete_workout
from routes.utils import success, error, login_required

workouts_bp = Blueprint("workouts", __name__, url_prefix="/workouts")


def _serialize_exercise(ex: Exercise) -> dict:
    return {
        "id":           ex.id,
        "name":         ex.name,
        "muscle_group": ex.muscle_group,
        "sets":         ex.sets,
        "reps":         ex.reps,
        "weight_lbs":   ex.weight_lbs,
    }


def _serialize_workout(w: Workout) -> dict:
    return {
        "id":            w.id,
        "date":          w.date.isoformat(),
        "duration_mins": w.duration_mins,
        "intensity":     w.intensity,
        "notes":         w.notes,
        "exercises":     [_serialize_exercise(ex) for ex in w.exercises],
        "muscle_groups": w.targeted_muscle_groups,
    }


# ---------------------------------------------------------------------------
# POST /workouts
# ---------------------------------------------------------------------------
@workouts_bp.post("/")
@login_required
def create_workout(user_id):
    """
    Log a new workout with one or more exercises.

    Request JSON:
        {
            "date":          "2026-03-25",      # optional, defaults to today
            "duration_mins": 60,
            "intensity":     "high",
            "notes":         "Felt strong",     # optional
            "exercises": [
                {
                    "name":         "Barbell Squat",
                    "muscle_group": "quads",
                    "sets":         4,
                    "reps":         6,
                    "weight_lbs":   205
                }
            ]
        }

    Response 201:
        { serialized workout }
    """
    data = request.get_json(silent=True) or {}

    # ── Validate top-level fields ──────────────────────────────────────────
    duration_mins = data.get("duration_mins")
    intensity     = data.get("intensity")
    raw_date      = data.get("date")

    if not duration_mins:
        return error("duration_mins is required.")
    if not intensity:
        return error("intensity is required.")

    try:
        duration_mins = int(duration_mins)
        if duration_mins <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return error("duration_mins must be a positive integer.")

    try:
        workout_date = date_type.fromisoformat(raw_date) if raw_date else date_type.today()
    except ValueError:
        return error("date must be in YYYY-MM-DD format.")

    # ── Validate exercises list ────────────────────────────────────────────
    raw_exercises = data.get("exercises")
    if not raw_exercises or not isinstance(raw_exercises, list):
        return error("exercises must be a non-empty list.")

    exercises = []
    for i, ex in enumerate(raw_exercises):
        missing = [f for f in ("name", "muscle_group", "sets", "reps", "weight_lbs") if f not in ex]
        if missing:
            return error(f"Exercise {i}: missing fields: {missing}")
        try:
            exercises.append(Exercise(
                name=str(ex["name"]).strip(),
                muscle_group=str(ex["muscle_group"]).strip(),
                sets=int(ex["sets"]),
                reps=int(ex["reps"]),
                weight_lbs=float(ex["weight_lbs"]),
            ))
        except ValueError as e:
            return error(f"Exercise {i}: {e}")

    # ── Persist ────────────────────────────────────────────────────────────
    workout = Workout(
        user_id=user_id,
        date=workout_date,
        duration_mins=duration_mins,
        intensity=intensity,
        exercises=exercises,
        notes=data.get("notes"),
    )

    try:
        db = get_db()
        insert_workout(db, workout)
    except ValueError as e:
        return error(str(e))

    return success(_serialize_workout(workout), 201)


# ---------------------------------------------------------------------------
# GET /workouts
# ---------------------------------------------------------------------------
@workouts_bp.get("/")
@login_required
def list_workouts(user_id):
    """
    Return all workouts for the logged-in user.

    Optional query params:
        ?start=YYYY-MM-DD
        ?end=YYYY-MM-DD

    Response 200:
        [ { serialized workout }, ... ]
    """
    start_str = request.args.get("start")
    end_str   = request.args.get("end")

    start_date = end_date = None
    try:
        if start_str:
            start_date = date_type.fromisoformat(start_str)
        if end_str:
            end_date = date_type.fromisoformat(end_str)
    except ValueError:
        return error("start and end must be in YYYY-MM-DD format.")

    db = get_db()
    workouts = get_workouts_for_user(db, user_id, start_date, end_date)
    return success([_serialize_workout(w) for w in workouts])


# ---------------------------------------------------------------------------
# GET /workouts/<workout_id>
# ---------------------------------------------------------------------------
@workouts_bp.get("/<int:workout_id>")
@login_required
def get_single_workout(user_id, workout_id):
    """
    Return a single workout by ID.
    Returns 404 if it doesn't exist or belongs to another user.
    """
    db = get_db()
    workout = get_workout(db, workout_id)

    if workout is None or workout.user_id != user_id:
        return error("Workout not found.", 404)

    return success(_serialize_workout(workout))


# ---------------------------------------------------------------------------
# DELETE /workouts/<workout_id>
# ---------------------------------------------------------------------------
@workouts_bp.delete("/<int:workout_id>")
@login_required
def remove_workout(user_id, workout_id):
    """
    Delete a workout and cascade to its exercises.
    Also refreshes the muscle fatigue cache for affected muscles.
    """
    db = get_db()
    deleted = delete_workout(db, workout_id, user_id)

    if not deleted:
        return error("Workout not found.", 404)

    return success({"message": f"Workout {workout_id} deleted."})
