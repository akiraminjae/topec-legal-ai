import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "TOPEC Legal AI",
  description: "TOPEC 사내 법률검토 AI 시스템",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "TOPEC Legal AI",
  },
  icons: {
    icon: [
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#0f4c81",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        {/*
          본문 글꼴(Pretendard) — 빌드 때 받지 않고 런타임에 CDN 에서 불러온다.
          · next/font 로 받으면 빌드가 외부 네트워크에 묶여 배포가 통째로 실패할 수 있다.
          · 동적 서브셋이라 실제 쓰인 글자만 내려받고, 차단되면 tailwind.config.ts 의
            폴백(Apple SD Gothic Neo / 맑은 고딕)으로 자연스럽게 떨어진다.
        */}
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
