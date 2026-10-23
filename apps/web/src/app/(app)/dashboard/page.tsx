"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, BarChart3, CheckCircle2, FileText, Loader2, PieChart as PieIcon, Plus, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DocumentOut, MyUsageOut } from "@/lib/types";
import { RiskBadge, StatusBadge } from "@/components/Badges";
import { Card, CardBody, CardHeader, EmptyState, PageHeader, StatCard, Table } from "@/components/ui";
import { CONTRACT_TYPE_LABELS, RISK_LEVEL_HEX, RISK_LEVEL_LABELS, documentTypeLabel } from "@/lib/labels";

const CHART_AXIS = { fontSize: 11, fill: "#64748b" } as const;

const TOOLTIP_STYLE = {
  contentStyle: {
    borderRadius: 8,
    border: "1px solid #e4e9f0",
    boxShadow: "0 4px 6px -2px rgb(15 23 42 / 0.05), 0 12px 24px -6px rgb(15 23 42 / 0.14)",
    fontSize: 12,
  },
  labelStyle: { color: "#0f172a", fontWeight: 600 },
} as const;

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: documents = [], isLoading } = useQuery<DocumentOut[]>({
    queryKey: ["documents"],
    queryFn: async () => (await api.get<DocumentOut[]>("/api/documents")).data,
  });

  const { data: myUsage } = useQuery<MyUsageOut>({
    queryKey: ["my-ai-usage"],
    queryFn: async () => (await api.get<MyUsageOut>("/api/auth/my-usage")).data,
  });

  const inProgress = documents.filter((d) => !["COMPLETED", "FAILED", "DELETED", "ARCHIVED"].includes(d.status));
  const completed = documents.filter((d) => d.status === "COMPLETED");
  const waitingReview = documents.filter((d) => d.status === "WAITING_FOR_REVIEW" || d.status === "REVIEW_IN_PROGRESS");
  const highRisk = documents.filter((d) => d.overall_risk_level === "CRITICAL" || d.overall_risk_level === "HIGH");

  const byType: Record<string, number> = {};
  for (const d of documents) {
    const key = d.document_category === "LITIGATION" ? "소송·분쟁 문서" : d.contract_type || "기타";
    byType[key] = (byType[key] || 0) + 1;
  }
  const typeChartData = Object.entries(byType)
    .map(([type, count]) => ({ name: CONTRACT_TYPE_LABELS[type] || type, count }))
    .sort((a, b) => b.count - a.count);

  const riskOrder = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "ACCEPTABLE"];
  const riskChartData = riskOrder
    .map((level) => ({
      name: RISK_LEVEL_LABELS[level],
      value: documents.filter((d) => d.overall_risk_level === level).length,
      color: RISK_LEVEL_HEX[level],
    }))
    .filter((d) => d.value > 0);
  const analyzedCount = riskChartData.reduce((sum, d) => sum + d.value, 0);

  return (
    <>
      <PageHeader
        title={`안녕하세요, ${user?.full_name ?? ""}님`}
        description="TOPEC 사내 법률검토 AI 시스템 대시보드입니다."
        actions={
          <Link href="/documents/new" className="btn-primary">
            <Plus className="h-4 w-4" strokeWidth={2.4} />
            계약서 업로드
          </Link>
        }
      />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="검토 중 문서" value={inProgress.length} icon={Loader2} href="/documents" />
        <StatCard label="완료된 문서" value={completed.length} icon={CheckCircle2} href="/documents" />
        <StatCard label="법무검토 대기·진행" value={waitingReview.length} icon={ShieldCheck} href="/documents" />
        <StatCard
          label="고위험 계약"
          value={highRisk.length}
          icon={AlertTriangle}
          tone={highRisk.length > 0 ? "alert" : "default"}
          hint={highRisk.length > 0 ? "법무담당자 확인이 필요합니다" : undefined}
          href="/documents"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="위험등급 분포"
            icon={PieIcon}
            description={analyzedCount > 0 ? `분석 완료 ${analyzedCount}건` : undefined}
          />
          <CardBody className="pt-2">
            {riskChartData.length === 0 ? (
              <EmptyState icon={PieIcon} title="분석 완료된 문서가 없습니다." compact />
            ) : (
              <div className="flex flex-col items-center gap-4 sm:flex-row">
                {/* ResponsiveContainer 는 부모의 가로폭을 재므로, flex 행 안에서는
                    폭이 0 으로 줄어든다. 고정폭 래퍼로 감싸 눌리지 않게 한다. */}
                <div className="h-[200px] w-[200px] shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={riskChartData}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={54}
                        outerRadius={84}
                        paddingAngle={2}
                        stroke="none"
                      >
                        {riskChartData.map((entry) => (
                          <Cell key={entry.name} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip {...TOOLTIP_STYLE} formatter={(v: number) => [`${v}건`, "문서"]} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                {/* recharts 기본 범례 대신 건수까지 함께 보여주는 목록을 쓴다 */}
                <ul className="flex w-full min-w-0 flex-1 flex-col gap-2">
                  {riskChartData.map((entry) => (
                    <li key={entry.name} className="flex items-center gap-2 text-sm">
                      <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: entry.color }} />
                      <span className="text-ink-600">{entry.name}</span>
                      <span className="ml-auto font-semibold tabular text-ink-900">{entry.value}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="문서유형별 건수" icon={BarChart3} />
          <CardBody className="pt-2">
            {typeChartData.length === 0 ? (
              <EmptyState icon={BarChart3} title="등록된 계약서가 없습니다." compact />
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(200, typeChartData.length * 34)}>
                <BarChart data={typeChartData} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid horizontal={false} stroke="#f1f5f9" />
                  <XAxis type="number" allowDecimals={false} tick={CHART_AXIS} axisLine={false} tickLine={false} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={132}
                    tick={CHART_AXIS}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: "#f8fafc" }} formatter={(v: number) => [`${v}건`, "문서"]} />
                  <Bar dataKey="count" fill="#175a93" radius={[0, 4, 4, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="나의 최근 계약검토"
          icon={FileText}
          actions={
            documents.length > 0 && (
              <Link href="/documents" className="text-sm font-medium text-brand-700 hover:underline">
                전체 보기
              </Link>
            )
          }
        />
        {isLoading ? (
          <EmptyState icon={Loader2} title="문서를 불러오는 중입니다." compact />
        ) : documents.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="아직 등록된 계약서가 없습니다."
            description="계약서나 소송·분쟁 문서를 업로드하면 AI가 1차 검토를 시작합니다."
            action={
              <Link href="/documents/new" className="btn-primary">
                <Plus className="h-4 w-4" strokeWidth={2.4} />
                계약서 업로드
              </Link>
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <th>계약명</th>
                <th>유형</th>
                <th>상태</th>
                <th>위험등급</th>
                <th className="text-right">등록일</th>
              </tr>
            </thead>
            <tbody>
              {documents.slice(0, 8).map((d) => (
                <tr key={d.id}>
                  <td className="max-w-[26rem]">
                    <Link href={`/documents/${d.id}`} className="font-medium text-ink-900 hover:text-brand-700 hover:underline">
                      {d.title}
                    </Link>
                  </td>
                  <td className="text-ink-500">{documentTypeLabel(d)}</td>
                  <td>
                    <StatusBadge status={d.status} />
                  </td>
                  <td>
                    <RiskBadge level={d.overall_risk_level} />
                  </td>
                  <td className="whitespace-nowrap text-right text-ink-500">
                    {new Date(d.created_at).toLocaleDateString("ko-KR")}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {myUsage && (
        <Card>
          <CardHeader title="나의 AI 사용량" icon={Sparkles} />
          <CardBody>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <UsageCard label="오늘" usage={myUsage.today} />
              <UsageCard label="이번 달" usage={myUsage.this_month} />
              <UsageCard label="전체 누적" usage={myUsage.total} />
            </div>
          </CardBody>
        </Card>
      )}
    </>
  );
}

function UsageCard({
  label,
  usage,
}: {
  label: string;
  usage: { calls: number; input_tokens: number; output_tokens: number };
}) {
  return (
    <div className="rounded-md border border-ink-200 bg-ink-50/60 p-4">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className="mt-1 text-xl font-bold tabular text-ink-900">
        {usage.calls.toLocaleString()}
        <span className="ml-0.5 text-sm font-semibold text-ink-400">건</span>
      </p>
      <p className="mt-0.5 text-xs tabular text-ink-500">
        입력 {usage.input_tokens.toLocaleString()} / 출력 {usage.output_tokens.toLocaleString()} 토큰
      </p>
    </div>
  );
}
