import { useCallback, useEffect, useRef, useState } from "react";
import { Beaker, SmilePlus, Sparkles, Target, BookCopy, Rows2 } from "lucide-react";
import { MessageBubble, type Message } from "../components/ui/MessageBubble";
import { InputArea } from "../components/ui/InputArea";
import { PasteModal } from "../components/modals/PasteModal";
import { NudgeNotification } from "../components/ui/NudgeNotification";
import { DashboardModal } from "../components/modals/DashboardModal";
import { EvalModal } from "../components/modals/EvalModal";
import { StylePreferenceModal } from "../components/modals/StylePreferenceModal";
import { LearningAssetsModal } from "../components/modals/LearningAssetsModal";
import { ConversationListModal, type ConversationListItem } from "../components/modals/ConversationListModal";
import { motion } from "motion/react";
import {
  askWithImage,
  ApiRequestError,
  type CitationItem as ApiCitationItem,
  type CitationSummary as ApiCitationSummary,
  compareEvaluationAnswers,
  exportAnswerToLearningCard,
  fetchEvaluationCases,
  fetchEvaluationTrends,
  fetchHealth,
  fetchHistory,
  fetchMemoryCards,
  fetchNudgeStrategy,
  fetchPendingNotification,
  fetchProfile,
  fetchReviewRecords,
  reportAnalyticsEvent,
  fetchWeeklyReport,
  generateWeeklyReport,
  ingestLearningContent,
  streamChatMessage,
  type EvaluationCase,
  type EvaluationTrendSummary,
  type MemoryCard,
  type NudgeStrategySummary,
  type ReviewRecord,
  updateProfile,
  uploadImage,
  type ApiMessage,
  type HealthResponse,
  type WeeklyReport,
} from "../services/api";

const USER_ID_STORAGE_KEY = "mindshadow_user_id";
const CONVERSATION_ID_STORAGE_KEY = "mindshadow_conversation_id";
const CONVERSATION_LIST_STORAGE_KEY = "mindshadow_conversation_list";
const RESPONSE_STYLE_OPTIONS = ["简洁版", "详细版", "速记版"] as const;
const SHOW_EVAL_ENTRY = false;

function createWelcomeMessage(): Message {
  return {
    id: "1",
    role: "ai",
    content: "哈喽呀！我是你的学习搭子，今天我们要搞定什么神仙知识？✨",
    timestamp: new Date(),
  };
}

function getOrCreateUserId() {
  const existing = window.localStorage.getItem(USER_ID_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const created = `u-${Math.random().toString(36).slice(2, 10)}`;
  window.localStorage.setItem(USER_ID_STORAGE_KEY, created);
  return created;
}

function createConversationId() {
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function createConversationTitle(seed = "") {
  const normalized = seed.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "新对话";
  }
  return normalized.slice(0, 18);
}

function getOrCreateConversationId() {
  const existing = window.localStorage.getItem(CONVERSATION_ID_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const created = createConversationId();
  window.localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, created);
  return created;
}

function mapApiMessage(message: ApiMessage): Message {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    timestamp: new Date(message.timestamp),
  };
}

function normalizeCitationSummary(summary?: ApiCitationSummary): Message["citationSummary"] | undefined {
  if (!summary) {
    return undefined;
  }
  return {
    total: Number(summary.total || 0),
    hasKb: Boolean(summary.has_kb),
    hasSemantic: Boolean(summary.has_semantic),
    hasWeb: Boolean(summary.has_web),
    hasConflict: Boolean(summary.has_conflict),
  };
}

function normalizeCitations(citations?: ApiCitationItem[]): Message["citations"] {
  if (!Array.isArray(citations)) {
    return [];
  }
  return citations
    .filter((item) => Boolean(item?.quote))
    .map((item) => ({
      sourceType: item.source_type,
      sourceLabel: item.source_label,
      title: item.title || "未命名来源",
      page: item.page || "",
      url: item.url || "",
      quote: item.quote,
      semanticSourceLabel: item.semantic_source_label || "",
    }));
}

