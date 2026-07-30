"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { DashboardStats, DepartmentOut, UserOut } from "@/lib/types";
import { ROLE_LABELS } from "@/lib/labels";

interface SystemHealthOut {
  database: string;
  redis: string;
  object_storage: string;
  ai_provider: string;
  ai_provider_configured: boolean;
  public_data_portal_configured: boolean;
  open_law_configured: boolean;
}

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"stats" | "users" | "approvals">("stats");

  const { data: stats } = useQuery<DashboardStats>({
    queryKey: ["admin-dashboard"],
    queryFn: async () => (await api.get<DashboardStats>("/api/admin/dashboard")).data,
  });

  const { data: health } = useQuery<SystemHealthOut>({
    queryKey: ["admin-system-health"],
    queryFn: async () => (await api.get<SystemHealthOut>("/api/admin/system-health")).data,
  });

  const { data: users = [] } = useQuery<UserOut[]>({
    queryKey: ["admin-users"],
    queryFn: async () => (await api.get<UserOut[]>("/api/users")).data,
  });

  const { data: departments = [] } = useQuery<DepartmentOut[]>({
    queryKey: ["departments"],
    queryFn: async () => (await api.get<DepartmentOut[]>("/api/departments")).data,
  });

  const { data: pendingApprovals = [] } = useQuery<UserOut[]>({
    queryKey: ["admin-pending-approvals"],
    queryFn: async () => (await api.get<UserOut[]>("/api/users/pending")).data,
    refetchInterval: 30000,
  });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-bold text-slate-800">관리자</h1>
      <div className="flex gap-1 border-b border-slate-200">
        <TabButton active={tab === "stats"} onClick={() => setTab("stats")} label="시스템 현황" />
        <TabButton active={tab === "users"} onClick={() => setTab("users")} label="사용자 관리" />
        <TabButton
          active={tab === "approvals"}
          onClick={() => setTab("approvals")}
          label={`가입 승인${pendingApprovals.length > 0 ? ` (${pendingApprovals.length})` : ""}`}
        />
      </div>

      {tab === "stats" && stats && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="전체 사용자" value={stats.total_users} />
            <Stat label="활성 사용자" value={stats.active_users} />
            <Stat label="전체 계약서" value={stats.total_documents} />
            <Stat label="이번 달 등록" value={stats.documents_this_month} />
            <Stat label="법무검토 요청 대기" value={stats.legal_review_requested} />
            <Stat label="법무검토 완료" value={stats.legal_review_completed} />
            <Stat label="분석 실패 건수" value={stats.analysis_failure_count} />
            <Stat label="AI 호출 건수" value={stats.ai_usage_total_calls} />
          </div>
          <div className="rounded border border-slate-200 bg-white p-4 text-sm">
            <p className="mb-1 text-slate-500">AI 토큰 사용량</p>
            <p>
              입력 {stats.ai_usage_total_input_tokens.toLocaleString()} / 출력{" "}
              {stats.ai_usage_total_output_tokens.toLocaleString()} 토큰
            </p>
          </div>

          {health && (
            <div className="rounded border border-slate-200 bg-white p-4 text-sm">
              <p className="mb-2 font-medium text-slate-700">시스템 연동 상태</p>
              <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                <HealthRow label="Database" ok={health.database === "OK"} />
                <HealthRow label="Redis" ok={health.redis === "OK"} />
                <HealthRow label="Object Storage" ok={health.object_storage === "OK"} />
                <HealthRow
                  label={`AI Provider (${health.ai_provider})`}
                  ok={health.ai_provider_configured}
                  note={health.ai_provider === "mock" ? "Mock 모드" : undefined}
                />
                <HealthRow
                  label="공공데이터포털 (법령)"
                  ok={health.public_data_portal_configured}
                  note={health.public_data_portal_configured ? undefined : "serviceKey 미설정"}
                />
                <HealthRow
                  label="국가법령정보 LINK (판례)"
                  ok={health.open_law_configured}
                  note={health.open_law_configured ? undefined : "OC 미설정"}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "users" && <UsersPanel users={users} departments={departments} />}
      {tab === "approvals" && <PendingApprovalsPanel users={pendingApprovals} />}
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

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-800">{value}</p>
    </div>
  );
}

