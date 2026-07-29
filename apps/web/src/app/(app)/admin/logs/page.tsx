"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AuditLogOut, LoginAttemptOut } from "@/lib/types";
import { AUDIT_ACTION_LABELS } from "@/lib/labels";

export default function AdminLogsPage() {
  const [tab, setTab] = useState<"audit" | "login">("audit");

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-bold text-slate-800">로그 기록</h1>
      <div className="flex gap-1 border-b border-slate-200">
        <TabButton active={tab === "audit"} onClick={() => setTab("audit")} label="감사 로그" />
        <TabButton active={tab === "login"} onClick={() => setTab("login")} label="로그인 시도 이력" />
      </div>
      {tab === "audit" && <AuditLogPanel />}
      {tab === "login" && <LoginAttemptPanel />}
    </div>
  );
}

function TabButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium ${active ? "border-b-2 border-brand-600 text-brand-700" : "text-slate-500"}`}
    >
      {label}
    </button>
  );
}

function AuditLogPanel() {
  const [action, setAction] = useState("");
  const [success, setSuccess] = useState("");

  const { data = [] } = useQuery<AuditLogOut[]>({
    queryKey: ["admin-audit-logs", action, success],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (action) params.action = action;
      if (success) params.success = success;
      return (await api.get<AuditLogOut[]>("/api/admin/audit-logs", { params })).data;
    },
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <select className="input" value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="">전체 유형</option>
          {Object.entries(AUDIT_ACTION_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <select className="input" value={success} onChange={(e) => setSuccess(e.target.value)}>
          <option value="">성공/실패 전체</option>
          <option value="true">성공만</option>
          <option value="false">실패만</option>
        </select>
      </div>
      <div className="overflow-x-auto rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="p-3">시각</th>
              <th>사용자</th>
              <th>동작</th>
              <th>대상</th>
              <th>결과</th>
              <th>IP</th>
              <th>상세</th>
            </tr>
          </thead>
          <tbody>
            {data.map((log) => (
              <tr key={log.id} className="border-b border-slate-100 align-top">
                <td className="whitespace-nowrap p-3">{new Date(log.created_at).toLocaleString("ko-KR")}</td>
                <td>{log.user_name || "-"}</td>
                <td>{AUDIT_ACTION_LABELS[log.action] || log.action}</td>
                <td>
                  {log.target_type || "-"}
                  {log.target_id ? ` (${log.target_id.slice(0, 8)})` : ""}
                </td>
                <td>
                  <span className={log.success ? "text-green-600" : "text-red-600"}>
                    {log.success ? "성공" : "실패"}
                  </span>
                </td>
                <td>{log.ip_address || "-"}</td>
                <td className="max-w-[240px] truncate text-slate-500">{log.failure_reason || log.change_summary || "-"}</td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td colSpan={7} className="p-3 text-center text-slate-400">
                  기록이 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LoginAttemptPanel() {
  const { data = [] } = useQuery<LoginAttemptOut[]>({
    queryKey: ["admin-login-attempts"],
    queryFn: async () => (await api.get<LoginAttemptOut[]>("/api/admin/login-attempts")).data,
  });

  return (
    <div className="overflow-x-auto rounded border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-500">
            <th className="p-3">시각</th>
            <th>시도한 계정</th>
            <th>결과</th>
            <th>실패 사유</th>
            <th>IP</th>
          </tr>
        </thead>
        <tbody>
          {data.map((attempt) => (
            <tr key={attempt.id} className="border-b border-slate-100">
              <td className="whitespace-nowrap p-3">{new Date(attempt.created_at).toLocaleString("ko-KR")}</td>
              <td>{attempt.email_attempted}</td>
              <td>
                <span className={attempt.success ? "text-green-600" : "text-red-600"}>
                  {attempt.success ? "성공" : "실패"}
                </span>
              </td>
              <td className="text-slate-500">{attempt.failure_reason || "-"}</td>
              <td>{attempt.ip_address || "-"}</td>
            </tr>
          ))}
          {data.length === 0 && (
            <tr>
              <td colSpan={5} className="p-3 text-center text-slate-400">
                기록이 없습니다.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
