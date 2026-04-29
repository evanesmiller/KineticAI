import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../context/AuthContext";
import Layout from "../components/Layout";

function SectionHeading({ label }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.25rem" }}>
      <div style={{ width: 3, height: 18, borderRadius: 2, background: "linear-gradient(to bottom,#8b5cf6,#6d28d9)" }} />
      <span style={{ fontFamily: "'Barlow Condensed',sans-serif", fontWeight: 700, fontSize: "0.75rem", letterSpacing: "0.18em", textTransform: "uppercase", color: "#6b6b8f" }}>
        {label}
      </span>
    </div>
  );
}

function inputStyle(focused) {
  return {
    width: "100%",
    background: "#080810",
    border: `1px solid ${focused ? "#6d28d9" : "#1e1e35"}`,
    borderRadius: "8px",
    color: "#eeeeff",
    fontSize: "0.9rem",
    fontFamily: "'DM Sans', sans-serif",
    padding: "0.6rem 0.85rem",
    outline: "none",
    boxSizing: "border-box",
    transition: "border-color 0.15s",
  };
}

function FieldLabel({ children }) {
  return (
    <div style={{ fontSize: "0.7rem", letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b6b8f", fontFamily: "'Barlow Condensed',sans-serif", fontWeight: 600, marginBottom: "0.4rem" }}>
      {children}
    </div>
  );
}

function StatusBanner({ type, message }) {
  if (!message) return null;
  const colors = { success: "#22c55e", error: "#ef4444" };
  const c = colors[type] || "#6b6b8f";
  return (
    <div style={{ background: `${c}15`, border: `1px solid ${c}44`, borderRadius: "8px", padding: "0.6rem 0.9rem", fontSize: "0.8rem", color: c, fontFamily: "'DM Sans',sans-serif", marginBottom: "1rem" }}>
      {message}
    </div>
  );
}

// Convert total inches → { feet, inches } for display
function inchesToFeetIn(totalIn) {
  if (totalIn == null || totalIn === "") return { feet: "", inches: "" };
  const ft = Math.floor(totalIn / 12);
  const inches = Math.round(((totalIn / 12) - ft) * 12);
  return { feet: String(ft), inches: String(inches) };
}

export default function Profile() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // ---------- body stats state ----------
  const [weightLbs, setWeightLbs]   = useState("");
  const [heightFt,  setHeightFt]    = useState("");
  const [heightIn,  setHeightIn]    = useState("");
  const [statsStatus, setStatsStatus] = useState(null); // { type, message }
  const [statsSaving, setStatsSaving] = useState(false);

  // ---------- change password state ----------
  const [currentPw,  setCurrentPw]  = useState("");
  const [newPw,      setNewPw]      = useState("");
  const [confirmPw,  setConfirmPw]  = useState("");
  const [pwStatus,   setPwStatus]   = useState(null);
  const [pwSaving,   setPwSaving]   = useState(false);

  // ---------- focused field tracking ----------
  const [focused, setFocused] = useState("");

  // Load profile on mount
  useEffect(() => {
    fetch(`${API}/auth/profile`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        setWeightLbs(data.body_weight_lbs != null ? String(data.body_weight_lbs) : "");
        const { feet, inches } = inchesToFeetIn(data.height_in);
        setHeightFt(feet);
        setHeightIn(inches);
      });
  }, []);

  async function handleSaveStats(e) {
    e.preventDefault();
    setStatsStatus(null);

    const weight = weightLbs !== "" ? parseFloat(weightLbs) : null;
    const totalIn = (heightFt !== "" || heightIn !== "")
      ? (parseFloat(heightFt || 0) * 12) + parseFloat(heightIn || 0)
      : null;

    if (weight !== null && (isNaN(weight) || weight <= 0)) {
      setStatsStatus({ type: "error", message: "Weight must be a positive number." });
      return;
    }
    if (totalIn !== null && (isNaN(totalIn) || totalIn <= 0)) {
      setStatsStatus({ type: "error", message: "Height must be a positive number." });
      return;
    }

    setStatsSaving(true);
    try {
      const r = await fetch(`${API}/auth/profile`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body_weight_lbs: weight, height_in: totalIn }),
      });
      const data = await r.json();
      if (!r.ok) {
        setStatsStatus({ type: "error", message: data.error || "Failed to save." });
      } else {
        setStatsStatus({ type: "success", message: "Body stats saved." });
      }
    } catch {
      setStatsStatus({ type: "error", message: "Network error. Please try again." });
    } finally {
      setStatsSaving(false);
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    setPwStatus(null);

    if (newPw !== confirmPw) {
      setPwStatus({ type: "error", message: "New passwords do not match." });
      return;
    }
    if (newPw.length < 6) {
      setPwStatus({ type: "error", message: "New password must be at least 6 characters." });
      return;
    }

    setPwSaving(true);
    try {
      const r = await fetch(`${API}/auth/change-password`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      const data = await r.json();
      if (!r.ok) {
        setPwStatus({ type: "error", message: data.error || "Failed to change password." });
      } else {
        setPwStatus({ type: "success", message: "Password changed successfully." });
        setCurrentPw(""); setNewPw(""); setConfirmPw("");
      }
    } catch {
      setPwStatus({ type: "error", message: "Network error. Please try again." });
    } finally {
      setPwSaving(false);
    }
  }

  async function handleSignOut() {
    await logout();
    navigate("/login");
  }

  const cardStyle = {
    background: "#0f0f1a",
    border: "1px solid #1e1e35",
    borderRadius: "0.75rem",
    padding: "1.5rem 1.75rem",
    marginBottom: "1.25rem",
  };

  const btnStyle = (disabled) => ({
    background: disabled ? "#1e1e35" : "linear-gradient(135deg,#6d28d9,#8b5cf6)",
    border: "none",
    borderRadius: "8px",
    color: disabled ? "#3a3a5c" : "#fff",
    fontSize: "0.75rem",
    fontFamily: "'Barlow Condensed',sans-serif",
    fontWeight: 700,
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    padding: "0.55rem 1.4rem",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "opacity 0.15s",
  });

  return (
    <Layout>
      <div style={{ maxWidth: 560, margin: "0 auto", padding: "2rem 1.5rem" }}>

        {/* Page header */}
        <div style={{ marginBottom: "2rem" }}>
          <h1 style={{ fontFamily: "'Barlow Condensed',sans-serif", fontWeight: 800, fontSize: "1.8rem", color: "#eeeeff", letterSpacing: "0.04em", margin: 0 }}>
            Profile
          </h1>
          <p style={{ fontFamily: "'DM Sans',sans-serif", fontSize: "0.85rem", color: "#6b6b8f", margin: "0.35rem 0 0" }}>
            {user?.username}
          </p>
        </div>

        {/* Body Stats */}
        <div style={cardStyle}>
          <SectionHeading label="Body Stats" />
          <form onSubmit={handleSaveStats}>
            <StatusBanner {...(statsStatus || {})} message={statsStatus?.message} />

            <div style={{ marginBottom: "1rem" }}>
              <FieldLabel>Body Weight (lbs)</FieldLabel>
              <input
                type="number"
                min="1"
                step="0.1"
                placeholder="e.g. 175"
                value={weightLbs}
                onChange={e => setWeightLbs(e.target.value)}
                onFocus={() => setFocused("weight")}
                onBlur={() => setFocused("")}
                style={inputStyle(focused === "weight")}
              />
            </div>

            <div style={{ marginBottom: "1.25rem" }}>
              <FieldLabel>Height</FieldLabel>
              <div style={{ display: "flex", gap: "0.75rem" }}>
                <div style={{ flex: 1 }}>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    placeholder="ft"
                    value={heightFt}
                    onChange={e => setHeightFt(e.target.value)}
                    onFocus={() => setFocused("ft")}
                    onBlur={() => setFocused("")}
                    style={inputStyle(focused === "ft")}
                  />
                  <div style={{ fontSize: "0.65rem", color: "#3a3a5c", fontFamily: "'DM Sans',sans-serif", marginTop: "0.3rem" }}>feet</div>
                </div>
                <div style={{ flex: 1 }}>
                  <input
                    type="number"
                    min="0"
                    max="11"
                    step="1"
                    placeholder="in"
                    value={heightIn}
                    onChange={e => setHeightIn(e.target.value)}
                    onFocus={() => setFocused("in")}
                    onBlur={() => setFocused("")}
                    style={inputStyle(focused === "in")}
                  />
                  <div style={{ fontSize: "0.65rem", color: "#3a3a5c", fontFamily: "'DM Sans',sans-serif", marginTop: "0.3rem" }}>inches</div>
                </div>
              </div>
            </div>

            <button type="submit" disabled={statsSaving} style={btnStyle(statsSaving)}>
              {statsSaving ? "Saving..." : "Save Stats"}
            </button>
          </form>
        </div>

        {/* Change Password */}
        <div style={cardStyle}>
          <SectionHeading label="Change Password" />
          <form onSubmit={handleChangePassword}>
            <StatusBanner {...(pwStatus || {})} message={pwStatus?.message} />

            <div style={{ marginBottom: "1rem" }}>
              <FieldLabel>Current Password</FieldLabel>
              <input
                type="password"
                placeholder="Enter current password"
                value={currentPw}
                onChange={e => setCurrentPw(e.target.value)}
                onFocus={() => setFocused("cpw")}
                onBlur={() => setFocused("")}
                style={inputStyle(focused === "cpw")}
              />
            </div>

            <div style={{ marginBottom: "1rem" }}>
              <FieldLabel>New Password</FieldLabel>
              <input
                type="password"
                placeholder="At least 6 characters"
                value={newPw}
                onChange={e => setNewPw(e.target.value)}
                onFocus={() => setFocused("npw")}
                onBlur={() => setFocused("")}
                style={inputStyle(focused === "npw")}
              />
            </div>

            <div style={{ marginBottom: "1.25rem" }}>
              <FieldLabel>Confirm New Password</FieldLabel>
              <input
                type="password"
                placeholder="Repeat new password"
                value={confirmPw}
                onChange={e => setConfirmPw(e.target.value)}
                onFocus={() => setFocused("conpw")}
                onBlur={() => setFocused("")}
                style={inputStyle(focused === "conpw")}
              />
            </div>

            <button type="submit" disabled={pwSaving} style={btnStyle(pwSaving)}>
              {pwSaving ? "Updating..." : "Update Password"}
            </button>
          </form>
        </div>

        {/* Sign Out */}
        <div style={cardStyle}>
          <SectionHeading label="Account" />
          <p style={{ fontFamily: "'DM Sans',sans-serif", fontSize: "0.82rem", color: "#6b6b8f", margin: "0 0 1.25rem" }}>
            You are signed in as <span style={{ color: "#a78bfa" }}>{user?.username}</span>.
          </p>
          <button
            onClick={handleSignOut}
            style={{
              background: "transparent",
              border: "1px solid #3a1a1a",
              borderRadius: "8px",
              color: "#ef4444",
              fontSize: "0.75rem",
              fontFamily: "'Barlow Condensed',sans-serif",
              fontWeight: 700,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              padding: "0.55rem 1.4rem",
              cursor: "pointer",
              transition: "all 0.15s",
            }}
            onMouseEnter={e => { e.target.style.background = "#ef444415"; e.target.style.borderColor = "#ef4444"; }}
            onMouseLeave={e => { e.target.style.background = "transparent"; e.target.style.borderColor = "#3a1a1a"; }}
          >
            Sign Out
          </button>
        </div>

      </div>
    </Layout>
  );
}
