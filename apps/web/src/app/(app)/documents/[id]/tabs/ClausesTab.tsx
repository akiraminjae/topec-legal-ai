"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ClauseOut } from "@/lib/types";
import { dejustifyText } from "@/lib/text";

export function ClausesTab({ documentId }: { documentId: string }) {
  const { data: clauses = [], isLoading } = useQuery<ClauseOut[]>({
    queryKey: ["clauses", documentId],
    queryFn: async () => (await api.get<ClauseOut[]>(`/api/documents/${documentId}/clauses`)).data,
  });

  if (isLoading) return <p className="text-ink-400">불러오는 중...</p>;
  if (clauses.length === 0)
    return <div className="card p-6 text-center text-ink-400">추출된 조항이 없습니다.</div>;

  return (
    <div className="flex flex-col gap-2">
      {clauses.map((c) => (
        <div key={c.id} className="card p-5">
          <div className="mb-1 flex items-center gap-2 text-sm">
            <span className="font-semibold text-ink-700">{c.clause_no || `문단 ${c.order_index + 1}`}</span>
            {c.title && <span className="text-ink-500">({c.title})</span>}
            <span className="rounded bg-ink-100 px-2 py-0.5 text-xs text-ink-500">{c.clause_type}</span>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">{dejustifyText(c.original_text)}</p>
        </div>
      ))}
    </div>
  );
}
