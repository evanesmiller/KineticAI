"""
routes/evaluation.py
--------------------
GET  /evaluation/   — Gemini-powered workout evaluation (cached per workout set)
"""

import json
from datetime import date, timedelta

from flask import Blueprint, request
from db.connection import get_db
from evaluation.data_builder import build_evaluation_data
from gemini.client import evaluate_workouts
from routes.utils import success, error, login_required
from constants import FATIGUE_WINDOW_DAYS

evaluation_bp = Blueprint("evaluation", __name__, url_prefix="/evaluation")

# Increment this whenever the Gemini prompt logic changes so existing
# caches are automatically invalidated on the next request.
PROMPT_VERSION = 7


def _window_fingerprint(db, user_id: int) -> str:
    """
    Returns a string that uniquely identifies the current set of workouts
    in the 7-day window AND the prompt version.
    Changes whenever a workout is added/deleted, the prompt is updated,
    or the user's body weight changes (since that affects the Gemini narrative).
    Format: "v<version>:<max_id>:<count>:bw<body_weight>"
    """
    cutoff = (date.today() - timedelta(days=FATIGUE_WINDOW_DAYS)).isoformat()
    row = db.execute(
        "SELECT COALESCE(MAX(id), 0) as max_id, COUNT(*) as cnt "
        "FROM workouts WHERE user_id = ? AND date >= ?",
        (user_id, cutoff),
    ).fetchone()
    # Include all-time count so consistency score re-evaluates when any historical
    # workout is added or removed, not just those in the current 7-day window.
    all_time = db.execute(
        "SELECT COUNT(*) as total FROM workouts WHERE user_id = ?", (user_id,)
    ).fetchone()
    profile = db.execute(
        "SELECT body_weight_lbs FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    bw = profile["body_weight_lbs"] if profile and profile["body_weight_lbs"] else "none"
    return f"v{PROMPT_VERSION}:{row['max_id']}:{row['cnt']}:all{all_time['total']}:bw{bw}"


@evaluation_bp.get("/")
@login_required
def get_evaluation(user_id):
    """
    Return the Gemini evaluation for the user's past 7 days.
    Serves a cached result if the workout set hasn't changed since
    the last evaluation, avoiding unnecessary Gemini API calls.
    """
    db = get_db()

    user = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        return error("User not found.", 404)

    fingerprint = _window_fingerprint(db, user_id)

    # Return cached result if the workout set is unchanged (skip if ?force=1)
    force = request.args.get("force") == "1"
    cached = db.execute(
        "SELECT fingerprint, result_json FROM evaluation_cache WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if not force and cached and cached["fingerprint"] == fingerprint:
        return success(json.loads(cached["result_json"]))

    # Workout set has changed — call Gemini and update the cache
    try:
        workout_data = build_evaluation_data(db, user_id)
        result       = evaluate_workouts(workout_data)
    except EnvironmentError as e:
        return error(str(e), 503)
    except Exception as e:
        return error(f"Evaluation failed: {str(e)}", 500)

    result["evaluation_date"] = workout_data["evaluation_date"]
    result["window_days"]     = workout_data["window_days"]

    db.execute(
        """
        INSERT INTO evaluation_cache (user_id, fingerprint, result_json, cached_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            fingerprint = excluded.fingerprint,
            result_json = excluded.result_json,
            cached_at   = excluded.cached_at
        """,
        (user_id, fingerprint, json.dumps(result)),
    )
    db.commit()

    return success(result)