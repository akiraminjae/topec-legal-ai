"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { RevisionOut } from "@/lib/types";
import { REVISION_LEVEL_LABELS } from "@/lib/labels";
import { ShareMenu } from "@/components/ShareMenu";
import { dejustifyText } from "@/lib/text";

function revisionShareText(r: RevisionOut): string {
  return [
    `[${REVISION_LEVEL_LABELS[r.level] || r.level}]`,
    "",
    `원문: ${r.original_text || "(원문 미확인)"}`,
    `수정안: ${r.revised_text}`,
    `수정 사유: ${r.change_reason}`,
  ].join("\n");
}

export function RevisionsTab({ documentId }: { documentId: string }) {
  const queryClient = useQueryClient();
  const { data: revisions = [], isLoading } = useQuery<RevisionOut[]>({
    queryKey: ["revisions", documentId],
    queryFn: async () => (await api.get<RevisionOut[]>(`/api/documents/${documentId}/revisions`)).data,
  });

  async function act(revisionId: string, action: "accept" | "reject") {
    await api.post(`/api/documents/${documentId}/revisions/${revisionId}/${action}`);
    queryClient.invalidateQueries({ queryKey: ["revisions", documentId] });
  }

  if (isLoading) return <p className="text-slate-400">불러오는 중...</p>;
  if (revisions.length === 0)
    return <div className="rounded border border-slate-200 bg-white p-6 text-center text-slate-400">생성된 수정안이 없습니다.</div>;

  return (
    <div className="flex flex-col gap-3">
      {revisions.map((r) => (
        <div key={r.id} className="rounded border border-slate-200 bg-white p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="rounded bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
              {REVISION_LEVEL_LABELS[r.level] || r.level}
            </span>
            <div className="flex items-center gap-2">
              <span
                className={`text-xs ${
                  r.status === "ACCEPTED" ? "text-green-600" : r.status === "REJECTED" ? "text-slate-400" : "text-slate-500"
                }`}
              >
                {r.status === "ACCEPTED" ? "채택됨" : r.status === "REJECTED" ? "거절됨" : "미결정"}
              </span>
              <ShareMenu title={REVISION_LEVEL_LABELS[r.level] || r.level} text={revisionShareText(r)} />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded bg-red-50 p-3 text-sm">
              <p className="mb-1 text-xs font-medium text-red-700">원문</p>
              <p className="whitespace-pre-wrap text-slate-700">{dejustifyText(r.original_text) || "(원문 미확인)"}</p>
            </div>
            <div className="rounded bg-green-50 p-3 text-sm">
              <p className="mb-1 text-xs font-medium text-green-700">수정안</p>
              <p className="whitespace-pre-wrap text-slate-700">{r.revised_text}</p>
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-500">수정 사유: {r.change_reason}</p>
          <div className="mt-3 flex gap-2">
            <button onClick={() => act(r.id, "accept")} className="btn-primary">
              채택
            </button>
            <button onClick={() => act(r.id, "reject")} className="btn-secondary">
              거절
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
