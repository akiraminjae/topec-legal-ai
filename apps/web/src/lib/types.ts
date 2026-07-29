export interface DocumentOut {
  id: string;
  title: string;
  document_category: string;
  contract_type: string | null;
  topec_position: string | null;
  litigation_document_type: string | null;
  topec_litigation_position: string | null;
  case_number: string | null;
  court: string | null;
  department: string | null;
  counterparty_name: string | null;
  contract_amount: number | null;
  security_level: string;
  retention_policy: string;
  status: string;
  failure_reason: string | null;
  overall_risk_level: string | null;
  legal_review_required: boolean;
  owner_id: string;
  owner_name: string | null;
  created_at: string;
}

export interface DocumentFileOut {
  id: string;
  original_filename: string;
  extension: string;
  size_bytes: number;
  virus_scan_status: string;
}

export interface ProcessingJobOut {
  step: string;
  status: string;
  detail: string | null;
}

export interface CrossReviewOut {
  provider: string;
  model: string;
  is_mock: boolean;
  agreement_level: string;
  overall_opinion: string;
  additional_risks: string | null;
  missed_points: string | null;
  confidence: number | null;
}

export interface ProcessingStatusOut {
  document_status: string;
  failure_reason: string | null;
  progress_percent: number;
  jobs: ProcessingJobOut[];
}

export interface ClauseOut {
  id: string;
  clause_no: string | null;
  clause_type: string;
  title: string | null;
  original_text: string;
  order_index: number;
}

export interface CitationOut {
  source_title: string;
  source_type: string;
  excerpt: string | null;
  verified: boolean;
}

export interface FindingOut {
  id: string;
  clause_id: string | null;
  category: string;
  title: string;
  risk_level: string;
  original_text: string | null;
  issue_summary: string;
  reason: string;
  impact_on_topec: string;
  recommended_action: string;
  questions_for_user: string[];
  legal_review_required: boolean;
  confidence: number;
  source_type: string;
  citations: CitationOut[];
}

export interface RevisionOut {
  id: string;
  risk_finding_id: string | null;
  level: string;
  original_text: string | null;
  revised_text: string;
  change_reason: string;
  status: string;
}

export interface DocumentSummaryOut {
  scope_summary: string | null;
  overall_risk_level: string;
  top_risks_summary: string | null;
  extracted_info: Record<string, unknown>;
  ai_provider?: string | null;
  ai_model?: string | null;
  is_mock?: boolean | null;
}

export interface ChatMessageOut {
  id: string;
  role: string;
  content: string;
  structured_answer: Record<string, unknown> | null;
}

export interface LegalReviewRequestOut {
  id: string;
  document_id: string;
  document_title: string | null;
  requested_by_name: string | null;
  assigned_to_name: string | null;
  status: string;
  due_date: string | null;
  request_note: string | null;
  overall_risk_level: string | null;
}

export interface KnowledgeDocumentOut {
  id: string;
  doc_type: string;
  title: string;
  case_number: string | null;
  court: string | null;
  decision_date: string | null;
  effective_date: string | null;
  repealed_date: string | null;
  source: string | null;
  security_level: string;
  is_valid: boolean;
  is_latest_version: boolean;
  applicable_contract_types: string[];
  applicable_clause_types: string[];
}

export interface LegalCaseOut {
  id: string;
  case_name: string;
  case_type: string | null;
  dispute_type: string | null;
  case_number: string | null;
  court_name: string | null;
  topec_position: string | null;
  opponent_name: string | null;
  opponent_counsel: string | null;
  topec_counsel: string | null;
  department: string | null;
  owner_name: string | null;
  claim_amount: number | null;
  currency: string;
  status: string;
  security_level: string;
  summary: string | null;
  key_issues_to_check: string | null;
  additional_instructions: string | null;
  first_event_date: string | null;
  filing_date: string | null;
  closed_date: string | null;
  document_count: number;
  unclassified_count: number;
  latest_document_date: string | null;
  overall_risk_level: string | null;
  created_at: string;
}

export interface CaseUploadBatchOut {
  id: string;
  case_id: string;
  status: string;
  total_files: number;
  uploaded_files: number;
  processed_files: number;
  failed_files: number;
  total_size_bytes: number;
  progress_percent: number;
  started_at: string | null;
  completed_at: string | null;
  error_summary: string | null;
  user_memo: string | null;
}

