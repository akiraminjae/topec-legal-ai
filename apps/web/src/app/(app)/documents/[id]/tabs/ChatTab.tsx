"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { ChatMessageOut } from "@/lib/types";
import { AIProviderBadge } from "@/components/Badges";
import { ShareMenu } from "@/components/ShareMenu";

interface ChatSessionOut {
  id: string;
  document_id: string;
  title: string | null;
}

const SUGGESTED_QUESTIONS = [
  "이 계약에서 TOPEC에 가장 불리한 조항은 무엇인가?",
  "지체상금 상한이 적정한가?",
  "추가업무 비용을 받을 수 있도록 수정해줘.",
  "경영진 보고용으로 요약해줘.",
];

/** Simulated 0~100% progress while waiting for the AI response. There's no real
 * server-sent progress for a single blocking chat call, so this eases up to ~92%
 * over a plausible response window and only snaps to 100% once the answer
 * actually arrives — never claims completion before it's true. */
function useFakeProgress(active: boolean) {
  const [progress, setProgress] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (active) {
      setProgress(4);
      timerRef.current = setInterval(() => {
        setProgress((p) => (p >= 92 ? 92 : p + Math.max(1, (92 - p) * 0.08)));
      }, 250);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setProgress((p) => (p > 0 ? 100 : 0));
      const resetTimer = setTimeout(() => setProgress(0), 500);
      return () => clearTimeout(resetTimer);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [active]);

  return Math.round(progress);
}

export function ChatTab({ documentId }: { documentId: string }) {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const progress = useFakeProgress(sending);

  const { data: sessions = [] } = useQuery<ChatSessionOut[]>({
    queryKey: ["chat-sessions", documentId],
    queryFn: async () => (await api.get<ChatSessionOut[]>(`/api/documents/${documentId}/chat/sessions`)).data,
  });

  useEffect(() => {
    if (!sessionId && sessions.length > 0) setSessionId(sessions[0].id);
  }, [sessions, sessionId]);

  const { data: messages = [] } = useQuery<ChatMessageOut[]>({
    queryKey: ["chat-messages", sessionId],
    queryFn: async () => (await api.get<ChatMessageOut[]>(`/api/chat/sessions/${sessionId}/messages`)).data,
    enabled: !!sessionId,
  });

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId;
    const { data } = await api.post<ChatSessionOut>(`/api/documents/${documentId}/chat/sessions`);
    queryClient.invalidateQueries({ queryKey: ["chat-sessions", documentId] });
    setSessionId(data.id);
    return data.id;
  }

  async function send(content: string) {
    if (!content.trim()) return;
    setSending(true);
    setError(null);
    try {
      const sid = await ensureSession();
      queryClient.setQueryData<ChatMessageOut[]>(["chat-messages", sid], (old = []) => [
        ...old,
        { id: `temp-${Date.now()}`, role: "user", content, structured_answer: null },
      ]);
      setInput("");
      await api.post(`/api/chat/sessions/${sid}/messages`, { content });
      queryClient.invalidateQueries({ queryKey: ["chat-messages", sid] });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap gap-2">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            disabled={sending}
            onClick={() => send(q)}
            className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>

      <div className="flex max-h-[500px] flex-col gap-3 overflow-y-auto rounded border border-slate-100 p-3">
        {messages.length === 0 && !sending && (
          <p className="text-sm text-slate-400">계약서에 대해 궁금한 점을 질문해 보세요.</p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "self-end" : "self-start"}>
            {m.role === "user" ? (
              <div className="max-w-2xl rounded bg-brand-600 px-3 py-2 text-sm text-white">{m.content}</div>
            ) : (
              <AssistantAnswer message={m} />
            )}
          </div>
        ))}
        {sending && (
          <div className="self-start">
            <ThinkingIndicator progress={progress} />
          </div>
        )}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-2">
        <input
          className="input"
          placeholder="질문을 입력하세요"
          value={input}
          disabled={sending}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
        />
        <button disabled={sending} onClick={() => send(input)} className="btn-primary min-w-[88px]">
          {sending ? `${progress}%` : "전송"}
        </button>
      </div>
    </div>
  );
}

function ThinkingIndicator({ progress }: { progress: number }) {
  return (
    <div className="w-64 max-w-sm rounded border border-brand-200 bg-brand-50 p-3">
      <p className="mb-2 flex items-center gap-2 text-sm text-brand-700">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-brand-500" />
        AI가 답변을 작성 중입니다...
      </p>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-brand-100">
        <div
          className="h-full rounded-full bg-brand-500 transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

function AssistantAnswer({ message }: { message: ChatMessageOut }) {
  const structured = message.structured_answer as Record<string, unknown> | null;
  if (!structured) {
    return <div className="max-w-3xl rounded bg-slate-100 px-3 py-2 text-sm text-slate-700">{message.content}</div>;
  }
  const isMock = structured.is_mock as boolean;
  const aiProvider = structured.ai_provider as string | undefined;

  const shareText = [
    `[결론] ${structured.conclusion}`,
    `[전제 및 사실관계] ${structured.facts_and_premises}`,
    `[관련 계약조항] ${structured.related_clauses}`,
    `[TOPEC에 미치는 영향] ${structured.impact_on_topec}`,
    `[관련 법령·판례·내부자료] ${structured.legal_sources}`,
    `[권고 대응방안] ${structured.recommended_action}`,
    structured.recommended_wording ? `[수정 권고문구] ${structured.recommended_wording}` : null,
  ]
    .filter(Boolean)
    .join("\n\n");

  return (
    <div className="max-w-3xl rounded border border-slate-200 bg-white p-3 text-sm">
      <div className="mb-2 flex items-center justify-between gap-2">
        <AIProviderBadge provider={aiProvider} isMock={isMock} />
        <ShareMenu title="AI 질의응답 답변" text={shareText} />
      </div>
      <Field label="결론" value={structured.conclusion as string} />
      <Field label="전제 및 사실관계" value={structured.facts_and_premises as string} />
      <Field label="관련 계약조항" value={structured.related_clauses as string} />
      <Field label="TOPEC에 미치는 영향" value={structured.impact_on_topec as string} />
      <Field label="관련 법령·판례·내부자료" value={structured.legal_sources as string} />
      <Field label="권고 대응방안" value={structured.recommended_action as string} />
      {!!structured.recommended_wording && <Field label="수정 권고문구" value={structured.recommended_wording as string} />}
      <p className="mt-2 text-xs text-slate-400">
        신뢰도 {structured.confidence as number}% · 법무검토 필요: {structured.legal_review_required ? "예" : "아니오"}
      </p>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="mb-1.5">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="whitespace-pre-wrap text-slate-700">{value}</p>
    </div>
  );
}
