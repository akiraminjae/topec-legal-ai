/**
 * 화면 공통 UI 조각.
 *
 * 페이지에서 카드·표·빈 상태를 매번 Tailwind 로 조립하면 화면마다 여백과 모서리가
 * 조금씩 달라진다(기존 화면들이 그랬다). 여기 있는 것부터 찾아 쓰고, 없으면 여기에 추가한다.
 * 색·굴곡·그림자 값은 tailwind.config.ts 와 globals.css 의 토큰만 사용한다.
 */
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { clsx } from "clsx";

/* ------------------------------------------------------------------ 페이지 머리말 */

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-500">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ 카드 */

export function Card({
  children,
  className,
  as: Tag = "div",
}: {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "section";
}) {
  return <Tag className={clsx("card", className)}>{children}</Tag>;
}

export function CardHeader({
  title,
  description,
  icon: Icon,
  actions,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: LucideIcon;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-start justify-between gap-3 border-b border-ink-100 px-5 py-3.5", className)}>
      <div className="flex min-w-0 items-start gap-2.5">
        {Icon && (
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-700">
            <Icon className="h-4 w-4" strokeWidth={2} />
          </span>
        )}
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-ink-900">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-ink-500">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function CardBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("p-5", className)}>{children}</div>;
}

/* ------------------------------------------------------------------ 지표 카드 */

export function StatCard({
  label,
  value,
  unit,
  icon: Icon,
  tone = "default",
  hint,
  href,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  icon?: LucideIcon;
  /** alert — 0보다 클 때 주의를 끌어야 하는 지표(고위험 계약, 실패 건수 등) */
  tone?: "default" | "alert" | "brand";
  hint?: string;
  href?: string;
}) {
  const alert = tone === "alert";
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-ink-500">{label}</p>
        {Icon && (
          <span
            className={clsx(
              "flex h-8 w-8 items-center justify-center rounded-md",
              alert ? "bg-red-100 text-red-600" : "bg-brand-50 text-brand-600"
            )}
          >
            <Icon className="h-4 w-4" strokeWidth={2} />
          </span>
        )}
      </div>
      <p className={clsx("mt-2 text-3xl font-bold tabular", alert ? "text-red-700" : "text-ink-900")}>
        {value}
        {unit && <span className="ml-1 text-base font-semibold text-ink-400">{unit}</span>}
      </p>
      {hint && <p className="mt-1 text-xs text-ink-500">{hint}</p>}
    </>
  );

  const className = clsx(
    "block rounded-lg border bg-white p-5 shadow-card transition-shadow",
    alert ? "border-red-200 bg-red-50/40" : "border-ink-200",
    href && "hover:shadow-card-hover"
  );

  return href ? (
    <Link href={href} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

/* ------------------------------------------------------------------ 빈 상태 */

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  compact,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={clsx("flex flex-col items-center justify-center text-center", compact ? "py-8" : "py-14")}>
      {Icon && (
        <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-ink-100 text-ink-400">
          <Icon className="h-5 w-5" strokeWidth={1.8} />
        </span>
      )}
      <p className="text-sm font-medium text-ink-700">{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs leading-relaxed text-ink-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ 안내 박스 */

const NOTICE_TONES = {
  info: "border-brand-200 bg-brand-50 text-brand-900",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  danger: "border-red-200 bg-red-50 text-red-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
} as const;

export function Notice({
  tone = "info",
  icon: Icon,
  title,
  children,
  actions,
}: {
  tone?: keyof typeof NOTICE_TONES;
  icon?: LucideIcon;
  title?: React.ReactNode;
  children?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className={clsx("rounded-lg border px-4 py-3", NOTICE_TONES[tone])}>
      <div className="flex gap-2.5">
        {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />}
        <div className="min-w-0 flex-1 text-sm leading-relaxed">
          {title && <p className="font-semibold">{title}</p>}
          {children && <div className={clsx(title && "mt-1", "text-[0.8125rem] opacity-90")}>{children}</div>}
          {actions && <div className="mt-3 flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ 표 */

export function Table({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className="table-wrap">
      <table className={clsx("table", className)}>{children}</table>
    </div>
  );
}

/* ------------------------------------------------------------------ 탭 */

export function TabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; icon?: LucideIcon; count?: number }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-ink-200">
      {tabs.map((t) => {
        const isActive = t.key === active;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={clsx(
              "-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors",
              isActive
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-500 hover:border-ink-300 hover:text-ink-800"
            )}
          >
            {t.icon && <t.icon className="h-4 w-4" strokeWidth={2} />}
            {t.label}
            {t.count != null && (
              <span
                className={clsx(
                  "rounded-full px-1.5 py-0.5 text-[0.6875rem] font-semibold tabular",
                  isActive ? "bg-brand-100 text-brand-700" : "bg-ink-200 text-ink-600"
                )}
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ 로딩 자리표시 */

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-md bg-ink-200/70", className)} />;
}
