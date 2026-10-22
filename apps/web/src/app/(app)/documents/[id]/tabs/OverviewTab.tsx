"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { CrossReviewOut, DocumentFileOut, DocumentOut, DocumentSummaryOut } from "@/lib/types";
import { Download, FileCheck2, FileDown, FileText, Paperclip, ScrollText, Users } from "lucide-react";
import { clsx } from "clsx";
import { MockModeBanner, AIProviderBadge } from "@/components/Badges";
import { ShareMenu } from "@/components/ShareMenu";
import { Card, CardBody, CardHeader, EmptyState, Notice } from "@/components/ui";

interface ReportOut {
  id: string;
  report_type: string;
  format: string;
  pdf_conversion_failed: boolean;
}

export function OverviewTab({ documentId, document }: { documentId: string; document: DocumentOut }) {
  const queryClient = useQueryClient();
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const { data: reports = [] } = useQuery<ReportOut[]>({
    queryKey: ["reports", documentId],
    queryFn: async () => (await api.get<ReportOut[]>(`/api/documents/${documentId}/reports`)).data,
  });

  const { data: files = [] } = useQuery<DocumentFileOut[]>({
    queryKey: ["document-files", documentId],
    queryFn: async () => (await api.get<DocumentFileOut[]>(`/api/documents/${documentId}/files`)).data,
  });

  const { data: crossReview } = useQuery<CrossReviewOut | null>({
    queryKey: ["cross-review", documentId],
    queryFn: async () => (await api.get<CrossReviewOut | null>(`/api/documents/${documentId}/cross-review`)).data,
  });

  async function downloadFile(fileId: string, filename: string) {
    const res = await api.get(`/api/documents/${documentId}/files/${fileId}`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const a = window.document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function generateReport(reportType: string, format: string) {
    setGenerating(true);
    setError(null);
    try {
      await api.post(`/api/documents/${documentId}/reports`, { report_type: reportType, format });
      queryClient.invalidateQueries({ queryKey: ["reports", documentId] });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  async function download(reportId: string, format: string, reportType: string) {
    const res = await api.get(`/api/documents/${documentId}/reports/${reportId}/download`, { responseType: "blob" });
    const ext = format === "PDF" ? "pdf" : "docx";
    const label = reportType === "REVISION_REQUEST_LETTER" ? "수정요청서" : "검토보고서";
    const safeTitle = (document.title || "문서").replace(/[\\/:*?"<>|]/g, "_");
    const url = window.URL.createObjectURL(res.data);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `${safeTitle}_${label}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function generateAndDownload(format: "DOCX" | "PDF") {
    setGenerating(true);
    setError(null);
    try {
      const res = await api.post(`/api/documents/${documentId}/reports`, { report_type: "REVIEW_REPORT", format });
      queryClient.invalidateQueries({ queryKey: ["reports", documentId] });
      await download(res.data.id, res.data.format, "REVIEW_REPORT");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <MockModeBanner show={!!summary} />

      {summary?.ai_provider && (
        <div className="flex items-center justify-between">
          <AIProviderBadge provider={summary.ai_provider} isMock={summary.is_mock} />
          {(summary.scope_summary || summary.top_risks_summary) && (
            <ShareMenu
              title={`${document.title || "문서"} 검토 요약`}
              text={`업무범위 요약\n${summary.scope_summary || "-"}\n\n주요 위험 요약\n${summary.top_risks_summary || "-"}`}
              onDownloadWord={() => generateAndDownload("DOCX")}
              onDownloadPdf={() => generateAndDownload("PDF")}
            />
          )}
        </div>
      )}

      <div className="card grid grid-cols-2 gap-5 p-5 text-sm md:grid-cols-4">
        <InfoItem label="상대방" value={document.counterparty_name || "-"} />
        {document.document_category === "LITIGATION" ? (
          <>
            <InfoItem label="사건번호" value={document.case_number || "-"} />
            <InfoItem label="법원" value={document.court || "-"} />
          </>
        ) : (
          <InfoItem
            label="계약금액"
            value={document.contract_amount ? `${document.contract_amount.toLocaleString()}원` : "-"}
          />
        )}
        <InfoItem label="담당부서" value={document.department || "-"} />
        <InfoItem label="법무검토 필요" value={document.legal_review_required ? "예" : "아니오"} />
      </div>

      {files.length > 0 && (
        <Card>
          <CardHeader title={`첨부파일 ${files.length}건`} icon={Paperclip} />
          <CardBody className="flex flex-col gap-1.5 p-3">
            {files.map((f, i) => (
              <div
                key={f.id}
                className="flex items-center gap-3 rounded-md border border-ink-100 px-3 py-2 text-sm hover:bg-ink-50"
              >
                <FileText className="h-4 w-4 shrink-0 text-ink-400" strokeWidth={2} />
                <span className="min-w-0 flex-1 truncate">
                  {i === 0 && (
                    <span className="badge mr-2 border-brand-200 bg-brand-50 text-brand-700">주 파일(분석대상)</span>
                  )}
                  {f.original_filename}
                  <span className="ml-2 text-xs tabular text-ink-400">({(f.size_bytes / 1024).toFixed(0)}KB)</span>
                </span>
                <button
                  onClick={() => downloadFile(f.id, f.original_filename)}
                  className="btn-ghost btn-sm shrink-0 text-brand-700"
                >
                  <Download className="h-3.5 w-3.5" strokeWidth={2} />
                  다운로드
                </button>
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      {summary && (
        <Card>
          <CardHeader title="AI 검토 요약" icon={ScrollText} />
          <CardBody className="flex flex-col gap-4">
            <section>
              <h3 className="mb-1.5 text-sm font-semibold text-ink-900">업무범위 요약</h3>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-600">{summary.scope_summary || "-"}</p>
            </section>
            <section>
              <h3 className="mb-1.5 text-sm font-semibold text-ink-900">주요 위험 요약</h3>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-600">{summary.top_risks_summary || "-"}</p>
            </section>
          </CardBody>
        </Card>
      )}

      {crossReview && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50/60 p-5">
          <div className="mb-2.5 flex flex-wrap items-center gap-2">
            <h3 className="flex items-center gap-1.5 text-base font-semibold text-ink-900">
              <Users className="h-4 w-4 text-indigo-600" strokeWidth={2} />
              듀얼 AI 교차검토
            </h3>
            <AIProviderBadge provider={crossReview.provider} isMock={crossReview.is_mock} />
            <span
              className={clsx(
                "badge",
                crossReview.agreement_level === "AGREE"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : crossReview.agreement_level === "DISAGREE"
                    ? "border-red-200 bg-red-50 text-red-700"
                    : "border-amber-200 bg-amber-50 text-amber-700"
              )}
            >
              {crossReview.agreement_level === "AGREE"
                ? "1차 분석에 동의"
                : crossReview.agreement_level === "DISAGREE"
                  ? "1차 분석에 이견"
                  : "부분 동의"}
            </span>
            {crossReview.confidence !== null && (
              <span className="text-xs tabular text-ink-500">확신도 {crossReview.confidence}%</span>
            )}
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">{crossReview.overall_opinion}</p>
          {crossReview.additional_risks && (
            <>
              <h4 className="mb-1 mt-4 text-sm font-semibold text-ink-900">2차 AI가 지적한 추가 리스크</h4>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">{crossReview.additional_risks}</p>
            </>
          )}
          {crossReview.missed_points && (
            <>
              <h4 className="mb-1 mt-4 text-sm font-semibold text-ink-900">1차 분석이 누락한 논점</h4>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">{crossReview.missed_points}</p>
            </>
          )}
        </div>
      )}

      <Card>
        <CardHeader
          title="검토보고서 생성"
          icon={FileDown}
          description="생성한 보고서는 아래 목록에서 내려받을 수 있습니다."
        />
        <CardBody className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            <button disabled={generating} onClick={() => generateReport("REVIEW_REPORT", "DOCX")} className="btn-secondary">
              <FileText className="h-4 w-4" strokeWidth={2} />
              검토보고서 (DOCX)
            </button>
            <button disabled={generating} onClick={() => generateReport("REVIEW_REPORT", "PDF")} className="btn-secondary">
              <FileText className="h-4 w-4" strokeWidth={2} />
              검토보고서 (PDF)
            </button>
            {document.document_category !== "LITIGATION" && (
              <button
                disabled={generating}
                onClick={() => generateReport("REVISION_REQUEST_LETTER", "DOCX")}
                className="btn-secondary"
              >
                <FileCheck2 className="h-4 w-4" strokeWidth={2} />
                상대방 수정요청서 (DOCX)
              </button>
            )}
          </div>

          {error && <Notice tone="danger">{error}</Notice>}

          {reports.length === 0 ? (
            <EmptyState icon={FileDown} title="생성된 보고서가 없습니다." compact />
          ) : (
            <div className="flex flex-col gap-1.5">
              {reports.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center gap-3 rounded-md border border-ink-100 px-3 py-2 text-sm hover:bg-ink-50"
                >
                  <FileText className="h-4 w-4 shrink-0 text-ink-400" strokeWidth={2} />
                  <span className="min-w-0 flex-1">
                    {r.report_type === "REVISION_REQUEST_LETTER" ? "수정요청서" : "검토보고서"}{" "}
                    <span className="text-ink-400">({r.format})</span>
                    {r.pdf_conversion_failed && (
                      <span className="ml-2 text-xs text-amber-600">PDF 변환 실패 → DOCX 제공</span>
                    )}
                  </span>
                  <button
                    onClick={() => download(r.id, r.format, r.report_type)}
                    className="btn-ghost btn-sm shrink-0 text-brand-700"
                  >
                    <Download className="h-3.5 w-3.5" strokeWidth={2} />
                    다운로드
                  </button>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className="mt-0.5 truncate font-semibold text-ink-900" title={value}>
        {value}
      </p>
    </div>
  );
}
