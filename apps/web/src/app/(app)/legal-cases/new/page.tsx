"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { api, extractErrorMessage } from "@/lib/api";
import {
  CASE_TYPE_SUGGESTIONS,
  DISPUTE_TYPE_SUGGESTIONS,
  SECURITY_LEVEL_LABELS,
  TOPEC_LITIGATION_POSITION_LABELS,
} from "@/lib/labels";

interface FormValues {
  case_name: string;
  case_type: string;
  dispute_type: string;
  case_number: string;
  court_name: string;
  topec_position: string;
  opponent_name: string;
  opponent_counsel: string;
  topec_counsel: string;
  claim_amount: string;
  security_level: string;
  first_event_date: string;
  filing_date: string;
  summary: string;
  key_issues_to_check: string;
  additional_instructions: string;
}

export default function NewLegalCasePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { register, handleSubmit } = useForm<FormValues>({
    defaultValues: { security_level: "CONFIDENTIAL" },
  });

  async function onSubmit(values: FormValues) {
    setError(null);
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        case_name: values.case_name,
        case_type: values.case_type || undefined,
        dispute_type: values.dispute_type || undefined,
        case_number: values.case_number || undefined,
        court_name: values.court_name || undefined,
        topec_position: values.topec_position || undefined,
        opponent_name: values.opponent_name || undefined,
        opponent_counsel: values.opponent_counsel || undefined,
        topec_counsel: values.topec_counsel || undefined,
        claim_amount: values.claim_amount ? Number(values.claim_amount) : undefined,
        security_level: values.security_level,
        first_event_date: values.first_event_date || undefined,
        filing_date: values.filing_date || undefined,
        summary: values.summary || undefined,
        key_issues_to_check: values.key_issues_to_check || undefined,
        additional_instructions: values.additional_instructions || undefined,
      };
      const { data: legalCase } = await api.post("/api/legal-cases", payload);
      router.push(`/legal-cases/${legalCase.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-xl font-bold text-slate-800">새 사건 등록</h1>
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 rounded border border-slate-200 bg-white p-6">
        <Field label="사건명">
          <input className="input" {...register("case_name")} required placeholder="예: OO공사 공사대금 청구소송" />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="사건유형">
            <input className="input" list="case-type-suggestions" {...register("case_type")} placeholder="예: 소송" />
            <datalist id="case-type-suggestions">
              {CASE_TYPE_SUGGESTIONS.map((v) => (
                <option key={v} value={v} />
              ))}
            </datalist>
          </Field>
          <Field label="분쟁유형">
            <input className="input" list="dispute-type-suggestions" {...register("dispute_type")} placeholder="예: 공사대금" />
            <datalist id="dispute-type-suggestions">
              {DISPUTE_TYPE_SUGGESTIONS.map((v) => (
                <option key={v} value={v} />
              ))}
            </datalist>
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="사건번호 (모르면 비워두세요)">
            <input className="input" {...register("case_number")} placeholder="예: 2026가합12345" />
          </Field>
          <Field label="법원 또는 기관">
            <input className="input" {...register("court_name")} placeholder="예: 서울중앙지방법원" />
          </Field>
        </div>

        <Field label="TOPEC의 소송상 지위">
          <select className="input" {...register("topec_position")}>
            <option value="">선택</option>
            {Object.entries(TOPEC_LITIGATION_POSITION_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </Field>

        <div className="grid grid-cols-3 gap-4">
          <Field label="상대방">
            <input className="input" {...register("opponent_name")} />
          </Field>
          <Field label="상대방 대리인">
            <input className="input" {...register("opponent_counsel")} />
          </Field>
          <Field label="TOPEC 대리인">
            <input className="input" {...register("topec_counsel")} />
          </Field>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <Field label="청구금액(원, 모르면 비워두세요)">
            <input type="number" className="input" {...register("claim_amount")} />
          </Field>
          <Field label="최초 사건 발생일">
            <input type="date" className="input" {...register("first_event_date")} />
          </Field>
          <Field label="소 제기일">
            <input type="date" className="input" {...register("filing_date")} />
          </Field>
        </div>

        <Field label="보안등급">
          <select className="input" {...register("security_level")}>
            {Object.entries(SECURITY_LEVEL_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </Field>
        <p className="-mt-2 rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
          소송·분쟁 사건은 기본적으로 &quot;극비&quot;를 권장합니다. 극비 등급은 내부망 AI(LocalModelProvider) 설정 전까지
          사건 통합분석·AI 질의응답이 제한됩니다. 실제 AI 분석을 바로 사용하려면 보안등급을 낮추세요.
        </p>

        <Field label="사건 개요">
          <textarea className="input" rows={3} {...register("summary")} />
        </Field>
        <Field label="반드시 확인할 쟁점">
          <textarea className="input" rows={2} {...register("key_issues_to_check")} />
        </Field>
        <Field label="추가 지시사항">
          <textarea className="input" rows={2} {...register("additional_instructions")} />
        </Field>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 rounded bg-brand-600 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "등록 중..." : "사건 등록 (파일은 다음 화면에서 일괄 업로드)"}
        </button>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm text-slate-600">{label}</label>
      {children}
    </div>
  );
}
