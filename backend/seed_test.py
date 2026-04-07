"""
seed_test.py
------------
Smoke-test and seed script. Run directly:

    python seed_test.py

Creates an in-memory SQLite DB, inserts a test user, logs two workouts
with multiple exercises, and prints the resulting muscle highlight map.
"""

import sqlite3
from datetime import date, timedelta

from db.connection import init_db, get_connection
from models import (
    Exercise,
    Workout,
    insert_workout,
    get_workout,
    get_workouts_for_user,
    get_muscle_highlight_map,
    refresh_all_muscle_fatigue,
)

# ── Use an in-memory DB so the test is self-contained ──────────────────────
TEST_DB = ":memory:"

def run():
    conn = get_connection(TEST_DB)
    # Manually apply schema (init_db writes to a file; for :memory: we inline)
    from pathlib import Path
    schema = (Path(__file__).parent / "db" / "schema.sql").read_text()
    conn.executescript(schema)

    # ── Create a test user ─────────────────────────────────────────────────
    conn.execute("INSERT INTO users (username) VALUES (?)", ("evan",))
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE username='evan'").fetchone()["id"]
    print(f"Created user id={user_id}")

    # ── Workout 1: Push day (4 days ago) ──────────────────────────────────
    push_day = Workout(
        user_id=user_id,
        date=date.today() - timedelta(days=4),
        duration_mins=60,
        intensity="high",
        notes="Heavy push session",
        exercises=[
            Exercise(name="Barbell Bench Press", muscle_group="chest",      sets=4, reps=6,  weight_lbs=185),
            Exercise(name="Incline DB Press",    muscle_group="chest",      sets=3, reps=10, weight_lbs=70),
            Exercise(name="Overhead Press",      muscle_group="front_delts",sets=4, reps=8,  weight_lbs=115),
            Exercise(name="Lateral Raise",       muscle_group="side_delts", sets=3, reps=15, weight_lbs=25),
            Exercise(name="Skull Crusher",       muscle_group="triceps",    sets=3, reps=10, weight_lbs=65),
            Exercise(name="Tricep Pushdown",     muscle_group="triceps",    sets=3, reps=12, weight_lbs=50),
        ],
    )
    wid1 = insert_workout(conn, push_day)
    print(f"Inserted push workout id={wid1}")

    # ── Workout 2: Pull day (2 days ago) ──────────────────────────────────
    pull_day = Workout(
        user_id=user_id,
        date=date.today() - timedelta(days=2),
        duration_mins=55,
        intensity="moderate",
        exercises=[
            Exercise(name="Deadlift",          muscle_group="spinal_erectors", sets=4, reps=5,  weight_lbs=225),
            Exercise(name="Pull-Up",           muscle_group="lats",            sets=4, reps=8,  weight_lbs=0),   # bodyweight
            Exercise(name="Barbell Row",       muscle_group="lats",            sets=3, reps=10, weight_lbs=135),
            Exercise(name="Face Pull",         muscle_group="rear_delts",      sets=3, reps=15, weight_lbs=40),
            Exercise(name="Barbell Curl",      muscle_group="biceps",          sets=3, reps=10, weight_lbs=75),
            Exercise(name="Hammer Curl",       muscle_group="forearms",        sets=3, reps=12, weight_lbs=35),
            Exercise(name="Shrugs",            muscle_group="traps",           sets=3, reps=15, weight_lbs=135),
        ],
    )
    wid2 = insert_workout(conn, pull_day)
    print(f"Inserted pull workout id={wid2}")

    # ── Workout 3: Leg day (today) ─────────────────────────────────────────
    leg_day = Workout(
        user_id=user_id,
        date=date.today(),
        duration_mins=70,
        intensity="high",
        exercises=[
            Exercise(name="Back Squat",       muscle_group="quads",    sets=5, reps=5,  weight_lbs=205),
            Exercise(name="Romanian Deadlift",muscle_group="hamstrings",sets=4, reps=8,  weight_lbs=155),
            Exercise(name="Leg Press",        muscle_group="quads",    sets=3, reps=12, weight_lbs=270),
            Exercise(name="Hip Thrust",       muscle_group="glutes",   sets=4, reps=10, weight_lbs=185),
            Exercise(name="Standing Calf Raise",muscle_group="calves", sets=4, reps=15, weight_lbs=100),
            Exercise(name="Ab Wheel",         muscle_group="abs",      sets=3, reps=10, weight_lbs=0),
        ],
    )
    wid3 = insert_workout(conn, leg_day)
    print(f"Inserted leg workout id={wid3}")

    # ── Verify retrieval ───────────────────────────────────────────────────
    fetched = get_workout(conn, wid1)
    assert fetched is not None
    assert len(fetched.exercises) == 6
    print(f"Fetched workout {wid1} — {len(fetched.exercises)} exercises ✓")

    all_workouts = get_workouts_for_user(conn, user_id)
    print(f"Total workouts for user: {len(all_workouts)} ✓")

    # ── Muscle highlight map (what the 3D model will consume) ─────────────
    highlight_map = get_muscle_highlight_map(conn, user_id)
    print("\n── 3D Model Highlight Map ─────────────────────────────")
    color_emoji = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
    for muscle, color in sorted(highlight_map.items()):
        print(f"  {color_emoji[color]}  {muscle:<20} {color}")

    conn.close()
    print("\n── All tests passed ✓ ──────────────────────────────────")


if __name__ == "__main__":
    run()
