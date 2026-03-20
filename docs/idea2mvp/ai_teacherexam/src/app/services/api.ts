const API_BASE_URL =
  (import.meta as ImportMeta & { env?: Record<string, string> }).env?.VITE_API_BASE_URL ?? "http://127.0.0.1:5001";
const API_TIMEOUT_MS = 15000;
const API_RETRY_COUNT = 1;

export interface ApiMessage {
  id: string;
  role: "user" | "ai" | "system";
  content: string;
  timestamp: string;
}

export interface CitationItem {
  source_type: "kb" | "semantic" | "web";
  source_label: string;
  title: string;
  page?: string;
  url?: string;
  quote: string;
  semantic_source_type?: string;
  semantic_source_label?: string;
}

export interface CitationSummary {
  total: number;
  has_kb: boolean;
  has_semantic: boolean;
  has_web: boolean;
  has_conflict: boolean;
}

interface ChatResponse {
  reply: string;
  mode?: "remote" | "mock";
  search_used?: boolean;
  sources?: Array<{ title: string; url: string; snippet: string }>;
  citations?: CitationItem[];
  citation_summary?: CitationSummary;
}

export interface ChatStreamMeta {
  mode?: "remote" | "mock";
  search_used?: boolean;
  kb_used?: boolean;
}

export interface ChatStreamDone extends ChatStreamMeta {
  reply: string;
  sources?: Array<{ title: string; url: string; snippet: string }>;
  kb_sources?: Array<{ title: string; page?: string; snippet: string }>;
  citations?: CitationItem[];
  citation_summary?: CitationSummary;
}

interface ChatStreamCallbacks {
  onMeta?: (meta: ChatStreamMeta) => void;
  onDelta?: (delta: string) => void;
  onDone?: (done: ChatStreamDone) => void;
}

interface HistoryResponse {
  messages: ApiMessage[];
}

interface IngestResponse {
  topic: string;
  concepts: string[];
  confusion_risk: string;
  ack: string;
  mode?: "remote" | "mock";
}

interface VisionResponse {
  reply: string;
  mode?: "remote" | "mock";
  search_used?: boolean;
  sources?: Array<{ title: string; url: string; snippet: string }>;
  citations?: CitationItem[];
  citation_summary?: CitationSummary;
}

interface UploadImageResponse {
  image_id: string;
  image_url: string;
}

interface NotificationResponse {
  notification: { id: string; content: string; timestamp: string } | null;
}

export interface WeeklyStatsSnapshot {
  week_start: string;
  week_end: string;
  task_completion_rate: number;
  repeat_mistake_rate: number;
  previous_repeat_mistake_rate: number;
  repeat_mistake_rate_change: number;
  repeat_mistake_drop_ratio: number;
  task_completion_target: number;
  repeat_mistake_drop_target: number;
  has_repeat_baseline: boolean;
  is_task_completion_target_met: boolean;
  is_repeat_mistake_target_met: boolean;
  is_weekly_goal_met: boolean;
}

export interface WeeklyReport {
  week_start: string;
  week_end: string;
  summary: string;
  highlights: string[];
  next_week_focus: string[];
  coach_message: string;
  stats_snapshot: WeeklyStatsSnapshot;
  updated_at?: string;
}

interface WeeklyReportResponse {
  user_id: string;
  week_start: string;
  week_end: string;
  report: WeeklyReport | null;
  mode?: "remote" | "mock";
}

export interface EvaluationCase {
  id: string;
  case_code: string;
  focus_topic: string;
  question: string;
  reference_points: string[];
  expected_style: string;
  difficulty: string;
}

export interface EvaluationRun {
  id: string;
  user_id: string;
  case_id: string;
  variant_label: string;
  answer: string;
  score_detail: {
    correctness: number;
    actionability: number;
    style_consistency: number;
    memory_utilization: number;
    brevity: number;
    total_score: number;
  };
  total_score: number;
  created_at: string;
}

interface EvaluationCasesResponse {
  cases: EvaluationCase[];
}

interface EvaluationScoreResponse {
  case: EvaluationCase;
  run: EvaluationRun;
}

