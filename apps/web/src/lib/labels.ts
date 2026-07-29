export const DOCUMENT_CATEGORY_LABELS: Record<string, string> = {
  CONTRACT: "계약서 검토",
  LITIGATION: "소송·분쟁 문서 검토",
};

export const LITIGATION_DOCUMENT_TYPE_LABELS: Record<string, string> = {
  COMPLAINT: "소장",
  ANSWER: "답변서",
  PREPARATORY_BRIEF: "준비서면",
  APPEAL_BRIEF: "항소·상고 이유서",
  RULING: "결정문",
  JUDGMENT: "판결문",
  DEMAND_LETTER: "내용증명·최고장",
  OTHER: "기타",
};

export const TOPEC_LITIGATION_POSITION_LABELS: Record<string, string> = {
  PLAINTIFF: "원고",
  DEFENDANT: "피고",
  INTERVENOR: "보조참가인",
  OTHER: "기타",
};

export const CONTRACT_TYPE_LABELS: Record<string, string> = {
  SUBCONTRACT: "하도급계약",
  DESIGN_SUPERVISION_CM: "설계·감리·CM 용역계약",
  GENERAL_SERVICE: "일반 용역계약",
  PURCHASE_SUPPLY: "물품구매·공급계약",
  SOFTWARE_SAAS: "소프트웨어·SaaS 계약",
  NDA: "비밀유지계약",
  MOU: "업무협약·MOU",
  CONSORTIUM: "공동수급·컨소시엄 협약",
  CONSULTING: "자문·위임계약",
  LEASE: "임대차계약",
  PERSONAL_DATA_PROCESSING: "개인정보 처리위탁계약",
  OTHER: "기타 계약",
};

export const TOPEC_POSITION_LABELS: Record<string, string> = {
  CLIENT: "발주자",
  PRINCIPAL_CONTRACTOR: "원사업자",
  SUBCONTRACTOR: "수급사업자·하도급업체",
  SERVICE_PROVIDER: "용역 제공자",
  SERVICE_RECIPIENT: "용역 수령자",
  SUPPLIER: "공급자",
  PURCHASER: "구매자",
  CONFIDENTIAL_INFO_PROVIDER: "비밀정보 제공자",
  CONFIDENTIAL_INFO_RECIPIENT: "비밀정보 수령자",
  CONSORTIUM_MEMBER: "공동수급체 구성원",
  OTHER: "기타",
};

export const RISK_LEVEL_LABELS: Record<string, string> = {
  CRITICAL: "매우 높음",
  HIGH: "높음",
  MEDIUM: "보통",
  LOW: "낮음",
  ACCEPTABLE: "적정",
};

export const RISK_LEVEL_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-100 text-red-800 border-red-300",
  HIGH: "bg-orange-100 text-orange-800 border-orange-300",
  MEDIUM: "bg-yellow-100 text-yellow-800 border-yellow-300",
  LOW: "bg-blue-100 text-blue-800 border-blue-300",
  ACCEPTABLE: "bg-green-100 text-green-800 border-green-300",
};

/** Hex equivalents of RISK_LEVEL_COLORS for use in chart fills (recharts can't
 * consume Tailwind utility classes). Kept in sync with the Tailwind palette
 * shades used above (red/orange/yellow/blue/green-500). */
export const RISK_LEVEL_HEX: Record<string, string> = {
  CRITICAL: "#ef4444",
  HIGH: "#f97316",
  MEDIUM: "#eab308",
  LOW: "#3b82f6",
  ACCEPTABLE: "#22c55e",
};

export const STATUS_HEX: Record<string, string> = {
  UPLOADED: "#94a3b8",
  VALIDATING: "#94a3b8",
  EXTRACTING: "#94a3b8",
  OCR_PROCESSING: "#94a3b8",
  STRUCTURING: "#94a3b8",
  ANALYZING: "#3b82f6",
  WAITING_FOR_REVIEW: "#eab308",
  REVIEW_IN_PROGRESS: "#eab308",
  COMPLETED: "#22c55e",
  FAILED: "#ef4444",
  ARCHIVED: "#cbd5e1",
  DELETED: "#cbd5e1",
};

export const REVISION_LEVEL_LABELS: Record<string, string> = {
  MINIMUM: "최소 수정안",
  STANDARD: "권고 수정안",
  STRONG: "TOPEC 보호 강화안",
};

