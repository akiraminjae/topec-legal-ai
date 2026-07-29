"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { CaseAnalysisSummaryOut, LegalCaseOut } from "@/lib/types";
import { AIProviderBadge } from "@/components/Badges";
import { ShareMenu } from "@/components/ShareMenu";

export function AnalysisTab({ caseId, legalCase }: { caseId: string; legalCase: LegalCaseOut }) {
  const queryClient = useQueryClient();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: analysis } = useQuery<CaseAnalysisSummaryOut | null>({
    queryKey: ["case-analysis", caseId],
    queryFn: async () => {
      const { data } = await api.get<CaseAnalysisSummaryOut | null>(`/api/legal-cases/${caseId}/analysis`);
      return data;
    },
  });

  async function runAnalysis() {
    setRunning(true);
    setError(null);
    try {
      await api.post(`/api/legal-cases/${caseId}/analysis`);
      queryClient.invalidateQueries({ queryKey: ["case-analysis", caseId] });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setRunning(false);
    }
  }

  const shareText = analysis
    ? [
        `[사건 개요] ${analysis.case_overview}`,
        `[상대방 주장] ${analysis.opponent_arguments_summary}`,
        `[TOPEC 입장] ${analysis.topec_position_summary}`,
        `[핵심 쟁점] ${analysis.key_issues_summary}`,
        `[누락 및 미대응사항] ${analysis.missing_or_unaddressed}`,
        `[종합 대응방향] ${analysis.recommended_response_direction}`,
      ].join("\n\n")
    : "";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between rounded border border-slate-200 bg-white p-4">
        <div>
          <h3 className="font-semibold text-slate-700">사건 통합분석</h3>
          <p className="text-xs text-slate-500">
            업로드된 문서들의 개별 1차 분석결과를 종합하여 사건 전체 관점의 요약을 생성합니다. 문서가 추가되면 다시
            실행해 최신 자료를 반영하세요.
          </p>
        </div>
        <button disabled={running} onClick={runAnalysis} className="btn-primary shrink-0">
          {running ? "분석 중..." : analysis ? "다시 통합분석 실행" : "통합분석 실행"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {!analysis && !running && (
        <div className="rounded border border-slate-200 bg-white p-6 text-center text-slate-400">
          아직 통합분석 결과가 없습니다. 문서 업로드 및 개별 처리가 완료된 후 &quot;통합분석 실행&quot;을 눌러주세요.
        </div>
      )}

      {analysis && (
        <div className="rounded border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {analysis.ai_provider && <AIProviderBadge provider={analysis.ai_provider} isMock={analysis.is_mock} />}
              <span className="text-xs text-slate-400">분석 대상 문서 {analysis.document_count}건</span>
            </div>
            <ShareMenu title={`${legalCase.case_name} 사건 통합분석`} text={shareText} />
          </div>

          <Section title="사건 개요" value={analysis.case_overview} />
          <Section title="상대방 주장" value={analysis.opponent_arguments_summary} />
          <Section title="TOPEC 입장" value={analysis.topec_position_summary} />
          <Section title="핵심 쟁점" value={analysis.key_issues_summary} />
          <Section title="누락 및 미대응사항" value={analysis.missing_or_unaddressed} />
          <Section title="종합 대응방향" value={analysis.recommended_response_direction} />
        </div>
      )}
    </div>
  );
}

function Section({ title, value }: { title: string; value: string }) {
  return (
    <div className="mb-4">
      <h4 className="mb-1 text-sm font-semibold text-slate-700">{title}</h4>
      <p className="whitespace-pre-wrap text-sm text-slate-600">{value}</p>
    </div>
  );
}
