"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  FileSearch,
  FileText,
  Loader2,
  MessageSquare,
  RotateCw,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  Wand2,
} from "lucide-react";
import { clsx } from "clsx";
import { api, extractErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
import { Card, CardBody, Notice, TabBar } from "@/components/ui";
import { OverviewTab } from "./tabs/OverviewTab";
import { RiskTab } from "./tabs/RiskTab";
import { RevisionsTab } from "./tabs/RevisionsTab";
import { ChatTab } from "./tabs/ChatTab";
import { LegalReviewTab } from "./tabs/LegalReviewTab";
import { ClausesTab } from "./tabs/ClausesTab";

function buildTabs(isLitigation: boolean) {
  const tabs = [
    { key: "overview", label: "개요", icon: FileText },
    { key: "clauses", label: isLitigation ? "원문/쟁점" : "원문/조항", icon: FileSearch },
    { key: "risk", label: isLitigation ? "쟁점 분석" : "위험분석", icon: ShieldAlert },
  ];
  if (!isLitigation) {
    tabs.push({ key: "revisions", label: "수정안", icon: Wand2 });
  }
  tabs.push({ key: "chat", label: "AI 질의응답", icon: MessageSquare }, { key: "legal", label: "법무검토", icon: ShieldCheck });
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
  const [newSecurityLevel, setNewSecurityLevel] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [isReanalyzing, setIsReanalyzing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, hasRole } = useAuth();

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
    return (
      <div className="flex items-center gap-2 text-sm text-ink-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        불러오는 중...
      </div>
    );
  }

  const inProgress = IN_PROGRESS_STATUSES.has(document.status);
  const isLitigation = document.document_category === "LITIGATION";
  const TABS = buildTabs(isLitigation);
  const canManage = user?.id === document.owner_id || hasRole("SYSTEM_ADMIN");
  const failureReason = processing?.failure_reason || document.failure_reason;

  // 제목 아래에 늘어놓을 메타 정보 — 값이 없는 항목은 빼고 가운뎃점으로 잇는다.
  const meta = isLitigation
    ? [
        LITIGATION_DOCUMENT_TYPE_LABELS[document.litigation_document_type || ""] || document.litigation_document_type,
        `TOPEC ${TOPEC_LITIGATION_POSITION_LABELS[document.topec_litigation_position || ""] || document.topec_litigation_position || "지위 미지정"}`,
        document.case_number || "사건번호 미확인",
        document.court || "법원 미확인",
        SECURITY_LEVEL_LABELS[document.security_level] || document.security_level,
      ]
    : [
        CONTRACT_TYPE_LABELS[document.contract_type || ""] || document.contract_type,
        TOPEC_POSITION_LABELS[document.topec_position || ""] || document.topec_position,
        document.counterparty_name,
        SECURITY_LEVEL_LABELS[document.security_level] || document.security_level,
      ];

  async function reanalyze() {
    setActionError(null);
    setIsReanalyzing(true);
    try {
      await api.post(`/api/documents/${documentId}/reanalyze`);
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
      queryClient.invalidateQueries({ queryKey: ["processing-status", documentId] });
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setIsReanalyzing(false);
    }
  }

  async function changeSecurityLevelAndReanalyze() {
    if (!newSecurityLevel) return;
    setActionError(null);
    setIsReanalyzing(true);
    try {
      await api.patch(`/api/documents/${documentId}`, { security_level: newSecurityLevel });
      await api.post(`/api/documents/${documentId}/reanalyze`);
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
      queryClient.invalidateQueries({ queryKey: ["processing-status", documentId] });
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setIsReanalyzing(false);
    }
  }

  async function handleDelete() {
    if (!confirm("이 문서를 삭제하시겠습니까? 삭제된 문서는 복구할 수 없습니다.")) return;
    setActionError(null);
    setIsDeleting(true);
    try {
      await api.delete(`/api/documents/${documentId}`);
      router.push(isLitigation ? "/legal-cases" : "/documents");
    } catch (err) {
      setActionError(extractErrorMessage(err));
      setIsDeleting(false);
    }
  }

  return (
    <>
      <Card>
        <CardBody className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold leading-snug text-ink-900">{document.title}</h1>
            <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-500">
              {meta
                .filter(Boolean)
                .map((part, i) => (
                  <span key={i} className="flex items-center gap-2">
                    {i > 0 && <span className="text-ink-300">·</span>}
                    {part}
                  </span>
                ))}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <StatusBadge status={document.status} />
            <RiskBadge level={document.overall_risk_level} />
            {canManage && (
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="btn-secondary btn-sm text-red-600 hover:border-red-300 hover:bg-red-50"
              >
                {isDeleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                {isDeleting ? "삭제 중..." : "삭제"}
              </button>
            )}
          </div>
        </CardBody>

        {(actionError || document.status === "FAILED" || (inProgress && processing)) && (
          <div className="flex flex-col gap-3 border-t border-ink-100 p-5">
            {actionError && (
              <Notice tone="danger" icon={AlertCircle}>
                {actionError}
              </Notice>
            )}

            {document.status === "FAILED" && (
              <Notice
                tone="danger"
                icon={AlertCircle}
                title="분석에 실패했습니다"
                actions={
                  <>
                    <button onClick={reanalyze} disabled={isReanalyzing} className="btn-danger btn-sm">
                      {isReanalyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCw className="h-3.5 w-3.5" />}
                      {isReanalyzing ? "재분석 시작 중..." : "재분석 시도"}
                    </button>
                    {canManage && (
                      <>
                        <span className="text-xs text-red-700/70">또는 보안등급 변경 후 재분석</span>
                        <select
                          className="input h-8 w-auto border-red-200 text-xs"
                          value={newSecurityLevel}
                          onChange={(e) => setNewSecurityLevel(e.target.value)}
                        >
                          <option value="">등급 선택</option>
                          {Object.entries(SECURITY_LEVEL_LABELS)
                            .filter(([k]) => k !== document.security_level)
                            .map(([k, v]) => (
                              <option key={k} value={k}>
                                {v}
                              </option>
                            ))}
                        </select>
                        <button
                          onClick={changeSecurityLevelAndReanalyze}
                          disabled={!newSecurityLevel || isReanalyzing}
                          className="btn-secondary btn-sm border-red-300 text-red-700 hover:bg-red-100"
                        >
                          변경 후 재분석
                        </button>
                      </>
                    )}
                  </>
                }
              >
                {failureReason || "관리자 또는 법무담당자에게 문의하세요."}
              </Notice>
            )}

            {inProgress && processing && (
              <div className="flex items-center gap-5 rounded-lg border border-brand-100 bg-brand-50/50 p-4">
                <ProgressGauge percent={processing.progress_percent} />
                <div className="min-w-0 flex-1">
                  <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-ink-700">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-600" />
                    AI 분석 진행 중
                    <span className="font-normal text-ink-500">
                      {processing.jobs.find((j) => j.status === "RUNNING")?.step || ""}
                    </span>
                  </p>
                  <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-white">
                    <div
                      className="h-full rounded-full bg-brand-600 transition-[width] duration-700 ease-out"
                      style={{ width: `${processing.progress_percent}%` }}
                    />
                  </div>
                  <ol className="flex flex-wrap gap-1.5 text-xs">
                    {processing.jobs.map((job, i) => (
                      <li
                        key={i}
                        className={clsx(
                          "rounded-md border px-2 py-1",
                          job.status === "DONE"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : job.status === "FAILED"
                              ? "border-red-200 bg-red-50 text-red-700"
                              : job.status === "RUNNING"
                                ? "border-brand-300 bg-white font-medium text-brand-700"
                                : "border-ink-200 bg-white text-ink-400"
                        )}
                      >
                        {job.step}
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      <div>
        <TabBar tabs={TABS} active={tab} onChange={setTab} />
        <div className="pt-5">
          {tab === "overview" && <OverviewTab documentId={documentId} document={document} />}
          {tab === "clauses" && <ClausesTab documentId={documentId} />}
          {tab === "risk" && <RiskTab documentId={documentId} />}
          {tab === "revisions" && <RevisionsTab documentId={documentId} />}
          {tab === "chat" && <ChatTab documentId={documentId} />}
          {tab === "legal" && <LegalReviewTab documentId={documentId} document={document} />}
        </div>
      </div>

      <AIDisclaimerBanner />
    </>
  );
}