export const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  UPLOADED: "업로드됨",
  VALIDATING: "파일 검증 중",
  EXTRACTING: "텍스트 추출 중",
  OCR_PROCESSING: "OCR 처리 중",
  STRUCTURING: "조항 구조화 중",
  ANALYZING: "AI 분석 중",
  WAITING_FOR_REVIEW: "법무검토 대기",
  REVIEW_IN_PROGRESS: "법무검토 진행 중",
  COMPLETED: "검토 완료",
  FAILED: "분석 실패",
  ARCHIVED: "보관됨",
  DELETED: "삭제됨",
};

export const SECURITY_LEVEL_LABELS: Record<string, string> = {
  INTERNAL: "일반(사내)",
  IMPORTANT: "중요",
  CONFIDENTIAL: "극비",
};

export const RETENTION_POLICY_LABELS: Record<string, string> = {
  DELETE_AFTER_ANALYSIS: "분석 후 삭제",
  KEEP_30_DAYS: "30일 보관",
  KEEP_1_YEAR: "1년 보관",
  KEEP_UNTIL_MANUAL_DELETE: "직접 삭제할 때까지 보관",
};

export const AUDIT_ACTION_LABELS: Record<string, string> = {
  LOGIN_SUCCESS: "로그인 성공",
  LOGIN_FAILURE: "로그인 실패",
  LOGOUT: "로그아웃",
  USER_CREATED: "사용자 생성",
  USER_UPDATED: "사용자 정보 변경",
  USER_DISABLED: "사용자 비활성화",
  DOCUMENT_UPLOADED: "문서 업로드",
  DOCUMENT_VIEWED: "문서 조회",
  DOCUMENT_DOWNLOADED: "문서 다운로드",
  DOCUMENT_ANALYSIS_STARTED: "AI 분석 시작",
  DOCUMENT_ANALYSIS_COMPLETED: "AI 분석 완료",
  DOCUMENT_ANALYSIS_FAILED: "AI 분석 실패",
  DOCUMENT_UPDATED: "문서 정보 변경",
  DOCUMENT_DELETED: "문서 삭제",
  REPORT_CREATED: "보고서 생성",
  REPORT_DOWNLOADED: "보고서 다운로드",
  LEGAL_REVIEW_REQUESTED: "법무검토 요청",
  LEGAL_REVIEW_ASSIGNED: "법무검토 담당자 지정",
  LEGAL_REVIEW_COMPLETED: "법무검토 완료",
  KNOWLEDGE_UPLOADED: "법률지식 업로드",
  KNOWLEDGE_UPDATED: "법률지식 수정",
  ROLE_CHANGED: "역할 변경",
  SYSTEM_SETTING_CHANGED: "시스템 설정 변경",
  SIGNUP_REQUESTED: "회원가입 신청",
  SIGNUP_EMAIL_VERIFIED: "회원가입 이메일 인증",
  SIGNUP_APPROVED: "회원가입 승인",
  SIGNUP_REJECTED: "회원가입 반려",
  LEGAL_CASE_CREATED: "소송·분쟁 사건 생성",
  LEGAL_CASE_UPDATED: "소송·분쟁 사건 수정",
  LEGAL_CASE_DELETED: "소송·분쟁 사건 삭제",
  CASE_BATCH_CREATED: "사건 일괄업로드 생성",
  CASE_BATCH_UPLOAD_COMPLETED: "사건 일괄업로드 완료",
  CASE_BATCH_PARTIALLY_COMPLETED: "사건 일괄업로드 일부완료",
  CASE_DOCUMENT_UPLOADED: "사건 문서 업로드",
  CASE_DOCUMENT_DUPLICATE_DETECTED: "사건 문서 중복 감지",
  CASE_DOCUMENT_REANALYZED: "사건 문서 재분석",
  CASE_ANALYSIS_STARTED: "사건 분석 시작",
  CASE_ANALYSIS_COMPLETED: "사건 분석 완료",
  CASE_ANALYSIS_FAILED: "사건 분석 실패",
  CASE_CHAT_QUESTIONED: "사건 AI 질의응답",
  CASE_FINAL_DOCUMENT_CREATED: "사건 최종 문서 생성",
  CASE_DOCUMENT_DOWNLOADED: "사건 문서 다운로드",
};

