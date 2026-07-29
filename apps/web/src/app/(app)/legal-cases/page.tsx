"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { LegalCaseOut } from "@/lib/types";
import { RiskBadge } from "@/components/Badges";
import { LEGAL_CASE_STATUS_LABELS } from "@/lib/labels";

export default function LegalCasesPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");

  const { data: cases = [], isLoading } = useQuery<LegalCaseOut[]>({
    queryKey: ["legal-cases", search, status],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (search) params.search = search;
      if (status) params.status_filter = status;
      return (await api.get<LegalCaseOut[]>("/api/legal-cases", { params })).data;
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">소송·분쟁 사건</h1>
        <Link href="/legal-cases/new" className="rounded bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700">
          + 새 사건 등록
        </Link>
      </div>

      <div className="flex flex-wrap gap-2 rounded border border-slate-200 bg-white p-3">
        <input
          className="rounded border border-slate-300 px-3 py-1.5 text-sm"
          placeholder="사건명 검색"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="rounded border border-slate-300 px-3 py-1.5 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">전체 상태</option>
          {Object.entries(LEGAL_CASE_STATUS_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="p-3">사건명</th>
              <th>사건번호</th>
              <th>법원</th>
              <th>상대방</th>
              <th>담당부서</th>
              <th>상태</th>
              <th>문서 수</th>
              <th>미분류</th>
              <th>전체 위험도</th>
              <th>등록일</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="p-3">
                  <Link href={`/legal-cases/${c.id}`} className="text-brand-700 hover:underline">
                    {c.case_name}
                  </Link>
                </td>
                <td>{c.case_number || "-"}</td>
                <td>{c.court_name || "-"}</td>
                <td>{c.opponent_name || "-"}</td>
                <td>{c.department || "-"}</td>
                <td>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs ${
                      c.status === "ACTIVE" ? "border-blue-300 bg-blue-50 text-blue-700" : "border-slate-300 bg-slate-50 text-slate-500"
                    }`}
                  >
                    {LEGAL_CASE_STATUS_LABELS[c.status] || c.status}
                  </span>
                </td>
                <td>{c.document_count}</td>
                <td>{c.unclassified_count > 0 ? <span className="text-amber-600">{c.unclassified_count}</span> : "-"}</td>
                <td>
                  <RiskBadge level={c.overall_risk_level} />
                </td>
                <td className="text-slate-500">{new Date(c.created_at).toLocaleDateString("ko-KR")}</td>
              </tr>
            ))}
            {!isLoading && cases.length === 0 && (
              <tr>
                <td colSpan={10} className="py-6 text-center text-slate-400">
                  등록된 사건이 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
