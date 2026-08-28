"use client";

// 관리자 매뉴얼 — SYSTEM_ADMIN 전용.
// 본문: src/content/manuals/admin.md
// 사이드바에서도 SYSTEM_ADMIN에게만 노출되지만, 주소로 직접 들어오는 경우를 대비해
// 이 화면에서도 권한을 한 번 더 확인합니다.

import Link from "next/link";
import adminManual from "@/content/manuals/admin.md";
import { ManualViewer } from "@/components/ManualViewer";
import { useAuth } from "@/lib/auth";

export default function AdminManualPage() {
  const { hasRole } = useAuth();

  if (!hasRole("SYSTEM_ADMIN")) {
    return (
      <div className="rounded border border-slate-200 bg-white p-6">
        <h1 className="mb-2 text-lg font-bold text-slate-900">관리자 매뉴얼</h1>
        <p className="text-sm text-slate-600">
          이 매뉴얼은 시스템관리자 전용입니다.{" "}
          <Link href="/manual" className="text-brand-700 underline">
            사용자 매뉴얼 보기
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">관리자 매뉴얼</h1>
      <p className="mb-6 text-sm text-slate-500">
        관리자 전용 화면과 운영 업무를 다룹니다. 일반 기능은 사용자 매뉴얼을 참고하세요.
      </p>
      <ManualViewer markdown={adminManual} label="관리자 매뉴얼" />
    </div>
  );
}
