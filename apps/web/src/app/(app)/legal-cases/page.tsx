"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus, Scale, Search, SlidersHorizontal } from "lucide-react";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import { LegalCaseOut } from "@/lib/types";
import { RiskBadge } from "@/components/Badges";
import { Card, EmptyState, PageHeader, Table } from "@/components/ui";
import { LEGAL_CASE_STATUS_LABELS } from "@/lib/labels";

export default function LegalCasesPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");

  const { data: cases = [], isLoading } = useQuery<LegalCaseOut[]>({
    queryKey: ["legal-cases", search, status],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (search) params.search = search;
      if (status) params.status_filter = status;
      return (await api.get<LegalCaseOut[]>("/api/legal-cases", { params })).data;
    },
  });

  const filtered = search || status;

  return (
    <>
      <PageHeader
        title="소송·분쟁 사건"
        description="사건 단위로 관련 문서를 모아 통합 분석합니다."
        actions={
          <Link href="/legal-cases/new" className="btn-primary">
            <Plus className="h-4 w-4" strokeWidth={2.4} />
            새 사건 등록
          </Link>
        }
      />

      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[14rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" strokeWidth={2} />
            <input
              className="input h-9 pl-9"
              placeholder="사건명 검색"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select className="input h-9 w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">전체 상태</option>
            {Object.entries(LEGAL_CASE_STATUS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          {filtered && (
            <button
              onClick={() => {
                setSearch("");
                setStatus("");
              }}
              className="btn-ghost btn-sm"
            >
              조건 초기화
            </button>
          )}
          {!isLoading && (
            <span className="ml-auto whitespace-nowrap pr-1 text-sm tabular text-ink-500">총 {cases.length}건</span>
          )}
        </div>
      </Card>

      <Card>
        {isLoading ? (
          <EmptyState icon={Loader2} title="사건을 불러오는 중입니다." compact />
        ) : cases.length === 0 ? (
          <EmptyState
            icon={filtered ? SlidersHorizontal : Scale}
            title={filtered ? "조건에 맞는 사건이 없습니다." : "등록된 사건이 없습니다."}
            description={
              filtered
                ? "검색어나 상태를 바꿔 다시 찾아보세요."
                : "사건을 등록하면 준비서면·소장·답변서를 한 사건으로 묶어 분석할 수 있습니다."
            }
            action={
              !filtered && (
                <Link href="/legal-cases/new" className="btn-primary">
                  <Plus className="h-4 w-4" strokeWidth={2.4} />
                  새 사건 등록
                </Link>
              )
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <th>사건명</th>
                <th>사건번호</th>
                <th>법원</th>
                <th>상대방</th>
                <th>담당부서</th>
                <th>상태</th>
                <th className="text-right">문서</th>
                <th className="text-right">미분류</th>
                <th>전체 위험도</th>
                <th className="text-right">등록일</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td className="max-w-[20rem]">
                    <Link
                      href={`/legal-cases/${c.id}`}
                      className="font-medium text-ink-900 hover:text-brand-700 hover:underline"
                    >
                      {c.case_name}
                    </Link>
                  </td>
                  <td className="whitespace-nowrap tabular">{c.case_number || <span className="text-ink-400">-</span>}</td>
                  <td>{c.court_name || <span className="text-ink-400">-</span>}</td>
                  <td>{c.opponent_name || <span className="text-ink-400">-</span>}</td>
                  <td>{c.department || <span className="text-ink-400">-</span>}</td>
                  <td>
                    <span
                      className={clsx(
                        "badge",
                        c.status === "ACTIVE"
                          ? "border-brand-200 bg-brand-50 text-brand-700"
                          : "border-ink-200 bg-ink-100 text-ink-600"
                      )}
                    >
                      {LEGAL_CASE_STATUS_LABELS[c.status] || c.status}
                    </span>
                  </td>
                  <td className="text-right tabular">{c.document_count}</td>
                  <td className="text-right tabular">
                    {c.unclassified_count > 0 ? (
                      <span className="font-semibold text-amber-600">{c.unclassified_count}</span>
                    ) : (
                      <span className="text-ink-400">-</span>
                    )}
                  </td>
                  <td>
                    <RiskBadge level={c.overall_risk_level} />
                  </td>
                  <td className="whitespace-nowrap text-right text-ink-500">
                    {new Date(c.created_at).toLocaleDateString("ko-KR")}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
