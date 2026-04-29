# KineticAI

AI-powered Workout Recommendation & Grading System using Flask, React, and Google Gemini.

## Features
- Personalized workout recommendations
- Muscle fatigue visualization
- Training split detection
- Progressive overload tracking

## Tech Stack
- Frontend: React + Vite
- Backend: Flask + SQLite
- AI: Google Gemini 2.5 Flash Lite

## Development Setup

### 1. Clone Repository
```
git clone https://github.com/evanesmiller/KineticAI.git
cd KineticAI
```

## Backend Setup

### 2. Create & Activate Virtual Environment
```
python3 -m venv venv
```

Mac / Linux

```
source venv/bin/activate
```

Windows

```
venv\Scripts\activate
```

### 3. Install Dependencies
```
pip install -r requirements.txt
```

### 4. Replace Google Gemini API and Flask keys in .env file
Gemini 2.5 Flash Lite (Free tier ~ 20 requests/day)

### 5. Start Backend Server
```
cd backend
python app.py
```

### Frontend Setup

### 6. Open New Terminal
```
cd KineticAI/frontend
npm install
npm run dev
```

---

## Project Structure

```
KineticAI/
├── requirements.txt              # Python package dependencies for the backend
├── backend/
│   ├── app.py                    # Entry point — creates the Flask app and registers all route blueprints
│   ├── constants.py              # Central config: muscle group names, fatigue thresholds, scoring weights
│   ├── models.py                 # SQLAlchemy model definitions (ORM layer for DB tables)
│   ├── db/
│   │   ├── connection.py         # Opens and returns the SQLite DB connection for each request
│   │   └── schema.sql            # SQL file that defines and seeds all database tables on first run
│   ├── gemini/
│   │   └── client.py             # Wrapper around the Gemini API — handles muscle detection and workout evaluation prompts
│   ├── evaluation/
│   │   ├── engine.py             # Rule-based scoring engine — computes 0–100 scores for balance, consistency, rest, and volume
│   │   ├── data_builder.py       # Queries the DB and builds the structured JSON payload sent to Gemini for evaluation
│   │   ├── progressive_overload.py  # Tracks weight progression per muscle by comparing first vs. latest logged weight per exercise
│   │   ├── split_detector.py     # Classifies the user's training style (PPL, Upper/Lower, Full Body, Bro Split, Unknown)
│   │   ├── recovery_analysis.py  # Analyses inter-session rest gaps per muscle group
│   │   └── edge_cases.py         # Handles edge cases for the scoring engine (e.g. empty weeks, new users)
│   └── routes/
│       ├── auth.py               # Login, registration, logout, and password change endpoints
│       ├── workouts.py           # CRUD endpoints for creating, reading, and deleting workout sessions
│       ├── exercises.py          # Endpoints for adding exercises to a workout; triggers Gemini muscle detection
│       ├── evaluation.py         # GET /evaluation/ — returns cached or freshly computed Gemini evaluation
│       ├── fatigue.py            # Returns per-muscle fatigue status (green/yellow/red) for the muscle map
│       ├── muscles.py            # Returns the canonical list of muscle groups from the DB
│       └── utils.py              # Shared helpers: success/error response formatting, login_required decorator
└── frontend/
    ├── index.html                # Root HTML file — React mounts into the <div id="root"> here
    ├── vite.config.js            # Vite build config — sets up the dev server proxy to the Flask backend
    ├── tailwind.config.js        # Tailwind CSS configuration
    ├── package.json              # Frontend dependencies and npm scripts
    ├── public/
    │   └── muscle_map/           # PNG image layers for each of the 15 muscle groups used in the muscle map overlay
    └── src/
        ├── main.jsx              # React entry point — renders <App /> into the DOM
        ├── App.jsx               # Top-level component — defines all client-side routes using react-router-dom
        ├── App.css               # Global styles and CSS animations
        ├── index.css             # Tailwind base imports and custom utility classes
        ├── context/
        │   └── AuthContext.jsx   # React context that stores the logged-in user and exposes login/logout/register functions
        ├── hooks/
        │   └── useFetch.js       # Custom hook that wraps fetch() with loading and error state management
        ├── components/
        │   ├── Navbar.jsx        # Top navigation bar with links and logout button
        │   ├── Layout.jsx        # Wrapper component that adds the Navbar above every protected page
        │   ├── ProtectedRoute.jsx # Route guard — redirects unauthenticated users to the login page
        │   ├── MuscleModel.jsx   # Interactive muscle map component — overlays colored PNG layers based on fatigue status
        │   └── WorkoutCard.jsx   # Reusable card component for displaying a single workout session summary
        └── pages/
            ├── AuthPage.jsx      # Login and registration form
            ├── Dashboard.jsx     # Home screen — shows the muscle fatigue map and recent workout history
            ├── LogWorkout.jsx    # Form to log a new workout session and add exercises with Gemini muscle detection
            ├── Evaluation.jsx    # Full AI evaluation page — score, grade, category breakdowns, progressive overload, and suggestions
            ├── History.jsx       # Paginated view of all past workout sessions
            └── Profile.jsx       # User profile page for updating body weight and other settings
```

---

### How the pieces connect

1. **User logs a workout** on `LogWorkout.jsx` → POST to `/workouts` and `/exercises` → `exercises.py` calls `gemini/client.py` to detect which muscles the exercise targets → saved to SQLite.

2. **Dashboard loads** → GET `/fatigue` → `fatigue.py` reads the rolling 7-day muscle volume from the DB → `MuscleModel.jsx` overlays the correct color (green/yellow/red) on each muscle PNG layer.

3. **Evaluation page loads** → GET `/evaluation/` → `evaluation.py` checks the fingerprint cache → if the workout set is unchanged, returns the cached result; otherwise calls `data_builder.py` to build a JSON summary, sends it to Gemini, runs the Python scoring engine, and caches the result.
