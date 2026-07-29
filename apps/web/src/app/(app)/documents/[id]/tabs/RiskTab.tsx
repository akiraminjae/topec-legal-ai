"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DocumentSummaryOut, FindingOut } from "@/lib/types";
import { RISK_LEVEL_LABELS } from "@/lib/labels";
import { RiskBadge, AIProviderBadge } from "@/components/Badges";
import { ShareMenu } from "@/components/ShareMenu";
import { dejustifyText } from "@/lib/text";

function findingShareText(f: FindingOut): string {
  const lines = [
    `[${RISK_LEVEL_LABELS[f.risk_level] || f.risk_level}] ${f.title}`,
    "",
    `위험 사유: ${f.reason}`,
    `TOPEC에 미치는 영향: ${f.impact_on_topec}`,
    `권고 대응: ${f.recommended_action}`,
  ];
  if (f.questions_for_user.length > 0) lines.push(`추가 확인사항: ${f.questions_for_user.join(", ")}`);
  return lines.join("\n");
}

export function RiskTab({ documentId }: { documentId: string }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const { data: findings = [], isLoading } = useQuery<FindingOut[]>({
    queryKey: ["findings", documentId],
    queryFn: async () => (await api.get<FindingOut[]>(`/api/documents/${documentId}/findings`)).data,
  });

  const { data: summary } = useQuery<DocumentSummaryOut | null>({
    queryKey: ["summary", documentId],
    queryFn: async () => {
      try {
        return (await api.get<DocumentSummaryOut>(`/api/documents/${documentId}/analysis`)).data;
      } catch {
        return null;
      }
    },
  });

  const filtered = filter ? findings.filter((f) => f.risk_level === filter) : findings;
  const order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "ACCEPTABLE"];
  const sorted = [...filtered].sort((a, b) => order.indexOf(a.risk_level) - order.indexOf(b.risk_level));

  if (isLoading) return <p className="text-slate-400">불러오는 중...</p>;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2">
          <FilterChip label="전체" active={filter === ""} onClick={() => setFilter("")} />
          {order.map((level) => (
            <FilterChip key={level} label={RISK_LEVEL_LABELS[level]} active={filter === level} onClick={() => setFilter(level)} />
          ))}
        </div>
        {summary?.ai_provider && <AIProviderBadge provider={summary.ai_provider} isMock={summary.is_mock} />}
      </div>

      {sorted.length === 0 && (
        <div className="rounded border border-slate-200 bg-white p-6 text-center text-slate-400">
          탐지된 위험사항이 없습니다.
        </div>
      )}

      {sorted.map((f) => (
        <div key={f.id} className="rounded border border-slate-200 bg-white">
          <button
            className="flex w-full items-center justify-between p-4 text-left"
            onClick={() => setExpanded(expanded === f.id ? null : f.id)}
          >
            <div className="flex items-center gap-3">
              <RiskBadge level={f.risk_level} />
              <span className="font-medium text-slate-700">{f.title}</span>
              {f.legal_review_required && (
                <span className="rounded bg-red-50 px-2 py-0.5 text-xs text-red-600">법무검토 필요</span>
              )}
            </div>
            <span
              className="rounded-full border border-slate-200 px-2 py-0.5 text-xs text-slate-400"
              title="AI 판단 신뢰도(참고용)"
            >
              신뢰도 참고값 {f.confidence}%
            </span>
          </button>
          {expanded === f.id && (
            <div className="border-t border-slate-100 p-4 text-sm">
              <div className="mb-3 flex justify-end">
                <ShareMenu title={f.title} text={findingShareText(f)} />
              </div>
              <Row label="원문" value={dejustifyText(f.original_text) || "(원문 미확인)"} />
              <Row label="위험 사유" value={f.reason} />
              <Row label="TOPEC에 미치는 영향" value={f.impact_on_topec} />
              <Row label="권고 대응" value={f.recommended_action} />
              {f.questions_for_user.length > 0 && (
                <Row label="추가 확인사항" value={f.questions_for_user.join(", ")} />
              )}
              <div className="mt-2">
                <p className="mb-1 text-xs font-medium text-slate-500">관련 법령·판례</p>
                {f.citations.length === 0 ? (
                  <p className="text-xs text-slate-400">현재 연결된 법률자료에서는 직접 확인되는 근거를 찾지 못했습니다.</p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {f.citations.map((c, i) => (
                      <li key={i} className="rounded bg-slate-50 p-2 text-xs">
                        <strong>[{c.source_type}]</strong> {c.source_title} {c.verified ? "" : "(미검증)"}
                        <p className="mt-1 text-slate-500">{c.excerpt}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-2">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="whitespace-pre-wrap text-slate-700">{value}</p>
    </div>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs ${
        active ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-white text-slate-600"
      }`}
    >
      {label}
    </button>
  );
}
