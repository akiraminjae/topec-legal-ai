"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DocumentOut } from "@/lib/types";
import { RiskBadge, StatusBadge } from "@/components/Badges";
import { CONTRACT_TYPE_LABELS, documentTypeLabel } from "@/lib/labels";

export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [contractType, setContractType] = useState("");
  const [riskLevel, setRiskLevel] = useState("");

  const { data: documents = [], isLoading } = useQuery<DocumentOut[]>({
    queryKey: ["documents", search, contractType, riskLevel],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (search) params.search = search;
      if (contractType) params.contract_type = contractType;
      if (riskLevel) params.risk_level = riskLevel;
      return (await api.get<DocumentOut[]>("/api/documents", { params })).data;
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">내 문서</h1>
        <Link href="/documents/new" className="rounded bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700">
          + 계약서 업로드
        </Link>
      </div>

      <div className="flex flex-wrap gap-2 rounded border border-slate-200 bg-white p-3">
        <input
          className="rounded border border-slate-300 px-3 py-1.5 text-sm"
          placeholder="계약명 검색"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="rounded border border-slate-300 px-3 py-1.5 text-sm"
          value={contractType}
          onChange={(e) => setContractType(e.target.value)}
        >
          <option value="">전체 계약유형</option>
          {Object.entries(CONTRACT_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <select
          className="rounded border border-slate-300 px-3 py-1.5 text-sm"
          value={riskLevel}
          onChange={(e) => setRiskLevel(e.target.value)}
        >
          <option value="">전체 위험등급</option>
          <option value="CRITICAL">매우 높음</option>
          <option value="HIGH">높음</option>
          <option value="MEDIUM">보통</option>
          <option value="LOW">낮음</option>
          <option value="ACCEPTABLE">적정</option>
        </select>
      </div>

      <div className="rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="p-3">계약명</th>
              <th>유형</th>
              <th>상대방</th>
              <th>부서</th>
              <th>상태</th>
              <th>위험등급</th>
              <th>등록일</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="p-3">
                  <Link href={`/documents/${d.id}`} className="text-brand-700 hover:underline">
                    {d.title}
                  </Link>
                </td>
                <td>{documentTypeLabel(d)}</td>
                <td>{d.counterparty_name || "-"}</td>
                <td>{d.department || "-"}</td>
                <td><StatusBadge status={d.status} /></td>
                <td><RiskBadge level={d.overall_risk_level} /></td>
                <td className="text-slate-500">{new Date(d.created_at).toLocaleDateString("ko-KR")}</td>
              </tr>
            ))}
            {!isLoading && documents.length === 0 && (
              <tr>
                <td colSpan={7} className="py-6 text-center text-slate-400">
                  조건에 맞는 문서가 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
