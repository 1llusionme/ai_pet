import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { Sparkle, Heart, ChevronDown, ChevronUp, Copy, ExternalLink } from "lucide-react";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type MessageRole = "user" | "ai" | "system";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  isTyping?: boolean;
  citations?: CitationItem[];
  citationSummary?: CitationSummary;
}

export interface CitationItem {
  sourceType: "kb" | "semantic" | "web";
  sourceLabel: string;
  title: string;
  page?: string;
  url?: string;
  quote: string;
  semanticSourceLabel?: string;
}

export interface CitationSummary {
  total: number;
  hasKb: boolean;
  hasSemantic: boolean;
  hasWeb: boolean;
  hasConflict: boolean;
}

interface MessageBubbleProps {
  message: Message;
  onCopyCitation?: (quote: string) => void;
  onTrackEvent?: (eventName: string, eventPayload?: Record<string, unknown>) => void;
  onExportLearningCard?: (message: Message) => void;
  preferExpandedLongText?: boolean;
  isLearningCardExported?: boolean;
  isLearningCardExporting?: boolean;
}

type RichTextBlock =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "unordered-list"; items: string[] }
  | { type: "ordered-list"; items: string[] }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "quote"; text: string };

function estimateVisualLines(content: string): number {
  const lines = content.split("\n");
  return lines.reduce((total, line) => total + Math.max(1, Math.ceil(line.length / 28)), 0);
}

function parseRichTextBlocks(content: string): RichTextBlock[] {
  const lines = content.replace(/\r/g, "").split("\n");
  const blocks: RichTextBlock[] = [];
  let currentParagraph: string[] = [];
  let currentQuote: string[] = [];
  let currentUnordered: string[] = [];
  let currentOrdered: string[] = [];

  const flushParagraph = () => {
    if (!currentParagraph.length) {
      return;
    }
    blocks.push({ type: "paragraph", text: currentParagraph.join(" ").trim() });
    currentParagraph = [];
  };
  const flushQuote = () => {
    if (!currentQuote.length) {
      return;
    }
    blocks.push({ type: "quote", text: currentQuote.join(" ").trim() });
    currentQuote = [];
  };
  const flushUnordered = () => {
    if (!currentUnordered.length) {
      return;
    }
    blocks.push({ type: "unordered-list", items: currentUnordered });
    currentUnordered = [];
  };
  const flushOrdered = () => {
    if (!currentOrdered.length) {
      return;
    }
    blocks.push({ type: "ordered-list", items: currentOrdered });
    currentOrdered = [];
  };
  const flushAll = () => {
    flushParagraph();
    flushQuote();
    flushUnordered();
    flushOrdered();
  };

  const labeledMatchPattern = /^(结论|为什么|怎么做|依据|行动建议|下一步)[:：]\s*(.+)?$/;
  const markdownHeadingPattern = /^#{1,3}\s+(.+)$/;
  const unorderedPattern = /^[-*]\s+(.+)$/;
  const orderedPattern = /^\d+\.\s+(.+)$/;
  const quotePattern = /^>\s?(.+)$/;
  const parseTableCells = (line: string) =>
    line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());
  const isPotentialTableRow = (line: string) => line.includes("|") && parseTableCells(line).length >= 2;
  const isTableSeparatorRow = (line: string) => {
    if (!isPotentialTableRow(line)) {
      return false;
    }
    const cells = parseTableCells(line);
    return cells.every((cell) => /^:?-{3,}:?$/.test(cell));
  };

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const rawLine = lines[lineIndex];
    const line = rawLine.trim();
    if (!line) {
      flushAll();
      continue;
    }
    if (
      lineIndex + 1 < lines.length &&
      isPotentialTableRow(line) &&
      isTableSeparatorRow(lines[lineIndex + 1].trim())
    ) {
      flushAll();
      const headers = parseTableCells(line);
      const rows: string[][] = [];
      lineIndex += 2;
      while (lineIndex < lines.length) {
        const rowLine = lines[lineIndex].trim();
        if (!rowLine || !isPotentialTableRow(rowLine)) {
          lineIndex -= 1;
          break;
        }
        rows.push(parseTableCells(rowLine));
        lineIndex += 1;
      }
      if (rows.length > 0) {
        blocks.push({ type: "table", headers, rows });
        continue;
      }
    }
    const markdownHeadingMatch = line.match(markdownHeadingPattern);
    if (markdownHeadingMatch) {
      flushAll();
      blocks.push({ type: "heading", text: markdownHeadingMatch[1].trim() });
      continue;
    }
    const labeledMatch = line.match(labeledMatchPattern);
    if (labeledMatch) {
      flushAll();
      blocks.push({ type: "heading", text: labeledMatch[1] });
      if (labeledMatch[2]) {
        blocks.push({ type: "paragraph", text: labeledMatch[2].trim() });
      }
      continue;
    }
    const unorderedMatch = line.match(unorderedPattern);
    if (unorderedMatch) {
      flushParagraph();
      flushQuote();
      flushOrdered();
      currentUnordered.push(unorderedMatch[1].trim());
      continue;
    }
    const orderedMatch = line.match(orderedPattern);
    if (orderedMatch) {
      flushParagraph();
      flushQuote();
      flushUnordered();
      currentOrdered.push(orderedMatch[1].trim());
      continue;
    }
    const quoteMatch = line.match(quotePattern);
    if (quoteMatch) {
      flushParagraph();
      flushUnordered();
      flushOrdered();
      currentQuote.push(quoteMatch[1].trim());
      continue;
    }
    flushQuote();
    flushUnordered();
    flushOrdered();
    currentParagraph.push(line);
  }
  flushAll();
  return blocks;
}

