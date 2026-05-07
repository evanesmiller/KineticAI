-- =============================================================
-- Workout Recommendation System - Database Schema
-- =============================================================

-- ---------------------------------------------------------------
-- USERS
-- Basic user table. Expandable later for auth, goals, etc.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    body_weight_lbs REAL,
    height_in       REAL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------
-- MUSCLE GROUPS
-- Canonical list of all trackable muscles for the 3D model.
-- Stored as a lookup table so the frontend/backend always agree
-- on valid muscle names and IDs.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS muscle_groups (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE   -- e.g. 'biceps', 'quads', etc.
);

-- Seed the 16 core muscles required by the 3D model frontend.
-- INSERT OR IGNORE means re-running init is safe.
INSERT OR IGNORE INTO muscle_groups (name) VALUES
    ('biceps'),
    ('triceps'),
    ('forearms'),
    ('chest'),
    ('abs'),
    ('front_delts'),
    ('side_delts'),
    ('rear_delts'),
    ('traps'),
    ('lats'),
    ('spinal_erectors'),
    ('glutes'),
    ('hamstrings'),
    ('quads'),
    ('calves'),
    ('adductors');

-- ---------------------------------------------------------------
-- WORKOUTS
-- One row per training session.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workouts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date            TEXT    NOT NULL,               -- ISO-8601 date: YYYY-MM-DD
    duration_mins   INTEGER NOT NULL CHECK(duration_mins > 0),
    intensity       TEXT    NOT NULL
                        CHECK(intensity IN ('low', 'moderate', 'high')),
    notes           TEXT,                           -- optional free-text field
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------
-- WORKOUT_MUSCLE_GROUPS
-- Many-to-many: a single workout can target several muscle groups.
-- This is what the 3D model frontend queries to determine per-muscle
-- workload over the past 7 days.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workout_muscle_groups (
    workout_id      INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    muscle_group_id INTEGER NOT NULL REFERENCES muscle_groups(id),
    PRIMARY KEY (workout_id, muscle_group_id)
);

-- ---------------------------------------------------------------
-- EXERCISES
-- Each exercise belongs to exactly one workout.
-- An exercise always targets one primary muscle group.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exercises (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id      INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    muscle_group_id INTEGER NOT NULL REFERENCES muscle_groups(id),
    name            TEXT    NOT NULL,   -- e.g. 'Barbell Squat', 'Bench Press'
    sets            INTEGER NOT NULL CHECK(sets > 0),
    reps            INTEGER NOT NULL CHECK(reps > 0),
    weight_lbs      REAL    NOT NULL CHECK(weight_lbs >= 0),  -- 0 = bodyweight
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------
-- MUSCLE_FATIGUE_CACHE
-- Pre-computed rolling fatigue scores per user per muscle.
-- Updated whenever a new workout is logged; read by the frontend
-- to drive the 3D model highlight colors without re-scanning all
-- historical data on every page load.
--
-- fatigue_score semantics (used by highlight logic):
--   >= RED_THRESHOLD   -> 'red'   (needs rest for remainder of week)
--   >= YELLOW_THRESHOLD -> 'yellow' (ready after a rest day)
--   < YELLOW_THRESHOLD  -> 'green'  (fresh / unworked)
--
-- Thresholds are defined in the Python layer (constants.py) so
-- they can be tuned without a schema migration.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS muscle_fatigue_cache (
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    muscle_group_id INTEGER NOT NULL REFERENCES muscle_groups(id),
    -- Rolling 7-day volume: SUM(sets * reps * weight_lbs) for this muscle
    weekly_volume   REAL    NOT NULL DEFAULT 0.0,
    -- Rolling 7-day session count for this muscle
    weekly_sessions INTEGER NOT NULL DEFAULT 0,
    -- Derived status; recomputed by Python after every workout insert
    highlight_color TEXT    NOT NULL DEFAULT 'green'
                        CHECK(highlight_color IN ('red', 'yellow', 'green')),
    last_updated    TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, muscle_group_id)
);

-- ---------------------------------------------------------------
-- EVALUATION_CACHE
-- Stores the most recent Gemini evaluation result per user so the
-- API is only called again when the 7-day workout set changes.
-- fingerprint = "<max_workout_id>:<workout_count>" for the window.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evaluation_cache (
    user_id      INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    fingerprint  TEXT    NOT NULL,
    result_json  TEXT    NOT NULL,
    cached_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------
-- INDEXES
-- Covering indexes for the most common query patterns:
--   1. All workouts for a user in a date range (fatigue calc)
--   2. All exercises for a workout (workout detail view)
--   3. Fatigue cache lookup by user (3D model load)
-- ---------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_workouts_user_date
    ON workouts(user_id, date);

CREATE INDEX IF NOT EXISTS idx_exercises_workout
    ON exercises(workout_id);

CREATE INDEX IF NOT EXISTS idx_exercises_muscle
    ON exercises(muscle_group_id);

CREATE INDEX IF NOT EXISTS idx_wmg_workout
    ON workout_muscle_groups(workout_id);

CREATE INDEX IF NOT EXISTS idx_fatigue_user
    ON muscle_fatigue_cache(user_id);
