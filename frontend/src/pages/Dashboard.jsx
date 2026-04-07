import { useFetch } from "../hooks/useFetch";
import { useAuth } from "../context/AuthContext";
import Layout from "../components/Layout";
import WorkoutCard from "../components/WorkoutCard";

function gradeColor(grade) {
  return { A: "#22c55e", B: "#a78bfa", C: "#f59e0b", D: "#f97316", F: "#ef4444" }[grade] || "#6b6b8f";
}
function fatigueColor(c) {
  return c === "red" ? "#ef4444" : c === "yellow" ? "#f59e0b" : "#22c55e";
}
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

function StatCard({ label, value, sub, color }) {
  return (
    <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1.25rem 1.5rem", flex:1, minWidth:0 }}>
      <div style={{ fontSize:"0.65rem", letterSpacing:"0.18em", textTransform:"uppercase", color:"#6b6b8f", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:600, marginBottom:"0.5rem" }}>
        {label}
      </div>
      <div style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"2.2rem", color:color||"#eeeeff", lineHeight:1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize:"0.7rem", color:"#3a3a5c", marginTop:"0.3rem", fontFamily:"'DM Sans',sans-serif" }}>{sub}</div>}
    </div>
  );
}

function ScoreRing({ score, grade }) {
  const r = 52, circ = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, score || 0));
  const color = gradeColor(grade);
  return (
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:"0.5rem" }}>
      <div style={{ position:"relative", width:128, height:128 }}>
        <svg width="128" height="128" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r={r} fill="none" stroke="#1e1e35" strokeWidth="8" />
          <circle cx="64" cy="64" r={r} fill="none" stroke={color} strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${(pct/100)*circ} ${circ}`}
            transform="rotate(-90 64 64)"
            style={{ filter:`drop-shadow(0 0 6px ${color}88)`, transition:"stroke-dasharray 1s ease" }} />
        </svg>
        <div style={{ position:"absolute", inset:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center" }}>
          <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"2rem", color:"#eeeeff", lineHeight:1 }}>{Math.round(pct)}</span>
          <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.65rem", letterSpacing:"0.15em", color:"#6b6b8f", textTransform:"uppercase" }}>Score</span>
        </div>
      </div>
      <div style={{ background:`${color}18`, border:`1px solid ${color}44`, borderRadius:"6px", padding:"0.2rem 0.75rem", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"1.1rem", color, letterSpacing:"0.05em" }}>
        Grade {grade}
      </div>
    </div>
  );
}

function FatigueGrid({ fatigueMap }) {
  return (
    <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(130px,1fr))", gap:"0.4rem" }}>
      {Object.entries(fatigueMap || {}).map(([muscle, color]) => (
        <div key={muscle} style={{ display:"flex", alignItems:"center", gap:"0.5rem", background:"#151525", border:"1px solid #1e1e35", borderRadius:"6px", padding:"0.4rem 0.65rem" }}>
          <div style={{ width:7, height:7, borderRadius:"50%", background:fatigueColor(color), boxShadow:`0 0 5px ${fatigueColor(color)}88`, flexShrink:0 }} />
          <span style={{ fontSize:"0.7rem", color:"#9999bb", fontFamily:"'DM Sans',sans-serif", textTransform:"capitalize", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
            {muscle.replace(/_/g," ")}
          </span>
        </div>
      ))}
    </div>
  );
}

function SuggestionCard({ name, muscle_groups, reason, priority }) {
  const pc = priority==="high" ? "#ef4444" : priority==="medium" ? "#f59e0b" : "#6b6b8f";
  return (
    <div style={{ background:"#151525", border:"1px solid #1e1e35", borderRadius:"0.65rem", padding:"0.9rem 1rem", display:"flex", flexDirection:"column", gap:"0.4rem" }}
      onMouseEnter={e=>e.currentTarget.style.borderColor="#3d1f7a"}
      onMouseLeave={e=>e.currentTarget.style.borderColor="#1e1e35"}>
      <div style={{ display:"flex", alignItems:"center", gap:"0.5rem" }}>
        <span style={{ fontSize:"0.58rem", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, letterSpacing:"0.15em", textTransform:"uppercase", color:pc, background:`${pc}15`, border:`1px solid ${pc}33`, borderRadius:"4px", padding:"0.1rem 0.35rem", flexShrink:0 }}>{priority}</span>
        <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.9rem", color:"#eeeeff" }}>{name}</span>
      </div>
      <p style={{ fontSize:"0.72rem", color:"#6b6b8f", fontFamily:"'DM Sans',sans-serif", margin:0, lineHeight:1.5 }}>{reason}</p>
      {muscle_groups.length > 0 && (
        <div style={{ display:"flex", flexWrap:"wrap", gap:"0.25rem" }}>
          {muscle_groups.map(m=>(
            <span key={m} style={{ fontSize:"0.62rem", color:"#a78bfa", background:"rgba(109,40,217,0.1)", border:"1px solid rgba(109,40,217,0.2)", borderRadius:"4px", padding:"0.1rem 0.35rem", fontFamily:"'DM Sans',sans-serif", textTransform:"capitalize" }}>
              {m.replace(/_/g," ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Shimmer() {
  return (
    <>
      {[...Array(3)].map((_,i)=>(
        <div key={i} style={{ height:52, background:"linear-gradient(90deg,#0f0f1a 25%,#151525 50%,#0f0f1a 75%)", backgroundSize:"200% 100%", animation:"shimmer 1.5s infinite", borderRadius:"0.5rem", marginBottom:"0.5rem" }} />
      ))}
      <style>{`@keyframes shimmer{0%{background-position:200% center}100%{background-position:-200% center}}`}</style>
    </>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data: workouts,   loading: wLoad } = useFetch("/workouts/");
  const { data: evaluation, loading: eLoad } = useFetch("/evaluation/");
  const { data: fatigue,    loading: fLoad } = useFetch("/fatigue/");

  const allWorkouts = workouts || [];
  const cutoff = new Date(Date.now() - 7*86400000);
  const thisWeek = allWorkouts.filter(w => new Date(w.date) >= cutoff);
  const restDays = 7 - new Set(thisWeek.map(w=>w.date)).size;
  const suggestions = evaluation?.suggestions || [];

  return (
    <Layout>
      {/* Header */}
      <div className="animate-fade-up" style={{ marginBottom:"2rem" }}>
        <p style={{ fontSize:"0.7rem", letterSpacing:"0.2em", textTransform:"uppercase", color:"#8b5cf6", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:600, marginBottom:"0.2rem" }}>
          Welcome back
        </p>
        <h1 style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"2.25rem", color:"#eeeeff", letterSpacing:"0.04em", lineHeight:1, margin:0 }}>
          {user?.username?.toUpperCase()}
        </h1>
      </div>

      {/* Row 1: Score + Stats */}
      <div style={{ display:"flex", gap:"1.25rem", marginBottom:"1.5rem", flexWrap:"wrap" }}>
        <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1.5rem", display:"flex", alignItems:"center", justifyContent:"center", minWidth:180 }}>
          {eLoad
            ? <div style={{ width:128, height:128, display:"flex", alignItems:"center", justifyContent:"center" }}><div style={{ width:24, height:24, border:"2px solid #6d28d9", borderTopColor:"transparent", borderRadius:"50%", animation:"spin 0.7s linear infinite" }} /><style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style></div>
            : <ScoreRing score={evaluation?.overall_score} grade={evaluation?.grade} />
          }
        </div>
        <div style={{ display:"flex", gap:"1rem", flex:1, flexWrap:"wrap" }}>
          <StatCard label="Total Workouts" value={allWorkouts.length} sub="all time" />
          <StatCard label="This Week" value={thisWeek.length} sub="sessions logged" color="#8b5cf6" />
          <StatCard label="Rest Days" value={restDays} sub="this week" color={restDays>=2?"#22c55e":restDays===1?"#f59e0b":"#ef4444"} />
        </div>
      </div>

      {/* Row 2: Fatigue + Suggestions */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"1.25rem", marginBottom:"1.5rem" }}>
        <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1.25rem" }}>
          <SectionHeading label="Muscle Fatigue" />
          <div style={{ display:"flex", gap:"1rem", marginBottom:"0.75rem" }}>
            {[["red","Needs Rest"],["yellow","Ready Soon"],["green","Ready"]].map(([c,l])=>(
              <div key={c} style={{ display:"flex", alignItems:"center", gap:"0.3rem" }}>
                <div style={{ width:6, height:6, borderRadius:"50%", background:fatigueColor(c) }} />
                <span style={{ fontSize:"0.62rem", color:"#3a3a5c", fontFamily:"'DM Sans',sans-serif" }}>{l}</span>
              </div>
            ))}
          </div>
          {/* 3D model placeholder */}
          <div style={{ background:"rgba(109,40,217,0.04)", border:"1px dashed #2a2a45", borderRadius:"0.5rem", height:72, display:"flex", alignItems:"center", justifyContent:"center", marginBottom:"0.75rem" }}>
            <span style={{ fontSize:"0.65rem", color:"#2a2a45", fontFamily:"'Barlow Condensed',sans-serif", letterSpacing:"0.12em", fontWeight:600 }}>3D MODEL — COMING SOON</span>
          </div>
          {fLoad ? <Shimmer /> : <FatigueGrid fatigueMap={fatigue} />}
        </div>

        <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1.25rem" }}>
          <SectionHeading label="Suggested Workouts" />
          {eLoad ? <Shimmer /> : suggestions.length === 0
            ? <p style={{ fontSize:"0.8rem", color:"#3a3a5c", fontFamily:"'DM Sans',sans-serif" }}>Log some workouts to get personalised suggestions.</p>
            : <div style={{ display:"flex", flexDirection:"column", gap:"0.65rem" }}>{suggestions.map((s,i)=><SuggestionCard key={i} {...s} />)}</div>
          }
        </div>
      </div>

      {/* Row 3: Recent Workouts */}
      <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1.25rem" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"1rem" }}>
          <SectionHeading label="Recent Workouts" />
          {allWorkouts.length > thisWeek.length && (
            <a href="/history" style={{ fontSize:"0.7rem", color:"#6d28d9", fontFamily:"'DM Sans',sans-serif", textDecoration:"none" }}
               onMouseEnter={e=>e.target.style.color="#a78bfa"} onMouseLeave={e=>e.target.style.color="#6d28d9"}>
              View all →
            </a>
          )}
        </div>
        {wLoad ? <Shimmer /> : thisWeek.length === 0
          ? <div style={{ textAlign:"center", padding:"2rem", color:"#3a3a5c", fontSize:"0.8rem", fontFamily:"'DM Sans',sans-serif" }}>
              {allWorkouts.length === 0
                ? <><span>No workouts yet. </span><a href="/log" style={{ color:"#6d28d9", textDecoration:"none" }}>Log your first workout →</a></>
                : "No workouts in the past 7 days."}
            </div>
          : <div style={{ display:"flex", flexDirection:"column", gap:"0.5rem" }}>
              {thisWeek.map(w=><WorkoutCard key={w.id} workout={w} />)}
            </div>
        }
      </div>
    </Layout>
  );
}
