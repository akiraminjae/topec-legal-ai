"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, extractErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ChangePasswordPage() {
  const { user, refetch } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("새 비밀번호가 일치하지 않습니다.");
      return;
    }
    if (newPassword.length < 10) {
      setError("비밀번호는 10자 이상이어야 합니다.");
      return;
    }
    setLoading(true);
    try {
      await api.post("/api/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      refetch();
      router.push("/dashboard");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="mb-1 text-lg font-bold text-brand-700">비밀번호 변경</h1>
        <p className="mb-6 text-sm text-slate-500">
          {user?.must_change_password
            ? "최초 로그인입니다. 새 비밀번호로 변경해 주세요."
            : "비밀번호를 변경합니다."}
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-sm text-slate-600">현재 비밀번호</label>
            <input
              type="password"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-600">새 비밀번호 (10자 이상)</label>
            <input
              type="password"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-600">새 비밀번호 확인</label>
            <input
              type="password"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="mt-2 rounded bg-brand-600 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? "변경 중..." : "비밀번호 변경"}
          </button>
        </form>
      </div>
    </main>
  );
}
