"""
app.py
------
KineticAI Flask application factory.

Usage:
    python app.py          # development
    flask --app app run    # Flask CLI
"""

import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

from db.connection import init_db, close_db

# Load .env before anything else reads environment variables
load_dotenv()


def create_app(test_config: dict = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-in-production"),
        DB_PATH=os.environ.get("DB_PATH", os.path.join(app.instance_path, "workout_app.db")),

        # ── Session cookie settings ────────────────────────────────────────
        # SameSite=None is required for cross-origin requests (React dev
        # server on :5173 talking to Flask on :5000). Secure=False allows
        # this over plain HTTP on localhost.
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
    )

    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    # ── CORS ───────────────────────────────────────────────────────────────
    # supports_credentials=True is required to allow the session cookie to
    # be sent and received across origins. The allowed origins must be
    # explicit (wildcard * does not work with credentials).
    CORS(app, supports_credentials=True, origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])

    # ── Database lifecycle ─────────────────────────────────────────────────
    with app.app_context():
        init_db(app.config["DB_PATH"])

    app.teardown_appcontext(close_db)

    # ── Blueprints ─────────────────────────────────────────────────────────
    from routes.auth       import auth_bp
    from routes.workouts   import workouts_bp
    from routes.exercises  import exercises_bp
    from routes.fatigue    import fatigue_bp
    from routes.evaluation import evaluation_bp
    from routes.muscles    import muscles_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(workouts_bp)
    app.register_blueprint(exercises_bp)
    app.register_blueprint(fatigue_bp)
    app.register_blueprint(evaluation_bp)
    app.register_blueprint(muscles_bp)

    # ── Health check ───────────────────────────────────────────────────────
    @app.get("/health")
    def health():
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        return {
            "status": "ok",
            "gemini": "configured" if gemini_key and gemini_key != "your_gemini_api_key_here" else "missing",
        }, 200

    return app


if __name__ == "__main__":
    create_app().run(debug=True)