export interface CaseDocumentOut {
  id: string;
  case_id: string;
  document_id: string;
  batch_id: string | null;
  sequence_number: number;
  is_duplicate: boolean;
  duplicate_of_document_id: string | null;
  title: string;
  litigation_document_type: string | null;
  status: string;
  failure_reason: string | null;
  overall_risk_level: string | null;
  legal_review_required: boolean;
  owner_id: string;
  created_at: string;
  ai_suggested_document_type: string | null;
  classification_confidence: number | null;
  classification_reasoning: string | null;
  extracted_case_number: string | null;
  extracted_court: string | null;
  extracted_plaintiff: string | null;
  extracted_defendant: string | null;
  extracted_plaintiff_counsel: string | null;
  extracted_defendant_counsel: string | null;
  case_info_confidence: number | null;
  needs_user_confirmation: boolean;
}

export interface TimelineEntryOut {
  date_value: string | null;
  date_type: string;
  confidence: number;
  source_text: string | null;
  document_id: string;
  document_title: string;
  litigation_document_type: string | null;
  is_fallback_upload_order: boolean;
}

export interface CaseDocumentRelationOut {
  id: string;
  document_a_id: string;
  document_a_title: string;
  document_b_id: string;
  document_b_title: string;
  relation_type: string;
  reasoning: string | null;
}

export interface CaseConflictOut {
  id: string;
  conflict_type: string;
  summary: string;
  value_a: string;
  source_document_a_id: string | null;
  source_document_a_title: string | null;
  value_b: string;
  source_document_b_id: string | null;
  source_document_b_title: string | null;
  impact: string | null;
  recommended_check: string | null;
  severity: string;
  confidence: number;
  resolution_status: string;
}

export interface CaseAnalysisSummaryOut {
  case_overview: string;
  opponent_arguments_summary: string;
  topec_position_summary: string;
  key_issues_summary: string;
  missing_or_unaddressed: string;
  recommended_response_direction: string;
  ai_provider: string | null;
  ai_model: string | null;
  is_mock: boolean | null;
  document_count: number;
  generated_at: string | null;
}

export interface CaseChatSessionOut {
  id: string;
  case_id: string;
  title: string | null;
}

export interface CaseChatMessageOut {
  id: string;
  role: string;
  content: string;
  structured_answer: Record<string, unknown> | null;
}

export interface CaseReportOut {
  id: string;
  report_type: string;
  format: string;
  pdf_conversion_failed: boolean;
}

export interface UserOut {
  id: string;
  employee_no: string;
  email: string;
  full_name: string;
  phone_number: string | null;
  position_title: string | null;
  department: string | null;
  roles: string[];
  is_active: boolean;
  must_change_password: boolean;
  email_verified_at: string | null;
  approval_status: string;
}

export interface DepartmentOut {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
}

export interface DashboardStats {
  total_users: number;
  active_users: number;
  total_documents: number;
  documents_by_contract_type: Record<string, number>;
  documents_by_department: Record<string, number>;
  documents_by_risk_level: Record<string, number>;
  legal_review_requested: number;
  legal_review_completed: number;
  analysis_failure_count: number;
  ai_usage_total_calls: number;
  ai_usage_total_input_tokens: number;
  ai_usage_total_output_tokens: number;
  documents_this_month: number;
}

export interface MyUsageOut {
  today: TokenUsagePeriod;
  this_month: TokenUsagePeriod;
  total: TokenUsagePeriod;
}

export interface TokenUsagePeriod {
  calls: number;
  input_tokens: number;
  output_tokens: number;
}

export interface ProviderUsageOut {
  provider: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
}

export interface ResourceUsageOut {
  storage: {
    used_bytes: number;
    quota_bytes: number;
    used_percent: number;
    db_size_bytes: number;
  };
  api_usage: {
    today: TokenUsagePeriod;
    this_month: TokenUsagePeriod;
    total: TokenUsagePeriod;
    by_provider: ProviderUsageOut[];
  };
}

export interface AuditLogOut {
  id: string;
  user_id: string | null;
  user_name: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  ip_address: string | null;
  success: boolean;
  failure_reason: string | null;
  change_summary: string | null;
  created_at: string;
}

export interface LoginAttemptOut {
  id: string;
  user_id: string | null;
  email_attempted: string;
  success: boolean;
  ip_address: string | null;
  user_agent: string | null;
  failure_reason: string | null;
  created_at: string;
}
