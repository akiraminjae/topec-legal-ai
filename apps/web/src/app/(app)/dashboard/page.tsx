"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DocumentOut, MyUsageOut } from "@/lib/types";
import { RiskBadge, StatusBadge } from "@/components/Badges";
import { CONTRACT_TYPE_LABELS, RISK_LEVEL_HEX, RISK_LEVEL_LABELS, documentTypeLabel } from "@/lib/labels";

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: documents = [] } = useQuery<DocumentOut[]>({
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
  const typeChartData = Object.entries(byType).map(([type, count]) => ({
    name: CONTRACT_TYPE_LABELS[type] || type,
    count,
  }));

  const riskOrder = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "ACCEPTABLE"];
  const riskChartData = riskOrder
    .map((level) => ({
      name: RISK_LEVEL_LABELS[level],
      value: documents.filter((d) => d.overall_risk_level === level).length,
      color: RISK_LEVEL_HEX[level],
    }))
    .filter((d) => d.value > 0);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-slate-800">안녕하세요, {user?.full_name}님</h1>
        <p className="text-sm text-slate-500">TOPEC 사내 법률검토 AI 시스템 대시보드입니다.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="검토 중 문서" value={inProgress.length} />
        <StatCard label="완료된 문서" value={completed.length} />
        <StatCard label="법무검토 대기/진행" value={waitingReview.length} />
        <StatCard label="고위험 계약" value={highRisk.length} highlight />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded border border-slate-200 bg-white p-4">
          <h2 className="mb-3 font-semibold text-slate-700">위험등급 분포</h2>
          {riskChartData.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">분석 완료된 문서가 없습니다.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={riskChartData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                  {riskChartData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded border border-slate-200 bg-white p-4">
          <h2 className="mb-3 font-semibold text-slate-700">문서유형별 건수</h2>
          {typeChartData.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">등록된 계약서가 없습니다.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={typeChartData} layout="vertical" margin={{ left: 16 }}>
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563eb" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="rounded border border-slate-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold text-slate-700">나의 최근 계약검토</h2>
          <Link href="/documents/new" className="rounded bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700">
            + 계약서 업로드
          </Link>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="py-2">계약명</th>
              <th>유형</th>
              <th>상태</th>
              <th>위험등급</th>
              <th>등록일</th>
            </tr>
          </thead>
          <tbody>
            {documents.slice(0, 10).map((d) => (
              <tr key={d.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="py-2">
                  <Link href={`/documents/${d.id}`} className="text-brand-700 hover:underline">
                    {d.title}
                  </Link>
                </td>
                <td>{documentTypeLabel(d)}</td>
                <td><StatusBadge status={d.status} /></td>
                <td><RiskBadge level={d.overall_risk_level} /></td>
                <td className="text-slate-500">{new Date(d.created_at).toLocaleDateString("ko-KR")}</td>
              </tr>
            ))}
            {documents.length === 0 && (
              <tr>
                <td colSpan={5} className="py-6 text-center text-slate-400">
                  아직 등록된 계약서가 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {myUsage && (
        <div className="rounded border border-slate-200 bg-white p-4">
          <h2 className="mb-3 font-semibold text-slate-700">나의 AI 사용량</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <UsageCard label="오늘" usage={myUsage.today} />
            <UsageCard label="이번 달" usage={myUsage.this_month} />
            <UsageCard label="전체 누적" usage={myUsage.total} />
          </div>
        </div>
      )}
    </div>
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
    <div className="rounded border border-slate-200 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-bold text-slate-800">{usage.calls.toLocaleString()}건</p>
      <p className="text-xs text-slate-500">
        입력 {usage.input_tokens.toLocaleString()} / 출력 {usage.output_tokens.toLocaleString()} 토큰
      </p>
    </div>
  );
}

function StatCard({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div className={`rounded border p-4 ${highlight && value > 0 ? "border-red-300 bg-red-50" : "border-slate-200 bg-white"}`}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${highlight && value > 0 ? "text-red-700" : "text-slate-800"}`}>{value}</p>
    </div>
  );
}