interface EvaluationCompareResponse {
  case: EvaluationCase;
  winner: string;
  delta: number;
  run_a: EvaluationRun;
  run_b: EvaluationRun;
}

export interface EvaluationTrendSummary {
  total_runs: number;
  best_variant: string;
  variants: Array<{
    variant_label: string;
    run_count: number;
    avg_score: number;
    best_score: number;
    latest_score: number;
  }>;
  recent_runs: Array<{
    variant_label: string;
    total_score: number;
    created_at: string;
  }>;
}

interface EvaluationTrendResponse {
  user_id: string;
  summary: EvaluationTrendSummary;
}

export interface NudgeStrategyItem {
  trigger_type: string;
  nudge_level: string;
  sent_count: number;
  reengaged_count: number;
  reengagement_rate: number;
  avg_reengage_hours: number | null;
}

export interface NudgeStrategySummary {
  window_days: number;
  overall: {
    window_days: number;
    sent_count: number;
    reengaged_count: number;
    reengagement_rate: number;
  };
  best_strategy: NudgeStrategyItem | null;
  strategies: NudgeStrategyItem[];
}

interface NudgeStrategyResponse {
  user_id: string;
  summary: NudgeStrategySummary;
}

export interface UserProfile {
  exam_goal: string;
  exam_date: string;
  response_style: string;
  weak_points: string[];
  study_schedule: string;
  motivation_note: string;
  updated_at?: string;
}

interface UserProfileResponse {
  user_id: string;
  profile: UserProfile;
}

export interface LearningExportResult {
  summary_card: {
    id: string;
    title: string;
    content: string;
    tags: string[];
    status: string;
    created_at: string;
    updated_at: string;
  };
  terms: string[];
  term_cards_added: number;
  term_cards_updated: number;
  review_records_created: number;
  review_records: Array<{
    id: string;
    focus_topic: string;
    source_question: string;
    mistake_type: string;
    reason: string;
    fix_action: string;
    next_drill: string;
    is_repeat_mistake: boolean;
    created_at: string;
  }>;
}

interface LearningExportResponse {
  user_id: string;
  export: LearningExportResult;
}

export interface MemoryCard {
  id: string;
  title: string;
  content: string;
  tags: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

interface MemoryCardsResponse {
  user_id: string;
  cards: MemoryCard[];
}

export interface ReviewRecord {
  id: string;
  focus_topic: string;
  source_question: string;
  mistake_type: string;
  reason: string;
  fix_action: string;
  next_drill: string;
  is_repeat_mistake: boolean;
  created_at: string;
}

interface ReviewRecordsResponse {
  user_id: string;
  records: ReviewRecord[];
}

export interface HealthResponse {
  status: string;
  time: string;
  llm?: {
    provider?: string;
    model?: string;
    remote_ready?: boolean;
    needs_api_key?: boolean;
  };
}

export class ApiRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let attempt = 0;
  let lastError: unknown;
  while (attempt <= API_RETRY_COUNT) {
    try {
      const response = await requestOnce<T>(path, options);
      return response;
    } catch (error) {
      lastError = error;
      const shouldRetry =
        attempt < API_RETRY_COUNT &&
        (error instanceof ApiRequestError
          ? error.status === 408 || error.status === 429 || error.status >= 500
          : true);
      if (!shouldRetry) {
        throw error;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 400));
      attempt += 1;
    }
  }
  throw lastError instanceof Error ? lastError : new ApiRequestError("请求失败", 500);
}

async function requestOnce<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiRequestError("请求超时，请稍后再试", 408);
    }
    throw new ApiRequestError("网络连接异常，请检查服务状态", 503);
  } finally {
    window.clearTimeout(timeoutId);
  }
  if (!response.ok) {
    let message = `请求失败 (${response.status})`;
    try {
      const payload = (await response.json()) as { error?: string };
      if (payload?.error) {
        message = payload.error;
      }
    } catch {
      const text = await response.text();
      if (text) {
        message = text;
      }
    }
    throw new ApiRequestError(message, response.status);
  }
  return (await response.json()) as T;
}

