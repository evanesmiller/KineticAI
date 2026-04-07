"""
routes/fatigue.py
-----------------
Muscle fatigue endpoints. These drive the 3D model highlight colors
on the frontend.

GET  /fatigue              — get highlight color map for all 15 muscles
POST /fatigue/refresh      — force a full cache rebuild (useful after bulk imports)
"""

from flask import Blueprint

from db.connection import get_db
from models import get_muscle_highlight_map, refresh_all_muscle_fatigue
from routes.utils import success, login_required

fatigue_bp = Blueprint("fatigue", __name__, url_prefix="/fatigue")


# ---------------------------------------------------------------------------
# GET /fatigue
# ---------------------------------------------------------------------------
@fatigue_bp.get("/")
@login_required
def highlight_map(user_id):
    """
    Return the current highlight color for every muscle group.
    This is the primary endpoint consumed by the 3D model frontend.

    Response 200:
        {
            "biceps":          "red",
            "triceps":         "yellow",
            "forearms":        "green",
            "chest":           "yellow",
            "abs":             "green",
            "front_delts":     "green",
            "side_delts":      "green",
            "rear_delts":      "green",
            "traps":           "yellow",
            "lats":            "yellow",
            "spinal_erectors": "green",
            "glutes":          "yellow",
            "hamstrings":      "yellow",
            "quads":           "red",
            "calves":          "yellow"
        }
    """
    db = get_db()
    muscle_map = get_muscle_highlight_map(db, user_id)
    return success(muscle_map)


# ---------------------------------------------------------------------------
# POST /fatigue/refresh
# ---------------------------------------------------------------------------
@fatigue_bp.post("/refresh")
@login_required
def force_refresh(user_id):
    """
    Trigger a full recompute of the fatigue cache for all 15 muscles.
    Normally the cache stays current automatically; this endpoint is
    useful after bulk data imports or manual DB edits.

    Response 200:
        { "message": "Fatigue cache refreshed.", "muscles_updated": 15 }
    """
    from constants import MUSCLE_GROUPS
    db = get_db()
    refresh_all_muscle_fatigue(db, user_id)
    db.commit()
    return success({
        "message":         "Fatigue cache refreshed.",
        "muscles_updated": len(MUSCLE_GROUPS),
    })
