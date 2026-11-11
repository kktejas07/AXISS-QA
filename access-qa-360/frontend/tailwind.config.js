/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Refero "Midnight Command Center" palette
        app: "#08090a",        // pitch-black canvas
        surface: {
          1: "#111214",        // elevated surface level 1
          2: "#1c1d20",        // elevated surface level 2
          3: "#2a2b2f",        // elevated surface level 3 / borders
        },
        accent: {
          DEFAULT: "#c8f135",  // neon lime CTA
          dim: "#a8cc1a",      // darker lime hover
        },
        muted: {
          DEFAULT: "#6b7280",  // secondary text
          dim: "#4a4b50",      // tertiary text
        },
        fg: {
          DEFAULT: "#f0f0ef",  // primary text
          soft: "#a8a9ae",     // secondary text on dark
        },
        // Keep brand for any legacy references
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#08090a",      // remap to Refero app bg
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Space Grotesk", "Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      borderRadius: {
        card: "6px",
        badge: "4px",
      },
      boxShadow: {
        surface: "0 0 0 1px #2a2b2f",
        "surface-lg": "0 4px 24px rgba(0,0,0,0.6)",
      },
    },
  },
  plugins: [],
};
