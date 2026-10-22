"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, KeyRound, Loader2, Lock, User, type LucideIcon } from "lucide-react";
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
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-ink-100 px-4 py-10">
      {/* 배경 장식 — 내용 위에 겹치지 않도록 포인터 이벤트와 접근성에서 제외 */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_40rem_at_50%_-10%,theme(colors.brand.100),transparent)]"
      />

      <div className="relative w-full max-w-[25rem]">
        <div className="card overflow-hidden">
          <div className="px-8 pb-6 pt-8 text-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo.png" alt="TOPEC Legal AI" className="mx-auto h-auto w-full max-w-[17rem]" />
            <p className="mt-3 text-sm text-ink-500">TOPEC 임직원 전용 사내 시스템입니다.</p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-8 pb-8">
            <Field label="이메일 또는 사번" icon={User}>
              <input
                className="input pl-9"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                autoComplete="username"
                placeholder="you@topec.co.kr"
                required
              />
            </Field>

            <Field label="비밀번호" icon={Lock}>
              <input
                type="password"
                className="input pl-9"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </Field>

            {needsTotp && (
              <Field label="2단계 인증 코드" icon={KeyRound}>
                <input
                  className="input pl-9 tabular tracking-[0.3em]"
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="000000"
                  maxLength={6}
                  autoFocus
                />
              </Field>
            )}

            {error && (
              <p className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
                <span>{error}</span>
              </p>
            )}

            <button type="submit" disabled={loading} className="btn-primary mt-1 h-10 w-full">
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? "로그인 중..." : "로그인"}
            </button>

            <p className="text-center text-sm text-ink-500">
              계정이 없으신가요?{" "}
              <Link href="/signup" className="font-medium text-brand-700 hover:underline">
                회원가입
              </Link>
            </p>
          </form>
        </div>

        <p className="mt-5 text-center text-xs leading-relaxed text-ink-400">
          본 시스템은 TOPEC 내부 임직원 업무지원 목적으로만 사용됩니다.
          <br />
          AI 검토 결과는 참고용 1차 검토자료이며 최종 법률판단을 대체하지 않습니다.
        </p>
      </div>
    </main>
  );
}

/** 라벨 + 왼쪽 아이콘이 붙은 입력 한 벌. 아이콘 자리만큼 input 에 pl-9 를 준다. */
function Field({
  label,
  icon: Icon,
  children,
}: {
  label: string;
  icon: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <span className="relative block">
        <Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" strokeWidth={2} />
        {children}
      </span>
    </label>
  );
}
