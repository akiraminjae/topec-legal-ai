"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { CaseReportOut } from "@/lib/types";
import { CASE_REPORT_TYPE_LABELS } from "@/lib/labels";

export function CaseReportsTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const [generating, setGenerating] = useState(false);
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: reports = [] } = useQuery<CaseReportOut[]>({
    queryKey: ["case-reports", caseId],
    queryFn: async () => (await api.get<CaseReportOut[]>(`/api/legal-cases/${caseId}/reports`)).data,
  });

  async function generateReport(reportType: string, format: string) {
    setGenerating(true);
    setError(null);
    try {
      await api.post(`/api/legal-cases/${caseId}/reports`, { report_type: reportType, format, instructions: instructions || undefined });
      queryClient.invalidateQueries({ queryKey: ["case-reports", caseId] });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  async function download(reportId: string, format: string, reportType: string) {
    const res = await api.get(`/api/legal-cases/${caseId}/reports/${reportId}/download`, { responseType: "blob" });
    const ext = format === "PDF" ? "pdf" : "docx";
    const label = CASE_REPORT_TYPE_LABELS[reportType] || reportType;
    const url = window.URL.createObjectURL(res.data);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `${label}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
        먼저 &quot;사건 통합분석&quot; 탭에서 통합분석을 실행해야 대응문서를 생성할 수 있습니다. 생성된 초안은 AI
        1차 초안이며, 담당 변호사·법무담당자의 검토 없이 그대로 제출해서는 안 됩니다.
      </div>

      <div className="rounded border border-slate-200 bg-white p-4">
        <h3 className="mb-3 font-semibold text-slate-700">대응문서 초안 생성</h3>
        <label className="mb-1 block text-sm text-slate-600">담당자 지정 작성지침 (선택)</label>
        <textarea
          className="input mb-3"
          rows={3}
          placeholder="예: 제3차 준비서면의 추가공사대금 주장을 중심으로 반박 논리를 강조해줘."
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <button disabled={generating} onClick={() => generateReport("PREPARATORY_BRIEF_DRAFT", "DOCX")} className="btn-secondary">
            준비서면 초안 (DOCX)
          </button>
          <button disabled={generating} onClick={() => generateReport("PREPARATORY_BRIEF_DRAFT", "PDF")} className="btn-secondary">
            준비서면 초안 (PDF)
          </button>
          <button disabled={generating} onClick={() => generateReport("EXECUTIVE_SUMMARY", "DOCX")} className="btn-secondary">
            경영진 보고 요약 (DOCX)
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      <div className="rounded border border-slate-200 bg-white p-4">
        <h3 className="mb-3 font-semibold text-slate-700">생성된 문서</h3>
        <ul className="flex flex-col gap-1 text-sm">
          {reports.map((r) => (
            <li key={r.id} className="flex items-center justify-between rounded border border-slate-100 px-3 py-1.5">
              <span>
                {CASE_REPORT_TYPE_LABELS[r.report_type] || r.report_type} ({r.format})
                {r.pdf_conversion_failed && <span className="ml-2 text-xs text-amber-600">PDF 변환 실패 → DOCX 제공</span>}
              </span>
              <button onClick={() => download(r.id, r.format, r.report_type)} className="text-brand-600 hover:underline">
                다운로드
              </button>
            </li>
          ))}
          {reports.length === 0 && <li className="text-slate-400">생성된 문서가 없습니다.</li>}
        </ul>
      </div>
    </div>
  );
}
