/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Core palette
        void:    "#080810",
        surface: "#0f0f1a",
        panel:   "#151525",
        border:  "#1e1e35",
        muted:   "#2a2a45",
        // Purple accent family
        purple: {
          dim:    "#3d1f7a",
          base:   "#6d28d9",
          bright: "#8b5cf6",
          glow:   "#a78bfa",
          soft:   "#c4b5fd",
        },
        // Text
        ink: {
          faint:  "#3a3a5c",
          muted:  "#6b6b8f",
          mid:    "#9999bb",
          base:   "#c8c8e8",
          bright: "#eeeeff",
        },
        // Status
        red:    "#ef4444",
        yellow: "#f59e0b",
        green:  "#22c55e",
      },
      fontFamily: {
        display: ["'Barlow Condensed'", "sans-serif"],
        body:    ["'DM Sans'", "sans-serif"],
        mono:    ["'JetBrains Mono'", "monospace"],
      },
      boxShadow: {
        purple: "0 0 24px rgba(109,40,217,0.35)",
        glow:   "0 0 48px rgba(139,92,246,0.25)",
      },
    },
  },
  plugins: [],
}
