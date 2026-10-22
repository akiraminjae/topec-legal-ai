import type { Config } from "tailwindcss";

/**
 * 디자인 토큰. 화면에서 색·여백·굴곡을 직접 고르지 말고 여기 정의된 토큰을 쓴다.
 *
 * brand  — TOPEC 네이비블루(로고/테마컬러 #0f4c81 계열). 주요 동작·링크·선택 상태.
 * risk   — 위험등급 5단계. 차트(RISK_LEVEL_HEX)와 배지가 같은 값을 공유해야 하므로
 *          lib/labels.ts 의 HEX 와 함께 고친다.
 * ink    — 본문 텍스트용 중성색(slate 기반이지만 살짝 더 차갑고 진하게).
 */
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef5fb",
          100: "#d8e8f5",
          200: "#b3d1ea",
          300: "#7fb1d9",
          400: "#4a8cc4",
          500: "#2770ae",
          600: "#175a93",
          700: "#0f4c81",
          800: "#0d3f6b",
          900: "#0b3053",
        },
        ink: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e4e9f0",
          300: "#cbd4e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
        },
        risk: {
          critical: "#dc2626",
          high: "#ea580c",
          medium: "#ca8a04",
          low: "#2563eb",
          acceptable: "#16a34a",
        },
      },
      fontFamily: {
        // Pretendard 는 CDN 에서 불러오고(app/layout.tsx), 실패하면 OS 기본 한글 글꼴로 떨어진다.
        sans: [
          "Pretendard Variable",
          "Pretendard",
          "-apple-system",
          "BlinkMacSystemFont",
          "system-ui",
          "Segoe UI",
          "Apple SD Gothic Neo",
          "Malgun Gothic",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      fontSize: {
        // 한글은 같은 px 에서 라틴 문자보다 빽빽해 보여 행간을 넉넉하게 잡는다.
        xs: ["0.75rem", { lineHeight: "1.125rem" }],
        sm: ["0.8125rem", { lineHeight: "1.3125rem" }],
        base: ["0.875rem", { lineHeight: "1.5rem" }],
        lg: ["1rem", { lineHeight: "1.625rem" }],
        xl: ["1.125rem", { lineHeight: "1.75rem" }],
        "2xl": ["1.375rem", { lineHeight: "2rem" }],
        "3xl": ["1.75rem", { lineHeight: "2.25rem" }],
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        md: "0.5rem",
        lg: "0.75rem",
        xl: "1rem",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)",
        "card-hover": "0 2px 4px -1px rgb(15 23 42 / 0.06), 0 8px 16px -4px rgb(15 23 42 / 0.10)",
        pop: "0 4px 6px -2px rgb(15 23 42 / 0.05), 0 12px 24px -6px rgb(15 23 42 / 0.14)",
      },
      keyframes: {
        "fade-in-up": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 0.18s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