function HealthRow({ label, ok, note }: { label: string; ok: boolean; note?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`} />
      <span className="text-slate-700">{label}</span>
      {note && <span className="text-xs text-slate-400">({note})</span>}
    </div>
  );
}

function UsersPanel({ users, departments }: { users: UserOut[]; departments: DepartmentOut[] }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ employee_no: "", email: "", full_name: "", department_id: "", role: "USER" });
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editRoles, setEditRoles] = useState<Set<string>>(new Set());
  const [savingRoles, setSavingRoles] = useState(false);

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { data } = await api.post("/api/users", {
        employee_no: form.employee_no,
        email: form.email,
        full_name: form.full_name,
        department_id: form.department_id || undefined,
        roles: [form.role],
      });
      setTempPassword(data.temporary_password);
      setForm({ employee_no: "", email: "", full_name: "", department_id: "", role: "USER" });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  async function toggleActive(user: UserOut) {
    const action = user.is_active ? "deactivate" : "activate";
    await api.post(`/api/users/${user.id}/${action}`);
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  }

  function startEditRoles(user: UserOut) {
    setError(null);
    setEditingUserId(user.id);
    setEditRoles(new Set(user.roles));
  }

  function cancelEditRoles() {
    setEditingUserId(null);
    setEditRoles(new Set());
  }

  function toggleEditRole(role: string) {
    setEditRoles((prev) => {
      const next = new Set(prev);
      if (next.has(role)) {
        next.delete(role);
      } else {
        next.add(role);
      }
      return next;
    });
  }

  async function saveRoles(userId: string) {
    setError(null);
    setSavingRoles(true);
    try {
      await api.patch(`/api/users/${userId}`, { roles: Array.from(editRoles) });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setEditingUserId(null);
      setEditRoles(new Set());
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSavingRoles(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={createUser} className="flex flex-wrap items-end gap-2 rounded border border-slate-200 bg-white p-4">
        <TextField label="사번" value={form.employee_no} onChange={(v) => setForm({ ...form, employee_no: v })} />
        <TextField label="이메일" value={form.email} onChange={(v) => setForm({ ...form, email: v })} />
        <TextField label="이름" value={form.full_name} onChange={(v) => setForm({ ...form, full_name: v })} />
        <div>
          <label className="mb-1 block text-xs text-slate-500">부서</label>
          <select className="input" value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })}>
            <option value="">미지정</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-500">역할</label>
          <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            {Object.entries(ROLE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <button className="btn-primary">사용자 등록</button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {tempPassword && (
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          초기 비밀번호: <strong>{tempPassword}</strong> — 최초 로그인 시 반드시 비밀번호를 변경해야 합니다. 이 창을
          닫으면 다시 조회할 수 없으니 안전하게 전달하세요.
        </div>
      )}

      <div className="rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="p-3">사번</th>
              <th>이름</th>
              <th>이메일</th>
              <th>휴대폰</th>
              <th>부서</th>
              <th>역할</th>
              <th>상태</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-slate-100 align-top">
                <td className="p-3">{u.employee_no}</td>
                <td>{u.full_name}</td>
                <td>{u.email}</td>
                <td>{u.phone_number || "-"}</td>
                <td>{u.department || "-"}</td>
                <td className="max-w-xs py-2">
                  {editingUserId === u.id ? (
                    <div className="flex flex-col gap-1">
                      {Object.entries(ROLE_LABELS).map(([roleKey, label]) => (
                        <label key={roleKey} className="flex items-center gap-1.5 text-xs text-slate-700">
                          <input
                            type="checkbox"
                            checked={editRoles.has(roleKey)}
                            onChange={() => toggleEditRole(roleKey)}
                          />
                          {label}
                        </label>
                      ))}
                    </div>
                  ) : (
                    u.roles.map((r) => ROLE_LABELS[r] || r).join(", ") || "-"
                  )}
                </td>
                <td>{userStatusLabel(u)}</td>
                <td>
                  {editingUserId === u.id ? (
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => saveRoles(u.id)}
                        disabled={savingRoles}
                        className="text-xs text-brand-600 hover:underline disabled:opacity-50"
                      >
                        저장
                      </button>
                      <button onClick={cancelEditRoles} className="text-xs text-slate-500 hover:underline">
                        취소
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-1">
                      <button onClick={() => startEditRoles(u)} className="text-xs text-brand-600 hover:underline">
                        권한 수정
                      </button>
                      <button onClick={() => toggleActive(u)} className="text-xs text-slate-500 hover:underline">
                        {u.is_active ? "비활성화" : "활성화"}
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="mb-1 block text-xs text-slate-500">{label}</label>
      <input className="input" value={value} onChange={(e) => onChange(e.target.value)} required />
    </div>
  );
}

function userStatusLabel(u: UserOut): string {
  if (u.approval_status === "PENDING_EMAIL_VERIFICATION") return "이메일 인증 대기";
  if (u.approval_status === "PENDING_ADMIN_APPROVAL") return "관리자 승인 대기";
  if (u.approval_status === "REJECTED") return "반려됨";
  return u.is_active ? "활성" : "비활성";
}

function PendingApprovalsPanel({ users }: { users: UserOut[] }) {
  const queryClient = useQueryClient();
  const [selections, setSelections] = useState<Record<string, { litigation: boolean; legalReviewer: boolean }>>({});
  const [error, setError] = useState<string | null>(null);

  function selectionFor(id: string) {
    return selections[id] || { litigation: false, legalReviewer: false };
  }

  function toggle(id: string, key: "litigation" | "legalReviewer") {
    setSelections((prev) => ({ ...prev, [id]: { ...selectionFor(id), [key]: !selectionFor(id)[key] } }));
  }

  async function approve(user: UserOut) {
    setError(null);
    const sel = selectionFor(user.id);
    try {
      await api.post(`/api/users/${user.id}/approve`, {
        grant_litigation_access: sel.litigation,
        grant_legal_reviewer: sel.legalReviewer,
      });
      queryClient.invalidateQueries({ queryKey: ["admin-pending-approvals"] });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  async function reject(user: UserOut) {
    setError(null);
    try {
      await api.post(`/api/users/${user.id}/reject`);
      queryClient.invalidateQueries({ queryKey: ["admin-pending-approvals"] });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  if (users.length === 0) {
    return <p className="rounded border border-slate-200 bg-white p-6 text-center text-sm text-slate-400">승인 대기 중인 가입 신청이 없습니다.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <p className="text-sm text-red-600">{error}</p>}
      {users.map((u) => {
        const sel = selectionFor(u.id);
        return (
          <div key={u.id} className="rounded border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-medium text-slate-800">
                  {u.full_name} <span className="text-sm font-normal text-slate-500">({u.employee_no})</span>
                </p>
                <p className="text-sm text-slate-500">
                  {u.email} · {u.phone_number || "-"}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button onClick={() => reject(u)} className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50">
                  반려
                </button>
                <button onClick={() => approve(u)} className="btn-primary">
                  승인
                </button>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-4 border-t border-slate-100 pt-3 text-sm">
              <label className="flex items-center gap-2 text-slate-400">
                <input type="checkbox" checked disabled />
                일반직원 기본 (대시보드 · 내 문서 · 계약서 업로드)
              </label>
              <label className="flex items-center gap-2 text-slate-700">
                <input type="checkbox" checked={sel.litigation} onChange={() => toggle(u.id, "litigation")} />
                소송·분쟁 사건 접근 권한
              </label>
              <label className="flex items-center gap-2 text-slate-700">
                <input type="checkbox" checked={sel.legalReviewer} onChange={() => toggle(u.id, "legalReviewer")} />
                법무 검토함 접근 권한 (법무담당자)
              </label>
            </div>
          </div>
        );
      })}
    </div>
  );
}
