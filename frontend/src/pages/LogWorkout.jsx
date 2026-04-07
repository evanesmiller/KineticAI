import { useState } from "react";
import Layout from "../components/Layout";
import { apiCall } from "../hooks/useFetch";

const MUSCLE_GROUPS = [
  "biceps","triceps","forearms","chest","abs",
  "front_delts","side_delts","rear_delts","traps","lats",
  "spinal_erectors","glutes","hamstrings","quads","calves",
];

const INTENSITY_OPTIONS = ["low","moderate","high"];
const INTENSITY_COLOR   = { low:"#22c55e", moderate:"#f59e0b", high:"#ef4444" };

const MUSCLE_INTENSITY_COLOR = {
  primary:   "#8b5cf6",
  secondary: "#f59e0b",
};

// ── Calendar ───────────────────────────────────────────────────────────────
function Calendar({ value, onChange }) {
  const today = new Date();
  const [view, setView] = useState(() => {
    const d = value ? new Date(value + "T12:00:00") : today;
    return { year: d.getFullYear(), month: d.getMonth() };
  });
  const { year, month } = view;
  const firstDay  = new Date(year, month, 1).getDay();
  const daysInMon = new Date(year, month + 1, 0).getDate();
  const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const DAYS   = ["Su","Mo","Tu","We","Th","Fr","Sa"];

  function iso(day) {
    return `${year}-${String(month+1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
  }
  function isFuture(day) { return new Date(iso(day)+"T12:00:00") > today; }

  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMon; d++) cells.push(d);

  return (
    <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1rem", userSelect:"none" }}>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"0.75rem" }}>
        <button onClick={()=>setView(v=>{ const d=new Date(v.year,v.month-1,1); return{year:d.getFullYear(),month:d.getMonth()}; })}
          style={{ background:"transparent", border:"none", color:"#6b6b8f", cursor:"pointer", fontSize:"1rem", padding:"0.2rem 0.5rem", borderRadius:4 }}
          onMouseEnter={e=>e.target.style.color="#a78bfa"} onMouseLeave={e=>e.target.style.color="#6b6b8f"}>‹</button>
        <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.85rem", letterSpacing:"0.12em", color:"#eeeeff", textTransform:"uppercase" }}>
          {MONTHS[month]} {year}
        </span>
        <button onClick={()=>setView(v=>{ const d=new Date(v.year,v.month+1,1); return{year:d.getFullYear(),month:d.getMonth()}; })}
          style={{ background:"transparent", border:"none", color:"#6b6b8f", cursor:"pointer", fontSize:"1rem", padding:"0.2rem 0.5rem", borderRadius:4 }}
          onMouseEnter={e=>e.target.style.color="#a78bfa"} onMouseLeave={e=>e.target.style.color="#6b6b8f"}>›</button>
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(7,1fr)", gap:"2px", marginBottom:"4px" }}>
        {DAYS.map(d=>(
          <div key={d} style={{ textAlign:"center", fontSize:"0.6rem", color:"#3a3a5c", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, padding:"2px 0" }}>{d}</div>
        ))}
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(7,1fr)", gap:"2px" }}>
        {cells.map((day,i) => {
          if (!day) return <div key={`e${i}`} />;
          const future   = isFuture(day);
          const selected = value === iso(day);
          const todayMark= today.getFullYear()===year && today.getMonth()===month && today.getDate()===day;
          return (
            <button key={day} disabled={future} onClick={()=>!future && onChange(iso(day))}
              style={{ background:selected?"#6d28d9":todayMark?"rgba(109,40,217,0.15)":"transparent", border:selected?"1px solid #8b5cf6":todayMark?"1px solid rgba(109,40,217,0.4)":"1px solid transparent", borderRadius:"6px", color:future?"#2a2a45":selected?"#fff":todayMark?"#a78bfa":"#9999bb", fontSize:"0.75rem", fontFamily:"'DM Sans',sans-serif", fontWeight:selected||todayMark?600:400, padding:"5px 2px", cursor:future?"not-allowed":"pointer", transition:"all 0.12s", boxShadow:selected?"0 0 8px rgba(109,40,217,0.4)":"none" }}
              onMouseEnter={e=>{ if(!future&&!selected) e.currentTarget.style.background="rgba(109,40,217,0.1)"; }}
              onMouseLeave={e=>{ if(!future&&!selected) e.currentTarget.style.background="transparent"; }}>
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Muscle tag (editable) ──────────────────────────────────────────────────
function MuscleTag({ muscle, intensity, onRemove }) {
  const color = MUSCLE_INTENSITY_COLOR[intensity] || "#3a3a5c";
  return (
    <div style={{ display:"flex", alignItems:"center", gap:"0.3rem", background:`${color}15`, border:`1px solid ${color}40`, borderRadius:"5px", padding:"0.2rem 0.5rem" }}>
      <div style={{ width:5, height:5, borderRadius:"50%", background:color, flexShrink:0 }} />
      <span style={{ fontSize:"0.68rem", color, fontFamily:"'DM Sans',sans-serif", textTransform:"capitalize", whiteSpace:"nowrap" }}>
        {muscle.replace(/_/g," ")}
      </span>
      <span style={{ fontSize:"0.55rem", color:`${color}99`, fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, letterSpacing:"0.08em", textTransform:"uppercase" }}>
        {intensity}
      </span>
      <button onClick={onRemove}
        style={{ background:"transparent", border:"none", color:`${color}80`, cursor:"pointer", fontSize:"0.7rem", lineHeight:1, padding:"0 0.1rem", marginLeft:"0.1rem" }}
        onMouseEnter={e=>e.target.style.color=color} onMouseLeave={e=>e.target.style.color=`${color}80`}>
        ✕
      </button>
    </div>
  );
}

// ── Exercise card ──────────────────────────────────────────────────────────
function ExerciseCard({ exercise, index, onChange, onRemove, style }) {
  const [detecting, setDetecting] = useState(false);
  const [detectError, setDetectError] = useState("");
  const [showAddMuscle, setShowAddMuscle] = useState(false);
  const [manualMuscle, setManualMuscle] = useState("");
  const [manualIntensity, setManualIntensity] = useState("primary");

  function field(key, val) { onChange(index, { ...exercise, [key]: val }); }

  async function handleDetect() {
    if (!exercise.name.trim()) {
      setDetectError("Enter an exercise name first.");
      return;
    }
    setDetecting(true);
    setDetectError("");
    try {
      const result = await apiCall("/api/detect-muscles", "POST", {
        exercise_name: exercise.name.trim(),
      });
      // Auto-fill detected muscles, preserving any the user already added
      onChange(index, { ...exercise, detected_muscles: result.muscles });
    } catch (err) {
      setDetectError(err.message);
    } finally {
      setDetecting(false);
    }
  }

  function removeMuscle(muscleIndex) {
    const updated = exercise.detected_muscles.filter((_,i) => i !== muscleIndex);
    onChange(index, { ...exercise, detected_muscles: updated });
  }

  function addManualMuscle() {
    if (!manualMuscle) return;
    const already = (exercise.detected_muscles || []).find(m => m.muscle === manualMuscle);
    if (already) return;
    onChange(index, {
      ...exercise,
      detected_muscles: [
        ...(exercise.detected_muscles || []),
        { muscle: manualMuscle, intensity: manualIntensity },
      ],
    });
    setManualMuscle("");
    setShowAddMuscle(false);
  }

  const muscles = exercise.detected_muscles || [];
  const primaryMuscle = muscles.find(m => m.intensity === "primary");

  return (
    <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1rem 1.25rem", ...style }}
      onMouseEnter={e=>e.currentTarget.style.borderColor="#2a2a45"}
      onMouseLeave={e=>e.currentTarget.style.borderColor="#1e1e35"}>

      {/* Header */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"0.85rem" }}>
        <span style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.75rem", letterSpacing:"0.15em", textTransform:"uppercase", color:"#8b5cf6" }}>
          Exercise {index + 1}
        </span>
        <button onClick={()=>onRemove(index)}
          style={{ background:"transparent", border:"1px solid #1e1e35", borderRadius:"5px", color:"#3a3a5c", cursor:"pointer", fontSize:"0.65rem", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, letterSpacing:"0.1em", textTransform:"uppercase", padding:"0.2rem 0.55rem", transition:"all 0.15s" }}
          onMouseEnter={e=>{ e.currentTarget.style.borderColor="#ef4444"; e.currentTarget.style.color="#ef4444"; }}
          onMouseLeave={e=>{ e.currentTarget.style.borderColor="#1e1e35"; e.currentTarget.style.color="#3a3a5c"; }}>
          Remove
        </button>
      </div>

      {/* Exercise name + Detect button */}
      <div style={{ marginBottom:"0.75rem" }}>
        <Label>Exercise Name</Label>
        <div style={{ display:"flex", gap:"0.5rem" }}>
          <input className="input-field" placeholder="e.g. Barbell Squat"
            value={exercise.name} onChange={e=>field("name", e.target.value)}
            style={{ flex:1 }}
            onKeyDown={e=>{ if(e.key==="Enter"){ e.preventDefault(); handleDetect(); }}} />
          <button onClick={handleDetect} disabled={detecting}
            style={{ background:detecting?"#1e1e35":"rgba(109,40,217,0.12)", border:`1px solid ${detecting?"#1e1e35":"rgba(109,40,217,0.35)"}`, borderRadius:"6px", color:detecting?"#3a3a5c":"#a78bfa", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.68rem", letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 0.9rem", cursor:detecting?"not-allowed":"pointer", transition:"all 0.15s", whiteSpace:"nowrap", display:"flex", alignItems:"center", gap:"0.4rem" }}
            onMouseEnter={e=>{ if(!detecting){ e.currentTarget.style.background="rgba(109,40,217,0.2)"; }}}
            onMouseLeave={e=>{ if(!detecting){ e.currentTarget.style.background="rgba(109,40,217,0.12)"; }}}>
            {detecting
              ? <><span style={{ width:10, height:10, border:"2px solid #3a3a5c", borderTopColor:"#6b6b8f", borderRadius:"50%", display:"inline-block", animation:"spin 0.7s linear infinite" }} /> Detecting…</>
              : <>✦ Detect Muscles</>
            }
          </button>
        </div>
        {detectError && (
          <p style={{ fontSize:"0.68rem", color:"#ef4444", fontFamily:"'DM Sans',sans-serif", marginTop:"0.3rem", margin:"0.3rem 0 0 0" }}>
            {detectError}
          </p>
        )}
      </div>

      {/* Detected muscles */}
      {muscles.length > 0 && (
        <div style={{ marginBottom:"0.75rem" }}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"0.15rem" }}>
            <Label>Muscles Detected</Label>
            <div style={{ display:"flex", gap:"0.4rem", alignItems:"center" }}>
              {/* Legend */}
              {["primary","secondary"].map(lvl=>(
                <span key={lvl} style={{ fontSize:"0.58rem", color:MUSCLE_INTENSITY_COLOR[lvl], fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, letterSpacing:"0.08em", textTransform:"uppercase" }}>
                  {lvl}
                </span>
              ))}
            </div>
          </div>
          <div style={{ display:"flex", flexWrap:"wrap", gap:"0.35rem" }}>
            {muscles.map((m,i) => (
              <MuscleTag key={i} muscle={m.muscle} intensity={m.intensity} onRemove={()=>removeMuscle(i)} />
            ))}
            {/* Add muscle button */}
            <button onClick={()=>setShowAddMuscle(s=>!s)}
              style={{ background:"transparent", border:"1px dashed #2a2a45", borderRadius:"5px", color:"#3a3a5c", cursor:"pointer", fontSize:"0.65rem", fontFamily:"'DM Sans',sans-serif", padding:"0.2rem 0.5rem", transition:"all 0.15s" }}
              onMouseEnter={e=>{ e.currentTarget.style.borderColor="#6d28d9"; e.currentTarget.style.color="#a78bfa"; }}
              onMouseLeave={e=>{ e.currentTarget.style.borderColor="#2a2a45"; e.currentTarget.style.color="#3a3a5c"; }}>
              + add
            </button>
          </div>

          {/* Manual muscle add row */}
          {showAddMuscle && (
            <div style={{ display:"flex", gap:"0.5rem", marginTop:"0.5rem", alignItems:"center" }}>
              <select value={manualMuscle} onChange={e=>setManualMuscle(e.target.value)}
                className="input-field" style={{ flex:1, cursor:"pointer", fontSize:"0.75rem" }}>
                <option value="">Select muscle…</option>
                {MUSCLE_GROUPS.filter(m=>!muscles.find(ex=>ex.muscle===m)).map(m=>(
                  <option key={m} value={m}>{m.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase())}</option>
                ))}
              </select>
              <select value={manualIntensity} onChange={e=>setManualIntensity(e.target.value)}
                className="input-field" style={{ width:110, cursor:"pointer", fontSize:"0.75rem" }}>
                <option value="primary">Primary</option>
                <option value="secondary">Secondary</option>
              </select>
              <button onClick={addManualMuscle}
                style={{ background:"rgba(109,40,217,0.12)", border:"1px solid rgba(109,40,217,0.3)", borderRadius:"6px", color:"#a78bfa", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.68rem", letterSpacing:"0.1em", textTransform:"uppercase", padding:"0.5rem 0.75rem", cursor:"pointer", whiteSpace:"nowrap" }}>
                Add
              </button>
            </div>
          )}
        </div>
      )}

      {/* Prompt to detect if no muscles yet */}
      {muscles.length === 0 && exercise.name.trim() && (
        <div style={{ background:"rgba(109,40,217,0.05)", border:"1px dashed #2a2a45", borderRadius:"6px", padding:"0.6rem 0.75rem", marginBottom:"0.75rem" }}>
          <p style={{ fontSize:"0.7rem", color:"#3a3a5c", fontFamily:"'DM Sans',sans-serif", margin:0 }}>
            Click <span style={{ color:"#8b5cf6" }}>✦ Detect Muscles</span> to auto-detect which muscles this exercise targets, or add them manually below.
          </p>
          {!showAddMuscle && (
            <button onClick={()=>setShowAddMuscle(true)}
              style={{ background:"transparent", border:"none", color:"#8b5cf6", fontFamily:"'DM Sans',sans-serif", fontSize:"0.7rem", cursor:"pointer", padding:0, marginTop:"0.3rem", textDecoration:"underline" }}>
              Add manually
            </button>
          )}
          {showAddMuscle && (
            <div style={{ display:"flex", gap:"0.5rem", marginTop:"0.5rem", alignItems:"center" }}>
              <select value={manualMuscle} onChange={e=>setManualMuscle(e.target.value)}
                className="input-field" style={{ flex:1, cursor:"pointer", fontSize:"0.75rem" }}>
                <option value="">Select muscle…</option>
                {MUSCLE_GROUPS.map(m=>(
                  <option key={m} value={m}>{m.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase())}</option>
                ))}
              </select>
              <select value={manualIntensity} onChange={e=>setManualIntensity(e.target.value)}
                className="input-field" style={{ width:110, cursor:"pointer", fontSize:"0.75rem" }}>
                <option value="primary">Primary</option>
                <option value="secondary">Secondary</option>
              </select>
              <button onClick={addManualMuscle}
                style={{ background:"rgba(109,40,217,0.12)", border:"1px solid rgba(109,40,217,0.3)", borderRadius:"6px", color:"#a78bfa", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.68rem", letterSpacing:"0.1em", textTransform:"uppercase", padding:"0.5rem 0.75rem", cursor:"pointer", whiteSpace:"nowrap" }}>
                Add
              </button>
            </div>
          )}
        </div>
      )}

      {/* Sets / Reps / Weight */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:"0.75rem" }}>
        {[["Sets","sets","e.g. 4"],["Reps","reps","e.g. 8"],["Weight (lbs)","weight_lbs","0 = bodyweight"]].map(([label,key,ph])=>(
          <div key={key}>
            <Label>{label}</Label>
            <input className="input-field" type="number" min="0" placeholder={ph}
              value={exercise[key]} onChange={e=>field(key, e.target.value)} />
          </div>
        ))}
      </div>

      {/* Primary muscle indicator */}
      {primaryMuscle && (
        <div style={{ marginTop:"0.6rem", fontSize:"0.65rem", color:"#3a3a5c", fontFamily:"'DM Sans',sans-serif" }}>
          Logged under: <span style={{ color:"#8b5cf6" }}>{primaryMuscle.muscle.replace(/_/g," ")}</span>
        </div>
      )}
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

function SuccessBanner({ onDismiss }) {
  return (
    <div className="animate-fade-up" style={{ background:"rgba(34,197,94,0.08)", border:"1px solid rgba(34,197,94,0.25)", borderRadius:"0.75rem", padding:"1rem 1.25rem", display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"1.5rem" }}>
      <div style={{ display:"flex", alignItems:"center", gap:"0.75rem" }}>
        <div style={{ width:28, height:28, borderRadius:"50%", background:"rgba(34,197,94,0.15)", border:"1px solid rgba(34,197,94,0.3)", display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
          <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
            <path d="M3 8l3.5 3.5L13 4.5" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div>
          <p style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.9rem", color:"#22c55e", margin:0 }}>Workout Logged!</p>
          <p style={{ fontSize:"0.72rem", color:"#6b6b8f", fontFamily:"'DM Sans',sans-serif", margin:"0.1rem 0 0 0" }}>Your session has been saved and fatigue scores updated.</p>
        </div>
      </div>
      <button onClick={onDismiss} style={{ background:"transparent", border:"none", color:"#3a3a5c", cursor:"pointer", fontSize:"1.1rem" }}
        onMouseEnter={e=>e.target.style.color="#6b6b8f"} onMouseLeave={e=>e.target.style.color="#3a3a5c"}>✕</button>
    </div>
  );
}

function newExercise() {
  return { name:"", detected_muscles:[], sets:"", reps:"", weight_lbs:"" };
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function LogWorkout() {
  const today = new Date().toISOString().split("T")[0];
  const [date,      setDate]      = useState(today);
  const [duration,  setDuration]  = useState("");
  const [intensity, setIntensity] = useState("moderate");
  const [notes,     setNotes]     = useState("");
  const [exercises, setExercises] = useState([newExercise()]);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState("");
  const [success,   setSuccess]   = useState(false);
  const [newIndex,  setNewIndex]  = useState(null);

  function addExercise() {
    setExercises(p => { setNewIndex(p.length); return [...p, newExercise()]; });
  }
  const [removingIndex, setRemovingIndex] = useState(null);

  function updateExercise(i, updated){ setExercises(p=>p.map((ex,idx)=>idx===i?updated:ex)); }
  function removeExercise(i) {
    setRemovingIndex(i);
    setTimeout(() => {
      setExercises(p=>p.filter((_,idx)=>idx!==i));
      setRemovingIndex(null);
    }, 400);
  }

  function reset() {
    setDate(today); setDuration(""); setIntensity("moderate");
    setNotes(""); setExercises([newExercise()]); setError(""); setSuccess(false);
  }

  async function handleSubmit() {
    setError("");
    if (!date)                              return setError("Please select a date.");
    if (!duration || Number(duration) <= 0) return setError("Please enter a valid duration.");
    if (exercises.length === 0)             return setError("Add at least one exercise.");

    for (let i = 0; i < exercises.length; i++) {
      const ex = exercises[i];
      if (!ex.name.trim())        return setError(`Exercise ${i+1}: name is required.`);
      if (!ex.sets || ex.sets<=0) return setError(`Exercise ${i+1}: sets must be > 0.`);
      if (!ex.reps || ex.reps<=0) return setError(`Exercise ${i+1}: reps must be > 0.`);
      if (ex.weight_lbs === "")   return setError(`Exercise ${i+1}: weight is required (use 0 for bodyweight).`);

      const muscles = ex.detected_muscles || [];
      const primary = muscles.find(m=>m.intensity==="primary");
      if (!primary) return setError(`Exercise ${i+1}: detect muscles or manually add at least one primary muscle.`);
    }

    setLoading(true);
    try {
      // Build exercises payload — primary muscle goes to muscle_group,
      // secondary/tertiary are included as additional exercises with lower weight
      const exercisesPayload = [];
      for (const ex of exercises) {
        const muscles = ex.detected_muscles || [];
        const primaries  = muscles.filter(m=>m.intensity==="primary");
        const primary    = primaries[0];

        // First primary muscle — full sets/reps/weight, no suffix
        exercisesPayload.push({
          name:         ex.name.trim(),
          muscle_group: primary.muscle,
          sets:         Number(ex.sets),
          reps:         Number(ex.reps),
          weight_lbs:   Number(ex.weight_lbs),
        });

        // Additional primary muscles — full volume, "(primary)" suffix
        primaries.slice(1).forEach(m=>{
          exercisesPayload.push({
            name:         `${ex.name.trim()} (primary)`,
            muscle_group: m.muscle,
            sets:         Number(ex.sets),
            reps:         Number(ex.reps),
            weight_lbs:   Number(ex.weight_lbs),
          });
        });

        // Secondary muscles — 60% volume credit
        muscles.filter(m=>m.intensity==="secondary").forEach(m=>{
          exercisesPayload.push({
            name:         `${ex.name.trim()} (secondary)`,
            muscle_group: m.muscle,
            sets:         Number(ex.sets),
            reps:         Number(ex.reps),
            weight_lbs:   Math.round(Number(ex.weight_lbs) * 0.6 * 10) / 10,
          });
        });

      }

      await apiCall("/workouts/", "POST", {
        date,
        duration_mins: Number(duration),
        intensity,
        notes: notes.trim() || null,
        exercises: exercisesPayload,
      });

      setSuccess(true);
      setExercises([newExercise()]);
      setDuration(""); setNotes(""); setDate(today);
      window.scrollTo({ top:0, behavior:"smooth" });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <div className="animate-fade-up" style={{ marginBottom:"2rem" }}>
        <p style={{ fontSize:"0.7rem", letterSpacing:"0.2em", textTransform:"uppercase", color:"#8b5cf6", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:600, marginBottom:"0.2rem" }}>
          KineticAI
        </p>
        <h1 style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:800, fontSize:"2.25rem", color:"#eeeeff", letterSpacing:"0.04em", lineHeight:1, margin:0 }}>
          LOG WORKOUT
        </h1>
      </div>

      {success && <SuccessBanner onDismiss={()=>setSuccess(false)} />}

      <div style={{ display:"grid", gridTemplateColumns:"300px 1fr", gap:"1.5rem 1.5rem", alignItems:"start" }}>

        {/* Row 1, Col 1: Date heading */}
        <div style={{ marginBottom:"0.15rem" }}>
          <SectionHeading label="Date" />
        </div>

        {/* Row 1, Col 2: exercises header */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"0.15rem" }}>
          <SectionHeading label={`Exercises (${exercises.length})`} />
          <button onClick={addExercise}
            style={{ background:"rgba(109,40,217,0.12)", border:"1px solid rgba(109,40,217,0.3)", borderRadius:"6px", color:"#a78bfa", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.72rem", letterSpacing:"0.12em", textTransform:"uppercase", padding:"0.4rem 0.9rem", cursor:"pointer", transition:"all 0.15s" }}
            onMouseEnter={e=>{ e.currentTarget.style.background="rgba(109,40,217,0.2)"; e.currentTarget.style.borderColor="rgba(139,92,246,0.5)"; }}
            onMouseLeave={e=>{ e.currentTarget.style.background="rgba(109,40,217,0.12)"; e.currentTarget.style.borderColor="rgba(109,40,217,0.3)"; }}>
            + Add Exercise
          </button>
        </div>

        {/* Row 2, Col 1: calendar + session details */}
        <div style={{ display:"flex", flexDirection:"column", gap:"1.25rem" }}>
          <div>
            <Calendar value={date} onChange={setDate} />
            {date && (
              <p style={{ fontSize:"0.7rem", color:"#8b5cf6", fontFamily:"'DM Sans',sans-serif", marginTop:"0.5rem", textAlign:"center" }}>
                {new Date(date+"T12:00:00").toLocaleDateString("en-US",{weekday:"long",month:"long",day:"numeric"})}
              </p>
            )}
          </div>

          <div style={{ background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"0.75rem", padding:"1.25rem" }}>
            <SectionHeading label="Session Details" />
            <div style={{ marginBottom:"1rem" }}>
              <Label>Duration (minutes)</Label>
              <input className="input-field" type="number" min="1" placeholder="e.g. 60"
                value={duration} onChange={e=>setDuration(e.target.value)} />
            </div>
            <div style={{ marginBottom:"1rem" }}>
              <Label>Intensity</Label>
              <div style={{ display:"flex", gap:"0.5rem" }}>
                {INTENSITY_OPTIONS.map(opt=>{
                  const active = intensity===opt;
                  const color  = INTENSITY_COLOR[opt];
                  return (
                    <button key={opt} onClick={()=>setIntensity(opt)}
                      style={{ flex:1, background:active?`${color}18`:"transparent", border:`1px solid ${active?color:"#1e1e35"}`, borderRadius:"6px", color:active?color:"#3a3a5c", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.72rem", letterSpacing:"0.12em", textTransform:"uppercase", padding:"0.5rem 0", cursor:"pointer", transition:"all 0.15s", boxShadow:active?`0 0 8px ${color}33`:"none" }}>
                      {opt}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <Label>Notes (optional)</Label>
              <textarea className="input-field" placeholder=""
                value={notes} onChange={e=>setNotes(e.target.value)}
                rows={3} style={{ resize:"vertical", fontFamily:"'DM Sans',sans-serif" }} />
            </div>
          </div>
        </div>

        {/* Row 2, Col 2: exercise cards */}
        <div>

          <div style={{ display:"flex", flexDirection:"column", gap:"0.85rem", marginBottom:"1.25rem" }}>
            {exercises.map((ex,i)=>(
              <div key={i} style={ i === removingIndex ? { animation:"fadeSlideOut 0.4s ease forwards" } : i === newIndex ? { animation:"fadeSlideIn 0.5s ease forwards" } : {} }>
                <ExerciseCard exercise={ex} index={i}
                  onChange={updateExercise} onRemove={removeExercise}
                  style={i === 0 ? { minHeight:"258px" } : {}} />
              </div>
            ))}
          </div>

          {error && (
            <div style={{ background:"rgba(239,68,68,0.08)", border:"1px solid rgba(239,68,68,0.2)", borderRadius:"0.5rem", padding:"0.65rem 0.9rem", marginBottom:"1rem" }}>
              <p style={{ color:"#ef4444", fontSize:"0.75rem", fontFamily:"'DM Sans',sans-serif", margin:0 }}>{error}</p>
            </div>
          )}

          <div style={{ display:"flex", gap:"0.75rem" }}>
            <button onClick={handleSubmit} disabled={loading}
              style={{ flex:1, background:loading?"#3d1f7a":"#6d28d9", border:"none", borderRadius:"0.5rem", color:"#fff", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.85rem", letterSpacing:"0.15em", textTransform:"uppercase", padding:"0.85rem 1.5rem", cursor:loading?"not-allowed":"pointer", transition:"all 0.2s", boxShadow:loading?"none":"0 0 20px rgba(109,40,217,0.3)" }}
              onMouseEnter={e=>{ if(!loading){ e.currentTarget.style.background="#8b5cf6"; e.currentTarget.style.boxShadow="0 0 28px rgba(139,92,246,0.4)"; }}}
              onMouseLeave={e=>{ if(!loading){ e.currentTarget.style.background="#6d28d9"; e.currentTarget.style.boxShadow="0 0 20px rgba(109,40,217,0.3)"; }}}>
              {loading
                ? <span style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:"0.5rem" }}>
                    <span style={{ width:13, height:13, border:"2px solid rgba(255,255,255,0.3)", borderTopColor:"white", borderRadius:"50%", display:"inline-block", animation:"spin 0.7s linear infinite" }} />
                    Saving…
                  </span>
                : "Save Workout"
              }
            </button>
            <button onClick={reset}
              style={{ background:"transparent", border:"1px solid #1e1e35", borderRadius:"0.5rem", color:"#6b6b8f", fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.72rem", letterSpacing:"0.12em", textTransform:"uppercase", padding:"0.85rem 1.25rem", cursor:"pointer", transition:"all 0.15s" }}
              onMouseEnter={e=>{ e.currentTarget.style.borderColor="#2a2a45"; e.currentTarget.style.color="#9999bb"; }}
              onMouseLeave={e=>{ e.currentTarget.style.borderColor="#1e1e35"; e.currentTarget.style.color="#6b6b8f"; }}>
              Reset
            </button>
          </div>
        </div>
      </div>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}} @keyframes fadeSlideIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}} @keyframes fadeSlideOut{from{opacity:1;transform:translateY(0)}to{opacity:0;transform:translateY(12px)}} input[type=number]::-webkit-inner-spin-button,input[type=number]::-webkit-outer-spin-button{-webkit-appearance:none;margin:0} input[type=number]{-moz-appearance:textfield}`}</style>
    </Layout>
  );
}
