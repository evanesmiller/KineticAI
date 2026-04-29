import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// Geometric background grid lines
function GridBackground() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 0 }}>
      {/* Vertical lines */}
      {[...Array(8)].map((_, i) => (
        <div key={`v${i}`}
          className="absolute top-0 bottom-0 w-px"
          style={{
            left: `${(i + 1) * 12.5}%`,
            background: "linear-gradient(to bottom, transparent, rgba(109,40,217,0.06) 30%, rgba(109,40,217,0.06) 70%, transparent)",
          }}
        />
      ))}
      {/* Horizontal lines */}
      {[...Array(6)].map((_, i) => (
        <div key={`h${i}`}
          className="absolute left-0 right-0 h-px"
          style={{
            top: `${(i + 1) * 16.66}%`,
            background: "linear-gradient(to right, transparent, rgba(109,40,217,0.06) 30%, rgba(109,40,217,0.06) 70%, transparent)",
          }}
        />
      ))}
      {/* Purple radial glow bottom-left */}
      <div className="absolute -bottom-32 -left-32 w-96 h-96 rounded-full"
           style={{ background: "radial-gradient(circle, rgba(109,40,217,0.12) 0%, transparent 70%)" }} />
      {/* Purple radial glow top-right */}
      <div className="absolute -top-32 -right-32 w-80 h-80 rounded-full"
           style={{ background: "radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%)" }} />
    </div>
  );
}

// Animated logo mark
function LogoMark() {
  return (
    <div className="flex items-center gap-3 mb-10 animate-fade-in">
      <div className="relative w-10 h-10 animate-pulse-glow rounded-lg"
           style={{ background: "linear-gradient(135deg, #6d28d9, #8b5cf6)" }}>
        {/* Dumbbell icon in SVG */}
        <svg viewBox="0 0 24 24" fill="none" className="absolute inset-0 w-full h-full p-2">
          <rect x="2" y="10" width="3" height="4" rx="1" fill="white" opacity="0.9"/>
          <rect x="5" y="8" width="2" height="8" rx="1" fill="white" opacity="0.7"/>
          <rect x="7" y="11" width="10" height="2" rx="1" fill="white" opacity="0.6"/>
          <rect x="17" y="8" width="2" height="8" rx="1" fill="white" opacity="0.7"/>
          <rect x="19" y="10" width="3" height="4" rx="1" fill="white" opacity="0.9"/>
        </svg>
      </div>
      <div>
        <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 800, fontSize: "1.4rem", letterSpacing: "0.1em", color: "#eeeeff", lineHeight: 1 }}>
          Kinetic<span style={{ color: "#8b5cf6" }}>AI</span>
        </div>
        <div style={{ fontSize: "0.6rem", letterSpacing: "0.25em", color: "#8b5cf6", fontFamily: "'DM Sans', sans-serif", textTransform: "uppercase", marginTop: "0.25rem" }}>
          AI Workout Analysis
        </div>
      </div>
    </div>
  );
}

// Thin purple divider with label
function Divider({ label }) {
  return (
    <div className="flex items-center gap-3 my-6">
      <div className="flex-1 h-px" style={{ background: "#1e1e35" }} />
      <span style={{ fontSize: "0.7rem", color: "#3a3a5c", letterSpacing: "0.15em", fontFamily: "'DM Sans', sans-serif", textTransform: "uppercase" }}>
        {label}
      </span>
      <div className="flex-1 h-px" style={{ background: "#1e1e35" }} />
    </div>
  );
}

