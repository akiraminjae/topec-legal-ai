"use client";

// 사용자 매뉴얼 — 전 직원이 볼 수 있습니다.
// 본문: src/content/manuals/employee.md

import employeeManual from "@/content/manuals/employee.md";
import { ManualViewer } from "@/components/ManualViewer";

export default function ManualPage() {
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">사용자 매뉴얼</h1>
      <p className="mb-6 text-sm text-slate-500">
        왼쪽 목차에서 항목을 고르면 오른쪽에 사용 방법이 표시됩니다.
      </p>
      <ManualViewer markdown={employeeManual} label="사용자 매뉴얼" />
    </div>
  );
}
