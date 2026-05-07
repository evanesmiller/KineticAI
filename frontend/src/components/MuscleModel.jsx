/**
 * MuscleModel.jsx
 *
 * Pixel-perfect muscle highlighting using mask PNGs.
 * Each muscle mask is a white-on-black PNG the same size as the base image.
 * CSS mask-image clips a colored div to only show through the white pixels.
 *
 */

import { useState, useRef, useEffect, useCallback } from "react";

// ── Fatigue status config ──────────────────────────────────────────────────
const STATUS = {
  red:    { color:"rgba(239,68,68,0.65)",  pulse:true,  label:"Needs Rest" },
  yellow: { color:"rgba(253,224,71,0.48)", pulse:false, label:"Ready Soon" },
  green:  { color:"rgba(34,197,94,0.38)",  pulse:false, label:"Ready"      },
  none:   { color:"transparent",           pulse:false, label:"Untracked"  },
};

const LEGEND = [
  { key:"red",    hex:"#ef4444", label:"Needs Rest" },
  { key:"yellow", hex:"#fde047", label:"Ready Soon" },
  { key:"green",  hex:"#22c55e", label:"Ready"      },
];

// ── Muscle definitions per view ────────────────────────────────────────────
const BACK_MUSCLES = [
  { key:"traps",           mask:"traps_back.png",     label:"Traps" },
  { key:"rear_delts",      mask:"reardelts.png",      label:"Rear Delts" },
  { key:"lats",            mask:"lats.png",           label:"Lats" },
  { key:"triceps",         mask:"triceps.png",        label:"Triceps" },
  { key:"spinal_erectors", mask:"spinalerectors.png", label:"Spinal Erectors" },
  { key:"glutes",          mask:"glutes.png",         label:"Glutes" },
  { key:"hamstrings",      mask:"hamstrings.png",     label:"Hamstrings" },
  { key:"calves",          mask:"calves.png",         label:"Calves" },
  { key:"forearms",        mask:"forearms_back.png",  label:"Forearms" },
  { key:"adductors",       mask:"adductors_back.png", label:"Adductors" }
];

// Uncomment entries as you create front mask PNGs
const FRONT_MUSCLES = [
  { key:"traps",       mask:"traps_front.png",        label:"Traps" }, 
  { key:"chest",       mask:"chest.png",              label:"Chest" },
  { key:"front_delts", mask:"frontdelts.png",         label:"Front Delts" },
  { key:"biceps",      mask:"biceps.png",             label:"Biceps" },
  { key:"forearms",    mask:"forearms_front.png",     label:"Forearms" },
  { key:"abs",         mask:"abs.png",                label:"Abs" },
  { key:"quads",       mask:"quads.png",              label:"Quads" },
  { key:"adductors",   mask:"adductors_front.png",    label:"Adductors" }
];

const VIEWS = {
  front: { base:"/muscle_map/front.png", w:702, h:1142, muscles:FRONT_MUSCLES },
  back:  { base:"/muscle_map/back.png",  w:702, h:1142, muscles:BACK_MUSCLES },
};

// Returns true if any pixel within `radius` of (x, y) is white in the canvas
function hitTest(ctx, x, y, radius = 3) {
  try {
    const size = radius * 2 + 1;
    const data = ctx.getImageData(x - radius, y - radius, size, size).data;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i] > 180 && data[i + 1] > 180 && data[i + 2] > 180) return true;
    }
  } catch { /* out of bounds */ }
  return false;
}

