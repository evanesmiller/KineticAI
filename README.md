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
- AI: Google Gemini

## Development Setup

### Clone Repository
git clone https://github.com/YOUR_USERNAME/KineticAI.git
cd KineticAI

### Backend Setup

### 1. Create & Activate Virtual Environment
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

### 2. Install Dependencies
```
pip install -r requirements.txt
```

### 3. Replace Google Gemini API and Flask keys in .env file
Gemini 2.5 Flash Lite (Free tier ~ 20 requests/day)

### 4. Start Backend Server
```
cd backend
python app.py
```

### Frontend Setup

### 5. Open New Terminal
```
cd KineticAI/frontend
npm install
npm run dev
```
