"""
constants.py
------------
Central location for tunable thresholds and canonical muscle definitions.

Changing a threshold here automatically affects both the fatigue
calculation engine and the 3D model highlight logic — no schema
migration required.
"""

# ---------------------------------------------------------------------------
# Canonical muscle group names
# Must match the 'name' column values seeded in muscle_groups table.
# ---------------------------------------------------------------------------
MUSCLE_GROUPS = [
    "biceps",
    "triceps",
    "forearms",
    "chest",
    "abs",
    "front_delts",
    "side_delts",
    "rear_delts",
    "traps",
    "lats",
    "spinal_erectors",
    "glutes",
    "hamstrings",
    "quads",
    "calves",
]

# ---------------------------------------------------------------------------
# Fatigue scoring: rolling 7-day window
# ---------------------------------------------------------------------------

# Number of calendar days to look back when computing fatigue.
FATIGUE_WINDOW_DAYS = 7

# ---------------------------------------------------------------------------
# Volume-based highlight thresholds
#
# weekly_volume = SUM(sets * reps * weight_lbs) for a muscle over the window.
# weekly_sessions = number of distinct workout days the muscle was trained.
#
# A muscle is highlighted RED if EITHER condition is met (whichever is more
# conservative), YELLOW if it clears the yellow bar but not red, else GREEN.
#
# These are starting values — adjust based on testing with real data.
# ---------------------------------------------------------------------------

# RED  — muscle needs full rest (trained 2+ times this week, or very high volume)
RED_VOLUME_THRESHOLD = 5_000    # lbs·reps (e.g. 2+ heavy compound sets on the same muscle)
RED_SESSION_THRESHOLD = 2       # trained 2+ times in the past 7 days

# YELLOW — muscle was trained and needs rest before next session
YELLOW_VOLUME_THRESHOLD = 1_500  # lbs·reps (roughly 1 solid working set on a muscle)
YELLOW_SESSION_THRESHOLD = 1     # trained at least once in the past 7 days

# Bodyweight exercise volume multiplier
# Weight is stored as 0 for bodyweight moves; this substitutes a nominal
# load so they still contribute to fatigue scoring.
BODYWEIGHT_NOMINAL_LBS = 100.0

# Secondary muscle fatigue discount
# Exercises stored with a "(secondary)" suffix are supporting muscles, not
# the primary mover. Their volume contribution to fatigue is scaled down
# by this factor (0.25 = 25% of a primary exercise's fatigue impact).
SECONDARY_FATIGUE_MULTIPLIER = 0.25

# ---------------------------------------------------------------------------
# Intensity multipliers
# High-intensity sessions count for more fatigue than low-intensity ones.
# Applied to the raw volume score before threshold comparison.
# ---------------------------------------------------------------------------
INTENSITY_MULTIPLIERS = {
    "low":      0.75,
    "moderate": 1.00,
    "high":     1.35,
}

# ---------------------------------------------------------------------------
# Muscle group classifications
# Used by the balance checker to group muscles into functional categories.
# ---------------------------------------------------------------------------

# Push muscles: primarily activated during pressing movements
PUSH_MUSCLES = {"chest", "front_delts", "side_delts", "triceps"}

# Pull muscles: primarily activated during rowing/pulling movements
PULL_MUSCLES = {"lats", "rear_delts", "traps", "biceps", "forearms"}

# Leg muscles
LEG_MUSCLES = {"quads", "hamstrings", "glutes", "calves"}

# Core / stabiliser muscles
CORE_MUSCLES = {"abs", "spinal_erectors"}

# Antagonist pairs: muscles on opposite sides that should be trained in balance
# Format: (agonist, antagonist)
ANTAGONIST_PAIRS = [
    ("chest",      "lats"),          # horizontal push vs pull
    ("front_delts","rear_delts"),    # anterior vs posterior shoulder
    ("quads",      "hamstrings"),    # knee extension vs flexion
    ("biceps",     "triceps"),       # elbow flexion vs extension
]

# ---------------------------------------------------------------------------
# Evaluation thresholds
# ---------------------------------------------------------------------------

# Balance: maximum acceptable ratio of push:pull weekly volume before flagging
# e.g. 2.0 means push volume can be at most 2x pull volume
PUSH_PULL_MAX_RATIO = 2.0

# Antagonist imbalance: flag if one muscle's volume is > this multiple of its pair
ANTAGONIST_MAX_RATIO = 2.5

# Rest between sessions for the same muscle group (days)
MIN_REST_DAYS_BETWEEN_SESSIONS = 1   # flag if same muscle trained on back-to-back days

# Weekly frequency targets per muscle group
MIN_WEEKLY_SESSIONS = 0   # 0 = no minimum enforced (muscles can rest all week)
MAX_WEEKLY_SESSIONS = 3   # flag if a muscle group is trained more than 3x/week

# Weekly volume targets (sets × reps × weight) per muscle — used for "undertrained" flag
# Set to 0 to disable undertrained warnings
MIN_WEEKLY_VOLUME = 0

# Workout-level checks
MAX_WORKOUT_DURATION_MINS = 120   # flag sessions over 2 hours
MAX_EXERCISES_PER_SESSION  = 12   # flag if a single session has too many exercises

# Score weights — how much each rule category contributes to the 0–100 score
# Ranked by user: balance > frequency > rest > volume
SCORE_WEIGHTS = {
    "balance":   0.35,
    "frequency": 0.25,
    "rest":      0.22,
    "volume":    0.18,
}
