import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#050B18",
          900: "#07111F",
          850: "#0B1628",
          800: "#0F1D33",
        },
        accent: {
          DEFAULT: "#4F46E5",
          hover: "#4338CA",
          soft: "#EEF2FF",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "20px",
        btn: "10px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 16px 32px rgba(15, 23, 42, 0.045)",
        shell: "12px 0 28px rgba(15, 23, 42, 0.16), inset -1px 0 rgba(255, 255, 255, 0.06)",
        header: "0 14px 34px rgba(15, 23, 42, 0.18), inset 0 -1px rgba(255, 255, 255, 0.06)",
      },
    },
  },
  plugins: [],
};
export default config;
