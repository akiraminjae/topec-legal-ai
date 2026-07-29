"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { LegalReviewRequestOut } from "@/lib/types";
import { LEGAL_REVIEW_STATUS_LABELS } from "@/lib/labels";
import { RiskBadge } from "@/components/Badges";
import { useAuth } from "@/lib/auth";

export default function LegalReviewInboxPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<LegalReviewRequestOut | null>(null);
  const [opinion, setOpinion] = useState("");
  const [adjustedRisk, setAdjustedRisk] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: requests = [], isLoading } = useQuery<LegalReviewRequestOut[]>({
    queryKey: ["legal-reviews"],
    queryFn: async () => (await api.get<LegalReviewRequestOut[]>("/api/legal-reviews")).data,
  });

  const order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "ACCEPTABLE"];
  const sorted = [...requests].sort(
    (a, b) => order.indexOf(a.overall_risk_level || "") - order.indexOf(b.overall_risk_level || "")
  );

  async function assignToMe(id: string) {
    if (!user) return;
    await api.post(`/api/legal-reviews/${id}/assign`, { reviewer_id: user.id });
    queryClient.invalidateQueries({ queryKey: ["legal-reviews"] });
  }

  async function decide(action: "approve" | "reject" | "request-revision") {
    if (!selected) return;
    setError(null);
    try {
      await api.post(`/api/legal-reviews/${selected.id}/${action}`, {
        opinion,
        adjusted_risk_level: adjustedRisk || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["legal-reviews"] });
      setSelected(null);
      setOpinion("");
      setAdjustedRisk("");
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <h1 className="mb-4 text-xl font-bold text-slate-800">법무 검토함</h1>
        <div className="rounded border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="p-3">계약명</th>
                <th>위험등급</th>
                <th>상태</th>
                <th>담당자</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id} className="cursor-pointer border-b border-slate-100 hover:bg-slate-50" onClick={() => setSelected(r)}>
                  <td className="p-3">
                    <Link href={`/documents/${r.document_id}`} className="text-brand-700 hover:underline" onClick={(e) => e.stopPropagation()}>
                      {r.document_title}
                    </Link>
                  </td>
                  <td><RiskBadge level={r.overall_risk_level} /></td>
                  <td>{LEGAL_REVIEW_STATUS_LABELS[r.status] || r.status}</td>
                  <td>{r.assigned_to_name || "-"}</td>
                  <td>
                    {!r.assigned_to_name && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          assignToMe(r.id);
                        }}
                        className="text-xs text-brand-600 hover:underline"
                      >
                        내가 담당
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {!isLoading && sorted.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-400">
                    검토 요청이 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded border border-slate-200 bg-white p-4">
        <h2 className="mb-3 font-semibold text-slate-700">검토의견 작성</h2>
        {!selected ? (
          <p className="text-sm text-slate-400">왼쪽 목록에서 검토할 문서를 선택하세요.</p>
        ) : (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">{selected.document_title}</p>
            <textarea className="input" rows={4} placeholder="검토의견" value={opinion} onChange={(e) => setOpinion(e.target.value)} />
            <select className="input" value={adjustedRisk} onChange={(e) => setAdjustedRisk(e.target.value)}>
              <option value="">위험등급 조정 안함</option>
              <option value="CRITICAL">매우 높음</option>
              <option value="HIGH">높음</option>
              <option value="MEDIUM">보통</option>
              <option value="LOW">낮음</option>
              <option value="ACCEPTABLE">적정</option>
            </select>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-2">
              <button onClick={() => decide("approve")} className="btn-primary">승인</button>
              <button onClick={() => decide("request-revision")} className="btn-secondary">보완요청</button>
              <button onClick={() => decide("reject")} className="btn-secondary">반려</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
