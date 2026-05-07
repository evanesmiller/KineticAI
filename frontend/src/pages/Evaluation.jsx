import { useState } from "react";
import { useFetch, apiCall } from "../hooks/useFetch";
import Layout from "../components/Layout";

// ── Helpers ────────────────────────────────────────────────────────────────
function gradeColor(grade) {
  return { A:"#22c55e", B:"#a78bfa", C:"#f59e0b", D:"#f97316", F:"#ef4444" }[grade] || "#6b6b8f";
}
function scoreColor(score) {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#f59e0b";
  return "#ef4444";
}
function priorityColor(p) {
  return p === "high" ? "#ef4444" : p === "medium" ? "#f59e0b" : "#6b6b8f";
}
function trendColor(t) {
  return t === "progressing" ? "#22c55e" : t === "stagnating" ? "#f59e0b" : t === "regressing" ? "#ef4444" : "#3a3a5c";
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

function Card({ children, style, ...props }) {
  return (
    <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1.25rem", ...style }} {...props}>
      {children}
    </div>
  );
}

// ── Score ring ─────────────────────────────────────────────────────────────
function ScoreRing({ score, grade, size = 160 }) {
  const r    = size * 0.4;
  const circ = 2 * Math.PI * r;
  const pct  = Math.min(100, Math.max(0, score || 0));
  const color = gradeColor(grade);
  const cx = size / 2;

  return (
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:"0.75rem" }}>
      <div style={{ position:"relative", width:size, height:size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={cx} cy={cx} r={r} fill="none" stroke="#1e1e35" strokeWidth="10" />
          <circle cx={cx} cy={cx} r={r} fill="none" stroke={color} strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={`${(pct/100)*circ} ${circ}`}
            transform={`rotate(-90 ${cx} ${cx})`}
            style={{ filter:`drop-shadow(0 0 8px ${color}88)`, transition:"stroke-dasharray 1.2s ease" }} />
        </svg>
        <div style={{ position:"absolute", inset:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center" }}>
          <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"2.6rem", color:"#eeeeff", lineHeight:1 }}>
            {Math.round(pct)}
          </span>
          <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:600, fontSize:"0.65rem", letterSpacing:"0.18em", color:"#6b6b8f", textTransform:"uppercase" }}>
            /100
          </span>
        </div>
      </div>
      <div style={{ background:`${color}18`, border:`1px solid ${color}44`, borderRadius:"8px", padding:"0.3rem 1.25rem", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"1.4rem", color, letterSpacing:"0.08em" }}>
        Grade {grade}
      </div>
    </div>
  );
}

// ── Mini score bar ─────────────────────────────────────────────────────────
function ScoreBar({ score }) {
  const color = scoreColor(score);
  return (
    <div style={{ display:"flex", alignItems:"center", gap:"0.75rem" }}>
      <div style={{ flex:1, height:5, background:"#1e1e35", borderRadius:3, overflow:"hidden" }}>
        <div style={{ height:"100%", width:`${score}%`, background:color, borderRadius:3, transition:"width 1s ease", boxShadow:`0 0 6px ${color}66` }} />
      </div>
      <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"0.9rem", color, minWidth:36, textAlign:"right" }}>
        {Math.round(score)}
      </span>
    </div>
  );
}

