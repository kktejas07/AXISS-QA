/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Wiseflow indigo, taken from the logo files in public/brand.
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4338ca",
          700: "#3730a3",
          800: "#312e81",
          900: "#1e1b4b",
          950: "#1e1b4b",
        },
        ink: "#101014",
        body: "#4b4f5c",
        line: "#e6e7ee",
        soft: "#f6f7fb",
      },
      boxShadow: {
        hard: "6px 6px 0 #3730a3",
        "hard-ink": "6px 6px 0 #101014",
      },
      fontFamily: {
        sans: ["Roboto", "system-ui", "sans-serif"],
        mono: ["Roboto Mono", "ui-monospace", "monospace"],
        // The wordmark only; everything else is Roboto.
        brand: ["'Source Serif 4'", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
