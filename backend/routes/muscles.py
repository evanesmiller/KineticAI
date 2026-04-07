"""
routes/muscles.py
-----------------
POST /api/detect-muscles   — Gemini-powered exercise → muscle group detection

Used by the Log Workout frontend when the user clicks "Detect Exercise".
Checks the user's own workout history first before calling Gemini.
"""

from flask import Blueprint, request
from db.connection import get_db
from gemini.client import detect_muscles
from routes.utils import success, error, login_required

muscles_bp = Blueprint("muscles", __name__, url_prefix="/api")


def _lookup_from_history(db, user_id: int, exercise_name: str):
    """
    Search the user's own workout history for a matching exercise name
    (case-insensitive). Returns a detect_muscles-style dict if found,
    or None if the exercise has never been logged by this user.

    Name variants stored in the DB:
      - "Barbell Squat"            → primary (no suffix)
      - "Barbell Squat (primary)"  → additional primary
      - "Barbell Squat (secondary)"→ secondary
    """
    base = exercise_name.lower().strip()

    rows = db.execute(
        """
        SELECT e.name, mg.name AS muscle_group
        FROM exercises e
        JOIN workouts w ON w.id = e.workout_id
        JOIN muscle_groups mg ON mg.id = e.muscle_group_id
        WHERE w.user_id = ?
          AND (
              LOWER(e.name) = ?
              OR LOWER(e.name) = ? || ' (primary)'
              OR LOWER(e.name) = ? || ' (secondary)'
          )
        """,
        (user_id, base, base, base),
    ).fetchall()

    if not rows:
        return None

    seen = {}
    for row in rows:
        name_lower = row["name"].lower()
        muscle = row["muscle_group"]
        if name_lower.endswith(" (secondary)"):
            intensity = "secondary"
        else:
            intensity = "primary"
        if muscle not in seen:
            seen[muscle] = intensity

    muscles = [{"muscle": m, "intensity": i} for m, i in seen.items()]
    return {"exercise": exercise_name, "muscles": muscles, "source": "history"}


@muscles_bp.post("/detect-muscles")
@login_required
def detect(user_id):
    """
    Detect which muscles an exercise targets using Gemini.

    Request JSON:
        { "exercise_name": "Barbell Squat" }

    Response 200:
        {
            "exercise": "Barbell Squat",
            "muscles": [
                { "muscle": "quads",           "intensity": "primary"   },
                { "muscle": "glutes",          "intensity": "primary"   },
                { "muscle": "hamstrings",      "intensity": "secondary" },
                { "muscle": "spinal_erectors", "intensity": "secondary" },
                { "muscle": "calves",          "intensity": "secondary" },
                { "muscle": "abs",             "intensity": "secondary" }
            ]
        }

    intensity levels:
        primary   — main mover, sets the exercise's muscle_group in the DB
        secondary — significantly activated
    """
    data          = request.get_json(silent=True) or {}
    exercise_name = (data.get("exercise_name") or "").strip()

    if not exercise_name:
        return error("exercise_name is required.")
    if len(exercise_name) > 100:
        return error("exercise_name is too long (max 100 characters).")

    db = get_db()
    cached = _lookup_from_history(db, user_id, exercise_name)
    if cached:
        return success(cached)

    try:
        result = detect_muscles(exercise_name)
    except EnvironmentError as e:
        return error(str(e), 503)
    except ValueError as e:
        return error(str(e), 422)
    except Exception as e:
        return error(f"Muscle detection failed: {str(e)}", 500)

    return success(result)
