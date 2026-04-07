import { useState, useMemo } from "react";
import { useFetch, apiCall } from "../hooks/useFetch";
import Layout from "../components/Layout";
import WorkoutCard from "../components/WorkoutCard";

function SectionHeading({ label }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:"0.6rem", marginBottom:"1rem" }}>
      <div style={{ width:3, height:18, borderRadius:2, background:"linear-gradient(to bottom,#8b5cf6,#6d28d9)" }} />
      <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.75rem", letterSpacing:"0.18em", textTransform:"uppercase", color:"#6b6b8f" }}>
        {label}
      </span>
    </div>
  );
}

function Label({ children }) {
  return (
    <div style={{ fontSize:"0.65rem", letterSpacing:"0.15em", textTransform:"uppercase", color:"#6b6b8f", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, marginBottom:"0.35rem" }}>
      {children}
    </div>
  );
}

function Shimmer() {
  return (
    <>
      {[...Array(5)].map((_,i) => (
        <div key={i} style={{ height:72, background:"linear-gradient(90deg,#0f0f1a 25%,#151525 50%,#0f0f1a 75%)", backgroundSize:"200% 100%", animation:"shimmer 1.5s infinite", borderRadius:"0.75rem" }} />
      ))}
      <style>{`@keyframes shimmer{0%{background-position:200% center}100%{background-position:-200% center}}`}</style>
    </>
  );
}

export default function History() {
  const { data: workouts, loading, error, refetch } = useFetch("/workouts/");

  const [startDate, setStartDate] = useState("");
  const [endDate,   setEndDate]   = useState("");

  async function handleDelete(id) {
    await apiCall(`/workouts/${id}`, "DELETE");
    refetch();
  }

  const filtered = useMemo(() => {
    if (!workouts) return [];
    return workouts.filter(w => {
      if (startDate && w.date < startDate) return false;
      if (endDate   && w.date > endDate)   return false;
      return true;
    });
  }, [workouts, startDate, endDate]);

  const totalMins = filtered.reduce((a, w) => a + w.duration_mins, 0);
  const intensityCounts = filtered.reduce((acc, w) => {
    acc[w.intensity] = (acc[w.intensity] || 0) + 1; return acc;
  }, {});

  return (
    <Layout>
      {/* Header */}
      <div className="animate-fade-up" style={{ marginBottom:"2rem" }}>
        <p style={{ fontSize:"0.7rem", letterSpacing:"0.2em", textTransform:"uppercase", color:"#8b5cf6", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:600, marginBottom:"0.2rem" }}>
          KineticAI
        </p>
        <h1 style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"2.25rem", color:"#eeeeff", letterSpacing:"0.04em", lineHeight:1, margin:0 }}>
          WORKOUT HISTORY
        </h1>
      </div>

      {/* Filters + stats row */}
      <div style={{ display:"flex", gap:"1.25rem", marginBottom:"1.5rem", flexWrap:"wrap", alignItems:"stretch" }}>

        {/* Date range filters */}
        <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1rem 1.25rem", display:"flex", gap:"1rem", alignItems:"flex-end", flexWrap:"wrap" }}>
          <div>
            <Label>From</Label>
            <input type="date" className="input-field"
              value={startDate} onChange={e => setStartDate(e.target.value)}
              style={{ width:160, colorScheme:"dark" }} />
          </div>
          <div>
            <Label>To</Label>
            <input type="date" className="input-field"
              value={endDate} onChange={e => setEndDate(e.target.value)}
              style={{ width:160, colorScheme:"dark" }} />
          </div>
          {(startDate || endDate) && (
            <button onClick={() => { setStartDate(""); setEndDate(""); }}
              style={{ background:"transparent", border:"1px solid #1e1e35", borderRadius:"6px", color:"#6b6b8f", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.7rem", letterSpacing:"0.1em", textTransform:"uppercase", padding:"0.5rem 0.75rem", cursor:"pointer", transition:"all 0.15s" }}
              onMouseEnter={e => { e.currentTarget.style.borderColor="#6d28d9"; e.currentTarget.style.color="#a78bfa"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor="#1e1e35"; e.currentTarget.style.color="#6b6b8f"; }}>
              Clear
            </button>
          )}
        </div>

        {/* Summary stats */}
        {!loading && filtered.length > 0 && (
          <div style={{ display:"flex", gap:"0.75rem", flex:1, flexWrap:"wrap", alignItems:"stretch" }}>
            {[
              [filtered.length, "Workouts"],
              [`${Math.round(totalMins / 60)}h ${totalMins % 60}m`, "Total Time"],
              [intensityCounts.high    || 0, "High Intensity"],
              [intensityCounts.moderate || 0, "Moderate Intensity"],
              [intensityCounts.low     || 0, "Low Intensity"],
            ].map(([val, label]) => (
              <div key={label} style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"0.75rem 1rem", textAlign:"center", flex:"1 1 0", minWidth:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center" }}>
                <div style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"1.4rem", color:"#eeeeff", lineHeight:1 }}>{val}</div>
                <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.62rem", color:"#3a3a5c", marginTop:"0.2rem" }}>{label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Workout list */}
      <div>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"1rem" }}>
          <SectionHeading label={
            startDate || endDate
              ? `${filtered.length} workout${filtered.length !== 1 ? "s" : ""} in range`
              : `All workouts (${filtered.length})`
          } />
        </div>

        {loading ? (
          <div style={{ display:"flex", flexDirection:"column", gap:"0.65rem" }}><Shimmer /></div>
        ) : error ? (
          <div style={{ background:"rgba(239,68,68,0.08)", border:"1px solid rgba(239,68,68,0.2)", borderRadius:"0.75rem", padding:"1.25rem", textAlign:"center" }}>
            <p style={{ color:"#ef4444", fontFamily:"'DM Sans',sans-serif", fontSize:"0.8rem", margin:0 }}>{error}</p>
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ background:"#0f0f1a", border:"1px dashed #1e1e35", borderRadius:"0.75rem", padding:"3rem", textAlign:"center" }}>
            <p style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"1.1rem", color:"#2a2a45", margin:0, letterSpacing:"0.05em" }}>
              {workouts?.length === 0 ? "No workouts logged yet." : "No workouts in this date range."}
            </p>
            {workouts?.length === 0 && (
              <a href="/log" style={{ display:"inline-block", marginTop:"0.75rem", fontSize:"0.75rem", color:"#6d28d9", fontFamily:"'DM Sans',sans-serif", textDecoration:"none" }}
                onMouseEnter={e => e.target.style.color="#a78bfa"}
                onMouseLeave={e => e.target.style.color="#6d28d9"}>
                Log your first workout →
              </a>
            )}
          </div>
        ) : (
          <div style={{ display:"flex", flexDirection:"column", gap:"0.65rem" }}>
            {filtered.map(w => <WorkoutCard key={w.id} workout={w} onDelete={handleDelete} />)}
          </div>
        )}
      </div>
    </Layout>
  );
}
