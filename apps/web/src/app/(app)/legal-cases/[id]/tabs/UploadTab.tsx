"use client";

import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { CaseUploadBatchOut } from "@/lib/types";
import { LITIGATION_DOCUMENT_TYPE_LABELS, CASE_UPLOAD_BATCH_STATUS_LABELS } from "@/lib/labels";

interface StagedFile {
  key: string;
  file: File;
  documentType: string;
  status: "대기" | "업로드 중" | "업로드 완료" | "실패";
  error?: string;
}

export function UploadTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [staged, setStaged] = useState<StagedFile[]>([]);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: batches = [] } = useQuery<CaseUploadBatchOut[]>({
    queryKey: ["case-upload-batches", caseId],
    queryFn: async () => (await api.get<CaseUploadBatchOut[]>(`/api/legal-cases/${caseId}/upload-batches`)).data,
    refetchInterval: (query) => {
      const list = query.state.data as CaseUploadBatchOut[] | undefined;
      const hasActive = list?.some((b) => b.status === "CREATED" || b.status === "PROCESSING");
      return hasActive ? 3000 : false;
    },
  });

  function addFiles(files: FileList | null) {
    if (!files) return;
    const next: StagedFile[] = Array.from(files).map((f) => ({
      key: `${f.name}-${f.size}-${Math.random().toString(36).slice(2)}`,
      file: f,
      documentType: "OTHER",
      status: "대기",
    }));
    setStaged((prev) => [...prev, ...next]);
  }

  function removeStaged(key: string) {
    setStaged((prev) => prev.filter((s) => s.key !== key));
  }

  function updateDocType(key: string, value: string) {
    setStaged((prev) => prev.map((s) => (s.key === key ? { ...s, documentType: value } : s)));
  }

  function clearCompleted() {
    setStaged((prev) => prev.filter((s) => s.status !== "업로드 완료"));
  }

  async function startUpload() {
    if (staged.length === 0) return;
    setError(null);
    setUploading(true);
    try {
      let batchId = activeBatchId;
      if (!batchId) {
        const { data } = await api.post(`/api/legal-cases/${caseId}/upload-batches`);
        batchId = data.id;
        setActiveBatchId(batchId);
      }

      // 파일별 순차 업로드 — 한 요청에 모든 파일을 담지 않고, 파일별 성공/실패를 개별 표시한다(§6.2).
      for (const item of staged) {
        if (item.status === "업로드 완료") continue;
        setStaged((prev) => prev.map((s) => (s.key === item.key ? { ...s, status: "업로드 중" } : s)));
        try {
          const formData = new FormData();
          formData.append("file", item.file);
          await api.post(`/api/legal-cases/${caseId}/upload-batches/${batchId}/files`, formData, {
            headers: { "Content-Type": "multipart/form-data" },
            params: { litigation_document_type: item.documentType },
          });
          setStaged((prev) => prev.map((s) => (s.key === item.key ? { ...s, status: "업로드 완료" } : s)));
        } catch (err) {
          setStaged((prev) =>
            prev.map((s) => (s.key === item.key ? { ...s, status: "실패", error: extractErrorMessage(err) } : s))
          );
        }
        queryClient.invalidateQueries({ queryKey: ["case-upload-batches", caseId] });
      }
      queryClient.invalidateQueries({ queryKey: ["legal-case", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-documents", caseId] });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function retryFailedBatch(batchId: string) {
    await api.post(`/api/legal-cases/${caseId}/upload-batches/${batchId}/retry-failed`);
    queryClient.invalidateQueries({ queryKey: ["case-upload-batches", caseId] });
  }

  const overallProgress =
    staged.length > 0 ? Math.round((staged.filter((s) => s.status === "업로드 완료" || s.status === "실패").length / staged.length) * 100) : 0;

  return (
    <div className="flex flex-col gap-4">
      <div
        className="flex flex-col items-center justify-center gap-2 rounded border-2 border-dashed border-slate-300 bg-white p-8 text-center"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          addFiles(e.dataTransfer.files);
        }}
      >
        <p className="text-sm text-slate-500">
          여러 개의 PDF 파일을 이 영역에 끌어다 놓거나, 아래 버튼으로 한꺼번에 선택하세요.
        </p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,.docx,.hwpx,.hwp,.txt"
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
        <button type="button" onClick={() => fileInputRef.current?.click()} className="btn-secondary">
          파일 선택 (여러 개 동시 선택 가능)
        </button>
      </div>

      {staged.length > 0 && (
        <div className="rounded border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold text-slate-700">업로드 대기 목록 ({staged.length}건)</h3>
            <div className="flex gap-2">
              <button type="button" onClick={clearCompleted} className="btn-secondary text-xs">
                완료 항목 정리
              </button>
              <button type="button" disabled={uploading} onClick={startUpload} className="btn-primary text-xs">
                {uploading ? `업로드 중... ${overallProgress}%` : "일괄 업로드 시작"}
              </button>
            </div>
          </div>

          {uploading && (
            <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-500 transition-all duration-300" style={{ width: `${overallProgress}%` }} />
            </div>
          )}

          <ul className="flex flex-col gap-2">
            {staged.map((s) => (
              <li key={s.key} className="flex items-center justify-between gap-2 rounded border border-slate-100 px-3 py-2 text-sm">
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <span className="truncate">{s.file.name}</span>
                  <span className="shrink-0 text-xs text-slate-400">({(s.file.size / 1024).toFixed(0)}KB)</span>
                </div>
                <select
                  className="rounded border border-slate-300 px-2 py-1 text-xs"
                  value={s.documentType}
                  disabled={s.status !== "대기"}
                  onChange={(e) => updateDocType(s.key, e.target.value)}
                >
                  {Object.entries(LITIGATION_DOCUMENT_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
                <StatusChip status={s.status} error={s.error} />
                {s.status === "대기" && (
                  <button type="button" onClick={() => removeStaged(s.key)} className="text-xs text-slate-400 hover:text-red-600">
                    제거
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {batches.length > 0 && (
        <div className="rounded border border-slate-200 bg-white p-4">
          <h3 className="mb-3 font-semibold text-slate-700">업로드 배치 이력</h3>
          <ul className="flex flex-col gap-2">
            {batches.map((b) => (
              <li key={b.id} className="rounded border border-slate-100 p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-700">
                    {CASE_UPLOAD_BATCH_STATUS_LABELS[b.status] || b.status} · 전체 {b.total_files}건
                  </span>
                  <span className="text-xs text-slate-500">
                    처리완료 {b.processed_files} · 실패/중복 {b.failed_files}
                  </span>
                </div>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-brand-500" style={{ width: `${b.progress_percent}%` }} />
                </div>
                {b.error_summary && <p className="mt-2 text-xs text-amber-700">{b.error_summary}</p>}
                {b.failed_files > 0 && (b.status === "PARTIALLY_COMPLETED" || b.status === "FAILED") && (
                  <button type="button" onClick={() => retryFailedBatch(b.id)} className="mt-2 text-xs text-brand-600 hover:underline">
                    실패 항목 재처리
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function StatusChip({ status, error }: { status: StagedFile["status"]; error?: string }) {
  const color =
    status === "업로드 완료"
      ? "bg-green-50 text-green-700 border-green-300"
      : status === "실패"
        ? "bg-red-50 text-red-700 border-red-300"
        : status === "업로드 중"
          ? "bg-brand-50 text-brand-700 border-brand-300"
          : "bg-slate-50 text-slate-500 border-slate-300";
  return (
    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${color}`} title={error}>
      {status}
    </span>
  );
}
