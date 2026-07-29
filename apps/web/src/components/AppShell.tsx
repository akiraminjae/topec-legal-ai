"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth, useLogout } from "@/lib/auth";
import { ROLE_LABELS } from "@/lib/labels";

const NAV_ITEMS = [
  { href: "/dashboard", label: "대시보드", roles: null },
  { href: "/documents", label: "내 문서", roles: null },
  { href: "/documents/new", label: "계약서 업로드", roles: null },
  {
    href: "/legal-cases",
    label: "소송·분쟁 사건",
    roles: ["LITIGATION_ACCESS", "LEGAL_REVIEWER", "DEPARTMENT_ADMIN", "EXECUTIVE", "SYSTEM_ADMIN"],
  },
  { href: "/legal-review", label: "법무 검토함", roles: ["LEGAL_REVIEWER", "SYSTEM_ADMIN"] },
  { href: "/admin", label: "관리자", roles: ["SYSTEM_ADMIN"] },
  { href: "/admin/monitoring", label: "리소스 모니터링", roles: ["SYSTEM_ADMIN"] },
  { href: "/admin/logs", label: "로그 기록", roles: ["SYSTEM_ADMIN"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, isLoading, hasRole } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const logout = useLogout();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    } else if (!isLoading && user?.must_change_password && pathname !== "/change-password") {
      router.replace("/change-password");
    }
  }, [isLoading, user, pathname, router]);

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        불러오는 중...
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-mark.png" alt="" width={36} height={36} className="shrink-0 rounded" />
          <div>
            <p className="text-lg font-bold leading-tight text-brand-700">TOPEC Legal AI</p>
            <p className="text-xs text-slate-400">사내 법률검토 AI 시스템</p>
          </div>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {NAV_ITEMS.filter((item) => !item.roles || hasRole(...item.roles)).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded px-3 py-2 text-sm ${
                pathname === item.href || pathname.startsWith(item.href + "/")
                  ? "bg-brand-50 font-semibold text-brand-700"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div />
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-600">
              {user.full_name} ({user.department || "-"}) ·{" "}
              {user.roles.map((r) => ROLE_LABELS[r] || r).join(", ")}
            </span>
            <button onClick={() => logout()} className="rounded border border-slate-300 px-3 py-1 text-slate-600 hover:bg-slate-50">
              로그아웃
            </button>
          </div>
        </header>
        <main className="flex-1 bg-slate-50 p-6">{children}</main>
      </div>
    </div>
  );
}
