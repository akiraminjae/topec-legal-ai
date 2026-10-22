import { AlertTriangle, Bot, CheckCircle2, CircleDot, FlaskConical, Loader2, XCircle } from "lucide-react";
import { clsx } from "clsx";
import {
  AI_PROVIDER_ICONS,
  AI_PROVIDER_LABELS,
  DOCUMENT_STATUS_LABELS,
  RISK_LEVEL_COLORS,
  RISK_LEVEL_LABELS,
} from "@/lib/labels";

export function RiskBadge({ level }: { level: string | null }) {
  if (!level) return <span className="text-xs text-ink-400">미분석</span>;
  const color = RISK_LEVEL_COLORS[level] || "border-ink-200 bg-ink-100 text-ink-600";
  return (
    <span className={clsx("badge", color)}>
      <AlertTriangle className="h-3 w-3" strokeWidth={2.4} />
      {RISK_LEVEL_LABELS[level] || level}
    </span>
  );
}

/** 상태 배지. 진행 중인 단계는 도는 아이콘으로 "아직 처리 중"임이 한눈에 보이게 한다. */
export function StatusBadge({ status }: { status: string }) {
  const label = DOCUMENT_STATUS_LABELS[status] || status;
  const settled = ["COMPLETED", "FAILED", "DELETED", "ARCHIVED"].includes(status);

  if (status === "FAILED") {
    return (
      <span className="badge border-red-200 bg-red-50 text-red-700">
        <XCircle className="h-3 w-3" strokeWidth={2.4} />
        {label}
      </span>
    );
  }
  if (status === "COMPLETED") {
    return (
      <span className="badge border-emerald-200 bg-emerald-50 text-emerald-700">
        <CheckCircle2 className="h-3 w-3" strokeWidth={2.4} />
        {label}
      </span>
    );
  }
  if (settled) {
    return (
      <span className="badge border-ink-200 bg-ink-100 text-ink-600">
        <CircleDot className="h-3 w-3" strokeWidth={2.4} />
        {label}
      </span>
    );
  }
  return (
    <span className="badge border-brand-200 bg-brand-50 text-brand-700">
      <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2.4} />
      {label}
    </span>
  );
}

export function AIDisclaimerBanner() {
  return (
    <div className="flex gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
      <p className="text-xs leading-relaxed">
        <strong className="font-semibold">AI 1차 검토 결과</strong> — 본 결과는 AI를 활용한 1차 계약·법률 검토
        지원자료입니다. 사실관계, 계약상 지위 및 적용 법령에 따라 판단이 달라질 수 있습니다. 중요 계약, 분쟁 가능
        계약 또는 고위험 조항이 있는 경우 법무담당자나 외부 법률전문가의 확인을 거쳐야 합니다.
      </p>
    </div>
  );
}

/** 어떤 AI가 만든 결과인지 표시 — 사용자가 확신도 숫자 대신 모델 이름을 보고 싶어 했다. */
export function AIProviderBadge({ provider, isMock }: { provider: string | null | undefined; isMock?: boolean | null }) {
  if (!provider) return null;
  const mock = isMock ?? provider === "mock";
  const label = AI_PROVIDER_LABELS[provider] || provider;
  const icon = AI_PROVIDER_ICONS[provider];
  return (
    <span
      className={clsx("badge", mock ? "border-purple-200 bg-purple-50 text-purple-700" : "border-brand-200 bg-brand-50 text-brand-700")}
      title={mock ? "테스트용 Mock 응답입니다" : `${label}가 생성한 실제 AI 응답입니다`}
    >
      {icon ? <span aria-hidden>{icon}</span> : <Bot className="h-3 w-3" strokeWidth={2.4} />}
      {label}
      {mock && <span className="text-purple-500">(테스트)</span>}
    </span>
  );
}

export function MockModeBanner({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <div className="flex gap-2.5 rounded-lg border border-purple-200 bg-purple-50 px-4 py-3 text-purple-900">
      <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
      <p className="text-xs leading-relaxed">
        Mock AI 모드입니다. 실제 AI 판단이 아닌 테스트용 예시 결과입니다. 관리자 설정에서 실제 AI Provider를
        연결하면 문맥 기반 심층분석이 제공됩니다.
      </p>
    </div>
  );
}
