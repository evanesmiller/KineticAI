"""
routes/utils.py
---------------
Shared utilities used across all route blueprints.
"""

from functools import wraps
from flask import session, jsonify


def login_required(f):
    """
    Decorator that blocks unauthenticated requests with 401.
    Attach to any route that requires the user to be logged in.

    Injects `user_id` as a keyword argument so the route function
    doesn't have to read session itself:

        @workouts_bp.get("/workouts")
        @login_required
        def get_workouts(user_id):
            ...
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None:
            return jsonify({"error": "Authentication required."}), 401
        return f(*args, user_id=user_id, **kwargs)
    return wrapper


def success(data: dict | list, status: int = 200):
    """Convenience wrapper for successful JSON responses."""
    return jsonify(data), status


def error(message: str, status: int = 400):
    """Convenience wrapper for error JSON responses."""
    return jsonify({"error": message}), status
