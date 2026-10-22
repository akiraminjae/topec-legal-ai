"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BookOpen,
  ChevronDown,
  FileText,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Scale,
  Settings,
  ShieldCheck,
  Upload,
  UserCog,
  X,
  type LucideIcon,
} from "lucide-react";
import { clsx } from "clsx";
import { useAuth, useLogout } from "@/lib/auth";
import { ROLE_LABELS } from "@/lib/labels";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  roles: string[] | null;
  /** 하위 경로까지 활성 표시하지 않을 항목 — /manual 이 /manual/admin 까지 잡는 것을 막는다. */
  exact?: boolean;
};

type NavGroup = { title: string | null; items: NavItem[] };

/** 업무 → 관리 → 도움말 순서. 권한이 없는 항목이 빠져 그룹이 비면 그룹째 숨긴다. */
const NAV_GROUPS: NavGroup[] = [
  {
    title: null,
    items: [
      { href: "/dashboard", label: "대시보드", icon: LayoutDashboard, roles: null },
      { href: "/documents", label: "내 문서", icon: FileText, roles: null },
      { href: "/documents/new", label: "계약서 업로드", icon: Upload, roles: null },
      {
        href: "/legal-cases",
        label: "소송·분쟁 사건",
        icon: Scale,
        roles: ["LITIGATION_ACCESS", "LEGAL_REVIEWER", "DEPARTMENT_ADMIN", "EXECUTIVE", "SYSTEM_ADMIN"],
      },
      { href: "/legal-review", label: "법무 검토함", icon: ShieldCheck, roles: ["LEGAL_REVIEWER", "SYSTEM_ADMIN"] },
    ],
  },
  {
    title: "관리",
    items: [
      { href: "/admin", label: "관리자", icon: UserCog, roles: ["SYSTEM_ADMIN"], exact: true },
      { href: "/admin/monitoring", label: "리소스 모니터링", icon: Gauge, roles: ["SYSTEM_ADMIN"] },
      { href: "/admin/logs", label: "로그 기록", icon: ScrollText, roles: ["SYSTEM_ADMIN"] },
    ],
  },
  {
    title: "도움말",
    items: [
      { href: "/manual", label: "사용자 매뉴얼", icon: BookOpen, roles: null, exact: true },
      { href: "/manual/admin", label: "관리자 매뉴얼", icon: Settings, roles: ["SYSTEM_ADMIN"] },
    ],
  },
];

function isActive(item: NavItem, pathname: string) {
  return item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(item.href + "/");
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, isLoading, hasRole } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const logout = useLogout();
  const [navOpen, setNavOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    } else if (!isLoading && user?.must_change_password && pathname !== "/change-password") {
      router.replace("/change-password");
    }
  }, [isLoading, user, pathname, router]);

  // 화면을 옮기면 모바일 메뉴와 프로필 메뉴는 닫는다.
  useEffect(() => {
    setNavOpen(false);
    setMenuOpen(false);
  }, [pathname]);

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-ink-100">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-ink-300 border-t-brand-600" />
        <p className="text-sm text-ink-500">불러오는 중...</p>
      </div>
    );
  }

  const groups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => !i.roles || hasRole(...i.roles)),
  })).filter((g) => g.items.length > 0);

  const current = groups.flatMap((g) => g.items).find((i) => isActive(i, pathname));

  return (
    <div className="min-h-screen lg:flex">
      {/* 모바일에서 사이드바를 열었을 때의 배경 가림막 */}
      {navOpen && (
        <div className="fixed inset-0 z-30 bg-ink-900/40 lg:hidden" onClick={() => setNavOpen(false)} aria-hidden />
      )}

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r border-ink-200 bg-white transition-transform lg:static lg:translate-x-0",
          navOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center gap-2.5 border-b border-ink-100 px-5 py-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-mark.png" alt="" width={34} height={34} className="shrink-0 rounded-md" />
          <div className="min-w-0">
            <p className="truncate text-base font-bold leading-tight text-brand-700">TOPEC Legal AI</p>
            <p className="truncate text-xs text-ink-400">사내 법률검토 AI 시스템</p>
          </div>
          <button
            onClick={() => setNavOpen(false)}
            className="ml-auto rounded-md p-1 text-ink-400 hover:bg-ink-100 lg:hidden"
            aria-label="메뉴 닫기"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {groups.map((group, gi) => (
            <div key={group.title ?? "main"} className={clsx(gi > 0 && "mt-5")}>
              {group.title && (
                <p className="mb-1.5 px-3 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-400">
                  {group.title}
                </p>
              )}
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => {
                  const active = isActive(item, pathname);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={clsx(
                        "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                        active
                          ? "bg-brand-50 font-semibold text-brand-700"
                          : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"
                      )}
                    >
                      <item.icon
                        className={clsx("h-[1.125rem] w-[1.125rem] shrink-0", active ? "text-brand-600" : "text-ink-400")}
                        strokeWidth={2}
                      />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-ink-100 px-5 py-3">
          <p className="text-[0.6875rem] leading-relaxed text-ink-400">
            AI 검토 결과는 참고자료입니다. 최종 판단은 법무담당자 확인을 거치세요.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-ink-200 bg-white/90 px-4 backdrop-blur md:px-6">
          <button
            onClick={() => setNavOpen(true)}
            className="rounded-md p-1.5 text-ink-500 hover:bg-ink-100 lg:hidden"
            aria-label="메뉴 열기"
          >
            <Menu className="h-5 w-5" />
          </button>

          <p className="truncate text-sm font-semibold text-ink-800">{current?.label ?? "TOPEC Legal AI"}</p>

          <div className="relative ml-auto">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="flex items-center gap-2 rounded-md py-1.5 pl-1.5 pr-2 text-sm hover:bg-ink-100"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
                {user.full_name?.slice(0, 1) || "?"}
              </span>
              <span className="hidden max-w-[12rem] truncate font-medium text-ink-700 sm:inline">{user.full_name}</span>
              <ChevronDown className="h-4 w-4 text-ink-400" />
            </button>

            {menuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} aria-hidden />
                <div className="card absolute right-0 z-20 mt-1.5 w-64 animate-fade-in-up p-1.5 shadow-pop">
                  <div className="border-b border-ink-100 px-3 py-2.5">
                    <p className="truncate text-sm font-semibold text-ink-900">{user.full_name}</p>
                    <p className="truncate text-xs text-ink-500">{user.email}</p>
                    <p className="mt-1.5 text-xs text-ink-500">{user.department || "소속 미지정"}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {user.roles.map((r) => (
                        <span key={r} className="badge border-ink-200 bg-ink-100 text-ink-600">
                          {ROLE_LABELS[r] || r}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button
                    onClick={() => logout()}
                    className="mt-1 flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-ink-700 hover:bg-ink-100"
                  >
                    <LogOut className="h-4 w-4 text-ink-400" />
                    로그아웃
                  </button>
                </div>
              </>
            )}
          </div>
        </header>

        <main className="flex-1 px-4 py-6 md:px-6 lg:px-8">
          <div className="mx-auto flex max-w-[1400px] flex-col gap-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