// ── Category card ──────────────────────────────────────────────────────────
function CategoryCard({ name, score, findings }) {
  const icons = { balance:"⚖", consistency:"📅", rest:"😴", volume:"📊" };
  return (
    <Card style={{ transition:"border-color 0.15s" }}
      onMouseEnter={e=>e.currentTarget.style.borderColor="#3d1f7a"}
      onMouseLeave={e=>e.currentTarget.style.borderColor="#1e1e35"}>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"0.75rem" }}>
        <div style={{ display:"flex", alignItems:"center", gap:"0.5rem" }}>
          <span style={{ fontSize:"1rem" }}>{icons[name]}</span>
          <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.85rem", letterSpacing:"0.1em", textTransform:"uppercase", color:"#eeeeff" }}>
            {name}
          </span>
        </div>
      </div>
      <ScoreBar score={score} />
      <div style={{ marginTop:"0.85rem", display:"flex", flexDirection:"column", gap:"0.4rem" }}>
        {(findings || []).map((f, i) => (
          <div key={i} style={{ display:"flex", gap:"0.5rem", alignItems:"flex-start" }}>
            <span style={{ color: f.includes("✓") ? "#22c55e" : "#6d28d9", fontSize:"0.7rem", marginTop:"0.1rem", flexShrink:0 }}>
              {f.includes("✓") ? "✓" : "•"}
            </span>
            <p style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.75rem", color: f.includes("✓") ? "#6b6b8f" : "#9999bb", margin:0, lineHeight:1.6 }}>
              {f.replace(" ✓", "")}
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Suggestion card ────────────────────────────────────────────────────────
function SuggestionCard({ name, muscle_groups, reason, priority }) {
  const pc = priorityColor(priority);
  return (
    <div style={{ background:"#151525", border:"1px solid #1e1e35", borderRadius:"0.65rem", padding:"1rem 1.1rem", display:"flex", flexDirection:"column", gap:"0.45rem", transition:"border-color 0.15s" }}
      onMouseEnter={e=>e.currentTarget.style.borderColor="#3d1f7a"}
      onMouseLeave={e=>e.currentTarget.style.borderColor="#1e1e35"}>
      <div style={{ display:"flex", alignItems:"center", gap:"0.5rem" }}>
        <span style={{ fontSize:"0.58rem", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, letterSpacing:"0.15em", textTransform:"uppercase", color:pc, background:`${pc}15`, border:`1px solid ${pc}33`, borderRadius:"4px", padding:"0.1rem 0.4rem", flexShrink:0 }}>
          {priority}
        </span>
        <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.95rem", color:"#eeeeff" }}>{name}</span>
      </div>
      <p style={{ fontSize:"0.73rem", color:"#6b6b8f", fontFamily:"'DM Sans',sans-serif", margin:0, lineHeight:1.55 }}>{reason}</p>
      {muscle_groups?.length > 0 && (
        <div style={{ display:"flex", flexWrap:"wrap", gap:"0.25rem" }}>
          {muscle_groups.map(m => (
            <span key={m} style={{ fontSize:"0.62rem", color:"#a78bfa", background:"rgba(109,40,217,0.1)", border:"1px solid rgba(109,40,217,0.2)", borderRadius:"4px", padding:"0.1rem 0.35rem", fontFamily:"'DM Sans',sans-serif", textTransform:"capitalize" }}>
              {m.replace(/_/g," ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Progressive overload grid ──────────────────────────────────────────────
const OVERLOAD_FILTERS = [
  { key:"progressing", label:"Progressing", hex:"#22c55e" },
  { key:"stagnating",  label:"Stagnating",  hex:"#f59e0b" },
  { key:"regressing",  label:"Regressing",  hex:"#ef4444" },
  { key:"new",         label:"New",         hex:"#6b6b8f" },
];
const PRIORITY_ORDER = { progressing:0, stagnating:1, regressing:2, new:3 };

function OverloadGrid({ statuses }) {
  const [hiddenTrends, setHiddenTrends] = useState(new Set());

  if (!statuses?.length) return (
    <p style={{ fontSize:"0.75rem", color:"#3a3a5c", fontFamily:"'DM Sans',sans-serif" }}>Not enough history to assess overload yet.</p>
  );

  function toggleTrend(trend) {
    setHiddenTrends(prev => {
      const next = new Set(prev);
      next.has(trend) ? next.delete(trend) : next.add(trend);
      return next;
    });
  }

  const visible = [...statuses]
    .filter(s => !hiddenTrends.has(s.trend))
    .sort((a, b) => (PRIORITY_ORDER[a.trend] ?? 4) - (PRIORITY_ORDER[b.trend] ?? 4));

  const rowCount = hiddenTrends.size === 0 ? 4 : (visible.length % 3 === 0 ? 3 : 2);

  return (
    <div>
      <div style={{ display:"grid", gridTemplateRows:`repeat(${rowCount},auto)`, gridAutoFlow:"column", gridAutoColumns:"1fr", gap:"0.5rem", marginBottom:"1rem" }}>
        {visible.map((s, i) => {
          const color = trendColor(s.trend);
          const pctLabel = s.pct_change !== null
            ? `${s.pct_change >= 0 ? "+" : ""}${s.pct_change}% since first logged`
            : s.exercise_name
              ? "log again to track progression"
              : "not logged yet";
          return (
            <div key={i} style={{ background:"#151525", borderRadius:"6px", padding:"0.55rem 0.75rem", borderLeft:`3px solid ${color}33`, borderTop:`1px solid #1e1e35`, borderRight:`1px solid #1e1e35`, borderBottom:`1px solid #1e1e35` }}>
              <div style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.82rem", color:"#eeeeff", textTransform:"capitalize", marginBottom:"0.1rem" }}>
                {s.muscle.replace(/_/g," ")}
              </div>
              {s.exercise_name && (
                <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.67rem", color:"#6b6b8f", marginBottom:"0.15rem", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
                  {s.exercise_name}
                </div>
              )}
              {s.first_weight != null && s.peak_weight != null && s.pct_change !== null && (
                <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:"0.63rem", color:"#6b6b8f" }}>
                  {s.first_weight} → {s.peak_weight} lbs
                </div>
              )}
              <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.65rem", color, marginTop:"0.2rem", lineHeight:1.3 }}>
                {pctLabel}
              </div>
            </div>
          );
        })}
      </div>

      {/* Filter legend */}
      <div style={{ display:"flex", gap:"1rem", flexWrap:"wrap", justifyContent:"center", paddingTop:"0.75rem" }}>
        {OVERLOAD_FILTERS.map(({ key, label, hex }) => {
          const count = statuses.filter(s => s.trend === key).length;
          if (!count) return null;
          const hidden = hiddenTrends.has(key);
          return (
            <div key={key} onClick={() => toggleTrend(key)}
              style={{ display:"flex", alignItems:"center", gap:"0.35rem", cursor:"pointer", userSelect:"none" }}>
              <div style={{
                width:8, height:8, borderRadius:"50%",
                background: hidden ? "#2a2a45" : hex,
                boxShadow:  hidden ? "none" : `0 0 6px 2px ${hex}`,
                transition: "all 0.2s",
              }} />
              <span style={{
                fontSize:"0.72rem",
                color: hidden ? "#3a3a5c" : "#9999bb",
                fontFamily:"'DM Sans',sans-serif",
                transition:"color 0.2s",
              }}>{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Split detection card ───────────────────────────────────────────────────
function SplitCard({ split }) {
  if (!split) return null;
  const adherence = split.adherence_score || 0;
  const color = adherence >= 80 ? "#22c55e" : adherence >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:"0.75rem" }}>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
        <div>
          <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"1.5rem", color:"#eeeeff", letterSpacing:"0.05em" }}>
            {split.detected_split}
          </span>
          <span style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.72rem", color:"#6b6b8f", marginLeft:"0.5rem" }}>
            detected split
          </span>
        </div>
        <div style={{ textAlign:"right" }}>
          <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"1.5rem", color, lineHeight:1 }}>
            {Math.round(adherence)}%
          </span>
          <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.62rem", color:"#3a3a5c" }}>adherence</div>
        </div>
      </div>
      {/* Adherence bar */}
      <div style={{ height:5, background:"#1e1e35", borderRadius:3, overflow:"hidden" }}>
        <div style={{ height:"100%", width:`${adherence}%`, background:color, borderRadius:3, boxShadow:`0 0 6px ${color}66`, transition:"width 1s ease" }} />
      </div>
      {/* Session breakdown */}
      {split.session_breakdown && (
        <div style={{ display:"flex", gap:"0.5rem", flexWrap:"wrap" }}>
          {Object.entries(split.session_breakdown).map(([type, count]) => (
            <div key={type} style={{ background:"#151525", border:"1px solid #1e1e35", borderRadius:"6px", padding:"0.3rem 0.65rem", display:"flex", gap:"0.4rem", alignItems:"center" }}>
              <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"0.9rem", color:"#eeeeff" }}>{count}</span>
              <span style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.65rem", color:"#3a3a5c", textTransform:"capitalize" }}>{type.replace(/_/g," ")}</span>
            </div>
          ))}
        </div>
      )}
      {/* Findings */}
      {split.findings?.map((f,i) => (
        <p key={i} style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.73rem", color:"#6b6b8f", margin:0, lineHeight:1.55 }}>{f}</p>
      ))}
    </div>
  );
}

// ── Shimmer ────────────────────────────────────────────────────────────────
function Shimmer({ height = 120 }) {
  return (
    <div style={{ height, background:"linear-gradient(90deg,#0f0f1a 25%,#151525 50%,#0f0f1a 75%)", backgroundSize:"200% 100%", animation:"shimmer 1.5s infinite", borderRadius:"0.75rem" }}>
      <style>{`@keyframes shimmer{0%{background-position:200% center}100%{background-position:-200% center}}`}</style>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function Evaluation() {
  const { data: fetchedData, loading, error } = useFetch("/evaluation/");
  const [overrideData, setOverrideData] = useState(null);
  const [refreshing, setRefreshing]     = useState(false);
  const data = overrideData ?? fetchedData;

  async function handleForceRefresh() {
    setRefreshing(true);
    try {
      const result = await apiCall("/evaluation/?force=1");
      setOverrideData(result);
    } catch (_) {}
    finally { setRefreshing(false); }
  }

  const categories  = data?.categories  || {};
  const suggestions = data?.suggestions || [];
  const advanced    = data?.advanced    || {};
  const overload    = advanced.progressive_overload || {};
  const split       = advanced.split_detection;
  const recovery    = advanced.recovery_patterns;
  const edgeCases   = advanced.edge_cases;

  return (
    <Layout>
      {/* Header */}
      <div className="animate-fade-up" style={{ marginBottom:"2rem", display:"flex", alignItems:"flex-end", justifyContent:"space-between", flexWrap:"wrap", gap:"1rem" }}>
        <div>
          <p style={{ fontSize:"0.7rem", letterSpacing:"0.2em", textTransform:"uppercase", color:"#8b5cf6", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:600, marginBottom:"0.2rem" }}>
            KineticAI
          </p>
          <h1 style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"2.25rem", color:"#eeeeff", letterSpacing:"0.04em", lineHeight:1, margin:0 }}>
            EVALUATION REPORT
          </h1>
          {data?.evaluation_date && (
            <p style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.72rem", color:"#3a3a5c", margin:"0.35rem 0 0 0" }}>
              Based on past {data.window_days} days · {new Date(data.evaluation_date + "T12:00:00").toLocaleDateString("en-US",{month:"long",day:"numeric",year:"numeric"})}
            </p>
          )}
        </div>
        <button onClick={handleForceRefresh} disabled={loading || refreshing}
          style={{ background:"rgba(109,40,217,0.12)", border:"1px solid rgba(109,40,217,0.3)", borderRadius:"6px", color:"#a78bfa", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.72rem", letterSpacing:"0.12em", textTransform:"uppercase", padding:"0.5rem 1rem", cursor: (loading || refreshing) ? "not-allowed" : "pointer", opacity: (loading || refreshing) ? 0.5 : 1, transition:"all 0.15s" }}
          onMouseEnter={e=>{ if(!loading && !refreshing){ e.currentTarget.style.background="rgba(109,40,217,0.2)"; }}}
          onMouseLeave={e=>{ if(!loading && !refreshing){ e.currentTarget.style.background="rgba(109,40,217,0.12)"; }}}>
          {refreshing ? "Refreshing…" : "↻ Refresh"}
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div style={{ background:"rgba(239,68,68,0.08)", border:"1px solid rgba(239,68,68,0.2)", borderRadius:"0.75rem", padding:"1.25rem", marginBottom:"1.5rem" }}>
          <p style={{ color:"#ef4444", fontFamily:"'DM Sans',sans-serif", fontSize:"0.8rem", margin:0 }}>{error}</p>
        </div>
      )}

      {/* Edge case: new user */}
      {!loading && edgeCases?.is_new_user && (
        <Card style={{ marginBottom:"1.5rem", textAlign:"center", padding:"2rem" }}>
          <p style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"1.1rem", color:"#6d28d9", margin:"0 0 0.5rem 0", letterSpacing:"0.05em" }}>
            Not enough data yet
          </p>
          <p style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.8rem", color:"#6b6b8f", margin:0 }}>
            Log at least 3 workouts to unlock your full AI evaluation report.
          </p>
          <a href="/log" style={{ display:"inline-block", marginTop:"1rem", fontSize:"0.75rem", color:"#6d28d9", fontFamily:"'DM Sans',sans-serif", textDecoration:"none" }}>
            Log a workout →
          </a>
        </Card>
      )}

      {/* ── Row 1: Score ring + narrative ── */}
      <div style={{ display:"grid", gridTemplateColumns:"auto 1fr", gap:"1.25rem", marginBottom:"1.25rem", alignItems:"stretch" }}>
        <Card style={{ display:"flex", alignItems:"center", justifyContent:"center", minWidth:200 }}>
          {loading
            ? <Shimmer height={160} />
            : <ScoreRing score={data?.overall_score} grade={data?.grade} />
          }
        </Card>

        <Card>
          <SectionHeading label="AI Analysis" />
          {loading
            ? <><Shimmer height={18} /><div style={{ height:8 }} /><Shimmer height={18} /><div style={{ height:8 }} /><Shimmer height={18} /></>
            : data?.narrative
              ? <p style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.875rem", color:"#9999bb", lineHeight:1.75, margin:0 }}>
                  {data.narrative}
                </p>
              : <p style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.8rem", color:"#3a3a5c", margin:0 }}>No narrative available.</p>
          }
        </Card>
      </div>

      {/* ── Row 2: Category scores ── */}
      <div style={{ marginBottom:"1.25rem" }}>
        <SectionHeading label="Category Breakdown" />
        <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:"1rem" }}>
          {loading
            ? [...Array(4)].map((_,i) => <Shimmer key={i} height={160} />)
            : ["balance","consistency","rest","volume"].map(cat => (
                <CategoryCard key={cat} name={cat}
                  score={categories[cat]?.score ?? 0}
                  findings={categories[cat]?.findings ?? []} />
              ))
          }
        </div>
      </div>

      {/* ── Row 3: Suggestions ── */}
      <div style={{ marginBottom:"1.25rem" }}>
        <SectionHeading label="Suggested Workouts" />
        {loading
          ? <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:"0.75rem" }}>{[...Array(4)].map((_,i)=><Shimmer key={i} height={100} />)}</div>
          : suggestions.length === 0
            ? <Card><p style={{ color:"#3a3a5c", fontFamily:"'DM Sans',sans-serif", fontSize:"0.8rem", margin:0 }}>No suggestions available yet.</p></Card>
            : <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:"0.75rem" }}>
                {suggestions.map((s,i) => <SuggestionCard key={i} {...s} />)}
              </div>
        }
      </div>

      {/* ── Row 4: Advanced insights ── */}
      <div>
        <SectionHeading label="Advanced Insights" />

        {/* Progressive Overload — full width */}
        <Card style={{ marginBottom:"1.25rem", transition:"border-color 0.15s" }}
          onMouseEnter={e => e.currentTarget.style.borderColor = "#3d1f7a"}
          onMouseLeave={e => e.currentTarget.style.borderColor = "#1e1e35"}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"0.9rem" }}>
            <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.8rem", letterSpacing:"0.1em", textTransform:"uppercase", color:"#eeeeff" }}>
              Progressive Overload
            </span>
            {overload.score !== undefined && (
              <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"0.9rem", color:scoreColor(overload.score) }}>
                {Math.round(overload.score)}/100
              </span>
            )}
          </div>
          {loading ? <Shimmer height={200} /> : <OverloadGrid statuses={overload.muscles} />}
        </Card>

        {/* Training Split + Recovery Patterns — side by side */}
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"1.25rem" }}>
          <Card style={{ transition:"border-color 0.15s" }}
            onMouseEnter={e => e.currentTarget.style.borderColor = "#3d1f7a"}
            onMouseLeave={e => e.currentTarget.style.borderColor = "#1e1e35"}>
            <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.8rem", letterSpacing:"0.1em", textTransform:"uppercase", color:"#eeeeff", display:"block", marginBottom:"0.75rem" }}>
              Training Split
            </span>
            {loading ? <Shimmer height={80} /> : <SplitCard split={split} />}
          </Card>

          <Card style={{ transition:"border-color 0.15s" }}
            onMouseEnter={e => e.currentTarget.style.borderColor = "#3d1f7a"}
            onMouseLeave={e => e.currentTarget.style.borderColor = "#1e1e35"}>
            <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"0.75rem" }}>
              <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.8rem", letterSpacing:"0.1em", textTransform:"uppercase", color:"#eeeeff" }}>
                Recovery Patterns
              </span>
              {recovery?.score !== undefined && (
                <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"0.9rem", color:scoreColor(recovery.score) }}>
                  {Math.round(recovery.score)}/100
                </span>
              )}
            </div>
            {loading ? <Shimmer height={80} /> : (
              recovery?.findings?.map((f,i) => (
                <p key={i} style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.73rem", color: f.includes("✓") ? "#6b6b8f" : "#9999bb", margin:"0 0 0.4rem 0", lineHeight:1.55 }}>{f}</p>
              ))
            )}
          </Card>
        </div>
      </div>
    </Layout>
  );
}
