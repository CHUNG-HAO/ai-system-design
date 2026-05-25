import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        triage: {
          p1: "#dc2626",
          p2: "#f59e0b",
          ok: "#16a34a",
          ai: "#2563eb",
        },
      },
    },
  },
  plugins: [],
};

export default config;
