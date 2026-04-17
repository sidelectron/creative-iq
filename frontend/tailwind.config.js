/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#0f172a", foreground: "#f8fafc" },
        secondary: { DEFAULT: "#334155", foreground: "#f1f5f9" },
        accent: { DEFAULT: "#2563eb", foreground: "#ffffff" },
        success: "#16a34a",
        warn: "#ca8a04",
        danger: "#dc2626",
        muted: "#64748b",
      },
      fontSize: {
        page: ["1.875rem", { lineHeight: "2.25rem", fontWeight: "600" }],
        section: ["1.25rem", { lineHeight: "1.75rem", fontWeight: "600" }],
        cardtitle: ["1.125rem", { lineHeight: "1.5rem", fontWeight: "600" }],
        body: ["1rem", { lineHeight: "1.5rem" }],
        datalabel: ["0.875rem", { lineHeight: "1.25rem" }],
      },
    },
  },
  plugins: [],
};
