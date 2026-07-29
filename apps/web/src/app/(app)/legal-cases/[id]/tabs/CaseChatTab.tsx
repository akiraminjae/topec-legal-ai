"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, extractErrorMessage } from "@/lib/api";
import { CaseChatMessageOut } from "@/lib/types";
import { AIProviderBadge } from "@/components/Badges";
import { LegalRobotIcon } from "@/components/LegalRobotIcon";
import { ShareMenu } from "@/components/ShareMenu";

interface CaseChatSessionOut {
  id: string;
  case_id: string;
  title: string | null;
}

const SUGGESTED_QUESTIONS = [
  "이 사건의 전체 경과를 날짜순으로 정리해줘.",
  "상대방 주장 중 서로 모순되는 부분을 찾아줘.",
  "아직 답변하지 않은 상대방 주장이 있는지 확인해줘.",
  "이 사건에서 추가 확보해야 할 증거를 알려줘.",
];

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

export function CaseChatTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const progress = useFakeProgress(sending);

  const { data: sessions = [] } = useQuery<CaseChatSessionOut[]>({
    queryKey: ["case-chat-sessions", caseId],
    queryFn: async () => (await api.get<CaseChatSessionOut[]>(`/api/legal-cases/${caseId}/chat/sessions`)).data,
  });

  useEffect(() => {
    if (!sessionId && sessions.length > 0) setSessionId(sessions[0].id);
  }, [sessions, sessionId]);

  const { data: messages = [] } = useQuery<CaseChatMessageOut[]>({
    queryKey: ["case-chat-messages", sessionId],
    queryFn: async () => (await api.get<CaseChatMessageOut[]>(`/api/legal-cases/${caseId}/chat/sessions/${sessionId}/messages`)).data,
    enabled: !!sessionId,
  });

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId;
    const { data } = await api.post<CaseChatSessionOut>(`/api/legal-cases/${caseId}/chat/sessions`);
    queryClient.invalidateQueries({ queryKey: ["case-chat-sessions", caseId] });
    setSessionId(data.id);
    return data.id;
  }

  async function send(content: string) {
    if (!content.trim()) return;
    setSending(true);
    setError(null);
    try {
      const sid = await ensureSession();
      queryClient.setQueryData<CaseChatMessageOut[]>(["case-chat-messages", sid], (old = []) => [
        ...old,
        { id: `temp-${Date.now()}`, role: "user", content, structured_answer: null },
      ]);
      setInput("");
      await api.post(`/api/legal-cases/${caseId}/chat/sessions/${sid}/messages`, { content });
      queryClient.invalidateQueries({ queryKey: ["case-chat-messages", sid] });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600 ring-1 ring-brand-200">
          <LegalRobotIcon className="h-7 w-7" />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-slate-700">사건 AI 질의응답</h3>
          <p className="text-xs text-slate-500">
            이 질의응답은 <strong>이 사건에 업로드된 문서에서만</strong> 근거를 찾습니다. 다른 사건의 자료는
            검색되지 않습니다.
          </p>
        </div>
      </div>
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
          <div className="flex flex-col items-center gap-2 py-8 text-slate-300">
            <LegalRobotIcon className="h-16 w-16" />
            <p className="text-sm text-slate-400">사건 자료에 대해 궁금한 점을 질문해 보세요.</p>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "self-end" : "self-start"}>
            {m.role === "user" ? (
              <div className="max-w-2xl rounded bg-brand-600 px-3 py-2 text-sm text-white">{m.content}</div>
            ) : (
              <div className="flex items-start gap-2">
                <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600 ring-1 ring-brand-200">
                  <LegalRobotIcon className="h-5 w-5" />
                </span>
                <CaseAssistantAnswer message={m} />
              </div>
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
          placeholder="사건 자료에 대해 질문을 입력하세요"
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
    <div className="flex items-start gap-2">
      <span className="mt-1 flex h-8 w-8 shrink-0 animate-pulse items-center justify-center rounded-full bg-brand-50 text-brand-600 ring-1 ring-brand-200">
        <LegalRobotIcon className="h-5 w-5" />
      </span>
      <div className="w-64 max-w-sm rounded border border-brand-200 bg-brand-50 p-3">
        <p className="mb-2 flex items-center gap-2 text-sm text-brand-700">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-brand-500" />
          AI 법률 로봇이 사건 자료를 검토 중입니다...
        </p>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-brand-100">
          <div className="h-full rounded-full bg-brand-500 transition-all duration-300 ease-out" style={{ width: `${progress}%` }} />
        </div>
      </div>
    </div>
  );
}

function CaseAssistantAnswer({ message }: { message: CaseChatMessageOut }) {
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
  ]
    .filter(Boolean)
    .join("\n\n");

  return (
    <div className="max-w-3xl rounded border border-slate-200 bg-white p-3 text-sm">
      <div className="mb-2 flex items-center justify-between gap-2">
        <AIProviderBadge provider={aiProvider} isMock={isMock} />
        <ShareMenu title="사건 AI 질의응답 답변" text={shareText} />
      </div>
      <Field label="결론" value={structured.conclusion as string} />
      <Field label="전제 및 사실관계" value={structured.facts_and_premises as string} />
      <Field label="관련 자료" value={structured.related_clauses as string} />
      <Field label="TOPEC에 미치는 영향" value={structured.impact_on_topec as string} />
      <Field label="관련 법령·판례·내부자료" value={structured.legal_sources as string} />
      <Field label="권고 대응방안" value={structured.recommended_action as string} />
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