export default function AuthPage() {
  const [mode, setMode]           = useState("login");  // "login" | "register"
  const [username, setUsername]   = useState("");
  const [password, setPassword]   = useState("");
  const [confirm, setConfirm]     = useState("");
  const [weightLbs, setWeightLbs] = useState("");
  const [heightFt,  setHeightFt]  = useState("");
  const [heightIn,  setHeightIn]  = useState("");
  const [error, setError]         = useState("");
  const [loading, setLoading]     = useState(false);

  const { login, register } = useAuth();
  const navigate = useNavigate();

  function switchMode(next) {
    setMode(next);
    setError("");
    setUsername("");
    setPassword("");
    setConfirm("");
    setWeightLbs("");
    setHeightFt("");
    setHeightIn("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (!username.trim() || !password.trim()) {
      setError("All fields are required.");
      return;
    }
    if (mode === "register") {
      if (password.length < 6) { setError("Password must be at least 6 characters."); return; }
      if (password !== confirm) { setError("Passwords do not match."); return; }
      if (!weightLbs || parseFloat(weightLbs) <= 0) { setError("Please enter your body weight."); return; }
      if (!heightFt && !heightIn) { setError("Please enter your height."); return; }
    }

    setLoading(true);
    try {
      if (mode === "login") {
        await login(username, password);
      }
      if (mode === "register") {
        const totalInches = (parseFloat(heightFt || 0) * 12) + parseFloat(heightIn || 0);
        await register(username, password, parseFloat(weightLbs), totalInches);
      }
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative" style={{ background: "#080810" }}>
      <GridBackground />

      <div className="w-full max-w-sm relative" style={{ zIndex: 1 }}>
        <LogoMark />

        {/* Mode toggle tabs */}
        <div className="flex mb-8 rounded-lg overflow-hidden stagger"
             style={{ background: "#0f0f1a", border: "1px solid #1e1e35" }}>
          {["login", "register"].map(m => (
            <button key={m} onClick={() => switchMode(m)}
              className="flex-1 py-2.5 text-xs font-display tracking-widest uppercase transition-all duration-200"
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontWeight: 700,
                letterSpacing: "0.15em",
                background:  mode === m ? "#6d28d9" : "transparent",
                color:       mode === m ? "#fff"    : "#6b6b8f",
                border:      "none",
                cursor:      "pointer",
              }}>
              {m === "login" ? "Sign In" : "Create Account"}
            </button>
          ))}
        </div>

        {/* Form card */}
        <div className="card stagger" style={{ background: "#0f0f1a", border: "1px solid #1e1e35" }}>
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

            {/* Username */}
            <div>
              <label style={{ display: "block", fontSize: "0.7rem", letterSpacing: "0.15em", textTransform: "uppercase", color: "#6b6b8f", marginBottom: "0.4rem", fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                Username
              </label>
              <input
                className="input-field"
                type="text"
                placeholder="Username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
                disabled={loading}
              />
            </div>

            {/* Password */}
            <div>
              <label style={{ display: "block", fontSize: "0.7rem", letterSpacing: "0.15em", textTransform: "uppercase", color: "#6b6b8f", marginBottom: "0.4rem", fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                Password
              </label>
              <input
                className="input-field"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                disabled={loading}
              />
            </div>

            {/* Confirm password (register only) */}
            <div style={{ overflow: "hidden", height: mode === "register" ? "auto" : 0, marginTop: mode === "register" ? 0 : "-1rem", transition: "height 0.8s ease" }}>
              <label style={{ display: "block", fontSize: "0.7rem", letterSpacing: "0.15em", textTransform: "uppercase", color: "#6b6b8f", marginBottom: "0.4rem", fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                Confirm Password
              </label>
              <input
                className="input-field"
                type="password"
                placeholder="••••••••"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                autoComplete="new-password"
                disabled={loading || mode === "login"}
              />
            </div>

            {/* Body weight (register only) */}
            <div style={{ overflow: "hidden", height: mode === "register" ? "auto" : 0, transition: "height 0.8s ease" }}>
              <label style={{ display: "block", fontSize: "0.7rem", letterSpacing: "0.15em", textTransform: "uppercase", color: "#6b6b8f", marginBottom: "0.4rem", fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                Body Weight (lbs)
              </label>
              <input
                className="input-field"
                type="number"
                min="1"
                step="0.1"
                placeholder="e.g. 175"
                value={weightLbs}
                onChange={e => setWeightLbs(e.target.value)}
                disabled={loading || mode === "login"}
              />
            </div>

            {/* Height (register only) */}
            <div style={{ overflow: "hidden", height: mode === "register" ? "auto" : 0, transition: "height 0.8s ease" }}>
              <label style={{ display: "block", fontSize: "0.7rem", letterSpacing: "0.15em", textTransform: "uppercase", color: "#6b6b8f", marginBottom: "0.4rem", fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                Height
              </label>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <div style={{ flex: 1 }}>
                  <input
                    className="input-field"
                    type="number"
                    min="0"
                    step="1"
                    placeholder="ft"
                    value={heightFt}
                    onChange={e => setHeightFt(e.target.value)}
                    disabled={loading || mode === "login"}
                  />
                  <div style={{ fontSize: "0.6rem", color: "#3a3a5c", fontFamily: "'DM Sans',sans-serif", marginTop: "0.25rem" }}>feet</div>
                </div>
                <div style={{ flex: 1 }}>
                  <input
                    className="input-field"
                    type="number"
                    min="0"
                    max="11"
                    step="1"
                    placeholder="in"
                    value={heightIn}
                    onChange={e => setHeightIn(e.target.value)}
                    disabled={loading || mode === "login"}
                  />
                  <div style={{ fontSize: "0.6rem", color: "#3a3a5c", fontFamily: "'DM Sans',sans-serif", marginTop: "0.25rem" }}>inches</div>
                </div>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "0.5rem", padding: "0.6rem 0.75rem" }}>
                <p className="error-msg" style={{ margin: 0 }}>{error}</p>
              </div>
            )}

            {/* Submit */}
            <button className="btn-primary" type="submit" disabled={loading} style={{ marginTop: "0.25rem" }}>
              {loading ? (
                <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}>
                  <span style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "white", borderRadius: "50%", display: "inline-block", animation: "spin 0.7s linear infinite" }} />
                  {mode === "login" ? "Signing in..." : "Creating account..."}
                </span>
              ) : (
                mode === "login" ? "Sign In" : "Create Account"
              )}
            </button>
          </form>

          <Divider label={mode === "login" ? "New here?" : "Already have an account?"} />

          <div style={{ textAlign: "center" }}>
            <button className="btn-ghost" onClick={() => switchMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "Create a free account →" : "← Back to sign in"}
            </button>
          </div>
        </div>

        {/* Footer tag */}
        <p style={{ textAlign: "center", marginTop: "2rem", fontSize: "0.65rem", color: "#3a3a5c", letterSpacing: "0.1em", fontFamily: "'DM Sans', sans-serif" }}>
          CPSC 481 · AI-Powered Workout System
        </p>
      </div>

      {/* Spin keyframe for loading spinner */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
