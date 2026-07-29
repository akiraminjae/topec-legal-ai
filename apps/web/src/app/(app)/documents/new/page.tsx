"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { api, extractErrorMessage } from "@/lib/api";
import {
  CONTRACT_TYPE_LABELS,
  DOCUMENT_CATEGORY_LABELS,
  LITIGATION_DOCUMENT_TYPE_LABELS,
  RETENTION_POLICY_LABELS,
  SECURITY_LEVEL_LABELS,
  TOPEC_LITIGATION_POSITION_LABELS,
  TOPEC_POSITION_LABELS,
} from "@/lib/labels";

interface FormValues {
  title: string;
  document_category: "CONTRACT" | "LITIGATION";
  contract_type: string;
  topec_position: string;
  litigation_document_type: string;
  topec_litigation_position: string;
  case_number: string;
  court: string;
  counterparty_name: string;
  project_name: string;
  contract_amount: string;
  contract_start_date: string;
  contract_end_date: string;
  security_level: string;
  retention_policy: string;
  additional_notes: string;
}

export default function NewDocumentPage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  function addFiles(fileList: FileList | null) {
    if (!fileList) return;
    const next = Array.from(fileList);
    setFiles((prev) => {
      // 같은 이름+크기 파일 중복 추가 방지
      const existingKeys = new Set(prev.map((f) => `${f.name}-${f.size}`));
      const deduped = next.filter((f) => !existingKeys.has(`${f.name}-${f.size}`));
      return [...prev, ...deduped];
    });
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  const { register, handleSubmit, watch } = useForm<FormValues>({
    defaultValues: { document_category: "CONTRACT", security_level: "INTERNAL", retention_policy: "KEEP_1_YEAR" },
  });

  const category = watch("document_category");

  async function onSubmit(values: FormValues) {
    setError(null);
    if (files.length === 0) {
      setError("문서 파일을 첨부해 주세요.");
      return;
    }
    if (category === "CONTRACT" && (!values.contract_type || !values.topec_position)) {
      setError("계약유형과 TOPEC 계약상 지위를 선택하세요.");
      return;
    }
    if (category === "LITIGATION" && (!values.litigation_document_type || !values.topec_litigation_position)) {
      setError("문서유형과 TOPEC의 소송상 지위를 선택하세요.");
      return;
    }

    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        title: values.title,
        document_category: values.document_category,
        counterparty_name: values.counterparty_name || undefined,
        project_name: values.project_name || undefined,
        security_level: values.security_level,
        retention_policy: values.retention_policy,
        additional_notes: values.additional_notes || undefined,
      };
      if (category === "CONTRACT") {
        payload.contract_type = values.contract_type;
        payload.topec_position = values.topec_position;
        payload.contract_amount = values.contract_amount ? Number(values.contract_amount) : undefined;
        payload.contract_start_date = values.contract_start_date || undefined;
        payload.contract_end_date = values.contract_end_date || undefined;
      } else {
        payload.litigation_document_type = values.litigation_document_type;
        payload.topec_litigation_position = values.topec_litigation_position;
        payload.case_number = values.case_number || undefined;
        payload.court = values.court || undefined;
      }

      const { data: document } = await api.post("/api/documents", payload);

      // 여러 파일을 순차 업로드한다. AI 분석은 첫 번째(주) 파일을 대상으로 수행되므로,
      // 마지막 파일 업로드에서만 분석을 트리거하고 나머지는 참고 첨부파일로만 저장한다.
      for (let i = 0; i < files.length; i++) {
        setUploadStatus(`파일 업로드 중... (${i + 1}/${files.length}) ${files[i].name}`);
        const formData = new FormData();
        formData.append("file", files[i]);
        const isLast = i === files.length - 1;
        await api.post(`/api/documents/${document.id}/files`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
          params: { skip_analysis: !isLast },
        });
      }
      router.push(`/documents/${document.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
      setUploadStatus(null);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-xl font-bold text-slate-800">문서 업로드</h1>
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 rounded border border-slate-200 bg-white p-6">
        <Field label="검토 종류">
          <select className="input" {...register("document_category")}>
            {Object.entries(DOCUMENT_CATEGORY_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </Field>

        <Field label={category === "LITIGATION" ? "문서명" : "계약명"}>
          <input className="input" {...register("title")} required />
        </Field>

        {category === "CONTRACT" ? (
          <>
            <div className="grid grid-cols-2 gap-4">
              <Field label="계약유형">
                <select className="input" {...register("contract_type")}>
                  <option value="">선택</option>
                  {Object.entries(CONTRACT_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="TOPEC 계약상 지위">
                <select className="input" {...register("topec_position")}>
                  <option value="">선택</option>
                  {Object.entries(TOPEC_POSITION_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Field label="계약금액(원)"><input type="number" className="input" {...register("contract_amount")} /></Field>
              <Field label="계약 시작일"><input type="date" className="input" {...register("contract_start_date")} /></Field>
              <Field label="계약 종료일"><input type="date" className="input" {...register("contract_end_date")} /></Field>
            </div>
          </>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4">
              <Field label="문서유형">
                <select className="input" {...register("litigation_document_type")}>
                  <option value="">선택</option>
                  {Object.entries(LITIGATION_DOCUMENT_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="TOPEC의 소송상 지위">
                <select className="input" {...register("topec_litigation_position")}>
                  <option value="">선택</option>
                  {Object.entries(TOPEC_LITIGATION_POSITION_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="사건번호"><input className="input" placeholder="예: 2026가합12345" {...register("case_number")} /></Field>
              <Field label="법원"><input className="input" placeholder="예: 서울중앙지방법원" {...register("court")} /></Field>
            </div>
          </>
        )}

        <div className="grid grid-cols-2 gap-4">
          <Field label="상대방"><input className="input" {...register("counterparty_name")} /></Field>
          <Field label="프로젝트명/현장명"><input className="input" {...register("project_name")} /></Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="보안등급">
            <select className="input" {...register("security_level")}>
              {Object.entries(SECURITY_LEVEL_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
          <Field label="문서 보존기간">
            <select className="input" {...register("retention_policy")}>
              {Object.entries(RETENTION_POLICY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
        </div>

        {category === "LITIGATION" && (
          <p className="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
            소송·분쟁 문서는 보안등급을 &quot;극비&quot;로 설정하는 것을 권장합니다. 극비 등급은 내부망
            AI(LocalModelProvider) 설정 전까지 AI 분석이 제한됩니다.
          </p>
        )}

        <Field label="추가 검토요청사항">
          <textarea className="input" rows={3} {...register("additional_notes")} />
        </Field>

        <Field label="파일 (PDF/이미지/DOCX/HWPX/HWP/TXT) — 여러 개 첨부 가능">
          <input
            type="file"
            multiple
            className="text-sm"
            accept=".pdf,.jpg,.jpeg,.png,.docx,.hwpx,.hwp,.txt"
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <p className="mt-1 text-xs text-slate-400">
            여러 파일을 한 번에 선택하거나, 선택창을 다시 열어 추가로 첨부할 수 있습니다. AI 분석은
            첨부한 모든 파일의 내용을 통합하여 수행되며, 첫 번째 파일이 주 파일(분석 기준)로 사용됩니다.
          </p>

          {files.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1">
              {files.map((f, i) => (
                <li
                  key={`${f.name}-${f.size}-${i}`}
                  className="flex items-center justify-between rounded border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs"
                >
                  <span className="truncate">
                    {i === 0 && (
                      <span className="mr-2 rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">
                        주 파일(분석대상)
                      </span>
                    )}
                    {f.name}
                    <span className="ml-2 text-slate-400">({(f.size / 1024).toFixed(0)}KB)</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    className="ml-2 shrink-0 text-slate-400 hover:text-red-600"
                  >
                    제거
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Field>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 rounded bg-brand-600 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? uploadStatus || "업로드 중..." : "업로드 및 AI 검토 시작"}
        </button>
      </form>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm text-slate-600">{label}</label>
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