// ── Hover detection via offscreen canvas ───────────────────────────────────
function useMaskHitTest(muscles, view, displayW, displayH, imgW, imgH) {
  const maskCanvases  = useRef({});
  const muscleCenterY = useRef({});  // center Y in original image px per muscle key
  const hoveredRef    = useRef(null);
  const [hovered, setHoveredState] = useState(null);

  function setHovered(key) {
    if (hoveredRef.current !== key) {
      hoveredRef.current = key;
      setHoveredState(key);
    }
  }

  useEffect(() => {
    maskCanvases.current  = {};
    muscleCenterY.current = {};
    muscles.forEach(({ key, mask }) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.src = `/muscle_map/${mask}`;
      img.onload = () => {
        const c = document.createElement("canvas");
        c.width = img.width;
        c.height = img.height;
        const ctx = c.getContext("2d");
        ctx.drawImage(img, 0, 0);
        maskCanvases.current[key] = ctx;

        // Find vertical midpoint of white pixels for static tooltip placement
        const data = ctx.getImageData(0, 0, img.width, img.height).data;
        let minY = img.height, maxY = 0;
        for (let py = 0; py < img.height; py++) {
          for (let px = 0; px < img.width; px++) {
            const i = (py * img.width + px) * 4;
            if (data[i] > 180 && data[i + 1] > 180 && data[i + 2] > 180) {
              if (py < minY) minY = py;
              if (py > maxY) maxY = py;
            }
          }
        }
        muscleCenterY.current[key] = (minY + maxY) / 2;
      };
    });
  }, [muscles, view]);

  const onMouseMove = useCallback((e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / displayW) * imgW);
    const y = Math.round(((e.clientY - rect.top) / displayH) * imgH);

    // If cursor is still inside the current muscle, skip the full scan
    const cur = hoveredRef.current;
    if (cur) {
      const ctx = maskCanvases.current[cur];
      if (ctx && hitTest(ctx, x, y)) return;
    }

    // Cursor left the current muscle — find the new one
    for (let i = muscles.length - 1; i >= 0; i--) {
      const { key } = muscles[i];
      const ctx = maskCanvases.current[key];
      if (!ctx) continue;
      if (hitTest(ctx, x, y)) {
        setHovered(key);
        return;
      }
    }
    setHovered(null);
  }, [muscles, displayW, displayH, imgW, imgH]);

  const onMouseLeave = useCallback(() => {
    hoveredRef.current = null;
    setHoveredState(null);
  }, []);

  return { hovered, onMouseMove, onMouseLeave, muscleCenterY };
}