function renderInlineText(text: string, keyPrefix: string): ReactNode[] {
  const tokenPattern = /(\*\*[^*]+\*\*|==[^=\n]+==)/g;
  const tokens = text.split(tokenPattern).filter(Boolean);
  return tokens.map((token, index) => {
    if (token.startsWith("**") && token.endsWith("**") && token.length > 4) {
      return (
        <strong key={`${keyPrefix}-strong-${index}`} className="font-black text-[#374151]">
          {token.slice(2, -2)}
        </strong>
      );
    }
    if (token.startsWith("==") && token.endsWith("==") && token.length > 4) {
      return (
        <mark key={`${keyPrefix}-mark-${index}`} className="rounded-[6px] bg-[#FEF3C7] px-1 py-0.5 text-[#92400E]">
          {token.slice(2, -2)}
        </mark>
      );
    }
    return <span key={`${keyPrefix}-text-${index}`}>{token}</span>;
  });
}

function renderRichTextContent(content: string, options?: { showTableScrollNudge?: boolean }): ReactNode {
  try {
    const blocks = parseRichTextBlocks(content);
    return (
      <div className="space-y-2.5">
        {blocks.map((block, index) => {
          if (block.type === "heading") {
            return (
              <h4 key={`heading-${index}`} className="text-[13px] font-black tracking-wide text-[#7E22CE]">
                {block.text}
              </h4>
            );
          }
          if (block.type === "paragraph") {
            return (
              <p key={`paragraph-${index}`} className="text-[15px] leading-[1.68] text-[#4A4A68]">
                {renderInlineText(block.text, `paragraph-${index}`)}
              </p>
            );
          }
          if (block.type === "unordered-list") {
            return (
              <ul key={`unordered-${index}`} className="list-disc space-y-1.5 pl-5 text-[15px] leading-[1.68] text-[#4A4A68]">
                {block.items.map((item, itemIndex) => (
                  <li key={`unordered-item-${index}-${itemIndex}`}>{renderInlineText(item, `unordered-${index}-${itemIndex}`)}</li>
                ))}
              </ul>
            );
          }
          if (block.type === "ordered-list") {
            return (
              <ol key={`ordered-${index}`} className="list-decimal space-y-1.5 pl-5 text-[15px] leading-[1.68] text-[#4A4A68]">
                {block.items.map((item, itemIndex) => (
                  <li key={`ordered-item-${index}-${itemIndex}`}>{renderInlineText(item, `ordered-${index}-${itemIndex}`)}</li>
                ))}
              </ol>
            );
          }
          if (block.type === "table") {
            const shouldShowHorizontalHint = block.headers.length >= 4;
            return (
              <div key={`table-${index}`} className="w-full min-w-0 space-y-1.5">
                <div className="w-full max-w-full overflow-x-auto rounded-[16px] border-[2px] border-white/80 bg-[#F8FAFF] shadow-[0_6px_14px_rgba(99,102,241,0.12)]">
                  <table className="w-max min-w-[460px] border-collapse text-left">
                    <thead>
                      <tr className="bg-[#EEF2FF]">
                        {block.headers.map((header, headerIndex) => (
                          <th
                            key={`table-header-${index}-${headerIndex}`}
                            className="border-b border-[#C7D2FE] px-3 py-2 text-[12px] font-black tracking-wide text-[#4338CA]"
                          >
                            {renderInlineText(header, `table-header-${index}-${headerIndex}`)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {block.rows.map((row, rowIndex) => (
                        <tr key={`table-row-${index}-${rowIndex}`} className={rowIndex % 2 === 0 ? "bg-white/80" : "bg-[#F8FAFF]"}>
                          {row.map((cell, cellIndex) => (
                            <td
                              key={`table-cell-${index}-${rowIndex}-${cellIndex}`}
                              className="max-w-[220px] border-b border-[#E5E7EB] px-3 py-2 align-top text-[14px] leading-[1.6] text-[#4A4A68]"
                            >
                              {renderInlineText(cell, `table-cell-${index}-${rowIndex}-${cellIndex}`)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {shouldShowHorizontalHint && (
                  <div className="inline-flex items-center gap-1.5 rounded-full bg-[#EEF2FF] px-2.5 py-1 text-[11px] font-bold text-[#4F46E5] md:hidden">
                    {options?.showTableScrollNudge && (
                      <motion.span
                        initial={{ opacity: 0.3, x: -3 }}
                        animate={{ opacity: [0.5, 1, 0.5], x: [-3, 3, -3] }}
                        transition={{ duration: 0.6, repeat: 3, ease: "easeInOut" }}
                      >
                        ↔
                      </motion.span>
                    )}
                    表格较宽，可左右滑动查看
                  </div>
                )}
              </div>
            );
          }
          return (
            <blockquote
              key={`quote-${index}`}
              className="rounded-[14px] border-l-[3px] border-[#A855F7] bg-[#F3E8FF]/70 px-3 py-2 text-[14px] leading-[1.65] text-[#5B4B74]"
            >
              {renderInlineText(block.text, `quote-${index}`)}
            </blockquote>
          );
        })}
      </div>
    );
  } catch {
    return <div className="whitespace-pre-wrap">{content}</div>;
  }
}

export function MessageBubble({
  message,
  onCopyCitation,
  onTrackEvent,
  onExportLearningCard,
  preferExpandedLongText = false,
  isLearningCardExported = false,
  isLearningCardExporting = false,
}: MessageBubbleProps) {
  if (message.role === "system") {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.8, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="w-full flex justify-center my-6"
      >
        <div className="flex items-center gap-1.5 px-4 py-2 bg-white/60 backdrop-blur-md rounded-full shadow-[0_4px_12px_rgba(255,107,158,0.15)] border-2 border-white">
          <Sparkle className="w-4 h-4 text-[#FF6B9E]" />
          <span className="text-[13px] font-bold text-[#FF6B9E] tracking-wider uppercase">
            {message.content}
          </span>
        </div>
      </motion.div>
    );
  }

  const isUser = message.role === "user";
  const [isCitationExpanded, setIsCitationExpanded] = useState(false);
  const [isAllCitationsVisible, setIsAllCitationsVisible] = useState(false);
  const [isLongTextExpanded, setIsLongTextExpanded] = useState(preferExpandedLongText);
  const [showTableScrollNudge, setShowTableScrollNudge] = useState(false);
  const citations = message.citations ?? [];
  const hasCitations = !message.isTyping && !isUser && citations.length > 0;
  const visibleCitations = isAllCitationsVisible ? citations : citations.slice(0, 1);
  const visualLines = useMemo(() => estimateVisualLines(message.content), [message.content]);
  const shouldCollapseLongText = !message.isTyping && !isUser && visualLines > 10 && !preferExpandedLongText;
  const richTextBlocks = useMemo(() => {
    try {
      return parseRichTextBlocks(message.content);
    } catch {
      return [];
    }
  }, [message.content]);
  const richTextBlockCount = richTextBlocks.length;
  const hasWideTable = useMemo(
    () => richTextBlocks.some((block) => block.type === "table" && block.headers.length >= 4),
    [richTextBlocks],
  );
  const renderTrackedRef = useRef(false);

  useEffect(() => {
    if (!preferExpandedLongText) {
      setIsLongTextExpanded(false);
      return;
    }
    setIsLongTextExpanded(true);
  }, [preferExpandedLongText]);

  useEffect(() => {
    if (isUser || message.isTyping || !hasWideTable) {
      setShowTableScrollNudge(false);
      return;
    }
    setShowTableScrollNudge(true);
    const timer = window.setTimeout(() => {
      setShowTableScrollNudge(false);
    }, 2200);
    return () => window.clearTimeout(timer);
  }, [hasWideTable, isUser, message.id, message.isTyping]);

  useEffect(() => {
    if (renderTrackedRef.current) {
      return;
    }
    if (isUser || message.isTyping) {
      return;
    }
    renderTrackedRef.current = true;
    onTrackEvent?.("answer_richtext_rendered", {
      message_id: message.id,
      visual_lines: visualLines,
      rich_block_count: richTextBlockCount,
      collapsed_by_default: shouldCollapseLongText,
      citation_count: citations.length,
    });
  }, [
    citations.length,
    isUser,
    message.id,
    message.isTyping,
    onTrackEvent,
    richTextBlockCount,
    shouldCollapseLongText,
    visualLines,
  ]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 30, rotate: isUser ? 2 : -2 }}
      animate={{ opacity: 1, y: 0, rotate: 0 }}
      transition={{ type: "spring", damping: 20, stiffness: 400 }}
      className={cn(
        "flex w-full mb-6",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div className={cn(
        "relative max-w-[80%] min-w-0 flex flex-col group",
        isUser ? "items-end" : "items-start"
      )}>
        {/* Avatar badge floating on top corner */}
        {!isUser && (
          <div className="absolute -top-4 -left-3 z-10 w-9 h-9 bg-[#A855F7] rounded-[12px] rotate-[-6deg] flex items-center justify-center border-[3px] border-white shadow-md">
            <span className="text-white font-black text-[16px]">M</span>
          </div>
        )}
        {isUser && (
          <div className="absolute -top-4 -right-3 z-10 w-9 h-9 bg-[#FF6B9E] rounded-[12px] rotate-[6deg] flex items-center justify-center border-[3px] border-white shadow-md">
            <Heart className="w-5 h-5 text-white fill-white" />
          </div>
        )}

        {/* Bubble container */}
        <div
          className={cn(
            "max-w-full min-w-0 px-5 py-4 text-[16px] font-medium leading-[1.5] border-[3px] border-white relative",
            isUser
              ? "bg-gradient-to-br from-[#FF9A9E] to-[#FF6B9E] text-white rounded-[28px] rounded-tr-[10px] shadow-[4px_6px_0px_rgba(255,107,158,0.3)] mt-2 mr-2"
              : "bg-white text-[#4A4A68] rounded-[28px] rounded-tl-[10px] shadow-[4px_6px_0px_rgba(168,85,247,0.2)] mt-2 ml-2"
          )}
        >
          <AnimatePresence mode="wait">
            {message.isTyping ? (
              <motion.div
                key="typing"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="flex items-center space-x-1.5 h-6 px-2"
              >
                <motion.div
                  animate={{ y: [0, -8, 0], scale: [1, 1.2, 1] }}
                  transition={{ repeat: Infinity, duration: 0.8, delay: 0 }}
                  className="w-3 h-3 bg-[#A855F7] rounded-full"
                />
                <motion.div
                  animate={{ y: [0, -8, 0], scale: [1, 1.2, 1] }}
                  transition={{ repeat: Infinity, duration: 0.8, delay: 0.15 }}
                  className="w-3 h-3 bg-[#38BDF8] rounded-full"
                />
                <motion.div
                  animate={{ y: [0, -8, 0], scale: [1, 1.2, 1] }}
                  transition={{ repeat: Infinity, duration: 0.8, delay: 0.3 }}
                  className="w-3 h-3 bg-[#FF6B9E] rounded-full"
                />
              </motion.div>
            ) : (
              <motion.div
                key="content"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.18 }}
                className="space-y-2"
              >
                {isUser ? (
                  <div className="whitespace-pre-wrap">{message.content}</div>
                ) : (
                  <>
                    <div
                      className={cn(
                        "relative",
                        shouldCollapseLongText && !isLongTextExpanded ? "max-h-[248px] overflow-hidden" : "",
                      )}
                    >
                      {renderRichTextContent(message.content, { showTableScrollNudge })}
                      {shouldCollapseLongText && !isLongTextExpanded && (
                        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-white to-transparent" />
                      )}
                    </div>
                    {shouldCollapseLongText && (
                      <button
                        type="button"
                        onClick={() => {
                          const nextExpanded = !isLongTextExpanded;
                          setIsLongTextExpanded(nextExpanded);
                          onTrackEvent?.("answer_expand_clicked", {
                            message_id: message.id,
                            visual_lines: visualLines,
                            expanded: nextExpanded,
                          });
                        }}
                        className="text-[12px] font-bold text-[#6366F1]"
                      >
                        {isLongTextExpanded ? "收起全文" : "展开全文"}
                      </button>
                    )}
                  </>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        {!isUser && !message.isTyping && (
          <button
            type="button"
            disabled={isLearningCardExported || isLearningCardExporting}
            onClick={() => {
              if (isLearningCardExported || isLearningCardExporting) {
                return;
              }
              onExportLearningCard?.(message);
              onTrackEvent?.("answer_export_learning_card_clicked", {
                message_id: message.id,
                content_length: message.content.length,
              });
            }}
            className={cn(
              "mt-2 ml-2 inline-flex items-center gap-1.5 px-3 py-2 rounded-full border-2 border-white text-[12px] font-bold",
              isLearningCardExported
                ? "bg-[#E0E7FF] text-[#4338CA] shadow-[0_4px_10px_rgba(99,102,241,0.2)] cursor-not-allowed"
                : isLearningCardExporting
                  ? "bg-[#F3E8FF] text-[#7E22CE] shadow-[0_4px_10px_rgba(168,85,247,0.2)] cursor-not-allowed"
                  : "bg-[#ECFDF5] text-[#047857] shadow-[0_4px_10px_rgba(16,185,129,0.18)]",
            )}
          >
            <Sparkle className="w-3.5 h-3.5" />
            {isLearningCardExported ? "已整理成学习卡片" : isLearningCardExporting ? "整理中..." : "转学习卡片"}
          </button>
        )}
        {hasCitations && (
          <div className="mt-2 ml-2 w-full max-w-[320px]">
            <button
              type="button"
              onClick={() => {
                const nextExpanded = !isCitationExpanded;
                setIsCitationExpanded(nextExpanded);
                onTrackEvent?.("answer_citation_toggled", {
                  message_id: message.id,
                  expanded: nextExpanded,
                  citation_total: citations.length,
                });
              }}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-[#EEF2FF] text-[#6366F1] border-2 border-white shadow-[0_4px_10px_rgba(99,102,241,0.18)] text-[12px] font-bold"
            >
              <span>引用来源（{message.citationSummary?.total ?? citations.length}）</span>
              {isCitationExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            <AnimatePresence initial={false}>
              {isCitationExpanded && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 4 }}
                  transition={{ duration: 0.18 }}
                  className="mt-2 space-y-2"
                >
                  {message.citationSummary?.hasConflict && (
                    <div className="px-3 py-2 rounded-[14px] bg-[#FFF7ED] border-2 border-white text-[12px] font-bold text-[#C2410C] shadow-sm">
                      检测到多来源口径，请优先按你的教材口径核对
                    </div>
                  )}
                  {visibleCitations.map((citation, index) => (
                    <div
                      key={`${message.id}-citation-${index}`}
                      className="p-3 rounded-[16px] bg-white border-2 border-white shadow-[0_4px_10px_rgba(168,85,247,0.12)]"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-black text-[#7E22CE] bg-[#F3E8FF] px-2 py-0.5 rounded-full">
                          {citation.sourceLabel}
                        </span>
                        <span className="text-[11px] font-bold text-[#6B7280]">
                          {citation.sourceType === "kb" && citation.page ? `第${citation.page}页` : citation.semanticSourceLabel || ""}
                        </span>
                      </div>
                      <div className="mt-1.5 text-[12px] font-bold text-[#4B5563]">{citation.title}</div>
                      <div className="mt-1.5 text-[13px] leading-[1.5] text-[#374151] line-clamp-2">{citation.quote}</div>
                      <div className="mt-2 flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            onCopyCitation?.(citation.quote);
                            onTrackEvent?.("answer_citation_copied", {
                              message_id: message.id,
                              source_type: citation.sourceType,
                              quote_length: citation.quote.length,
                            });
                          }}
                          className="inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 bg-[#ECFEFF] text-[#0E7490] text-[11px] font-bold"
                        >
                          <Copy className="w-3.5 h-3.5" />
                          复制来源句
                        </button>
                        {citation.sourceType === "web" && citation.url && (
                          <a
                            href={citation.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 bg-[#EEF2FF] text-[#4F46E5] text-[11px] font-bold"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            查看原文
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                  {citations.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setIsAllCitationsVisible((prev) => !prev)}
                      className="text-[12px] font-bold text-[#6366F1] px-2"
                    >
                      {isAllCitationsVisible ? "收起更多" : `展开更多（+${citations.length - 1}）`}
                    </button>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </motion.div>
  );
}
