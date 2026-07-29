"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { CaseDocumentRelationOut } from "@/lib/types";
import { RELATION_TYPE_LABELS } from "@/lib/labels";

export function RelationsTab({ caseId }: { caseId: string }) {
  const { data: relations = [], isLoading } = useQuery<CaseDocumentRelationOut[]>({
    queryKey: ["case-relations", caseId],
    queryFn: async () => (await api.get<CaseDocumentRelationOut[]>(`/api/legal-cases/${caseId}/relations`)).data,
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-500">
        &quot;사건 통합분석&quot; 탭에서 통합분석을 실행하면 문서 간 관계(응답/반박/보충/개정/인용/모순
        등)도 함께 분석됩니다.
      </div>

      {isLoading && <p className="text-slate-400">불러오는 중...</p>}
      {!isLoading && relations.length === 0 && (
        <div className="rounded border border-slate-200 bg-white p-6 text-center text-slate-400">
          아직 분석된 문서 간 관계가 없습니다. 통합분석을 먼저 실행하세요.
        </div>
      )}

      <ul className="flex flex-col gap-2">
        {relations.map((r) => (
          <li key={r.id} className="rounded border border-slate-200 bg-white p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Link href={`/documents/${r.document_a_id}`} className="font-medium text-brand-700 hover:underline">
                {r.document_a_title}
              </Link>
              <span className="rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                {RELATION_TYPE_LABELS[r.relation_type] || r.relation_type}
              </span>
              <Link href={`/documents/${r.document_b_id}`} className="font-medium text-brand-700 hover:underline">
                {r.document_b_title}
              </Link>
            </div>
            {r.reasoning && <p className="mt-1 text-xs text-slate-500">{r.reasoning}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
