"use client";

import { useState } from "react";
import Link from "next/link";
import { api, extractErrorMessage } from "@/lib/api";

export default function SignupPage() {
  const [form, setForm] = useState({
    employee_no: "",
    full_name: "",
    phone_number: "",
    email: "",
    password: "",
    passwordConfirm: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);
  const [resendMessage, setResendMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (form.password !== form.passwordConfirm) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }
    if (form.password.length < 10) {
      setError("비밀번호는 10자 이상이어야 합니다.");
      return;
    }
    setLoading(true);
    try {
      await api.post("/api/auth/signup", {
        employee_no: form.employee_no,
        full_name: form.full_name,
        phone_number: form.phone_number,
        email: form.email,
        password: form.password,
      });
      setSubmittedEmail(form.email);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (!submittedEmail) return;
    setResendMessage(null);
    try {
      const { data } = await api.post("/api/auth/resend-verification", { identifier: submittedEmail });
      setResendMessage(data.message);
    } catch (err) {
      setResendMessage(extractErrorMessage(err));
    }
  }

  if (submittedEmail) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="mb-2 text-lg font-bold text-brand-700">인증 메일을 발송했습니다</h1>
          <p className="mb-4 text-sm text-slate-600">
            <strong>{submittedEmail}</strong>로 발송된 인증 메일의 링크를 클릭한 후, 관리자 승인이 완료되면 로그인할 수
            있습니다.
          </p>
          <button onClick={handleResend} className="text-sm text-brand-600 hover:underline">
            인증 메일 다시 받기
          </button>
          {resendMessage && <p className="mt-2 text-xs text-slate-500">{resendMessage}</p>}
          <div className="mt-6 border-t border-slate-100 pt-4">
            <Link href="/login" className="text-sm text-slate-500 hover:underline">
              로그인 화면으로 이동
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 text-center">
          <h1 className="text-lg font-bold text-brand-700">회원가입</h1>
          <p className="mt-1 text-sm text-slate-500">TOPEC 임직원 회사 이메일로만 가입할 수 있습니다.</p>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <Field label="사용자 ID" value={form.employee_no} onChange={(v) => setForm({ ...form, employee_no: v })} />
          <Field label="이름" value={form.full_name} onChange={(v) => setForm({ ...form, full_name: v })} />
          <Field
            label="휴대폰 번호"
            value={form.phone_number}
            onChange={(v) => setForm({ ...form, phone_number: v })}
            placeholder="010-1234-5678"
          />
          <Field
            label="회사 이메일"
            type="email"
            value={form.email}
            onChange={(v) => setForm({ ...form, email: v })}
          />
          <Field
            label="비밀번호 (10자 이상)"
            type="password"
            value={form.password}
            onChange={(v) => setForm({ ...form, password: v })}
          />
          <Field
            label="비밀번호 확인"
            type="password"
            value={form.passwordConfirm}
            onChange={(v) => setForm({ ...form, passwordConfirm: v })}
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="mt-2 rounded bg-brand-600 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? "신청 중..." : "가입 신청"}
          </button>
        </form>
        <div className="mt-6 text-center">
          <Link href="/login" className="text-sm text-slate-500 hover:underline">
            이미 계정이 있으신가요? 로그인
          </Link>
        </div>
      </div>
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm text-slate-600">{label}</label>
      <input
        type={type}
        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required
      />
    </div>
  );
}
