import { useState } from "react";

const INTENSITY_COLOR = { low:"#22c55e", moderate:"#f59e0b", high:"#ef4444" };

function formatDate(iso) {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric"
  });
}

function daysAgo(iso) {
  const diff = Math.round((Date.now() - new Date(iso + "T12:00:00")) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return `${diff}d ago`;
}

function ExerciseRow({ primary, extraPrimaries = [], secondaries = [] }) {
  const allMuscles = [
    { muscle: primary.muscle_group, intensity: "primary" },
    ...extraPrimaries.map(s => ({ muscle: s.muscle_group, intensity: "primary" })),
    ...secondaries.map(s => ({ muscle: s.muscle_group, intensity: "secondary" })),
  ];
  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"0.5rem 0.75rem", background:"#151525", borderRadius:"6px" }}>
      <div style={{ display:"flex", flexDirection:"column", gap:"0.2rem", minWidth:0 }}>
        <span style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.8rem", color:"#c8c8e8" }}>
          {primary.name}
        </span>
        <div style={{ display:"flex", flexWrap:"wrap", gap:"0.25rem" }}>
          {allMuscles.map(({ muscle, intensity }) => (
            <span key={muscle} style={{
              fontSize:"0.6rem", fontFamily:"'DM Sans',sans-serif", textTransform:"capitalize",
              color: intensity === "primary" ? "#a78bfa" : "#f59e0b",
              background: intensity === "primary" ? "rgba(109,40,217,0.1)" : "rgba(245,158,11,0.08)",
              border: `1px solid ${intensity === "primary" ? "rgba(109,40,217,0.2)" : "rgba(245,158,11,0.25)"}`,
              borderRadius:"4px", padding:"0.05rem 0.35rem",
            }}>
              {muscle?.replace(/_/g," ")}
            </span>
          ))}
        </div>
      </div>
      <div style={{ display:"flex", gap:"1.25rem", flexShrink:0 }}>
        {[[primary.sets,32],[primary.reps,32],[primary.weight_lbs > 0 ? `${primary.weight_lbs} lbs` : "BW",60]].map(([val,w], i) => (
          <div key={i} style={{ width:w, textAlign:"right" }}>
            <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.9rem", color:"#eeeeff", display:"block", lineHeight:1 }}>{val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConfirmModal({ onConfirm, onCancel }) {
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.6)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:100 }}>
      <div style={{ background:"#0f0f1a", border:"1px solid #2a2a45", borderRadius:"0.75rem", padding:"1.75rem 2rem", maxWidth:380, width:"90%", textAlign:"center" }}>
        <div style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"1.2rem", color:"#eeeeff", marginBottom:"0.5rem" }}>Delete Workout?</div>
        <p style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.8rem", color:"#6b6b8f", margin:"0 0 1.5rem" }}>This action cannot be undone.</p>
        <div style={{ display:"flex", gap:"0.75rem", justifyContent:"center" }}>
          <button onClick={onCancel}
            style={{ background:"transparent", border:"1px solid #1e1e35", borderRadius:"6px", color:"#6b6b8f", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.75rem", letterSpacing:"0.1em", textTransform:"uppercase", padding:"0.55rem 1.25rem", cursor:"pointer" }}>
            Cancel
          </button>
          <button onClick={onConfirm}
            style={{ background:"rgba(239,68,68,0.12)", border:"1px solid rgba(239,68,68,0.3)", borderRadius:"6px", color:"#ef4444", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.75rem", letterSpacing:"0.1em", textTransform:"uppercase", padding:"0.55rem 1.25rem", cursor:"pointer" }}>
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// onDelete is optional — omit it to hide the trash button (e.g. on Dashboard)
export default function WorkoutCard({ workout, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const allExercises = workout.exercises || [];
  const primaryExercises = allExercises.filter(
    ex => !/\((secondary|primary)\)$/i.test(ex.name)
  );

  const color = INTENSITY_COLOR[workout.intensity] || "#6b6b8f";
  const muscles = [...new Set(
    primaryExercises.map(ex => ex.muscle_group?.replace(/_/g," "))
  )].filter(Boolean);

  return (
    <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", overflow:"hidden", transition:"border-color 0.15s" }}
      onMouseEnter={e => e.currentTarget.style.borderColor = "#2a2a45"}
      onMouseLeave={e => e.currentTarget.style.borderColor = "#1e1e35"}>

      {/* Header row */}
      <div style={{ display:"flex", alignItems:"center", padding:"1rem 1.25rem", gap:"1rem" }}>
        <button onClick={() => setExpanded(v => !v)}
          style={{ flex:1, background:"transparent", border:"none", cursor:"pointer", padding:0, display:"flex", alignItems:"center", gap:"1rem", textAlign:"left" }}>

          {/* Chevron */}
          <div style={{ flexShrink:0, width:20, height:20, display:"flex", alignItems:"center", justifyContent:"center", transition:"transform 0.2s", transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}>
            <svg viewBox="0 0 8 12" fill="none" width="8" height="12">
              <path d="M1 1l5 5-5 5" stroke="#3a3a5c" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>

          {/* Date + time ago */}
          <div style={{ minWidth:160 }}>
            <div style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.95rem", color:"#eeeeff", letterSpacing:"0.03em" }}>
              {formatDate(workout.date)}
            </div>
            <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.68rem", color:"#3a3a5c", marginTop:"0.1rem" }}>
              {daysAgo(workout.date)}
            </div>
          </div>

          {/* Muscle tags */}
          <div style={{ flex:1, display:"flex", flexWrap:"wrap", gap:"0.3rem" }}>
            {muscles.slice(0,5).map(m => (
              <span key={m} style={{ fontSize:"0.62rem", color:"#a78bfa", background:"rgba(109,40,217,0.1)", border:"1px solid rgba(109,40,217,0.2)", borderRadius:"4px", padding:"0.1rem 0.4rem", fontFamily:"'DM Sans',sans-serif", textTransform:"capitalize" }}>
                {m}
              </span>
            ))}
            {muscles.length > 5 && (
              <span style={{ fontSize:"0.62rem", color:"#3a3a5c", fontFamily:"'DM Sans',sans-serif" }}>+{muscles.length - 5} more</span>
            )}
          </div>

          {/* Stats */}
          <div style={{ display:"flex", alignItems:"center", gap:"1.25rem", flexShrink:0 }}>
            <div style={{ textAlign:"right" }}>
              <div style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"1rem", color:"#eeeeff", lineHeight:1 }}>{workout.duration_mins}</div>
              <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.6rem", color:"#3a3a5c" }}>min</div>
            </div>
            <div style={{ textAlign:"right" }}>
              <div style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"1rem", color:"#eeeeff", lineHeight:1 }}>{primaryExercises.length}</div>
              <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.6rem", color:"#3a3a5c" }}>exercises</div>
            </div>
            <span style={{ fontSize:"0.62rem", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, letterSpacing:"0.12em", textTransform:"uppercase", color, background:`${color}15`, border:`1px solid ${color}33`, borderRadius:"4px", padding:"0.15rem 0.5rem" }}>
              {workout.intensity}
            </span>
          </div>
        </button>

        {/* Trash button — only shown when onDelete is provided */}
        {onDelete && (
          <button onClick={() => setConfirming(true)}
            style={{ flexShrink:0, background:"transparent", border:"none", cursor:"pointer", padding:"0.25rem", color:"#3a3a5c", transition:"color 0.15s" }}
            onMouseEnter={e => e.currentTarget.style.color="#ef4444"}
            onMouseLeave={e => e.currentTarget.style.color="#3a3a5c"}>
            <svg viewBox="0 0 16 16" fill="none" width="15" height="15">
              <path d="M2 4h12M5 4V2.5A.5.5 0 0 1 5.5 2h5a.5.5 0 0 1 .5.5V4M6 7v5M10 7v5M3 4l1 9.5A.5.5 0 0 0 4.5 14h7a.5.5 0 0 0 .5-.5L13 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        )}
      </div>

      {confirming && <ConfirmModal onConfirm={() => { setConfirming(false); onDelete(workout.id); }} onCancel={() => setConfirming(false)} />}

      {/* Expanded detail */}
      <div style={{
        maxHeight: expanded ? "1000px" : "0",
        overflow: "hidden",
        transition: "max-height 0.5s ease",
      }}>
        <div style={{ borderTop:"1px solid #1e1e35", padding:"1rem 1.25rem", display:"flex", flexDirection:"column", gap:"0.4rem" }}>
          {/* Notes */}
          {workout.notes && (
            <div style={{ marginBottom:"0.5rem" }}>
              <div style={{ padding:"0 0.75rem", marginBottom:"0.25rem" }}>
                <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontSize:"0.65rem", fontWeight:700, letterSpacing:"0.12em", textTransform:"uppercase", color:"#3a3a5c" }}>Notes</span>
              </div>
              <div style={{ background:"rgba(109,40,217,0.05)", border:"1px solid rgba(109,40,217,0.12)", borderRadius:"6px", padding:"0.6rem 0.75rem" }}>
                <p style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.75rem", color:"#6b6b8f", margin:0, fontStyle:"italic" }}>
                  "{workout.notes}"
                </p>
              </div>
            </div>
          )}

          {/* Column headers */}
          <div style={{ display:"flex", justifyContent:"space-between", padding:"0 0.75rem", marginBottom:"0.25rem" }}>
            <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontSize:"0.65rem", fontWeight:700, letterSpacing:"0.12em", textTransform:"uppercase", color:"#3a3a5c" }}>Exercise</span>
            <div style={{ display:"flex", gap:"1.25rem" }}>
              {[["Sets",32],["Reps",32],["Weight",60]].map(([h,w]) => (
                <span key={h} style={{ fontFamily:"'Barlow Condensed',sans-serif", fontSize:"0.65rem", fontWeight:700, letterSpacing:"0.12em", textTransform:"uppercase", color:"#3a3a5c", width:w, textAlign:"right", display:"inline-block" }}>{h}</span>
              ))}
            </div>
          </div>

          {/* Exercise rows */}
          {primaryExercises.map((ex, i) => {
            const baseName = ex.name.trim();
            const extraPrimaries = allExercises.filter(s =>
              /\(primary\)$/i.test(s.name) &&
              s.name.replace(/\s*\(primary\)$/i, "").trim() === baseName
            );
            const secondaries = allExercises.filter(s =>
              /\(secondary\)$/i.test(s.name) &&
              s.name.replace(/\s*\(secondary\)$/i, "").trim() === baseName
            );
            return <ExerciseRow key={i} primary={ex} extraPrimaries={extraPrimaries} secondaries={secondaries} />;
          })}
        </div>
      </div>
    </div>
  );
}
