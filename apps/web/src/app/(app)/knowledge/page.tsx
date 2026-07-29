"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { KnowledgeDocumentOut } from "@/lib/types";

const DOC_TYPE_LABELS: Record<string, string> = {
  STATUTE: "법령",
  ENFORCEMENT_DECREE: "시행령",
  ENFORCEMENT_RULE: "시행규칙",
  NOTIFICATION: "고시",
  ADMIN_GUIDELINE: "행정지침",
  COURT_CASE: "판례",
  STANDARD_CONTRACT: "표준계약서",
  TOPEC_STANDARD_CLAUSE: "TOPEC 표준조항",
  PAST_REVIEW_OPINION: "과거 계약검토 의견",
  EXTERNAL_COUNSEL_OPINION: "외부 변호사 자문의견",
  DISPUTE_CASE: "분쟁·클레임 사례",
  REVIEW_CHECKLIST: "계약검토 체크리스트",
};

export default function KnowledgePage() {
  const queryClient = useQueryClient();
  const [docType, setDocType] = useState("REVIEW_CHECKLIST");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const { data: documents = [] } = useQuery<KnowledgeDocumentOut[]>({
    queryKey: ["knowledge-documents"],
    queryFn: async () => (await api.get<KnowledgeDocumentOut[]>("/api/knowledge/documents")).data,
  });

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !title) {
      setError("제목과 파일을 모두 입력하세요.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api.post(
        `/api/knowledge/documents?doc_type=${docType}&title=${encodeURIComponent(title)}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents"] });
      setTitle("");
      setFile(null);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-bold text-slate-800">법률지식 관리</h1>

      <form onSubmit={upload} className="flex flex-wrap items-end gap-2 rounded border border-slate-200 bg-white p-4">
        <div>
          <label className="mb-1 block text-xs text-slate-500">자료유형</label>
          <select className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
            {Object.entries(DOC_TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="mb-1 block text-xs text-slate-500">제목</label>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-500">파일 (PDF/DOCX/TXT/HWPX)</label>
          <input type="file" accept=".pdf,.docx,.txt,.hwpx" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </div>
        <button disabled={uploading} className="btn-primary">
          {uploading ? "업로드 중..." : "업로드"}
        </button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="p-3">제목</th>
              <th>유형</th>
              <th>출처</th>
              <th>유효</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id} className="border-b border-slate-100">
                <td className="p-3">{d.title}</td>
                <td>{DOC_TYPE_LABELS[d.doc_type] || d.doc_type}</td>
                <td>{d.source || "-"}</td>
                <td>{d.is_valid ? "유효" : "폐지/무효"}</td>
              </tr>
            ))}
            {documents.length === 0 && (
              <tr>
                <td colSpan={4} className="py-6 text-center text-slate-400">
                  등록된 지식자료가 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
