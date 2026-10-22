"use client";

import { useState } from "react";
import { clsx } from "clsx";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ClipboardCheck, Inbox, Loader2, UserPlus } from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { LegalReviewRequestOut } from "@/lib/types";
import { LEGAL_REVIEW_STATUS_LABELS } from "@/lib/labels";
import { RiskBadge } from "@/components/Badges";
import { useAuth } from "@/lib/auth";
import { Card, CardBody, CardHeader, EmptyState, Notice, PageHeader, Table } from "@/components/ui";

export default function LegalReviewInboxPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<LegalReviewRequestOut | null>(null);
  const [opinion, setOpinion] = useState("");
  const [adjustedRisk, setAdjustedRisk] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: requests = [], isLoading } = useQuery<LegalReviewRequestOut[]>({
    queryKey: ["legal-reviews"],
    queryFn: async () => (await api.get<LegalReviewRequestOut[]>("/api/legal-reviews")).data,
  });

  const order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "ACCEPTABLE"];
  const sorted = [...requests].sort(
    (a, b) => order.indexOf(a.overall_risk_level || "") - order.indexOf(b.overall_risk_level || "")
  );

  async function assignToMe(id: string) {
    if (!user) return;
    await api.post(`/api/legal-reviews/${id}/assign`, { reviewer_id: user.id });
    queryClient.invalidateQueries({ queryKey: ["legal-reviews"] });
  }

  async function decide(action: "approve" | "reject" | "request-revision") {
    if (!selected) return;
    setError(null);
    try {
      await api.post(`/api/legal-reviews/${selected.id}/${action}`, {
        opinion,
        adjusted_risk_level: adjustedRisk || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["legal-reviews"] });
      setSelected(null);
      setOpinion("");
      setAdjustedRisk("");
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  return (
    <>
      <PageHeader title="법무 검토함" description="위험등급이 높은 요청이 위로 정렬됩니다. 행을 클릭하면 오른쪽에서 의견을 작성합니다." />

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          {isLoading ? (
            <EmptyState icon={Loader2} title="검토 요청을 불러오는 중입니다." compact />
          ) : sorted.length === 0 ? (
            <EmptyState icon={Inbox} title="검토 요청이 없습니다." description="법무검토가 요청된 문서가 여기에 표시됩니다." />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>계약명</th>
                  <th>위험등급</th>
                  <th>상태</th>
                  <th>담당자</th>
                  <th className="w-px" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => setSelected(r)}
                    className={clsx(
                      "cursor-pointer",
                      selected?.id === r.id && "bg-brand-50/70 hover:bg-brand-50/70"
                    )}
                  >
                    <td className="max-w-[22rem]">
                      <Link
                        href={`/documents/${r.document_id}`}
                        className="font-medium text-ink-900 hover:text-brand-700 hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {r.document_title}
                      </Link>
                    </td>
                    <td>
                      <RiskBadge level={r.overall_risk_level} />
                    </td>
                    <td className="whitespace-nowrap text-ink-600">
                      {LEGAL_REVIEW_STATUS_LABELS[r.status] || r.status}
                    </td>
                    <td className="whitespace-nowrap">
                      {r.assigned_to_name || <span className="text-ink-400">미지정</span>}
                    </td>
                    <td className="pr-3">
                      {!r.assigned_to_name && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            assignToMe(r.id);
                          }}
                          className="btn-secondary btn-sm whitespace-nowrap"
                        >
                          <UserPlus className="h-3.5 w-3.5" strokeWidth={2} />
                          내가 담당
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        <Card className="lg:sticky lg:top-20">
          <CardHeader title="검토의견 작성" icon={ClipboardCheck} />
          <CardBody>
            {!selected ? (
              <EmptyState icon={ClipboardCheck} title="문서를 선택하세요." description="왼쪽 목록에서 검토할 문서를 고르면 의견을 작성할 수 있습니다." compact />
            ) : (
              <div className="flex flex-col gap-3">
                <div className="rounded-md border border-ink-100 bg-ink-50 px-3 py-2">
                  <p className="text-xs text-ink-500">선택한 문서</p>
                  <p className="mt-0.5 text-sm font-semibold text-ink-900">{selected.document_title}</p>
                </div>

                <label className="block">
                  <span className="label">검토의견</span>
                  <textarea
                    className="input"
                    rows={5}
                    placeholder="검토 결과와 근거를 적어주세요."
                    value={opinion}
                    onChange={(e) => setOpinion(e.target.value)}
                  />
                </label>

                <label className="block">
                  <span className="label">위험등급 조정</span>
                  <select className="input" value={adjustedRisk} onChange={(e) => setAdjustedRisk(e.target.value)}>
                    <option value="">조정 안함</option>
                    <option value="CRITICAL">매우 높음</option>
                    <option value="HIGH">높음</option>
                    <option value="MEDIUM">보통</option>
                    <option value="LOW">낮음</option>
                    <option value="ACCEPTABLE">적정</option>
                  </select>
                </label>

                {error && (
                  <Notice tone="danger" icon={AlertCircle}>
                    {error}
                  </Notice>
                )}

                <div className="flex flex-wrap gap-2">
                  <button onClick={() => decide("approve")} className="btn-primary flex-1">
                    승인
                  </button>
                  <button onClick={() => decide("request-revision")} className="btn-secondary">
                    보완요청
                  </button>
                  <button onClick={() => decide("reject")} className="btn-secondary text-red-600 hover:border-red-300 hover:bg-red-50">
                    반려
                  </button>
                </div>
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </>
  );
}