export function fetchHealth() {
  return request<HealthResponse>("/api/health");
}

export function sendChatMessage(text: string, userId = "default", conversationId = "default") {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ text, user_id: userId, conversation_id: conversationId }),
  });
}

export async function streamChatMessage(
  text: string,
  userId = "default",
  conversationId = "default",
  callbacks: ChatStreamCallbacks = {},
) {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, user_id: userId, conversation_id: conversationId }),
    });
  } catch {
    throw new ApiRequestError("网络连接异常，请检查服务状态", 503);
  }
  if (!response.ok) {
    let message = `请求失败 (${response.status})`;
    try {
      const payload = (await response.json()) as { error?: string };
      if (payload?.error) {
        message = payload.error;
      }
    } catch {}
    throw new ApiRequestError(message, response.status);
  }
  if (!response.body) {
    const fallback = await sendChatMessage(text, userId, conversationId);
    callbacks.onDone?.({
      reply: fallback.reply,
      mode: fallback.mode,
      search_used: fallback.search_used,
      sources: fallback.sources,
      citations: fallback.citations,
      citation_summary: fallback.citation_summary,
    });
    return {
      reply: fallback.reply,
      mode: fallback.mode,
      search_used: fallback.search_used,
      sources: fallback.sources,
      citations: fallback.citations,
      citation_summary: fallback.citation_summary,
    } satisfies ChatStreamDone;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let donePayload: ChatStreamDone | null = null;

  const consumeLine = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) {
      return;
    }
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(trimmed) as Record<string, unknown>;
    } catch {
      return;
    }
    const type = String(payload.type ?? "");
    if (type === "meta") {
      callbacks.onMeta?.({
        mode: payload.mode as "remote" | "mock" | undefined,
        search_used: Boolean(payload.search_used),
        kb_used: Boolean(payload.kb_used),
      });
      return;
    }
    if (type === "delta") {
      const delta = String(payload.delta ?? "");
      if (delta) {
        callbacks.onDelta?.(delta);
      }
      return;
    }
    if (type === "done") {
      donePayload = {
        reply: String(payload.reply ?? ""),
        mode: payload.mode as "remote" | "mock" | undefined,
        search_used: Boolean(payload.search_used),
        kb_used: Boolean(payload.kb_used),
        sources: (payload.sources as Array<{ title: string; url: string; snippet: string }>) ?? [],
        kb_sources: (payload.kb_sources as Array<{ title: string; page?: string; snippet: string }>) ?? [],
        citations: (payload.citations as CitationItem[]) ?? [],
        citation_summary: (payload.citation_summary as CitationSummary | undefined) ?? undefined,
      };
      callbacks.onDone?.(donePayload);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      consumeLine(line);
    }
  }
  buffer += decoder.decode();
  if (buffer.trim()) {
    consumeLine(buffer);
  }
  if (donePayload) {
    return donePayload;
  }
  const fallback = await sendChatMessage(text, userId, conversationId);
  const normalized = {
    reply: fallback.reply,
    mode: fallback.mode,
    search_used: fallback.search_used,
    sources: fallback.sources,
    citations: fallback.citations,
    citation_summary: fallback.citation_summary,
  } satisfies ChatStreamDone;
  callbacks.onDone?.(normalized);
  return normalized;
}

export function fetchHistory(userId = "default", limit = 50, conversationId = "default") {
  return request<HistoryResponse>(
    `/api/history?user_id=${encodeURIComponent(userId)}&conversation_id=${encodeURIComponent(conversationId)}&limit=${limit}`,
  );
}

export function ingestLearningContent(content: string, userId = "default", conversationId = "default") {
  return request<IngestResponse>("/api/ingest", {
    method: "POST",
    body: JSON.stringify({ content, user_id: userId, conversation_id: conversationId }),
  });
}

export function fetchPendingNotification(userId = "default", conversationId = "default") {
  return request<NotificationResponse>(
    `/api/notifications?user_id=${encodeURIComponent(userId)}&conversation_id=${encodeURIComponent(conversationId)}`,
  );
}