// ── Component ──────────────────────────────────────────────────────────────
export default function MuscleModel({ fatigueMap = {} }) {
  const [view, setView] = useState("front");
  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [hiddenStatuses, setHiddenStatuses] = useState(new Set());

  function toggleStatus(key) {
    setHiddenStatuses(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      setContainerWidth(entries[0].contentRect.width);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const { base, w: imgW, h: imgH, muscles } = VIEWS[view];
  const maxH = 500;
  const fullW = containerWidth || Math.round(imgW * (maxH / imgH));
  const displayH = Math.min(maxH, Math.round(fullW * (imgH / imgW)));
  const displayW = Math.round(displayH * (imgW / imgH));

  const { hovered, onMouseMove, onMouseLeave, muscleCenterY } = useMaskHitTest(
    muscles, view, displayW, displayH, imgW, imgH
  );

  function getStatus(key) { return fatigueMap[key]?.color || "none"; }
  function getDetails(key) { return fatigueMap[key] || { workout_days: 0, total_days: 0, exercises: [] }; }

  const hoveredMuscle = muscles.find(m => m.key === hovered);
  const hoveredStatus = hovered ? getStatus(hovered) : "none";

  return (
    <div ref={containerRef} style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:"0.75rem", width:"100%" }}>

      {/* View toggle */}
      <div style={{ display:"flex", width:"100%", background:"#0f0f1a", border:"1px solid #1e1e35", borderRadius:"7px", overflow:"hidden", marginTop:"2.25rem" }}>
        {Object.keys(VIEWS).map(v => (
          <button key={v} onClick={() => setView(v)} style={{
            flex:          1,
            background:    view===v ? "#6d28d9" : "transparent",
            border:        "none",
            color:         view===v ? "#fff"    : "#6b6b8f",
            fontFamily:    "'Barlow Condensed',sans-serif",
            fontWeight:    700,
            fontSize:      "0.78rem",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            padding:       "0.45rem 1rem",
            cursor:        "pointer",
            transition:    "all 0.15s",
          }}>{v}</button>
        ))}
      </div>

      {/* Image stack */}
      <div
        style={{ position:"relative", width:displayW, height:displayH, cursor:"default" }}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
      >
        {/* Base body diagram */}
        <img
          src={base}
          alt={`${view} body diagram`}
          width={displayW}
          height={displayH}
          style={{ display:"block", userSelect:"none", pointerEvents:"none" }}
        />

        {/* Colored mask layers — one per muscle */}
        {muscles.map(({ key, mask }) => {
          const status = getStatus(key);
          const s = STATUS[status];
          if (status === "none" || hiddenStatuses.has(status)) return null;

          return (
            <div
              key={`${view}-${key}`}
              style={{
                position:        "absolute",
                top:             0,
                left:            0,
                width:           displayW,
                height:          displayH,
                backgroundColor: s.color,
                WebkitMaskImage: `url(/muscle_map/${mask})`,
                maskImage:       `url(/muscle_map/${mask})`,
                WebkitMaskSize:  `${displayW}px ${displayH}px`,
                maskSize:        `${displayW}px ${displayH}px`,
                WebkitMaskRepeat:"no-repeat",
                maskRepeat:      "no-repeat",
                pointerEvents:   "none",
                animation:       s.pulse ? "musclePulse 2s ease-in-out infinite" : "none",
              }}
            />
          );
        })}

        {/* Hover highlight — white semi-transparent layer on hovered muscle */}
        {hovered && (() => {
          const m = muscles.find(m => m.key === hovered);
          if (!m) return null;
          return (
            <div style={{
              position:        "absolute",
              top:             0,
              left:            0,
              width:           displayW,
              height:          displayH,
              backgroundColor: "rgba(255,255,255,0.18)",
              WebkitMaskImage: `url(/muscle_map/${m.mask})`,
              maskImage:       `url(/muscle_map/${m.mask})`,
              WebkitMaskSize:  `${displayW}px ${displayH}px`,
              maskSize:        `${displayW}px ${displayH}px`,
              WebkitMaskRepeat:"no-repeat",
              maskRepeat:      "no-repeat",
              pointerEvents:   "none",
            }} />
          );
        })()}

        {/* Tooltip */}
        {hoveredMuscle && (() => {
          const details     = getDetails(hovered);
          const borderColor = hoveredStatus !== "none" ? STATUS[hoveredStatus].color : "#2a2a45";
          const dayWord     = details.workout_days === 1 ? "time" : "times";
          return (
            <div style={{
              position:      "absolute",
              top:           hovered && muscleCenterY.current[hovered] != null
                               ? (muscleCenterY.current[hovered] / imgH) * displayH
                               : displayH / 2,
              left:          "calc(100% + 8px)",
              transform:     "translateY(-50%)",
              background:    "#151525",
              border:        `1px solid ${borderColor}`,
              borderRadius:  "8px",
              padding:       "0.5rem 0.8rem",
              minWidth:      150,
              pointerEvents: "none",
              zIndex:        30,
              whiteSpace:    "nowrap",
            }}>
              <div style={{ fontFamily:"'Barlow Condensed',sans-serif", fontWeight:700, fontSize:"0.85rem", color:"#eeeeff", marginBottom:"0.25rem" }}>
                {hoveredMuscle.label}
              </div>
              <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.62rem", color:"#9999bb", marginBottom:"0.1rem" }}>
                Worked out {details.workout_days} {dayWord} this week
              </div>
              <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.62rem", color:"#6b6b8f", marginBottom:"0.35rem" }}>
                {details.total_days} total session{details.total_days === 1 ? "" : "s"} all-time
              </div>
              {details.exercises.length > 0 && (
                <>
                  <div style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.62rem", color:"#6b6b8f", marginBottom:"0.15rem" }}>
                    Exercises:
                  </div>
                  {details.exercises.map(ex => (
                    <div key={ex} style={{ fontFamily:"'DM Sans',sans-serif", fontSize:"0.60rem", color:"#9999bb", paddingLeft:"0.5rem" }}>
                      · {ex}
                    </div>
                  ))}
                </>
              )}
            </div>
          );
        })()}

        <style>{`@keyframes musclePulse{0%,100%{opacity:.50}50%{opacity:.85}}`}</style>
      </div>

      {/* Legend — click to filter */}
      <div style={{ display:"flex", gap:"1rem", flexWrap:"wrap", justifyContent:"center" }}>
        {LEGEND.map(({ key, hex, label }) => {
          const hidden = hiddenStatuses.has(key);
          return (
            <div
              key={key}
              onClick={() => toggleStatus(key)}
              style={{ display:"flex", alignItems:"center", gap:"0.35rem", cursor:"pointer", userSelect:"none" }}
            >
              <div style={{
                width:       8,
                height:      8,
                borderRadius:"50%",
                background:  hidden ? "#2a2a45" : hex,
                boxShadow:   hidden ? "none" : `0 0 6px 2px ${hex}`,
                transition:  "all 0.2s",
              }} />
              <span style={{
                fontSize:   "0.72rem",
                color:      hidden ? "#3a3a5c" : "#9999bb",
                fontFamily: "'DM Sans',sans-serif",
                transition: "color 0.2s",
              }}>{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
