"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { CrossReviewOut, DocumentFileOut, DocumentOut, DocumentSummaryOut } from "@/lib/types";
import { MockModeBanner, AIProviderBadge } from "@/components/Badges";
import { ShareMenu } from "@/components/ShareMenu";

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

      <div className="grid grid-cols-2 gap-4 rounded border border-slate-200 bg-white p-4 text-sm md:grid-cols-4">
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
        <div className="rounded border border-slate-200 bg-white p-4">
          <h3 className="mb-3 font-semibold text-slate-700">첨부파일 ({files.length}건)</h3>
          <ul className="flex flex-col gap-1">
            {files.map((f, i) => (
              <li
                key={f.id}
                className="flex items-center justify-between rounded border border-slate-100 px-3 py-1.5 text-sm"
              >
                <span className="truncate">
                  {i === 0 && (
                    <span className="mr-2 rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">
                      주 파일(분석대상)
                    </span>
                  )}
                  {f.original_filename}
                  <span className="ml-2 text-xs text-slate-400">({(f.size_bytes / 1024).toFixed(0)}KB)</span>
                </span>
                <button onClick={() => downloadFile(f.id, f.original_filename)} className="shrink-0 text-brand-600 hover:underline">
                  다운로드
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {summary && (
        <div className="rounded border border-slate-200 bg-white p-4">
          <h3 className="mb-2 font-semibold text-slate-700">업무범위 요약</h3>
          <p className="whitespace-pre-wrap text-sm text-slate-600">{summary.scope_summary || "-"}</p>
          <h3 className="mb-2 mt-4 font-semibold text-slate-700">주요 위험 요약</h3>
          <p className="whitespace-pre-wrap text-sm text-slate-600">{summary.top_risks_summary || "-"}</p>
        </div>
      )}

      {crossReview && (
        <div className="rounded border border-indigo-200 bg-indigo-50/50 p-4">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-slate-700">듀얼 AI 교차검토</h3>
            <AIProviderBadge provider={crossReview.provider} isMock={crossReview.is_mock} />
            <span
              className={`rounded px-2 py-0.5 text-xs font-medium ${
                crossReview.agreement_level === "AGREE"
                  ? "bg-green-100 text-green-700"
                  : crossReview.agreement_level === "DISAGREE"
                    ? "bg-red-100 text-red-700"
                    : "bg-amber-100 text-amber-700"
              }`}
            >
              {crossReview.agreement_level === "AGREE"
                ? "1차 분석에 동의"
                : crossReview.agreement_level === "DISAGREE"
                  ? "1차 분석에 이견"
                  : "부분 동의"}
            </span>
            {crossReview.confidence !== null && (
              <span className="text-xs text-slate-400">확신도 {crossReview.confidence}%</span>
            )}
          </div>
          <p className="whitespace-pre-wrap text-sm text-slate-600">{crossReview.overall_opinion}</p>
          {crossReview.additional_risks && (
            <>
              <h4 className="mb-1 mt-3 text-sm font-semibold text-slate-700">2차 AI가 지적한 추가 리스크</h4>
              <p className="whitespace-pre-wrap text-sm text-slate-600">{crossReview.additional_risks}</p>
            </>
          )}
          {crossReview.missed_points && (
            <>
              <h4 className="mb-1 mt-3 text-sm font-semibold text-slate-700">1차 분석이 누락한 논점</h4>
              <p className="whitespace-pre-wrap text-sm text-slate-600">{crossReview.missed_points}</p>
            </>
          )}
        </div>
      )}

      <div className="rounded border border-slate-200 bg-white p-4">
        <h3 className="mb-3 font-semibold text-slate-700">검토보고서 생성</h3>
        <div className="flex flex-wrap gap-2">
          <button disabled={generating} onClick={() => generateReport("REVIEW_REPORT", "DOCX")} className="btn-secondary">
            검토보고서 (DOCX)
          </button>
          <button disabled={generating} onClick={() => generateReport("REVIEW_REPORT", "PDF")} className="btn-secondary">
            검토보고서 (PDF)
          </button>
          <button
            disabled={generating || document.document_category === "LITIGATION"}
            onClick={() => generateReport("REVISION_REQUEST_LETTER", "DOCX")}
            className="btn-secondary"
            hidden={document.document_category === "LITIGATION"}
          >
            상대방 수정요청서 (DOCX)
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        <ul className="mt-3 flex flex-col gap-1 text-sm">
          {reports.map((r) => (
            <li key={r.id} className="flex items-center justify-between rounded border border-slate-100 px-3 py-1.5">
              <span>
                {r.report_type === "REVISION_REQUEST_LETTER" ? "수정요청서" : "검토보고서"} ({r.format})
                {r.pdf_conversion_failed && <span className="ml-2 text-xs text-amber-600">PDF 변환 실패 → DOCX 제공</span>}
              </span>
              <button onClick={() => download(r.id, r.format, r.report_type)} className="text-brand-600 hover:underline">
                다운로드
              </button>
            </li>
          ))}
          {reports.length === 0 && <li className="text-slate-400">생성된 보고서가 없습니다.</li>}
        </ul>
      </div>
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
