"""
routes/auth.py
--------------
Authentication endpoints.

POST /auth/register         — create a new account
POST /auth/login            — start a session
POST /auth/logout           — end the session
GET  /auth/me               — return the currently logged-in user
GET  /auth/profile          — return profile fields (weight, height)
PUT  /auth/profile          — update profile fields (weight, height)
POST /auth/change-password  — change password (requires current password)
"""

from flask import Blueprint, request, session
from werkzeug.security import generate_password_hash, check_password_hash

from db.connection import get_db
from routes.utils import success, error, login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------
@auth_bp.post("/register")
def register():
    """
    Create a new user account.

    Request JSON:
        { "username": "evan", "password": "secret123" }

    Response 201:
        { "id": 1, "username": "evan" }
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username:
        return error("username is required.")
    if not password:
        return error("password is required.")
    if len(password) < 6:
        return error("password must be at least 6 characters.")

    # Body weight and height are required at registration so the evaluation
    # engine always has accurate values for volume and fatigue thresholds.
    body_weight_lbs = data.get("body_weight_lbs")
    height_in       = data.get("height_in")

    if body_weight_lbs is None:
        return error("body_weight_lbs is required.")
    if height_in is None:
        return error("height_in is required.")

    try:
        body_weight_lbs = float(body_weight_lbs)
        if body_weight_lbs <= 0:
            return error("body_weight_lbs must be a positive number.")
    except (TypeError, ValueError):
        return error("body_weight_lbs must be a number.")

    try:
        height_in = float(height_in)
        if height_in <= 0:
            return error("height_in must be a positive number.")
    except (TypeError, ValueError):
        return error("height_in must be a number.")

    db = get_db()

    # Check for duplicate username
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        return error("Username already taken.", 409)

    password_hash = generate_password_hash(password)

    cur = db.execute(
        "INSERT INTO users (username, password_hash, body_weight_lbs, height_in) VALUES (?, ?, ?, ?)",
        (username, password_hash, body_weight_lbs, height_in),
    )
    db.commit()
    user_id = cur.lastrowid

    # Log the user in immediately after registration
    session.clear()
    session["user_id"] = user_id

    return success({"id": user_id, "username": username}, 201)


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------
@auth_bp.post("/login")
def login():
    """
    Authenticate and start a session.

    Request JSON:
        { "username": "evan", "password": "secret123" }

    Response 200:
        { "id": 1, "username": "evan" }
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return error("username and password are required.")

    db = get_db()
    user = db.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return error("Invalid username or password.", 401)

    session.clear()
    session["user_id"] = user["id"]

    return success({"id": user["id"], "username": user["username"]})


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------
@auth_bp.post("/logout")
def logout():
    """Clear the session cookie."""
    session.clear()
    return success({"message": "Logged out."})


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------
@auth_bp.get("/me")
@login_required
def me(user_id):
    """Return the currently authenticated user."""
    db = get_db()
    user = db.execute(
        "SELECT id, username, body_weight_lbs, height_in, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if user is None:
        return error("User not found.", 404)

    return success({
        "id":              user["id"],
        "username":        user["username"],
        "body_weight_lbs": user["body_weight_lbs"],
        "height_in":       user["height_in"],
        "created_at":      user["created_at"],
    })


# ---------------------------------------------------------------------------
# GET /auth/profile  |  PUT /auth/profile
# ---------------------------------------------------------------------------
@auth_bp.get("/profile")
@login_required
def get_profile(user_id):
    """Return the user's profile fields."""
    db = get_db()
    user = db.execute(
        "SELECT id, username, body_weight_lbs, height_in, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if user is None:
        return error("User not found.", 404)

    return success({
        "id":              user["id"],
        "username":        user["username"],
        "body_weight_lbs": user["body_weight_lbs"],
        "height_in":       user["height_in"],
        "created_at":      user["created_at"],
    })


@auth_bp.put("/profile")
@login_required
def update_profile(user_id):
    """
    Update body weight and height for the current user.

    Request JSON (all fields optional):
        { "body_weight_lbs": 175.5, "height_in": 70 }
    """
    data = request.get_json(silent=True) or {}

    body_weight_lbs = data.get("body_weight_lbs")
    height_in       = data.get("height_in")

    if body_weight_lbs is not None:
        try:
            body_weight_lbs = float(body_weight_lbs)
            if body_weight_lbs <= 0:
                return error("body_weight_lbs must be a positive number.")
        except (TypeError, ValueError):
            return error("body_weight_lbs must be a number.")

    if height_in is not None:
        try:
            height_in = float(height_in)
            if height_in <= 0:
                return error("height_in must be a positive number.")
        except (TypeError, ValueError):
            return error("height_in must be a number.")

    db = get_db()
    db.execute(
        """UPDATE users
           SET body_weight_lbs = COALESCE(?, body_weight_lbs),
               height_in       = COALESCE(?, height_in)
           WHERE id = ?""",
        (body_weight_lbs, height_in, user_id),
    )
    db.commit()

    user = db.execute(
        "SELECT id, username, body_weight_lbs, height_in, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    return success({
        "id":              user["id"],
        "username":        user["username"],
        "body_weight_lbs": user["body_weight_lbs"],
        "height_in":       user["height_in"],
        "created_at":      user["created_at"],
    })


# ---------------------------------------------------------------------------
# POST /auth/change-password
# ---------------------------------------------------------------------------
@auth_bp.post("/change-password")
@login_required
def change_password(user_id):
    """
    Change the current user's password.

    Request JSON:
        { "current_password": "old", "new_password": "new123" }
    """
    data             = request.get_json(silent=True) or {}
    current_password = (data.get("current_password") or "").strip()
    new_password     = (data.get("new_password") or "").strip()

    if not current_password:
        return error("current_password is required.")
    if not new_password:
        return error("new_password is required.")
    if len(new_password) < 6:
        return error("new_password must be at least 6 characters.")

    db = get_db()
    user = db.execute(
        "SELECT password_hash FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    if user is None:
        return error("User not found.", 404)

    if not check_password_hash(user["password_hash"], current_password):
        return error("Current password is incorrect.", 401)

    new_hash = generate_password_hash(new_password)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    db.commit()

    return success({"message": "Password updated successfully."})
