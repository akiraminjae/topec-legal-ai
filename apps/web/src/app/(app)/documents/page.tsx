"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, FileText, Loader2, Plus, Search, SlidersHorizontal, Trash2 } from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DocumentOut } from "@/lib/types";
import { RiskBadge, StatusBadge } from "@/components/Badges";
import { Card, EmptyState, Notice, PageHeader, Table } from "@/components/ui";
import { CONTRACT_TYPE_LABELS, documentTypeLabel } from "@/lib/labels";

const RISK_OPTIONS = [
  { value: "CRITICAL", label: "매우 높음" },
  { value: "HIGH", label: "높음" },
  { value: "MEDIUM", label: "보통" },
  { value: "LOW", label: "낮음" },
  { value: "ACCEPTABLE", label: "적정" },
];

export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [contractType, setContractType] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { user, hasRole } = useAuth();

  const { data: documents = [], isLoading } = useQuery<DocumentOut[]>({
    queryKey: ["documents", search, contractType, riskLevel],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (search) params.search = search;
      if (contractType) params.contract_type = contractType;
      if (riskLevel) params.risk_level = riskLevel;
      return (await api.get<DocumentOut[]>("/api/documents", { params })).data;
    },
  });

  const filtered = search || contractType || riskLevel;

  async function handleDelete(id: string) {
    if (!confirm("이 문서를 삭제하시겠습니까? 삭제된 문서는 복구할 수 없습니다.")) return;
    setError(null);
    setDeletingId(id);
    try {
      await api.delete(`/api/documents/${id}`);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="내 문서"
        description="내가 업로드한 계약서와 소송·분쟁 문서입니다."
        actions={
          <Link href="/documents/new" className="btn-primary">
            <Plus className="h-4 w-4" strokeWidth={2.4} />
            계약서 업로드
          </Link>
        }
      />

      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[14rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" strokeWidth={2} />
            <input
              className="input h-9 pl-9"
              placeholder="계약명 검색"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select className="input h-9 w-auto" value={contractType} onChange={(e) => setContractType(e.target.value)}>
            <option value="">전체 계약유형</option>
            {Object.entries(CONTRACT_TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <select className="input h-9 w-auto" value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)}>
            <option value="">전체 위험등급</option>
            {RISK_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {filtered && (
            <button
              onClick={() => {
                setSearch("");
                setContractType("");
                setRiskLevel("");
              }}
              className="btn-ghost btn-sm"
            >
              조건 초기화
            </button>
          )}
          {!isLoading && (
            <span className="ml-auto whitespace-nowrap pr-1 text-sm tabular text-ink-500">총 {documents.length}건</span>
          )}
        </div>
      </Card>

      {error && (
        <Notice tone="danger" icon={AlertCircle}>
          {error}
        </Notice>
      )}

      <Card>
        {isLoading ? (
          <EmptyState icon={Loader2} title="문서를 불러오는 중입니다." compact />
        ) : documents.length === 0 ? (
          <EmptyState
            icon={filtered ? SlidersHorizontal : FileText}
            title={filtered ? "조건에 맞는 문서가 없습니다." : "아직 등록된 문서가 없습니다."}
            description={
              filtered
                ? "검색어나 필터를 바꿔 다시 찾아보세요."
                : "계약서나 소송·분쟁 문서를 업로드하면 AI가 1차 검토를 시작합니다."
            }
            action={
              !filtered && (
                <Link href="/documents/new" className="btn-primary">
                  <Plus className="h-4 w-4" strokeWidth={2.4} />
                  계약서 업로드
                </Link>
              )
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <th>계약명</th>
                <th>유형</th>
                <th>상대방</th>
                <th>부서</th>
                <th>상태</th>
                <th>위험등급</th>
                <th className="text-right">등록일</th>
                <th className="w-px" />
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => {
                const canManage = user?.id === d.owner_id || hasRole("SYSTEM_ADMIN");
                return (
                  <tr key={d.id} className="group">
                    <td className="max-w-[24rem]">
                      <Link
                        href={`/documents/${d.id}`}
                        className="font-medium text-ink-900 hover:text-brand-700 hover:underline"
                      >
                        {d.title}
                      </Link>
                    </td>
                    <td className="text-ink-500">{documentTypeLabel(d)}</td>
                    <td>{d.counterparty_name || <span className="text-ink-400">-</span>}</td>
                    <td>{d.department || <span className="text-ink-400">-</span>}</td>
                    <td>
                      <StatusBadge status={d.status} />
                    </td>
                    <td>
                      <RiskBadge level={d.overall_risk_level} />
                    </td>
                    <td className="whitespace-nowrap text-right text-ink-500">
                      {new Date(d.created_at).toLocaleDateString("ko-KR")}
                    </td>
                    <td className="pr-3">
                      {canManage && (
                        <button
                          onClick={() => handleDelete(d.id)}
                          disabled={deletingId === d.id}
                          title="문서 삭제"
                          aria-label={`${d.title} 삭제`}
                          className="rounded-md p-1.5 text-ink-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 focus-visible:opacity-100 group-hover:opacity-100 disabled:opacity-50"
                        >
                          {deletingId === d.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" strokeWidth={2} />
                          )}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
