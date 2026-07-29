"use client";

/** KakaoTalk sharing via the Kakao JavaScript SDK.
 *
 * Requires an app key issued at https://developers.kakao.com (JavaScript key,
 * under 내 애플리케이션 > 앱 키) — this can't be generated on the user's behalf
 * since it requires their own Kakao Developers account. Configure it as
 * NEXT_PUBLIC_KAKAO_JS_KEY; until then, `isKakaoConfigured()` returns false and
 * every caller shows a "카카오 SDK 키가 설정되지 않았습니다" state instead of
 * silently failing.
 */

declare global {
  interface Window {
    Kakao?: {
      isInitialized: () => boolean;
      init: (key: string) => void;
      Share: {
        sendDefault: (options: Record<string, unknown>) => void;
      };
    };
  }
}

const KAKAO_SDK_URL = "https://t1.kakaocdn.net/kakao_js_sdk/2.8.1/kakao.min.js";
const KAKAO_SDK_INTEGRITY =
  "sha384-OL+ylM/iuPLtW5U3XcvLSGhE8JzReKDank5InqlHGWPhb4140/yrBw0bg0y7+C9J";
let sdkLoadPromise: Promise<void> | null = null;

export function isKakaoConfigured(): boolean {
  return !!process.env.NEXT_PUBLIC_KAKAO_JS_KEY;
}

function loadKakaoSdk(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("브라우저 환경이 아닙니다."));
  if (window.Kakao) return Promise.resolve();
  if (sdkLoadPromise) return sdkLoadPromise;

  sdkLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = KAKAO_SDK_URL;
    script.integrity = KAKAO_SDK_INTEGRITY;
    script.crossOrigin = "anonymous";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("카카오 SDK 로드에 실패했습니다."));
    document.head.appendChild(script);
  });
  return sdkLoadPromise;
}

async function ensureKakaoInitialized(): Promise<void> {
  const key = process.env.NEXT_PUBLIC_KAKAO_JS_KEY;
  if (!key) throw new Error("카카오 SDK 키(NEXT_PUBLIC_KAKAO_JS_KEY)가 설정되지 않았습니다.");
  await loadKakaoSdk();
  if (!window.Kakao) throw new Error("카카오 SDK 로드에 실패했습니다.");
  if (!window.Kakao.isInitialized()) {
    window.Kakao.init(key);
  }
}

export async function shareToKakao(title: string, description: string, url?: string): Promise<void> {
  await ensureKakaoInitialized();
  const pageUrl = url || (typeof window !== "undefined" ? window.location.href : "");
  // "text" template (not "feed") — no imageUrl required, appropriate for sharing
  // a text excerpt of an internal review result rather than a rich link card.
  window.Kakao!.Share.sendDefault({
    objectType: "text",
    text: `${title}\n\n${description.slice(0, 180)}`,
    link: { webUrl: pageUrl, mobileWebUrl: pageUrl },
  });
}
