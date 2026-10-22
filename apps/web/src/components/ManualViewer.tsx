"use client";

// 매뉴얼 뷰어 — 왼쪽 사이드바의 [사용자 매뉴얼] / [관리자 매뉴얼] 메뉴에서 들어옵니다.
// 본문은 src/content/manuals/*.md 를 그대로 렌더링하므로, 문구 수정은 그 Markdown만
// 고치면 됩니다(배포용 PDF는 docs/manuals 참고).
// 화면 안에서 다시 좌측에 목차(H1 기준), 우측에 본문을 배치합니다.

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ManualSection {
  id: string;
  title: string;
  body: string;
}

// 목차 버튼은 일반 텍스트로 그리므로, 제목에 남은 인라인 마크업을 벗겨냅니다.
// (예: "3. 관리자 홈 (`/admin`)" → "3. 관리자 홈 (/admin)")
function plainTitle(raw: string): string {
  return raw
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]*)\*\*/g, "$1")
    .replace(/\*([^*]*)\*/g, "$1")
    .trim();
}

// Markdown을 최상위 제목(# ...) 기준으로 잘라 목차를 만듭니다.
// 두 매뉴얼 모두 "문서 제목 H1 → 버전/대상 안내 → 본 章 H1들" 순서로 쓰여 있으므로,
// 첫 H1 블록은 목차 항목이 아니라 문서 머리말로 취급합니다.
function splitSections(markdown: string): { preamble: string; sections: ManualSection[] } {
  const lines = markdown.split(/\r?\n/);
  const leading: string[] = [];
  const blocks: { title: string; body: string }[] = [];
  let current: { title: string; body: string } | null = null;
  let inCodeFence = false;

  for (const line of lines) {
    if (/^```/.test(line)) inCodeFence = !inCodeFence;
    const heading = !inCodeFence ? /^#\s+(.*)$/.exec(line) : null;
    if (heading) {
      current = { title: heading[1].trim(), body: "" };
      blocks.push(current);
      continue;
    }
    if (current) current.body += line + "\n";
    else leading.push(line);
  }

  // 章이 2개 이상일 때만 첫 블록을 머리말로 떼어냅니다(한 덩어리짜리 문서는 그대로 표시).
  const preambleParts = [leading.join("\n").trim()];
  const chapters = blocks.length > 1 ? blocks.slice(1) : blocks;
  if (blocks.length > 1) preambleParts.push(blocks[0].body.trim());

  return {
    preamble: preambleParts.filter(Boolean).join("\n\n").trim(),
    sections: chapters.map((b, i) => ({ id: `sec-${i}`, title: plainTitle(b.title), body: b.body })),
  };
}

export function ManualViewer({ markdown, label }: { markdown: string; label: string }) {
  const { preamble, sections } = useMemo(() => splitSections(markdown), [markdown]);
  const [activeId, setActiveId] = useState(sections[0]?.id ?? "");
  const active = sections.find((s) => s.id === activeId) ?? sections[0];
  const idx = sections.findIndex((s) => s.id === active?.id);
  const prev = idx > 0 ? sections[idx - 1] : null;
  const next = idx >= 0 && idx < sections.length - 1 ? sections[idx + 1] : null;

  if (!active) {
    return <p className="text-sm text-ink-500">매뉴얼 내용을 불러오지 못했습니다.</p>;
  }

  return (
    <div className="flex gap-6">
      {/* 목차 */}
      <nav className="hidden w-64 shrink-0 lg:block">
        <div className="sticky top-6 card p-4">
          <p className="mb-2 px-2 text-xs font-semibold text-ink-400">{label} · 목차</p>
          {sections.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveId(s.id)}
              className={`mb-0.5 block w-full rounded px-2 py-1.5 text-left text-sm leading-snug ${
                s.id === active.id
                  ? "bg-brand-50 font-semibold text-brand-700"
                  : "text-ink-600 hover:bg-ink-50"
              }`}
            >
              {s.title}
            </button>
          ))}
        </div>
      </nav>

      {/* 본문 */}
      <div className="min-w-0 flex-1">
        {/* 목차를 숨기는 좁은 화면에서는 셀렉트로 이동 */}
        <div className="mb-4 lg:hidden">
          <select
            value={active.id}
            onChange={(e) => setActiveId(e.target.value)}
            className="w-full input"
          >
            {sections.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </div>

        {/* 버전·대상·주의사항 등 문서 머리말은 어느 항목을 보든 계속 보이게 둡니다 */}
        {preamble && (
          <div className="mb-4 card px-6 pb-1 pt-4">
            <Markdown>{preamble}</Markdown>
          </div>
        )}

        <article className="card p-6">
          <h1 className="mb-4 text-xl font-bold text-ink-900">{active.title}</h1>
          <Markdown>{active.body}</Markdown>
        </article>

        <div className="mt-4 flex items-center justify-between text-sm">
          {prev ? (
            <button onClick={() => setActiveId(prev.id)} className="text-ink-500 hover:text-brand-700">
              ‹ {prev.title}
            </button>
          ) : (
            <span />
          )}
          {next ? (
            <button onClick={() => setActiveId(next.id)} className="font-semibold text-brand-700 hover:underline">
              {next.title} ›
            </button>
          ) : (
            <span />
          )}
        </div>
      </div>
    </div>
  );
}

// react-markdown v9는 커스텀 컴포넌트에 AST 노드(node)를 함께 넘깁니다.
// 그대로 spread하면 DOM에 node="[object Object]" 속성이 붙으므로 걸러냅니다.
function clean<T extends object>({ node, ...rest }: T & { node?: unknown }) {
  return rest;
}

// Tailwind typography 플러그인이 없으므로 요소별 스타일을 직접 지정합니다.
function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: (p) => <h2 className="mb-3 mt-6 text-lg font-bold text-ink-900" {...clean(p)} />,
        h2: (p) => <h3 className="mb-2 mt-6 text-base font-bold text-ink-800" {...clean(p)} />,
        h3: (p) => <h4 className="mb-2 mt-4 text-sm font-bold text-ink-700" {...clean(p)} />,
        p: (p) => <p className="mb-3 text-sm leading-relaxed text-ink-700" {...clean(p)} />,
        ul: (p) => <ul className="mb-3 list-disc space-y-1 pl-5 text-sm leading-relaxed text-ink-700" {...clean(p)} />,
        ol: (p) => <ol className="mb-3 list-decimal space-y-1 pl-5 text-sm leading-relaxed text-ink-700" {...clean(p)} />,
        li: (p) => <li className="pl-1" {...clean(p)} />,
        strong: (p) => <strong className="font-semibold text-ink-900" {...clean(p)} />,
        a: (p) => <a className="text-brand-700 underline" {...clean(p)} />,
        blockquote: (p) => (
          <blockquote
            className="mb-3 border-l-4 border-amber-300 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-900"
            {...clean(p)}
          />
        ),
        code: (p) => <code className="rounded bg-ink-100 px-1 py-0.5 text-[13px] text-ink-800" {...clean(p)} />,
        pre: (p) => <pre className="mb-3 overflow-x-auto rounded bg-ink-900 p-4 text-xs text-ink-100" {...clean(p)} />,
        hr: () => <hr className="my-6 border-ink-200" />,
        table: (p) => (
          <div className="mb-4 overflow-x-auto">
            <table className="w-full border-collapse text-sm" {...clean(p)} />
          </div>
        ),
        th: (p) => (
          <th className="border border-ink-200 bg-ink-50 px-3 py-2 text-left font-semibold text-ink-700" {...clean(p)} />
        ),
        td: (p) => <td className="border border-ink-200 px-3 py-2 align-top text-ink-700" {...clean(p)} />,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
