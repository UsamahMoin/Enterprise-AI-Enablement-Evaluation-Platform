import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#ffffff",
        canvas: "#f6f7f9",
        ink: "#12151a",
        muted: "#5b6472",
        line: "#e3e6eb",
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          500: "#5b63d3",
          600: "#4a51bd",
          700: "#3d43a0",
        },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