function buildLocalReply(text: string) {
  const trimmed = text.trim();
  if (!trimmed) {
    return "我在这儿，随时可以开始。";
  }
  if (trimmed.includes("不懂") || trimmed.includes("卡住") || trimmed.includes("难")) {
    return "我们先把问题拆成最小一步，你先说说你卡在哪个关键词。";
  }
  if (trimmed.includes("谢谢") || trimmed.includes("懂了") || trimmed.includes("明白")) {
    return "太棒了，趁热打铁，我给你出一道超短练习题继续巩固。";
  }
  if (trimmed.includes("你好") || trimmed.toLowerCase().includes("hello")) {
    return "在的！今天想先攻克哪个知识点？";
  }
  return `收到，我先记住「${trimmed.slice(0, 20)}${trimmed.length > 20 ? "..." : ""}」，你想先讲思路还是先做题？`;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([createWelcomeMessage()]);

  const [isTyping, setIsTyping] = useState(false);
  const [isPasteModalOpen, setIsPasteModalOpen] = useState(false);
  const [isDashboardOpen, setIsDashboardOpen] = useState(false);
  const [isEvalOpen, setIsEvalOpen] = useState(false);
  const [isStylePreferenceOpen, setIsStylePreferenceOpen] = useState(false);
  const [isAssetsModalOpen, setIsAssetsModalOpen] = useState(false);
  const [isConversationListOpen, setIsConversationListOpen] = useState(false);
  const [nudgeMessage, setNudgeMessage] = useState<string | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [healthState, setHealthState] = useState<HealthResponse | null>(null);
  const [isOnline, setIsOnline] = useState(false);
  const [userId, setUserId] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [conversationList, setConversationList] = useState<ConversationListItem[]>([]);
  const [pendingImageUrl, setPendingImageUrl] = useState<string | null>(null);
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReport | null>(null);
  const [isWeeklyLoading, setIsWeeklyLoading] = useState(false);
  const [evaluationCases, setEvaluationCases] = useState<EvaluationCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [variantALabel, setVariantALabel] = useState("PromptA");
  const [variantBLabel, setVariantBLabel] = useState("PromptB");
  const [variantAAnswer, setVariantAAnswer] = useState("");
  const [variantBAnswer, setVariantBAnswer] = useState("");
  const [evalResult, setEvalResult] = useState<{
    winner: string;
    delta: number;
    scoreA: number;
    scoreB: number;
  } | null>(null);
  const [evalTrends, setEvalTrends] = useState<EvaluationTrendSummary | null>(null);
  const [isEvalLoading, setIsEvalLoading] = useState(false);
  const [nudgeStrategy, setNudgeStrategy] = useState<NudgeStrategySummary | null>(null);
  const [isNudgeStrategyLoading, setIsNudgeStrategyLoading] = useState(false);
  const [responseStyle, setResponseStyle] = useState<(typeof RESPONSE_STYLE_OPTIONS)[number]>("详细版");
  const [memoryCards, setMemoryCards] = useState<MemoryCard[]>([]);
  const [reviewRecords, setReviewRecords] = useState<ReviewRecord[]>([]);
  const [isAssetsLoading, setIsAssetsLoading] = useState(false);
  const [latestFreshAiMessageId, setLatestFreshAiMessageId] = useState<string | null>(null);
  const [learningCardExportStatus, setLearningCardExportStatus] = useState<Record<string, "loading" | "done">>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const learningCardExportingRef = useRef<Set<string>>(new Set());

  const getConversationListStorageKey = useCallback(
    (targetUserId: string) => `${CONVERSATION_LIST_STORAGE_KEY}:${targetUserId || "default"}`,
    [],
  );

  const persistConversationList = useCallback(
    (targetUserId: string, list: ConversationListItem[]) => {
      window.localStorage.setItem(getConversationListStorageKey(targetUserId), JSON.stringify(list));
    },
    [getConversationListStorageKey],
  );

  const loadConversationList = useCallback(
    (targetUserId: string) => {
      const raw = window.localStorage.getItem(getConversationListStorageKey(targetUserId));
      if (!raw) {
        return [];
      }
      try {
        const parsed = JSON.parse(raw) as ConversationListItem[];
        if (!Array.isArray(parsed)) {
          return [];
        }
        return parsed
          .filter((item) => Boolean(item?.id))
          .map((item) => ({
            id: String(item.id),
            title: createConversationTitle(String(item.title || "")),
            updatedAt: String(item.updatedAt || new Date().toISOString()),
          }))
          .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
      } catch {
        return [];
      }
    },
    [getConversationListStorageKey],
  );

  const ensureConversationInList = useCallback(
    (targetUserId: string, targetConversationId: string, titleSeed = "") => {
      const nowIso = new Date().toISOString();
      setConversationList((prev) => {
        const base = prev.length > 0 ? prev : loadConversationList(targetUserId);
        const exists = base.some((item) => item.id === targetConversationId);
        const next = exists
          ? base.map((item) =>
              item.id === targetConversationId
                ? {
                    ...item,
                    updatedAt: nowIso,
                    title:
                      titleSeed.trim() && (!item.title || item.title === "新对话")
                        ? createConversationTitle(titleSeed)
                        : item.title || "新对话",
                  }
                : item,
            )
          : [{ id: targetConversationId, title: createConversationTitle(titleSeed), updatedAt: nowIso }, ...base];
        const sorted = [...next].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
        persistConversationList(targetUserId, sorted);
        return sorted;
      });
    },
    [loadConversationList, persistConversationList],
  );

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  useEffect(() => {
    setUserId(getOrCreateUserId());
    setConversationId(getOrCreateConversationId());
  }, []);

  useEffect(() => {
    if (!userId || !conversationId) {
      return;
    }
    const loaded = loadConversationList(userId);
    const hasCurrent = loaded.some((item) => item.id === conversationId);
    const next = hasCurrent
      ? loaded
      : [{ id: conversationId, title: "新对话", updatedAt: new Date().toISOString() }, ...loaded];
    const sorted = [...next].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
    setConversationList(sorted);
    persistConversationList(userId, sorted);
  }, [conversationId, loadConversationList, persistConversationList, userId]);

  useEffect(() => {
    if (!userId) {
      return;
    }
    const syncHealth = async () => {
      try {
        const data = await fetchHealth();
        setHealthState(data);
        setIsOnline(true);
      } catch {
        setIsOnline(false);
      }
    };
    syncHealth();
    const timer = window.setInterval(syncHealth, 20000);
    return () => window.clearInterval(timer);
  }, [userId]);

  useEffect(() => {
    if (!userId) {
      return;
    }
    let mounted = true;
    const syncProfile = async () => {
      try {
        const response = await fetchProfile(userId);
        if (!mounted) {
          return;
        }
        const profileStyle = String(response.profile?.response_style || "").trim();
        if (RESPONSE_STYLE_OPTIONS.includes(profileStyle as (typeof RESPONSE_STYLE_OPTIONS)[number])) {
          setResponseStyle(profileStyle as (typeof RESPONSE_STYLE_OPTIONS)[number]);
        }
      } catch {}
    };
    syncProfile();
    return () => {
      mounted = false;
    };
  }, [userId]);

  useEffect(() => {
    if (!userId) {
      return;
    }
    let mounted = true;
    const syncNudgeStrategy = async () => {
      setIsNudgeStrategyLoading(true);
      try {
        const response = await fetchNudgeStrategy(userId, 14);
        if (!mounted) {
          return;
        }
        setNudgeStrategy(response.summary);
      } catch {
        if (!mounted) {
          return;
        }
        setNudgeStrategy(null);
      } finally {
        if (mounted) {
          setIsNudgeStrategyLoading(false);
        }
      }
    };
    syncNudgeStrategy();
    const timer = window.setInterval(syncNudgeStrategy, 120000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [userId]);

  useEffect(() => {
    if (!userId) {
      return;
    }
    let mounted = true;
    const syncWeeklyReport = async () => {
      setIsWeeklyLoading(true);
      try {
        const existing = await fetchWeeklyReport(userId);
        if (!mounted) {
          return;
        }
        if (existing.report) {
          setWeeklyReport(existing.report);
          return;
        }
        const generated = await generateWeeklyReport(userId);
        if (!mounted) {
          return;
        }
        setWeeklyReport(generated.report);
      } catch {
        if (!mounted) {
          return;
        }
        setWeeklyReport(null);
      } finally {
        if (mounted) {
          setIsWeeklyLoading(false);
        }
      }
    };
    syncWeeklyReport();
    const timer = window.setInterval(syncWeeklyReport, 120000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [userId]);

  useEffect(() => {
    if (!userId) {
      return;
    }
    let mounted = true;
    const syncEvaluationData = async () => {
      try {
        const casesResp = await fetchEvaluationCases(30);
        if (!mounted) {
          return;
        }
        setEvaluationCases(casesResp.cases);
        if (casesResp.cases.length > 0 && !selectedCaseId) {
          setSelectedCaseId(casesResp.cases[0].id);
        }
      } catch {}
      try {
        const trendResp = await fetchEvaluationTrends(userId, 200);
        if (!mounted) {
          return;
        }
        setEvalTrends(trendResp.summary);
      } catch {}
    };
    syncEvaluationData();
    return () => {
      mounted = false;
    };
  }, [userId]);

  useEffect(() => {
    if (!userId || !conversationId) {
      return;
    }
    let mounted = true;
    const loadInitial = async () => {
      setIsBootstrapping(true);
      try {
        const { messages: history } = await fetchHistory(userId, 50, conversationId);
        if (!mounted) {
          return;
        }
        if (history.length > 0) {
          setMessages(history.map(mapApiMessage));
          return;
        }
        setMessages([createWelcomeMessage()]);
      } catch {
        if (!mounted) {
          return;
        }
        setMessages((prev) => [
          ...prev,
          {
            id: `sys-${Date.now()}`,
            role: "system",
            content: "服务连接中断，当前使用本地演示模式",
            timestamp: new Date(),
          },
        ]);
      } finally {
        if (mounted) {
          setIsBootstrapping(false);
        }
      }
    };
    loadInitial();
    return () => {
      mounted = false;
    };
  }, [conversationId, userId]);

  const modelReady = Boolean(isOnline && !healthState?.llm?.needs_api_key && healthState?.llm?.remote_ready !== false);
  const dotClass = modelReady ? "bg-[#22C55E]" : "bg-[#EF4444]";
  useEffect(() => {
    if (!userId || !conversationId) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const { notification } = await fetchPendingNotification(userId, conversationId);
        if (notification?.content) {
          setNudgeMessage(notification.content);
        }
      } catch {}
    }, 30000);
    return () => window.clearInterval(timer);
  }, [conversationId, userId]);

  const handleSendMessage = async (text: string) => {
    const effectiveUserId = userId || getOrCreateUserId();
    const effectiveConversationId = conversationId || getOrCreateConversationId();
    if (!effectiveUserId) {
      return;
    }
    if (!userId) {
      setUserId(effectiveUserId);
    }
    if (!conversationId) {
      setConversationId(effectiveConversationId);
    }
    ensureConversationInList(effectiveUserId, effectiveConversationId, text);
    setLatestFreshAiMessageId(null);
    const newUserMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newUserMessage]);
    setIsTyping(true);
    try {
      let result: {
        reply: string;
        mode?: "remote" | "mock";
        search_used?: boolean;
        citations?: ApiCitationItem[];
        citation_summary?: ApiCitationSummary;
      };
      if (pendingImageUrl) {
        result = await askWithImage(text, pendingImageUrl, effectiveUserId, effectiveConversationId);
        setIsTyping(false);
        const newAiMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "ai",
          content: result.reply,
          timestamp: new Date(),
          citations: normalizeCitations(result.citations),
          citationSummary: normalizeCitationSummary(result.citation_summary),
        };
        setLatestFreshAiMessageId(newAiMessage.id);
        setMessages((prev) => [...prev, newAiMessage]);
      } else {
        const aiMessageId = `${Date.now()}-stream-ai`;
        let streamedAnyDelta = false;
        let finalReplyText = "";
        setMessages((prev) => [
          ...prev,
          {
            id: aiMessageId,
            role: "ai",
            content: "",
            timestamp: new Date(),
            isTyping: true,
          },
        ]);
        setLatestFreshAiMessageId(aiMessageId);
        result = { reply: "", mode: "mock", search_used: false };
        await streamChatMessage(text, effectiveUserId, effectiveConversationId, {
          onMeta: (meta) => {
            result = {
              ...result,
              mode: meta.mode ?? result.mode,
              search_used: meta.search_used ?? result.search_used,
            };
          },
          onDelta: (delta) => {
            if (!delta) {
              return;
            }
            streamedAnyDelta = true;
            setIsTyping(false);
            setMessages((prev) =>
              prev.map((message) =>
                message.id === aiMessageId
                  ? { ...message, isTyping: false, content: `${message.content}${delta}` }
                  : message,
              ),
            );
          },
          onDone: (done) => {
            result = {
              reply: done.reply,
              mode: done.mode ?? result.mode,
              search_used: done.search_used ?? result.search_used,
              citations: done.citations,
              citation_summary: done.citation_summary,
            };
            finalReplyText = done.reply;
            setMessages((prev) =>
              prev.map((message) =>
                message.id === aiMessageId
                  ? {
                      ...message,
                      isTyping: false,
                      content: done.reply || message.content,
                      citations: normalizeCitations(done.citations),
                      citationSummary: normalizeCitationSummary(done.citation_summary),
                    }
                  : message,
              ),
            );
          },
        });
        if (!streamedAnyDelta && finalReplyText) {
          setIsTyping(false);
          const step = finalReplyText.length > 240 ? 6 : 3;
          for (let index = step; index <= finalReplyText.length; index += step) {
            const partial = finalReplyText.slice(0, index);
            setMessages((prev) =>
              prev.map((message) =>
                message.id === aiMessageId ? { ...message, isTyping: false, content: partial } : message,
              ),
            );
            await new Promise((resolve) => window.setTimeout(resolve, 16));
          }
        }
        setIsTyping(false);
      }
      setMessages((prev) => {
        const next = [...prev];
        if (result.search_used) {
          next.push({
            id: `${Date.now()}-search`,
            role: "system",
            content: "🔎 本次回答已联网检索",
            timestamp: new Date(),
          });
        }
        if (result.mode === "mock") {
          next.push({
            id: `${Date.now()}-mode`,
            role: "system",
            content: "当前为本地兜底回复，远端模型暂不可用",
            timestamp: new Date(),
          });
        }
        return next;
      });
      if (pendingImageUrl) {
        setPendingImageUrl(null);
      }
    } catch (error) {
      setIsTyping(false);
      const message =
        error instanceof ApiRequestError ? `消息发送失败：${error.message}` : "消息发送失败，请确认服务端已启动";
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-local-ai`,
          role: "ai",
          content: buildLocalReply(text),
          timestamp: new Date(),
        },
        {
          id: (Date.now() + 1).toString(),
          role: "system",
          content: `${message}，已切换本地体验模式`,
          timestamp: new Date(),
        },
      ]);
    }
  };

  const handleCreateNewConversation = useCallback(() => {
    if (!userId) {
      return;
    }
    const nextConversationId = createConversationId();
    window.localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, nextConversationId);
    ensureConversationInList(userId, nextConversationId);
    setConversationId(nextConversationId);
    setPendingImageUrl(null);
    setLatestFreshAiMessageId(null);
    setMessages([createWelcomeMessage()]);
    setIsConversationListOpen(false);
  }, [ensureConversationInList, userId]);

  const handleSelectConversation = useCallback(
    (targetConversationId: string) => {
      if (!userId || !targetConversationId) {
        return;
      }
      window.localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, targetConversationId);
      ensureConversationInList(userId, targetConversationId);
      setConversationId(targetConversationId);
      setPendingImageUrl(null);
      setLatestFreshAiMessageId(null);
      setMessages([createWelcomeMessage()]);
      setIsConversationListOpen(false);
    },
    [ensureConversationInList, userId],
  );

  const hasInlineTypingBubble = messages.some((message) => message.role === "ai" && message.isTyping);

  const syncLearningAssets = useCallback(async () => {
    if (!userId) {
      return;
    }
    setIsAssetsLoading(true);
    try {
      const [cardsResp, reviewsResp] = await Promise.all([fetchMemoryCards(userId, 60), fetchReviewRecords(userId, 40)]);
      setMemoryCards(cardsResp.cards);
      setReviewRecords(reviewsResp.records);
    } catch {
      setMemoryCards([]);
      setReviewRecords([]);
    } finally {
      setIsAssetsLoading(false);
    }
  }, [userId]);

  const handleTrackAnswerEvent = useCallback(
    (eventName: string, eventPayload: Record<string, unknown> = {}) => {
      if (!userId) {
        return;
      }
      reportAnalyticsEvent(userId, eventName, eventPayload).catch(() => undefined);
    },
    [userId],
  );

  const handleExportLearningCard = useCallback(
    async (message: Message) => {
      if (!userId || !message.content.trim()) {
        return;
      }
      if (learningCardExportStatus[message.id] === "done" || learningCardExportingRef.current.has(message.id)) {
        return;
      }
      const messageIndex = messages.findIndex((item) => item.id === message.id);
      let sourceQuestion = "";
      for (let index = messageIndex - 1; index >= 0; index -= 1) {
        if (messages[index]?.role === "user") {
          sourceQuestion = messages[index].content.slice(0, 300);
          break;
        }
      }
      learningCardExportingRef.current.add(message.id);
      setLearningCardExportStatus((prev) => ({ ...prev, [message.id]: "loading" }));
      try {
        const result = await exportAnswerToLearningCard(userId, sourceQuestion, message.content);
        const exportInfo = result.export;
        setLearningCardExportStatus((prev) => ({ ...prev, [message.id]: "done" }));
        syncLearningAssets().catch(() => undefined);
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-card-export`,
            role: "system",
            content: `已转学习卡片：主卡1张，术语新增${exportInfo.term_cards_added}，术语更新${exportInfo.term_cards_updated}，错题联动${exportInfo.review_records_created}`,
            timestamp: new Date(),
          },
        ]);
      } catch (error) {
        const exportError = error instanceof ApiRequestError ? error.message : "导出失败，请稍后重试";
        setLearningCardExportStatus((prev) => {
          const next = { ...prev };
          delete next[message.id];
          return next;
        });
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-card-export-error`,
            role: "system",
            content: `转学习卡片失败：${exportError}`,
            timestamp: new Date(),
          },
        ]);
      } finally {
        learningCardExportingRef.current.delete(message.id);
      }
    },
    [learningCardExportStatus, messages, syncLearningAssets, userId],
  );

  const handleResponseStyleChange = useCallback(
    async (nextStyle: (typeof RESPONSE_STYLE_OPTIONS)[number]) => {
      if (!userId) {
        return;
      }
      const previousStyle = responseStyle;
      setResponseStyle(nextStyle);
      try {
        await updateProfile(userId, { response_style: nextStyle });
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-style-updated`,
            role: "system",
            content: `回答风格已切换为${nextStyle}`,
            timestamp: new Date(),
          },
        ]);
      } catch (error) {
        setResponseStyle(previousStyle);
        const saveError = error instanceof ApiRequestError ? error.message : "保存失败";
        setMessages((prev) => [
          ...prev,
          {
            id: `${Date.now()}-style-update-error`,
            role: "system",
            content: `回答风格保存失败：${saveError}`,
            timestamp: new Date(),
          },
        ]);
      }
    },
    [responseStyle, userId],
  );

  const openLearningAssetsModal = useCallback(() => {
    setIsAssetsModalOpen(true);
    syncLearningAssets().catch(() => undefined);
  }, [syncLearningAssets]);

  const handleCopyCitation = async (quote: string) => {
    if (!quote.trim()) {
      return;
    }
    try {
      await navigator.clipboard.writeText(quote);
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-citation-copied`,
          role: "system",
          content: "引用来源已复制",
          timestamp: new Date(),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-citation-copy-failed`,
          role: "system",
          content: "复制失败，请稍后重试",
          timestamp: new Date(),
        },
      ]);
    }
  };

  const handlePickImage = async (file: File) => {
    if (!userId) {
      return;
    }
    setIsTyping(true);
    try {
      const { image_url } = await uploadImage(file, userId);
      setPendingImageUrl(image_url);
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-upload`,
          role: "system",
          content: "图片上传成功，直接发送问题即可开始识图讲解",
          timestamp: new Date(),
        },
      ]);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "图片上传失败，请稍后重试";
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-upload-error`,
          role: "system",
          content: `图片上传失败：${message}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleLearn = async (content: string) => {
    if (!userId) {
      return;
    }
    setIsTyping(true);
    try {
      const result = await ingestLearningContent(content, userId, conversationId || getOrCreateConversationId());
      setIsTyping(false);
      const systemMsg: Message = {
        id: Date.now().toString(),
        role: "system",
        content: `知识吸收完毕 💖`,
        timestamp: new Date(),
      };
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "ai",
        content: `${result.ack}`,
        timestamp: new Date(),
      };
      setMessages((prev) => {
        const next = [...prev, systemMsg, aiMsg];
        if (result.mode === "mock") {
          next.push({
            id: `${Date.now()}-ingest-mode`,
            role: "system",
            content: "知识总结使用了本地兜底逻辑，可继续使用",
            timestamp: new Date(),
          });
        }
        return next;
      });
    } catch (error) {
      setIsTyping(false);
      const message =
        error instanceof ApiRequestError ? `知识吸收失败：${error.message}` : "知识吸收失败，请检查服务端状态";
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-local-ingest`,
          role: "ai",
          content: "我先用本地模式帮你记住了这段内容，稍后服务恢复后会自动切回云端。",
          timestamp: new Date(),
        },
        {
          id: Date.now().toString(),
          role: "system",
          content: `${message}，已启用本地兜底`,
          timestamp: new Date(),
        },
      ]);
    }
  };

  const handleNudgeClick = () => {
    if (nudgeMessage) {
      const msg: Message = {
        id: Date.now().toString(),
        role: "ai",
        content: nudgeMessage,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, msg]);
      setNudgeMessage(null);
    }
  };

  const selectedCase = evaluationCases.find((item) => item.id === selectedCaseId) ?? null;

  const handleRunAbCompare = async () => {
    if (!userId || !selectedCaseId || !variantAAnswer.trim() || !variantBAnswer.trim()) {
      return;
    }
    setIsEvalLoading(true);
    try {
      const result = await compareEvaluationAnswers(
        selectedCaseId,
        variantAAnswer,
        variantBAnswer,
        variantALabel,
        variantBLabel,
        userId,
      );
      const scoreA = result.run_a.score_detail.total_score ?? result.run_a.total_score;
      const scoreB = result.run_b.score_detail.total_score ?? result.run_b.total_score;
      setEvalResult({
        winner: result.winner,
        delta: result.delta,
        scoreA,
        scoreB,
      });
      const trendResp = await fetchEvaluationTrends(userId, 200);
      setEvalTrends(trendResp.summary);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "A/B评测失败，请检查服务状态";
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-eval-error`,
          role: "system",
          content: `A/B评测失败：${message}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsEvalLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-full bg-[#FEF2F2] sm:p-6 md:p-10 overflow-hidden items-center justify-center font-sans">
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <motion.div
          animate={{ y: [0, -20, 0], rotate: [0, 5, 0] }}
          transition={{ duration: 6, repeat: Infinity }}
          className="absolute top-[10%] left-[20%] w-[400px] h-[400px] bg-[#FFE4E6] rounded-full mix-blend-multiply blur-3xl opacity-60"
        />
        <motion.div
          animate={{ y: [0, 20, 0], rotate: [0, -5, 0] }}
          transition={{ duration: 8, repeat: Infinity }}
          className="absolute bottom-[10%] right-[15%] w-[500px] h-[500px] bg-[#E0E7FF] rounded-full mix-blend-multiply blur-3xl opacity-60"
        />
      </div>
      <div className="relative w-full h-full sm:max-w-[400px] sm:max-h-[850px] bg-[#FAFAF9] sm:border-[12px] sm:border-white overflow-hidden flex flex-col sm:rounded-[56px] z-10 isolate shadow-[0_20px_50px_rgba(0,0,0,0.05),_0_0_0_1px_rgba(0,0,0,0.02)]">
        <div className="absolute top-0 w-full h-10 z-50 flex justify-center hidden sm:flex pt-3 pointer-events-none">
          <div className="w-[100px] h-[26px] bg-[#1E293B] rounded-full shadow-sm" />
        </div>
        <div className="absolute top-12 sm:top-14 left-4 z-40">
          <motion.div
            whileHover={{ scale: 1.05, y: -2 }}
            onClick={() => setIsConversationListOpen(true)}
            className="group relative bg-white/90 backdrop-blur-md px-4 py-2.5 rounded-[24px] shadow-[0_8px_20px_rgba(0,0,0,0.04)] hover:shadow-[0_12px_25px_rgba(244,114,182,0.15)] border-2 border-white flex items-center gap-3 cursor-pointer transition-all"
          >
            <div className="relative">
              <motion.div
                animate={{ rotate: [3, -3, 3] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                className="w-9 h-9 bg-gradient-to-tr from-[#A855F7] to-[#F472B6] rounded-[14px] flex items-center justify-center shadow-inner relative z-10"
              >
                <SmilePlus className="w-5 h-5 text-white" />
              </motion.div>
              <motion.div
                animate={{ scale: [1, 1.5, 1], opacity: [0, 1, 0] }}
                transition={{ duration: 1.5, repeat: Infinity, delay: 0.5 }}
                className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-[#FDE047] rounded-full z-20"
              />
              <motion.div
                animate={{ scale: [1, 1.5, 1], opacity: [0, 1, 0] }}
                transition={{ duration: 1.5, repeat: Infinity, delay: 1 }}
                className="absolute -bottom-0.5 -left-1 w-2 h-2 bg-[#38BDF8] rounded-full z-20"
              />
            </div>
            <motion.span
              animate={{ opacity: [0.65, 1, 0.65], scale: [1, 1.12, 1] }}
              transition={{ duration: 1.8, repeat: Infinity }}
              className={`absolute top-2.5 right-2.5 inline-block w-3 h-3 rounded-full ${dotClass} shadow-[0_0_0_4px_rgba(255,255,255,0.78)]`}
            />
            <div className="flex flex-col">
              <span className="text-[16px] font-black text-[#334155] tracking-tight leading-none group-hover:text-[#F472B6] transition-colors">
                你一定要上岸！
              </span>
            </div>
            <motion.div
              whileHover={{ rotate: 6 }}
              className="w-8 h-8 rounded-[12px] bg-[#ECFEFF] border-2 border-white text-[#0EA5E9] flex items-center justify-center shadow-sm"
            >
              <Rows2 className="w-4.5 h-4.5 stroke-[2.5]" />
            </motion.div>
          </motion.div>
        </div>
        <div className="absolute top-12 sm:top-14 right-4 z-40 flex flex-col gap-3">
          <motion.button
            whileHover={{ scale: 1.1, rotate: 10 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setIsStylePreferenceOpen(true)}
            title="回答风格"
            className="w-11 h-11 bg-white/90 backdrop-blur-md rounded-[16px] shadow-[0_8px_20px_rgba(0,0,0,0.04)] border-[2px] border-white flex items-center justify-center text-[#FBBF24] hover:bg-[#FEF9C3] transition-colors"
          >
            <Sparkles className="w-5 h-5 fill-[#FDE047]" />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.1, rotate: -8 }}
            whileTap={{ scale: 0.9 }}
            onClick={openLearningAssetsModal}
            title="学习资产库"
            className="w-11 h-11 bg-white/90 backdrop-blur-md rounded-[16px] shadow-[0_8px_20px_rgba(0,0,0,0.04)] border-[2px] border-white flex items-center justify-center text-[#8B5CF6] hover:bg-[#F3E8FF] transition-colors"
          >
            <BookCopy className="w-5 h-5 stroke-[2.5]" />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.1, rotate: -5 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setIsDashboardOpen(true)}
            title="周目标看板"
            className="w-11 h-11 bg-white/90 backdrop-blur-md rounded-[16px] shadow-[0_8px_20px_rgba(0,0,0,0.04)] border-[2px] border-white flex items-center justify-center text-[#FF9A9E] hover:bg-[#FFE4E6] transition-colors"
          >
            <Target className="w-5 h-5 stroke-[2.5]" />
          </motion.button>
          {SHOW_EVAL_ENTRY && (
            <motion.button
              whileHover={{ scale: 1.1, rotate: 5 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => setIsEvalOpen(true)}
              title="A/B 评测台"
              className="w-11 h-11 bg-white/90 backdrop-blur-md rounded-[16px] shadow-[0_8px_20px_rgba(0,0,0,0.04)] border-[2px] border-white flex items-center justify-center text-[#38BDF8] hover:bg-[#E0F2FE] transition-colors"
            >
              <Beaker className="w-5 h-5 stroke-[2.5]" />
            </motion.button>
          )}
        </div>
        <NudgeNotification
          isOpen={!!nudgeMessage}
          message={nudgeMessage || ""}
          onClose={() => setNudgeMessage(null)}
          onClick={handleNudgeClick}
        />
        <div className="flex-1 overflow-y-auto overflow-x-hidden px-4 pt-[140px] pb-4 scroll-smooth flex flex-col z-10 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onCopyCitation={handleCopyCitation}
              onTrackEvent={handleTrackAnswerEvent}
              onExportLearningCard={handleExportLearningCard}
              preferExpandedLongText={msg.role === "ai" && msg.id === latestFreshAiMessageId}
              isLearningCardExported={learningCardExportStatus[msg.id] === "done"}
              isLearningCardExporting={learningCardExportStatus[msg.id] === "loading"}
            />
          ))}
          {(isBootstrapping || (isTyping && !hasInlineTypingBubble)) && (
            <MessageBubble
              message={{
                id: "typing",
                role: "ai",
                content: "",
                timestamp: new Date(),
                isTyping: true,
              }}
            />
          )}
          <div ref={messagesEndRef} className="h-4 shrink-0" />
        </div>
        <InputArea
          onSendMessage={handleSendMessage}
          onOpenOptions={() => setIsPasteModalOpen(true)}
          isInputDisabled={isTyping || !userId}
        />
        <PasteModal
          isOpen={isPasteModalOpen}
          onClose={() => setIsPasteModalOpen(false)}
          onLearn={handleLearn}
          onPickImage={handlePickImage}
        />
        <DashboardModal
          isOpen={isDashboardOpen}
          onClose={() => setIsDashboardOpen(false)}
          weeklyReport={weeklyReport}
          isWeeklyLoading={isWeeklyLoading}
          nudgeStrategy={nudgeStrategy}
          isNudgeStrategyLoading={isNudgeStrategyLoading}
        />
        <EvalModal
          isOpen={isEvalOpen}
          onClose={() => {
            setIsEvalOpen(false);
            setEvalResult(null);
          }}
          cases={evaluationCases}
          selectedCaseId={selectedCaseId}
          onSelectCase={setSelectedCaseId}
          variantALabel={variantALabel}
          onVariantALabelChange={setVariantALabel}
          variantBLabel={variantBLabel}
          onVariantBLabelChange={setVariantBLabel}
          variantAAnswer={variantAAnswer}
          onVariantAAnswerChange={setVariantAAnswer}
          variantBAnswer={variantBAnswer}
          onVariantBAnswerChange={setVariantBAnswer}
          isComparing={isEvalLoading}
          onCompare={handleRunAbCompare}
          result={evalResult}
          trendSummary={evalTrends}
          selectedCaseQuestion={selectedCase?.question || ""}
        />
        <StylePreferenceModal
          isOpen={isStylePreferenceOpen}
          onClose={() => setIsStylePreferenceOpen(false)}
          currentStyle={responseStyle}
          onSelectStyle={(style) => {
            if (style !== responseStyle) {
              handleResponseStyleChange(style).catch(() => undefined);
            }
            setIsStylePreferenceOpen(false);
          }}
        />
        <LearningAssetsModal
          isOpen={isAssetsModalOpen}
          onClose={() => setIsAssetsModalOpen(false)}
          cards={memoryCards}
          reviews={reviewRecords}
          isLoading={isAssetsLoading}
        />
        <ConversationListModal
          isOpen={isConversationListOpen}
          onClose={() => setIsConversationListOpen(false)}
          sessions={conversationList}
          activeSessionId={conversationId}
          onSelectSession={handleSelectConversation}
          onCreateSession={handleCreateNewConversation}
        />
      </div>
    </div>
  );
}
