"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DocumentOut, ProcessingStatusOut } from "@/lib/types";
import {
  CONTRACT_TYPE_LABELS,
  LITIGATION_DOCUMENT_TYPE_LABELS,
  TOPEC_LITIGATION_POSITION_LABELS,
  TOPEC_POSITION_LABELS,
  SECURITY_LEVEL_LABELS,
} from "@/lib/labels";
import { RiskBadge, StatusBadge, AIDisclaimerBanner } from "@/components/Badges";
import { ProgressGauge } from "@/components/ProgressGauge";
import { OverviewTab } from "./tabs/OverviewTab";
import { RiskTab } from "./tabs/RiskTab";
import { RevisionsTab } from "./tabs/RevisionsTab";
import { ChatTab } from "./tabs/ChatTab";
import { LegalReviewTab } from "./tabs/LegalReviewTab";
import { ClausesTab } from "./tabs/ClausesTab";

function buildTabs(isLitigation: boolean) {
  const tabs = [
    { key: "overview", label: "개요" },
    { key: "clauses", label: isLitigation ? "원문/쟁점" : "원문/조항" },
    { key: "risk", label: isLitigation ? "쟁점 분석" : "위험분석" },
  ];
  if (!isLitigation) {
    tabs.push({ key: "revisions", label: "수정안" });
  }
  tabs.push({ key: "chat", label: "AI 질의응답" }, { key: "legal", label: "법무검토" });
  return tabs;
}

const IN_PROGRESS_STATUSES = new Set([
  "UPLOADED",
  "VALIDATING",
  "EXTRACTING",
  "OCR_PROCESSING",
  "STRUCTURING",
  "ANALYZING",
]);

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const documentId = params.id;
  const [tab, setTab] = useState("overview");

  const { data: document } = useQuery<DocumentOut>({
    queryKey: ["document", documentId],
    queryFn: async () => (await api.get<DocumentOut>(`/api/documents/${documentId}`)).data,
    refetchInterval: (query) => (IN_PROGRESS_STATUSES.has(query.state.data?.status || "") ? 3000 : false),
  });

  const { data: processing } = useQuery<ProcessingStatusOut>({
    queryKey: ["processing-status", documentId],
    queryFn: async () => (await api.get<ProcessingStatusOut>(`/api/documents/${documentId}/processing-status`)).data,
    refetchInterval: (query) => (IN_PROGRESS_STATUSES.has(query.state.data?.document_status || "") ? 3000 : false),
  });

  if (!document) {
    return <p className="text-slate-400">불러오는 중...</p>;
  }

  const inProgress = IN_PROGRESS_STATUSES.has(document.status);
  const isLitigation = document.document_category === "LITIGATION";
  const TABS = buildTabs(isLitigation);

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded border border-slate-200 bg-white p-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-lg font-bold text-slate-800">{document.title}</h1>
            <p className="text-sm text-slate-500">
              {isLitigation ? (
                <>
                  {LITIGATION_DOCUMENT_TYPE_LABELS[document.litigation_document_type || ""] ||
                    document.litigation_document_type}{" "}
                  · TOPEC{" "}
                  {TOPEC_LITIGATION_POSITION_LABELS[document.topec_litigation_position || ""] ||
                    document.topec_litigation_position}{" "}
                  · {document.case_number || "사건번호 미확인"} · {document.court || "법원 미확인"}
                </>
              ) : (
                <>
                  {CONTRACT_TYPE_LABELS[document.contract_type || ""] || document.contract_type} ·{" "}
                  {TOPEC_POSITION_LABELS[document.topec_position || ""] || document.topec_position}
                </>
              )}{" "}
              · {SECURITY_LEVEL_LABELS[document.security_level] || document.security_level}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <StatusBadge status={document.status} />
            <RiskBadge level={document.overall_risk_level} />
          </div>
        </div>

        {document.status === "FAILED" && (
          <div className="mt-3 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            분석에 실패했습니다. 관리자 또는 법무담당자에게 문의하세요.
          </div>
        )}

        {inProgress && processing && (
          <div className="mt-4 flex items-center gap-5">
            <ProgressGauge percent={processing.progress_percent} />
            <div className="min-w-0 flex-1">
              <p className="mb-2 text-sm font-medium text-slate-600">
                AI 분석 진행 중...{" "}
                <span className="text-slate-400">
                  {processing.jobs.find((j) => j.status === "RUNNING")?.step || ""}
                </span>
              </p>
              <div className="mb-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-brand-500 transition-[width] duration-700 ease-out"
                  style={{ width: `${processing.progress_percent}%` }}
                />
              </div>
              <ol className="grid grid-cols-2 gap-1 text-xs md:grid-cols-5">
                {processing.jobs.map((job, i) => (
                  <li
                    key={i}
                    className={`rounded border px-2 py-1 ${
                      job.status === "DONE"
                        ? "border-green-300 bg-green-50 text-green-700"
                        : job.status === "FAILED"
                          ? "border-red-300 bg-red-50 text-red-700"
                          : job.status === "RUNNING"
                            ? "border-brand-300 bg-brand-50 text-brand-700"
                            : "border-slate-200 bg-slate-50 text-slate-400"
                    }`}
                  >
                    {job.step}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium ${
              tab === t.key ? "border-b-2 border-brand-600 text-brand-700" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div>
        {tab === "overview" && <OverviewTab documentId={documentId} document={document} />}
        {tab === "clauses" && <ClausesTab documentId={documentId} />}
        {tab === "risk" && <RiskTab documentId={documentId} />}
        {tab === "revisions" && <RevisionsTab documentId={documentId} />}
        {tab === "chat" && <ChatTab documentId={documentId} />}
        {tab === "legal" && <LegalReviewTab documentId={documentId} document={document} />}
      </div>

      <AIDisclaimerBanner />
    </div>
  );
}
