"use client";

import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { isKakaoConfigured, shareToKakao } from "@/lib/kakaoShare";

interface ShareMenuProps {
  /** Short label used as the shared item's title (Kakao card title, filename stem). */
  title: string;
  /** Plain-text content shared via copy/txt/Kakao. */
  text: string;
  /** Optional: wire up when a Word/PDF version already exists (e.g. document reports). */
  onDownloadWord?: () => void;
  onDownloadPdf?: () => void;
}

const MENU_WIDTH = 208; // matches w-52

export function ShareMenu({ title, text, onDownloadWord, onDownloadPdf }: ShareMenuProps) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackPos, setFeedbackPos] = useState({ top: 0, left: 0 });

  function buttonRect() {
    return buttonRef.current?.getBoundingClientRect() ?? new DOMRect();
  }

  // Rendered via a portal into <body> and positioned with `fixed` coordinates
  // (not `absolute` inside this component's own DOM position) — otherwise any
  // scrollable ancestor (e.g. the chat message list's overflow-y-auto) clips
  // the dropdown instead of letting it float above the page.
  function toggle() {
    if (!open) {
      const rect = buttonRect();
      setMenuPos({
        top: rect.bottom + 4,
        left: Math.min(rect.right - MENU_WIDTH, window.innerWidth - MENU_WIDTH - 8),
      });
    }
    setOpen((v) => !v);
  }

  function flash(message: string) {
    const rect = buttonRect();
    setFeedbackPos({ top: rect.bottom + 4, left: Math.max(8, rect.right - 160) });
    setFeedback(message);
    setTimeout(() => setFeedback(null), 2000);
  }

  async function copyText() {
    try {
      await navigator.clipboard.writeText(text);
      flash("복사되었습니다");
    } catch {
      flash("복사에 실패했습니다");
    }
    setOpen(false);
  }

  function downloadTxt() {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title.replace(/[\\/:*?"<>|]/g, "_")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    setOpen(false);
  }

  async function handleKakao() {
    if (!isKakaoConfigured()) {
      flash("카카오 SDK 키가 설정되지 않았습니다");
      return;
    }
    try {
      await shareToKakao(title, text);
    } catch {
      flash("카카오톡 공유에 실패했습니다");
    }
    setOpen(false);
  }

  return (
    <div className="relative inline-block">
      <button
        ref={buttonRef}
        type="button"
        onClick={toggle}
        className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
      >
        🔗 공유하기
      </button>

      {feedback &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="fixed z-50 whitespace-nowrap rounded bg-slate-800 px-2 py-1 text-xs text-white"
            style={{ top: feedbackPos.top, left: feedbackPos.left }}
          >
            {feedback}
          </div>,
          document.body
        )}

      {open &&
        typeof document !== "undefined" &&
        createPortal(
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <div
              className="fixed z-50 w-52 rounded border border-slate-200 bg-white py-1 shadow-lg"
              style={{ top: menuPos.top, left: menuPos.left }}
            >
              <MenuItem onClick={copyText}>📋 텍스트 복사</MenuItem>
              <MenuItem onClick={downloadTxt}>📄 텍스트 파일(.txt) 다운로드</MenuItem>
              {onDownloadWord && <MenuItem onClick={() => (onDownloadWord(), setOpen(false))}>📝 Word(DOCX) 다운로드</MenuItem>}
              {onDownloadPdf && <MenuItem onClick={() => (onDownloadPdf(), setOpen(false))}>📕 PDF 다운로드</MenuItem>}
              <MenuItem onClick={handleKakao} disabled={!isKakaoConfigured()}>
                💬 카카오톡 공유{!isKakaoConfigured() && " (미설정)"}
              </MenuItem>
            </div>
          </>,
          document.body
        )}
    </div>
  );
}

function MenuItem({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}
