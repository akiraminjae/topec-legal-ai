"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { DocumentOut } from "@/lib/types";
import { useAuth } from "@/lib/auth";

export function LegalReviewTab({ documentId, document }: { documentId: string; document: DocumentOut }) {
  const { hasRole } = useAuth();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const isLegalReviewer = hasRole("LEGAL_REVIEWER", "SYSTEM_ADMIN");

  async function requestReview() {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/api/documents/${documentId}/legal-review/request`, { request_note: note });
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
      setNote("");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded border border-slate-200 bg-white p-4">
        <h3 className="mb-2 font-semibold text-slate-700">법무검토 요청</h3>
        <p className="mb-3 text-sm text-slate-500">
          현재 문서 상태: <strong>{document.status}</strong> · 법무검토 필요:{" "}
          <strong>{document.legal_review_required ? "예" : "아니오"}</strong>
        </p>
        <textarea
          className="input mb-2"
          rows={2}
          placeholder="법무담당자에게 전달할 요청사항 (선택)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
        <button disabled={submitting} onClick={requestReview} className="btn-primary">
          {submitting ? "요청 중..." : "법무검토 요청"}
        </button>
      </div>

      {isLegalReviewer && (
        <p className="text-sm text-slate-500">
          법무담당자는 <strong>법무 검토함</strong> 메뉴에서 배정된 요청을 확인하고 검토의견을 작성할 수 있습니다.
        </p>
      )}
    </div>
  );
}
