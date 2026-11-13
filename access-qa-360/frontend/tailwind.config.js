/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f1f0fe",
          100: "#e4e2fc",
          500: "#5a50ea",
          600: "#3b30e0",
          700: "#2a21b8",
          800: "#211a8f",
          900: "#101014",
        },
        ink: "#101014",
        body: "#4b4f5c",
        line: "#e6e7ee",
        soft: "#f6f7fb",
      },
      boxShadow: {
        hard: "6px 6px 0 #3b30e0",
        "hard-ink": "6px 6px 0 #101014",
      },
      fontFamily: {
        sans: ["Roboto", "system-ui", "sans-serif"],
        mono: ["Roboto Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
