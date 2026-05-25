/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        df: {
          blue: "#00AEEF",
          "blue-deep": "#0072BC",
          orange: "#F7941E",
          "orange-deep": "#ED1C24",
          black: "#050508",
        },
        dfui: {
          bg: "#050508",
          surface: "#0c0e14",
          "surface-hover": "#141820",
          "surface-active": "#1a2030",
          panel: "#0a0c12",
          border: "#252a38",
          fg: "#eef1f8",
          secondary: "#9aa3b8",
          tertiary: "#6b7589",
          muted: "#5c667a",
          accent: "#F7941E",
          "accent-dim": "#ED1C24",
          data: "#00AEEF",
          dream: "#00AEEF",
          forge: "#F7941E",
          success: "#34d399",
          warn: "#fbbf24",
        },
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "Inter", "Segoe UI Variable", "Segoe UI", "system-ui", "sans-serif"],
        display: ["Outfit", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "Consolas", "monospace"],
      },
      boxShadow: {
        glass: "0 12px 40px rgba(0, 0, 0, 0.55)",
        glow: "0 0 28px rgba(0, 174, 239, 0.18)",
        "glow-orange": "0 0 28px rgba(247, 148, 30, 0.22)",
      },
      backgroundImage: {
        "df-brand": "linear-gradient(90deg, #00AEEF 0%, #F7941E 55%, #ED1C24 100%)",
        "df-dream": "linear-gradient(135deg, #00AEEF 0%, #0072BC 100%)",
        "df-forge": "linear-gradient(135deg, #F7941E 0%, #ED1C24 100%)",
      },
      backdropBlur: {
        glass: "18px",
      },
    },
  },
  plugins: [],
};
