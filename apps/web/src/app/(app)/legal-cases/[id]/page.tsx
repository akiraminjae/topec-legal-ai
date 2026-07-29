"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { LegalCaseOut } from "@/lib/types";
import { LEGAL_CASE_STATUS_LABELS, TOPEC_LITIGATION_POSITION_LABELS } from "@/lib/labels";
import { RiskBadge, AIDisclaimerBanner } from "@/components/Badges";
import { LegalRobotIcon } from "@/components/LegalRobotIcon";
import { UploadTab } from "./tabs/UploadTab";
import { DocumentsTab } from "./tabs/DocumentsTab";
import { TimelineTab } from "./tabs/TimelineTab";
import { AnalysisTab } from "./tabs/AnalysisTab";
import { RelationsTab } from "./tabs/RelationsTab";
import { ConflictsTab } from "./tabs/ConflictsTab";
import { CaseChatTab } from "./tabs/CaseChatTab";
import { CaseReportsTab } from "./tabs/CaseReportsTab";

const TABS = [
  { key: "upload", label: "사건자료 일괄 업로드" },
  { key: "documents", label: "문서 목록" },
  { key: "timeline", label: "사건 타임라인" },
  { key: "analysis", label: "사건 통합분석" },
  { key: "relations", label: "문서 관계" },
  { key: "conflicts", label: "모순·불일치" },
  { key: "chat", label: "사건 AI 질의응답" },
  { key: "reports", label: "대응문서 작성" },
];

export default function LegalCaseDetailPage() {
  const params = useParams<{ id: string }>();
  const caseId = params.id;
  const [tab, setTab] = useState("upload");

  const { data: legalCase } = useQuery<LegalCaseOut>({
    queryKey: ["legal-case", caseId],
    queryFn: async () => (await api.get<LegalCaseOut>(`/api/legal-cases/${caseId}`)).data,
    refetchInterval: 5000,
  });

  if (!legalCase) {
    return <p className="text-slate-400">불러오는 중...</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded border border-slate-200 bg-white p-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-lg font-bold text-slate-800">{legalCase.case_name}</h1>
            <p className="text-sm text-slate-500">
              {legalCase.case_type || "사건유형 미지정"} · {legalCase.dispute_type || "분쟁유형 미지정"} ·{" "}
              {legalCase.case_number || "사건번호 미확인"} · {legalCase.court_name || "법원 미확인"} · TOPEC{" "}
              {TOPEC_LITIGATION_POSITION_LABELS[legalCase.topec_position || ""] || "지위 미지정"}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span
              className={`rounded-full border px-2 py-0.5 text-xs ${
                legalCase.status === "ACTIVE" ? "border-blue-300 bg-blue-50 text-blue-700" : "border-slate-300 bg-slate-50 text-slate-500"
              }`}
            >
              {LEGAL_CASE_STATUS_LABELS[legalCase.status] || legalCase.status}
            </span>
            <RiskBadge level={legalCase.overall_risk_level} />
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-5">
          <InfoItem label="상대방" value={legalCase.opponent_name || "-"} />
          <InfoItem label="담당부서" value={legalCase.department || "-"} />
          <InfoItem
            label="청구금액"
            value={legalCase.claim_amount ? `${legalCase.claim_amount.toLocaleString()} ${legalCase.currency}` : "-"}
          />
          <InfoItem label="등록 문서 수" value={String(legalCase.document_count)} />
          <InfoItem
            label="미분류 문서"
            value={legalCase.unclassified_count > 0 ? `${legalCase.unclassified_count}건` : "없음"}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium ${
              tab === t.key ? "border-b-2 border-brand-600 text-brand-700" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.key === "chat" && <LegalRobotIcon className="h-[18px] w-[18px]" />}
            {t.label}
          </button>
        ))}
      </div>

      <div>
        {tab === "upload" && <UploadTab caseId={caseId} />}
        {tab === "documents" && <DocumentsTab caseId={caseId} />}
        {tab === "timeline" && <TimelineTab caseId={caseId} />}
        {tab === "analysis" && <AnalysisTab caseId={caseId} legalCase={legalCase} />}
        {tab === "relations" && <RelationsTab caseId={caseId} />}
        {tab === "conflicts" && <ConflictsTab caseId={caseId} />}
        {tab === "chat" && <CaseChatTab caseId={caseId} />}
        {tab === "reports" && <CaseReportsTab caseId={caseId} />}
      </div>

      <AIDisclaimerBanner />
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p className="font-medium text-slate-700">{value}</p>
    </div>
  );
}
