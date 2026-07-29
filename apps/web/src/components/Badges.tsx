import {
  AI_PROVIDER_ICONS,
  AI_PROVIDER_LABELS,
  DOCUMENT_STATUS_LABELS,
  RISK_LEVEL_COLORS,
  RISK_LEVEL_LABELS,
} from "@/lib/labels";

export function RiskBadge({ level }: { level: string | null }) {
  if (!level) return <span className="text-xs text-slate-400">미분석</span>;
  const color = RISK_LEVEL_COLORS[level] || "bg-slate-100 text-slate-700 border-slate-300";
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${color}`}>
      ⚠ {RISK_LEVEL_LABELS[level] || level}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const label = DOCUMENT_STATUS_LABELS[status] || status;
  const isFailed = status === "FAILED";
  const isDone = status === "COMPLETED";
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${
        isFailed
          ? "border-red-300 bg-red-50 text-red-700"
          : isDone
            ? "border-green-300 bg-green-50 text-green-700"
            : "border-slate-300 bg-slate-50 text-slate-600"
      }`}
    >
      {label}
    </span>
  );
}

export function AIDisclaimerBanner() {
  return (
    <div className="rounded border border-amber-300 bg-amber-50 p-3 text-xs leading-relaxed text-amber-800">
      <strong>AI 1차 검토 결과</strong> — 본 결과는 AI를 활용한 1차 계약·법률 검토 지원자료입니다. 사실관계, 계약상
      지위 및 적용 법령에 따라 판단이 달라질 수 있습니다. 중요 계약, 분쟁 가능 계약 또는 고위험 조항이 있는 경우
      법무담당자나 외부 법률전문가의 확인을 거쳐야 합니다.
    </div>
  );
}

/** Shows which AI actually generated a result (Claude/Gemini/OpenAI/Mock) instead
 * of a bare confidence percentage — the user explicitly asked to see the model
 * identity, not just a number. */
export function AIProviderBadge({ provider, isMock }: { provider: string | null | undefined; isMock?: boolean | null }) {
  if (!provider) return null;
  const mock = isMock ?? provider === "mock";
  const label = AI_PROVIDER_LABELS[provider] || provider;
  const icon = AI_PROVIDER_ICONS[provider] || "🤖";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        mock
          ? "border-purple-300 bg-purple-50 text-purple-700"
          : "border-brand-300 bg-brand-50 text-brand-700"
      }`}
      title={mock ? "테스트용 Mock 응답입니다" : `${label}가 생성한 실제 AI 응답입니다`}
    >
      <span>{icon}</span>
      {label}
      {mock && <span className="text-purple-500">(테스트)</span>}
    </span>
  );
}

export function MockModeBanner({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <div className="rounded border border-purple-300 bg-purple-50 p-2 text-xs text-purple-800">
      🧪 Mock AI 모드입니다. 실제 AI 판단이 아닌 테스트용 예시 결과입니다. 관리자 설정에서 실제 AI Provider를
      연결하면 문맥 기반 심층분석이 제공됩니다.
    </div>
  );
}