export const ROLE_LABELS: Record<string, string> = {
  USER: "일반사용자",
  DEPARTMENT_ADMIN: "부서관리자",
  LEGAL_REVIEWER: "법무담당자",
  EXECUTIVE: "경영진",
  SYSTEM_ADMIN: "시스템관리자",
  LITIGATION_ACCESS: "소송·분쟁 사건 담당",
};

export const LEGAL_REVIEW_STATUS_LABELS: Record<string, string> = {
  NOT_REQUESTED: "요청 전",
  REQUESTED: "요청됨",
  ASSIGNED: "담당자 지정됨",
  IN_REVIEW: "검토 중",
  APPROVED: "승인",
  REJECTED: "반려",
  REVISION_REQUIRED: "보완요청",
  COMPLETED: "완료",
};

export const AI_PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Claude",
  openai: "OpenAI GPT",
  azure_openai: "Azure OpenAI",
  gemini: "Gemini",
  local: "내부망 AI",
  mock: "Mock AI",
};

export const AI_PROVIDER_ICONS: Record<string, string> = {
  anthropic: "◆",
  openai: "●",
  azure_openai: "◆",
  gemini: "✦",
  local: "🏢",
  mock: "🧪",
};

export const AI_DISCLAIMER =
  "본 결과는 AI를 활용한 1차 계약·법률 검토 지원자료입니다. 사실관계, 계약상 지위 및 적용 법령에 따라 판단이 달라질 수 있습니다. 중요 계약, 분쟁 가능 계약 또는 고위험 조항이 있는 경우 법무담당자나 외부 법률전문가의 확인을 거쳐야 합니다.";

export const DATE_TYPE_LABELS: Record<string, string> = {
  DOCUMENT_DATE: "문서 작성일",
  FILING_DATE: "제출일",
  RECEIVED_DATE: "접수일",
  SERVICE_DATE: "송달일",
  COURT_RECEIPT_DATE: "법원 접수일",
  HEARING_DATE: "기일",
  DUE_DATE: "대응기한",
  NOTICE_DATE: "통지일",
  EVENT_DATE: "사건 발생일",
  UNKNOWN_DATE: "미분류 날짜",
};

export const RELATION_TYPE_LABELS: Record<string, string> = {
  RESPONSE_TO: "응답",
  REBUTS: "반박",
  SUPPLEMENTS: "보충",
  AMENDS: "개정",
  REFERENCES: "인용",
  SUPPORTS: "지지",
  CONTRADICTS: "모순",
  DUPLICATES: "중복",
  RELATED_TO: "관련",
};

export const CONFLICT_SEVERITY_LABELS: Record<string, string> = {
  HIGH: "높음",
  MEDIUM: "보통",
  LOW: "낮음",
};

export const LEGAL_CASE_STATUS_LABELS: Record<string, string> = {
  ACTIVE: "진행 중",
  CLOSED: "종결",
};

export const CASE_UPLOAD_BATCH_STATUS_LABELS: Record<string, string> = {
  CREATED: "대기",
  PROCESSING: "처리 중",
  PARTIALLY_COMPLETED: "일부 완료",
  COMPLETED: "완료",
  FAILED: "실패",
};

export const CASE_REPORT_TYPE_LABELS: Record<string, string> = {
  PREPARATORY_BRIEF_DRAFT: "준비서면 초안",
  EXECUTIVE_SUMMARY: "경영진 보고 요약",
};

/** Free-text suggestions only — the backend stores case_type/dispute_type as
 * free text rather than a fixed enum, since the spec's category lists overlap
 * heavily (소송/민사/공사대금/하도급 등이 동시에 해당 가능) and forcing a single
 * enum value would block real cases from being classified accurately. */
export const CASE_TYPE_SUGGESTIONS = ["소송", "중재", "조정", "클레임", "내용증명"];
export const DISPUTE_TYPE_SUGGESTIONS = ["민사", "행정", "형사 관련", "계약분쟁", "공사대금", "하도급", "손해배상"];

/** Document type label that works for both CONTRACT and LITIGATION documents,
 * since `contract_type` is null for the latter (and vice versa). */
export function documentTypeLabel(doc: {
  document_category: string;
  contract_type: string | null;
  litigation_document_type: string | null;
}): string {
  if (doc.document_category === "LITIGATION") {
    return LITIGATION_DOCUMENT_TYPE_LABELS[doc.litigation_document_type || ""] || doc.litigation_document_type || "-";
  }
  return CONTRACT_TYPE_LABELS[doc.contract_type || ""] || doc.contract_type || "-";
}
