"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, extractErrorMessage } from "@/lib/api";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("인증 링크가 올바르지 않습니다.");
      return;
    }
    api
      .get("/api/auth/verify-email", { params: { token } })
      .then(({ data }) => {
        setStatus("success");
        setMessage(data.message);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(extractErrorMessage(err));
      });
  }, [token]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
        {status === "loading" && <p className="text-sm text-slate-500">이메일 인증을 처리하고 있습니다...</p>}
        {status === "success" && (
          <>
            <h1 className="mb-2 text-lg font-bold text-brand-700">인증 완료</h1>
            <p className="mb-4 text-sm text-slate-600">{message}</p>
            <Link href="/login" className="rounded bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700">
              로그인하러 가기
            </Link>
          </>
        )}
        {status === "error" && (
          <>
            <h1 className="mb-2 text-lg font-bold text-red-600">인증 실패</h1>
            <p className="mb-4 text-sm text-slate-600">{message}</p>
            <Link href="/signup" className="text-sm text-brand-600 hover:underline">
              회원가입 화면으로 돌아가기
            </Link>
          </>
        )}
      </div>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}
