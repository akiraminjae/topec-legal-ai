"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { TimelineEntryOut } from "@/lib/types";
import { DATE_TYPE_LABELS, LITIGATION_DOCUMENT_TYPE_LABELS } from "@/lib/labels";

export function TimelineTab({ caseId }: { caseId: string }) {
  const { data: timeline = [], isLoading } = useQuery<TimelineEntryOut[]>({
    queryKey: ["case-timeline", caseId],
    queryFn: async () => (await api.get<TimelineEntryOut[]>(`/api/legal-cases/${caseId}/timeline`)).data,
    refetchInterval: 5000,
  });

  const dated = timeline.filter((e) => e.date_value);
  const undated = timeline.filter((e) => !e.date_value);

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-500">
        각 문서에서 AI가 자동 추출한 날짜(작성일·제출일·접수일·송달일 등) 기준으로 정렬되어 있습니다.
        날짜는 문서 원문에 명시된 것만 표시하며, 법정기간(초일 산입, 공휴일 등) 계산은 별도 확인이
        필요합니다.
      </div>

      {isLoading && <p className="text-slate-400">불러오는 중...</p>}
      {!isLoading && timeline.length === 0 && (
        <div className="rounded border border-slate-200 bg-white p-6 text-center text-slate-400">
          타임라인에 표시할 문서가 없습니다.
        </div>
      )}

      {dated.length > 0 && (
        <ol className="relative flex flex-col gap-3 border-l-2 border-slate-200 pl-6">
          {dated.map((e, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-brand-500 bg-white" />
              <div className="rounded border border-slate-200 bg-white p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-700">{e.date_value}</span>
                  <span className="rounded-full border border-brand-300 bg-brand-50 px-2 py-0.5 text-xs text-brand-700">
                    {DATE_TYPE_LABELS[e.date_type] || e.date_type}
                  </span>
                </div>
                <p className="mt-1">
                  <Link href={`/documents/${e.document_id}`} className="font-medium text-brand-700 hover:underline">
                    {e.document_title}
                  </Link>
                  <span className="ml-2 text-xs text-slate-400">
                    {LITIGATION_DOCUMENT_TYPE_LABELS[e.litigation_document_type || ""] || "미분류"}
                  </span>
                </p>
                {e.source_text && <p className="mt-1 text-xs text-slate-500">원문: &quot;{e.source_text}&quot;</p>}
                <p className="mt-1 text-xs text-slate-400">AI 추출 신뢰도 {e.confidence}%</p>
              </div>
            </li>
          ))}
        </ol>
      )}

      {undated.length > 0 && (
        <div className="rounded border border-slate-200 bg-white p-3">
          <h3 className="mb-2 text-sm font-semibold text-slate-600">일자 미확인</h3>
          <ul className="flex flex-col gap-1">
            {undated.map((e, i) => (
              <li key={i} className="text-sm">
                <Link href={`/documents/${e.document_id}`} className="text-brand-700 hover:underline">
                  {e.document_title}
                </Link>
                <span className="ml-2 text-xs text-slate-400">
                  {e.is_fallback_upload_order ? "날짜가 추출되지 않았습니다" : "미분류 날짜"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
