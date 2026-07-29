"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { CaseConflictOut } from "@/lib/types";
import { CONFLICT_SEVERITY_LABELS } from "@/lib/labels";

const SEVERITY_COLOR: Record<string, string> = {
  HIGH: "border-red-300 bg-red-50 text-red-700",
  MEDIUM: "border-amber-300 bg-amber-50 text-amber-700",
  LOW: "border-slate-300 bg-slate-50 text-slate-600",
};

export function ConflictsTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const { data: conflicts = [], isLoading } = useQuery<CaseConflictOut[]>({
    queryKey: ["case-conflicts", caseId],
    queryFn: async () => (await api.get<CaseConflictOut[]>(`/api/legal-cases/${caseId}/conflicts`)).data,
  });

  async function updateStatus(conflictId: string, status: "OPEN" | "RESOLVED") {
    await api.patch(`/api/legal-cases/${caseId}/conflicts/${conflictId}`, { resolution_status: status });
    queryClient.invalidateQueries({ queryKey: ["case-conflicts", caseId] });
  }

  const openCount = conflicts.filter((c) => c.resolution_status === "OPEN").length;

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-500">
        &quot;사건 통합분석&quot; 탭에서 통합분석을 실행하면 문서 간 금액·일자·당사자·사실관계 불일치도
        함께 탐지됩니다. 확인 후 해결 처리할 수 있습니다.
        {conflicts.length > 0 && <span className="ml-1 font-medium text-slate-700">(미해결 {openCount}건)</span>}
      </div>

      {isLoading && <p className="text-slate-400">불러오는 중...</p>}
      {!isLoading && conflicts.length === 0 && (
        <div className="rounded border border-slate-200 bg-white p-6 text-center text-slate-400">
          탐지된 불일치가 없습니다.
        </div>
      )}

      <ul className="flex flex-col gap-2">
        {conflicts.map((c) => (
          <li key={c.id} className={`rounded border bg-white p-3 text-sm ${c.resolution_status === "RESOLVED" ? "opacity-60" : ""}`}>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className={`rounded-full border px-2 py-0.5 text-xs ${SEVERITY_COLOR[c.severity] || SEVERITY_COLOR.LOW}`}>
                  {CONFLICT_SEVERITY_LABELS[c.severity] || c.severity}
                </span>
                <span className="font-medium text-slate-700">{c.conflict_type}</span>
                <span className="text-xs text-slate-400">신뢰도 {c.confidence}%</span>
              </div>
              {c.resolution_status === "RESOLVED" ? (
                <button onClick={() => updateStatus(c.id, "OPEN")} className="text-xs text-slate-500 hover:underline">
                  다시 열기
                </button>
              ) : (
                <button onClick={() => updateStatus(c.id, "RESOLVED")} className="text-xs text-brand-600 hover:underline">
                  해결 처리
                </button>
              )}
            </div>
            <p className="mb-2 text-slate-600">{c.summary}</p>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <div className="rounded bg-slate-50 p-2">
                <p className="text-xs text-slate-400">
                  {c.source_document_a_id ? (
                    <Link href={`/documents/${c.source_document_a_id}`} className="text-brand-700 hover:underline">
                      {c.source_document_a_title}
                    </Link>
                  ) : (
                    "출처 미상"
                  )}
                </p>
                <p className="text-slate-700">{c.value_a}</p>
              </div>
              <div className="rounded bg-slate-50 p-2">
                <p className="text-xs text-slate-400">
                  {c.source_document_b_id ? (
                    <Link href={`/documents/${c.source_document_b_id}`} className="text-brand-700 hover:underline">
                      {c.source_document_b_title}
                    </Link>
                  ) : (
                    "출처 미상"
                  )}
                </p>
                <p className="text-slate-700">{c.value_b}</p>
              </div>
            </div>
            {c.impact && <p className="mt-2 text-xs text-slate-500">TOPEC에 미치는 영향: {c.impact}</p>}
            {c.recommended_check && <p className="mt-1 text-xs text-slate-500">확인 필요: {c.recommended_check}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
