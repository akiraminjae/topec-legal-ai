"use client";

/** AI 법률 로봇 아이콘 — 로봇이 법조계 저울(정의의 저울)을 들고 있는 모습.
 *  stroke가 currentColor라 부모의 text-* 색을 그대로 따른다. */
export function LegalRobotIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      {/* 안테나 */}
      <line x1="16" y1="10" x2="16" y2="6.5" />
      <circle cx="16" cy="4.8" r="1.9" fill="currentColor" stroke="none" />
      {/* 머리 + 눈 */}
      <rect x="6" y="10" width="20" height="15" rx="4.5" />
      <circle cx="12.5" cy="17.5" r="1.7" fill="currentColor" stroke="none" />
      <circle cx="19.5" cy="17.5" r="1.7" fill="currentColor" stroke="none" />
      {/* 몸통 + 가슴 표시등 */}
      <rect x="8" y="29" width="16" height="14" rx="3.5" />
      <circle cx="16" cy="36" r="1.6" fill="currentColor" stroke="none" />
      {/* 다리 */}
      <line x1="12" y1="43" x2="12" y2="48" />
      <line x1="20" y1="43" x2="20" y2="48" />
      {/* 저울 기둥을 잡은 팔과 손 */}
      <path d="M24 32 L40 34" />
      <circle cx="44" cy="34" r="2.6" fill="currentColor" stroke="none" />
      {/* 저울: 기둥·꼭지·받침 */}
      <line x1="44" y1="14" x2="44" y2="46" />
      <circle cx="44" cy="11.5" r="2" fill="currentColor" stroke="none" />
      <line x1="37.5" y1="46" x2="50.5" y2="46" />
      {/* 저울대 */}
      <line x1="34" y1="17" x2="54" y2="17" />
      {/* 왼쪽 접시 */}
      <path d="M34 17 L30.5 25.5 M34 17 L37.5 25.5" strokeWidth={2} />
      <path d="M29.5 26 A4.6 4.6 0 0 0 38.5 26 Z" strokeWidth={2} />
      {/* 오른쪽 접시 */}
      <path d="M54 17 L50.5 25.5 M54 17 L57.5 25.5" strokeWidth={2} />
      <path d="M49.5 26 A4.6 4.6 0 0 0 58.5 26 Z" strokeWidth={2} />
    </svg>
  );
}
