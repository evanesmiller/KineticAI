import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/log",       label: "Log Workout" },
  { to: "/history",   label: "History" },
  { to: "/evaluation",label: "Evaluation" },
];

export default function Navbar() {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <nav style={{
      position:   "sticky",
      top:        0,
      zIndex:     50,
      background: "rgba(8,8,16,0.85)",
      backdropFilter: "blur(12px)",
      borderBottom: "1px solid #1e1e35",
    }}>
      <div style={{
        maxWidth: "1200px",
        margin:   "0 auto",
        padding:  "0 1.5rem",
        height:   "56px",
        display:  "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        {/* Logo */}
        <div onClick={() => navigate("/dashboard")}
             role="button" tabIndex={0}
             onKeyDown={e => e.key === "Enter" && navigate("/dashboard")}
             style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <div style={{
            width: 28, height: 28,
            background: "linear-gradient(135deg, #6d28d9, #8b5cf6)",
            borderRadius: "6px",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg viewBox="0 0 24 24" fill="none" width="16" height="16">
              <rect x="2"  y="10" width="3" height="4" rx="1" fill="white" opacity="0.9"/>
              <rect x="5"  y="8"  width="2" height="8" rx="1" fill="white" opacity="0.7"/>
              <rect x="7"  y="11" width="10" height="2" rx="1" fill="white" opacity="0.6"/>
              <rect x="17" y="8"  width="2" height="8" rx="1" fill="white" opacity="0.7"/>
              <rect x="19" y="10" width="3" height="4" rx="1" fill="white" opacity="0.9"/>
            </svg>
          </div>
          <span style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontWeight: 800,
            fontSize:   "1.1rem",
            letterSpacing: "0.12em",
            color: "#eeeeff",
          }}>Kinetic<span style={{ color: "#8b5cf6" }}>AI</span></span>
        </div>

        {/* Nav links */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
          {NAV_ITEMS.map(item => (
            <NavLink key={item.to} to={item.to} style={({ isActive }) => ({
              fontFamily:    "'Barlow Condensed', sans-serif",
              fontWeight:    600,
              fontSize:      "0.8rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              textDecoration: "none",
              padding:       "0.35rem 0.75rem",
              borderRadius:  "6px",
              color:         isActive ? "#a78bfa" : "#6b6b8f",
              background:    isActive ? "rgba(109,40,217,0.12)" : "transparent",
              transition:    "all 0.15s",
            })}>
              {item.label}
            </NavLink>
          ))}
        </div>

        {/* User + profile */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span style={{
            fontSize:   "0.75rem",
            color:      "#6b6b8f",
            fontFamily: "'DM Sans', sans-serif",
          }}>
            {user?.username}
          </span>
          <button onClick={() => navigate("/profile")} style={{
            background:    "transparent",
            border:        "1px solid #1e1e35",
            borderRadius:  "6px",
            color:         "#6b6b8f",
            fontSize:      "0.7rem",
            fontFamily:    "'Barlow Condensed', sans-serif",
            fontWeight:    600,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            padding:       "0.3rem 0.7rem",
            cursor:        "pointer",
            transition:    "all 0.15s",
          }}
          onMouseEnter={e => { e.target.style.borderColor = "#6d28d9"; e.target.style.color = "#a78bfa"; }}
          onMouseLeave={e => { e.target.style.borderColor = "#1e1e35"; e.target.style.color = "#6b6b8f"; }}>
            Profile
          </button>
        </div>
      </div>
    </nav>
  );
}
