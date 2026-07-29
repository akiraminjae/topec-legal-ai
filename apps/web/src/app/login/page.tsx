"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";

export default function LoginPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/api/auth/login", {
        identifier,
        password,
        totp_code: totpCode || undefined,
      });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      router.push("/dashboard");
    } catch (err) {
      const message = extractErrorMessage(err);
      if (message.includes("2단계 인증")) {
        setNeedsTotp(true);
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 text-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="TOPEC Legal AI" className="mx-auto mb-3 h-auto w-full max-w-[320px] rounded" />
          <p className="mt-1 text-sm text-slate-500">TOPEC 임직원 전용 사내 시스템입니다.</p>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-sm text-slate-600">이메일 또는 사번</label>
            <input
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-600">비밀번호</label>
            <input
              type="password"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {needsTotp && (
            <div>
              <label className="mb-1 block text-sm text-slate-600">2단계 인증 코드</label>
              <input
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
              />
            </div>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="mt-2 rounded bg-brand-600 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? "로그인 중..." : "로그인"}
          </button>
        </form>
        <div className="mt-4 text-center">
          <Link href="/signup" className="text-sm text-brand-600 hover:underline">
            계정이 없으신가요? 회원가입
          </Link>
        </div>
        <p className="mt-6 text-center text-xs text-slate-400">
          본 시스템은 TOPEC 내부 임직원 업무지원 목적으로만 사용됩니다.
          <br />
          AI 검토 결과는 참고용 1차 검토자료이며 최종 법률판단을 대체하지 않습니다.
        </p>
      </div>
    </main>
  );
}