export function fetchWeeklyReport(userId = "default", weekStart = "", weekEnd = "") {
  const search = new URLSearchParams({ user_id: userId });
  if (weekStart) {
    search.set("week_start", weekStart);
  }
  if (weekEnd) {
    search.set("week_end", weekEnd);
  }
  return request<WeeklyReportResponse>(`/api/weekly-report?${search.toString()}`);
}

export function generateWeeklyReport(userId = "default", weekStart = "", weekEnd = "") {
  return request<WeeklyReportResponse>("/api/weekly-report/generate", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      week_start: weekStart,
      week_end: weekEnd,
    }),
  });
}

export async function uploadImage(file: File, userId = "default") {
  const form = new FormData();
  form.append("image", file);
  form.append("user_id", userId);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/upload-image`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new ApiRequestError("网络连接异常，请检查服务状态", 503);
  }
  if (!response.ok) {
    let message = `上传失败 (${response.status})`;
    try {
      const payload = (await response.json()) as { error?: string };
      if (payload?.error) {
        message = payload.error;
      }
    } catch {}
    throw new ApiRequestError(message, response.status);
  }
  return (await response.json()) as UploadImageResponse;
}

export function askWithImage(question: string, imageUrl: string, userId = "default", conversationId = "default") {
  return request<VisionResponse>("/api/vision-query", {
    method: "POST",
    body: JSON.stringify({ question, image_url: imageUrl, user_id: userId, conversation_id: conversationId }),
  });
}

export function fetchEvaluationCases(limit = 30) {
  return request<EvaluationCasesResponse>(`/api/eval/cases?limit=${limit}`);
}

export function scoreEvaluationAnswer(
  caseId: string,
  answer: string,
  variantLabel: string,
  userId = "default",
) {
  return request<EvaluationScoreResponse>("/api/eval/score", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      case_id: caseId,
      answer,
      variant_label: variantLabel,
    }),
  });
}

export function compareEvaluationAnswers(
  caseId: string,
  answerA: string,
  answerB: string,
  labelA: string,
  labelB: string,
  userId = "default",
) {
  return request<EvaluationCompareResponse>("/api/eval/ab-compare", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      case_id: caseId,
      answer_a: answerA,
      answer_b: answerB,
      label_a: labelA,
      label_b: labelB,
    }),
  });
}

export function fetchEvaluationTrends(userId = "default", limit = 200) {
  const search = new URLSearchParams({ user_id: userId, limit: String(limit) });
  return request<EvaluationTrendResponse>(`/api/eval/trends?${search.toString()}`);
}

export function fetchNudgeStrategy(userId = "default", days = 14) {
  const search = new URLSearchParams({ user_id: userId, days: String(days) });
  return request<NudgeStrategyResponse>(`/api/nudge/strategy?${search.toString()}`);
}

export function reportAnalyticsEvent(
  userId: string,
  eventName: string,
  eventPayload: Record<string, unknown> = {},
) {
  return request<{ ok: boolean; event_name: string }>("/api/analytics/events", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      event_name: eventName,
      event_payload: eventPayload,
    }),
  });
}

export function fetchProfile(userId = "default") {
  return request<UserProfileResponse>(`/api/profile?user_id=${encodeURIComponent(userId)}`);
}

export function updateProfile(userId: string, profile: Partial<UserProfile>) {
  return request<UserProfileResponse>("/api/profile", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, profile }),
  });
}

export function exportAnswerToLearningCard(userId: string, sourceQuestion: string, answerText: string) {
  return request<LearningExportResponse>("/api/learning/export-answer", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      source_question: sourceQuestion,
      answer_text: answerText,
    }),
  });
}

export function fetchMemoryCards(userId = "default", limit = 50) {
  const search = new URLSearchParams({ user_id: userId, limit: String(limit) });
  return request<MemoryCardsResponse>(`/api/memory-cards?${search.toString()}`);
}

export function fetchReviewRecords(userId = "default", limit = 20) {
  const search = new URLSearchParams({ user_id: userId, limit: String(limit) });
  return request<ReviewRecordsResponse>(`/api/review-records?${search.toString()}`);
}
