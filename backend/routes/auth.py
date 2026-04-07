"""
routes/auth.py
--------------
Authentication endpoints.

POST /auth/register  — create a new account
POST /auth/login     — start a session
POST /auth/logout    — end the session
GET  /auth/me        — return the currently logged-in user
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

    db = get_db()

    # Check for duplicate username
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        return error("Username already taken.", 409)

    password_hash = generate_password_hash(password)

    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
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
        "SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    if user is None:
        return error("User not found.", 404)

    return success({
        "id":         user["id"],
        "username":   user["username"],
        "created_at": user["created_at"],
    })
