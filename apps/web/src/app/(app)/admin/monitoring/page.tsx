"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { ResourceUsageOut } from "@/lib/types";
import { ProgressGauge } from "@/components/ProgressGauge";
import { AI_PROVIDER_LABELS } from "@/lib/labels";

function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}

export default function ResourceMonitoringPage() {
  const queryClient = useQueryClient();
  const [quotaGb, setQuotaGb] = useState("");
  const [quotaError, setQuotaError] = useState<string | null>(null);
  const [savingQuota, setSavingQuota] = useState(false);

  const { data, dataUpdatedAt } = useQuery<ResourceUsageOut>({
    queryKey: ["admin-resource-usage"],
    queryFn: async () => (await api.get<ResourceUsageOut>("/api/admin/resource-usage")).data,
    refetchInterval: 15000,
  });

  async function saveQuota(e: React.FormEvent) {
    e.preventDefault();
    setQuotaError(null);
    const gb = Number(quotaGb);
    if (!gb || gb <= 0) {
      setQuotaError("올바른 GB 값을 입력하세요.");
      return;
    }
    setSavingQuota(true);
    try {
      await api.patch("/api/admin/settings/storage_quota_bytes", { value: { bytes: Math.round(gb * 1024 ** 3) } });
      setQuotaGb("");
      queryClient.invalidateQueries({ queryKey: ["admin-resource-usage"] });
    } catch (err) {
      setQuotaError(extractErrorMessage(err));
    } finally {
      setSavingQuota(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">리소스 모니터링</h1>
        {dataUpdatedAt > 0 && (
          <p className="text-xs text-slate-400">
            마지막 갱신: {new Date(dataUpdatedAt).toLocaleTimeString("ko-KR")} (15초마다 자동 갱신)
          </p>
        )}
      </div>

      {data && (
        <>
          <section className="rounded border border-slate-200 bg-white p-4">
            <p className="mb-3 font-medium text-slate-700">DB / 파일 저장 공간</p>
            <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
              <ProgressGauge percent={Math.round(data.storage.used_percent)} />
              <div className="flex-1 text-sm">
                <p>
                  사용량 <strong>{formatBytes(data.storage.used_bytes)}</strong> / 임계치{" "}
                  <strong>{formatBytes(data.storage.quota_bytes)}</strong>
                </p>
                <p className="mt-1 text-slate-500">데이터베이스 자체 용량: {formatBytes(data.storage.db_size_bytes)}</p>
                <form onSubmit={saveQuota} className="mt-3 flex items-end gap-2">
                  <div>
                    <label className="mb-1 block text-xs text-slate-500">저장 공간 임계치 변경 (GB)</label>
                    <input
                      className="input w-32"
                      type="number"
                      min={1}
                      step="0.1"
                      value={quotaGb}
                      onChange={(e) => setQuotaGb(e.target.value)}
                      placeholder="예: 200"
                    />
                  </div>
                  <button className="btn-primary" disabled={savingQuota}>
                    {savingQuota ? "저장 중..." : "적용"}
                  </button>
                </form>
                {quotaError && <p className="mt-1 text-xs text-red-600">{quotaError}</p>}
              </div>
            </div>
          </section>

          <section className="rounded border border-slate-200 bg-white p-4">
            <p className="mb-3 font-medium text-slate-700">AI API(토큰) 사용 현황</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <UsageCard label="오늘" usage={data.api_usage.today} />
              <UsageCard label="이번 달" usage={data.api_usage.this_month} />
              <UsageCard label="전체 누적" usage={data.api_usage.total} />
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="p-2">Provider</th>
                    <th className="p-2">호출 수</th>
                    <th className="p-2">입력 토큰</th>
                    <th className="p-2">출력 토큰</th>
                  </tr>
                </thead>
                <tbody>
                  {data.api_usage.by_provider.map((p) => (
                    <tr key={p.provider} className="border-b border-slate-100">
                      <td className="p-2">{AI_PROVIDER_LABELS[p.provider] || p.provider}</td>
                      <td className="p-2">{p.calls.toLocaleString()}</td>
                      <td className="p-2">{p.input_tokens.toLocaleString()}</td>
                      <td className="p-2">{p.output_tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                  {data.api_usage.by_provider.length === 0 && (
                    <tr>
                      <td colSpan={4} className="p-2 text-center text-slate-400">
                        사용 이력이 없습니다.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function UsageCard({ label, usage }: { label: string; usage: { calls: number; input_tokens: number; output_tokens: number } }) {
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
