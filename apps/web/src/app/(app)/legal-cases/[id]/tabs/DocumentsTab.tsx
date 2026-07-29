"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { CaseDocumentOut } from "@/lib/types";
import { StatusBadge, RiskBadge } from "@/components/Badges";
import { LITIGATION_DOCUMENT_TYPE_LABELS } from "@/lib/labels";

export function DocumentsTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: documents = [], isLoading } = useQuery<CaseDocumentOut[]>({
    queryKey: ["case-documents", caseId],
    queryFn: async () => (await api.get<CaseDocumentOut[]>(`/api/legal-cases/${caseId}/documents`)).data,
    refetchInterval: 5000,
  });

  async function confirmClassification(caseDocumentId: string, documentType?: string) {
    setConfirmingId(caseDocumentId);
    setError(null);
    try {
      await api.post(`/api/legal-cases/${caseId}/documents/${caseDocumentId}/confirm`, {
        document_type: documentType,
      });
      queryClient.invalidateQueries({ queryKey: ["case-documents", caseId] });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setConfirmingId(null);
    }
  }

  if (isLoading) return <p className="text-slate-400">불러오는 중...</p>;
  if (documents.length === 0)
    return (
      <div className="rounded border border-slate-200 bg-white p-6 text-center text-slate-400">
        아직 업로드된 문서가 없습니다. &quot;사건자료 일괄 업로드&quot; 탭에서 파일을 추가하세요.
      </div>
    );

  return (
    <div className="flex flex-col gap-3">
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="overflow-x-auto rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="p-3">순번</th>
              <th>문서명</th>
              <th>문서유형</th>
              <th>AI 분류(신뢰도)</th>
              <th>사건정보(AI 추출)</th>
              <th>상태</th>
              <th>위험등급</th>
              <th>업로드일</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id} className="border-b border-slate-100 align-top hover:bg-slate-50">
                <td className="p-3 text-slate-400">{d.sequence_number}</td>
                <td>
                  <Link href={`/documents/${d.document_id}`} className="text-brand-700 hover:underline">
                    {d.title}
                  </Link>
                  {d.is_duplicate && (
                    <div className="mt-1">
                      <span className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">중복 파일</span>
                    </div>
                  )}
                </td>
                <td>{LITIGATION_DOCUMENT_TYPE_LABELS[d.litigation_document_type || ""] || "미분류"}</td>
                <td>
                  {d.ai_suggested_document_type ? (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-slate-600">
                        {LITIGATION_DOCUMENT_TYPE_LABELS[d.ai_suggested_document_type] || d.ai_suggested_document_type}{" "}
                        ({d.classification_confidence}%)
                      </span>
                      {d.needs_user_confirmation && (
                        <button
                          disabled={confirmingId === d.id}
                          onClick={() => confirmClassification(d.id, d.ai_suggested_document_type || undefined)}
                          className="w-fit rounded border border-amber-400 bg-amber-50 px-2 py-0.5 text-xs text-amber-800 hover:bg-amber-100"
                        >
                          ⚠ 확인 필요 — 클릭하여 확정
                        </button>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400">미실행</span>
                  )}
                </td>
                <td className="text-xs text-slate-500">
                  {d.extracted_case_number && <div>사건번호: {d.extracted_case_number}</div>}
                  {d.extracted_court && <div>법원: {d.extracted_court}</div>}
                  {d.extracted_plaintiff && <div>원고: {d.extracted_plaintiff}</div>}
                  {d.extracted_defendant && <div>피고: {d.extracted_defendant}</div>}
                  {!d.extracted_case_number && !d.extracted_court && !d.extracted_plaintiff && !d.extracted_defendant && "-"}
                </td>
                <td>
                  <StatusBadge status={d.status} />
                </td>
                <td>
                  <RiskBadge level={d.overall_risk_level} />
                </td>
                <td className="text-slate-500">{new Date(d.created_at).toLocaleString("ko-KR")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
