import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { X, Library, BookCopy, NotebookPen, ChevronRight, ArrowLeft } from "lucide-react";
import type { MemoryCard, ReviewRecord } from "../../services/api";

interface LearningAssetsModalProps {
  isOpen: boolean;
  onClose: () => void;
  cards: MemoryCard[];
  reviews: ReviewRecord[];
  isLoading: boolean;
}

type AssetFilter = "all" | "cards" | "reviews";
type RichTextBlock =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "unordered-list"; items: string[] }
  | { type: "ordered-list"; items: string[] }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "quote"; text: string };

type LearningCardType = "definition" | "comparison" | "steps" | "mistake" | "mnemonic";

function resolveCardType(card: MemoryCard): LearningCardType {
  if (card.card_type) {
    return card.card_type;
  }
  if (card.tags.includes("卡片类型:辨析卡")) {
    return "comparison";
  }
  if (card.tags.includes("卡片类型:步骤卡")) {
    return "steps";
  }
  if (card.tags.includes("卡片类型:错因卡")) {
    return "mistake";
  }
  if (card.tags.includes("卡片类型:速记卡")) {
    return "mnemonic";
  }
  return "definition";
}

function cardTypeStyle(cardType: LearningCardType) {
  if (cardType === "comparison") {
    return { label: "辨析卡", badge: "bg-[#DBEAFE] text-[#1D4ED8]" };
  }
  if (cardType === "steps") {
    return { label: "步骤卡", badge: "bg-[#DCFCE7] text-[#166534]" };
  }
  if (cardType === "mistake") {
    return { label: "错因卡", badge: "bg-[#FEE2E2] text-[#B91C1C]" };
  }
  if (cardType === "mnemonic") {
    return { label: "速记卡", badge: "bg-[#FEF3C7] text-[#B45309]" };
  }
  return { label: "定义卡", badge: "bg-[#E0F2FE] text-[#0369A1]" };
}

function formatTime(raw: string) {
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return "刚刚";
  }
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, "0")}:${date
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
}

function trimPoint(text: string, limit = 28) {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= limit) {
    return cleaned;
  }
  return `${cleaned.slice(0, limit)}...`;
}

function visibleCardTags(tags: string[]): string[] {
  return tags.filter((tag) => !["重点术语", "自动收集", "学习卡片"].includes(tag) && !tag.startsWith("卡片类型:"));
}

function buildSelfTestPrompt(card: MemoryCard): { question: string; hints: string[] } {
  const title = String(card.title || "").replace(/^(定义卡|辨析卡|步骤卡|错因卡|速记卡|学习卡片)[:：]/, "").trim();
  const lines = String(card.content || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  let question = "";
  const hints: string[] = [];
  for (const line of lines) {
    if (!question && line.startsWith("自测题：")) {
      question = line.replace("自测题：", "").trim();
      continue;
    }
    if (!question && line.startsWith("来源问题：")) {
      question = line.replace("来源问题：", "").trim();
      continue;
    }
    if (line.startsWith("答题动作：")) {
      hints.push(line.replace("答题动作：", "").trim());
      continue;
    }
    if (line.startsWith("记忆清单：")) {
      hints.push(`可先回忆清单：${line.replace("记忆清单：", "").trim()}`);
      continue;
    }
    if (line.startsWith("怎么做：")) {
      hints.push(line.replace("怎么做：", "").trim());
      continue;
    }
  }
  if (!question) {
    question = title ? `请用自己的话回答：${title}是什么？` : "请先口述这张卡片的核心结论。";
  }
  return { question, hints: Array.from(new Set(hints.filter(Boolean))).slice(0, 2) };
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

function renderRichTextContent(content: string): ReactNode {
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
              <p key={`paragraph-${index}`} className="text-[14px] leading-[1.68] text-[#4A4A68]">
                {renderInlineText(block.text, `paragraph-${index}`)}
              </p>
            );
          }
          if (block.type === "unordered-list") {
            return (
              <ul key={`unordered-${index}`} className="list-disc space-y-1.5 pl-5 text-[14px] leading-[1.68] text-[#4A4A68]">
                {block.items.map((item, itemIndex) => (
                  <li key={`unordered-item-${index}-${itemIndex}`}>{renderInlineText(item, `unordered-${index}-${itemIndex}`)}</li>
                ))}
              </ul>
            );
          }
          if (block.type === "ordered-list") {
            return (
              <ol key={`ordered-${index}`} className="list-decimal space-y-1.5 pl-5 text-[14px] leading-[1.68] text-[#4A4A68]">
                {block.items.map((item, itemIndex) => (
                  <li key={`ordered-item-${index}-${itemIndex}`}>{renderInlineText(item, `ordered-${index}-${itemIndex}`)}</li>
                ))}
              </ol>
            );
          }
          if (block.type === "table") {
            return (
              <div key={`table-${index}`} className="w-full min-w-0 overflow-x-auto rounded-[14px] border-[2px] border-white/80 bg-[#F8FAFF]">
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
                            className="max-w-[200px] border-b border-[#E5E7EB] px-3 py-2 align-top text-[13px] leading-[1.6] text-[#4A4A68]"
                          >
                            {renderInlineText(cell, `table-cell-${index}-${rowIndex}-${cellIndex}`)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }
          return (
            <blockquote
              key={`quote-${index}`}
              className="rounded-[12px] border-l-[3px] border-[#A855F7] bg-[#F3E8FF]/70 px-3 py-2 text-[13px] leading-[1.65] text-[#5B4B74]"
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

function extractCardHighlights(content: string): string[] {
  try {
    const blocks = parseRichTextBlocks(content);
    const points: string[] = [];
    for (const block of blocks) {
      if (points.length >= 3) {
        break;
      }
      if (block.type === "heading") {
        points.push(trimPoint(block.text));
        continue;
      }
      if (block.type === "unordered-list" || block.type === "ordered-list") {
        for (const item of block.items) {
          if (points.length >= 3) {
            break;
          }
          points.push(trimPoint(item));
        }
        continue;
      }
      if (block.type === "paragraph") {
        const sentence = block.text.split(/[。！？]/).map((item) => item.trim()).find(Boolean);
        if (sentence) {
          points.push(trimPoint(sentence));
        }
        continue;
      }
      if (block.type === "quote") {
        points.push(trimPoint(block.text));
        continue;
      }
      const rowText = block.rows.flat().find((item) => item.trim().length > 0);
      if (rowText) {
        points.push(trimPoint(rowText));
      }
    }
    const unique = Array.from(new Set(points.filter(Boolean)));
    if (unique.length > 0) {
      return unique.slice(0, 3);
    }
  } catch {
    return [];
  }
  const fallback = content
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3)
    .map((item) => trimPoint(item));
  return fallback.length > 0 ? fallback : ["这张卡片已生成，请点击查看全文"];
}

export function LearningAssetsModal({ isOpen, onClose, cards, reviews, isLoading }: LearningAssetsModalProps) {
  const [filter, setFilter] = useState<AssetFilter>("all");
  const [selectedCard, setSelectedCard] = useState<MemoryCard | null>(null);
  const [selfTestEnabled, setSelfTestEnabled] = useState(false);
  const [selfTestRevealed, setSelfTestRevealed] = useState(false);
  const filteredCards = filter === "reviews" ? [] : cards;
  const filteredReviews = filter === "cards" ? [] : reviews;
  const isEmpty = !isLoading && filteredCards.length === 0 && filteredReviews.length === 0;
  const selectedCardStyle = selectedCard ? cardTypeStyle(resolveCardType(selectedCard)) : null;
  const cardHighlights = useMemo(
    () =>
      cards.reduce<Record<string, string[]>>((acc, card) => {
        acc[card.id] = extractCardHighlights(card.content);
        return acc;
      }, {}),
    [cards],
  );
  const selfTestPrompt = useMemo(() => (selectedCard ? buildSelfTestPrompt(selectedCard) : null), [selectedCard]);

  useEffect(() => {
    setSelfTestEnabled(false);
    setSelfTestRevealed(false);
  }, [selectedCard?.id]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.24 }}
          className="absolute inset-0 z-50 flex items-center justify-center bg-white/40 backdrop-blur-md rounded-[inherit] p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.86, y: 34, rotate: -2 }}
            animate={{ scale: 1, y: 0, rotate: 0 }}
            exit={{ scale: 0.86, y: 34, rotate: 2 }}
            transition={{ type: "spring", damping: 22, stiffness: 360 }}
            onClick={(event) => event.stopPropagation()}
            className="w-full max-w-[360px] bg-[#FAFAF9] border-[4px] border-white shadow-[0_20px_60px_rgba(0,0,0,0.1),_0_0_0_1px_rgba(0,0,0,0.05)] rounded-[40px] flex flex-col relative overflow-hidden"
          >
            <div className="flex justify-between items-center p-6 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#C4B5FD] rounded-[14px] flex items-center justify-center rotate-6 border-2 border-white shadow-inner">
                  <Library className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-[20px] font-black text-[#334155] tracking-tight">学习资产库</h2>
                  <p className="text-[12px] font-bold text-[#64748B]">卡片和错题复盘都在这里</p>
                </div>
              </div>
              <motion.button
                whileTap={{ scale: 0.82, rotate: 90 }}
                onClick={onClose}
                className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-[#64748B] hover:bg-[#F1F5F9] shadow-sm border-2 border-[#F1F5F9] transition-colors"
              >
                <X className="w-6 h-6 stroke-[3]" />
              </motion.button>
            </div>
            <div className="px-6 pb-3">
              <div className="bg-white rounded-[18px] p-1.5 border-2 border-[#EEF2FF] grid grid-cols-3 gap-1.5">
                {[
                  { key: "all", label: "全部" },
                  { key: "cards", label: "学习卡片" },
                  { key: "reviews", label: "错题复盘" },
                ].map((item) => {
                  const selected = filter === item.key;
                  return (
                    <motion.button
                      key={item.key}
                      type="button"
                      whileTap={{ scale: 0.96 }}
                      onClick={() => setFilter(item.key as AssetFilter)}
                      className={`rounded-[12px] py-2 text-[12px] font-black transition-all ${
                        selected ? "bg-[#EEF2FF] text-[#4F46E5]" : "text-[#64748B] hover:bg-[#F8FAFC]"
                      }`}
                    >
                      {item.label}
                    </motion.button>
                  );
                })}
              </div>
            </div>
            <div className="px-6 pb-6 max-h-[62vh] overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] space-y-3">
              {isLoading && (
                <div className="space-y-3">
                  {[1, 2, 3].map((index) => (
                    <div key={index} className="rounded-[20px] bg-white border-2 border-[#F1F5F9] p-4 animate-pulse">
                      <div className="h-4 bg-[#E2E8F0] rounded w-2/3" />
                      <div className="h-3 bg-[#E2E8F0] rounded mt-3 w-full" />
                      <div className="h-3 bg-[#E2E8F0] rounded mt-2 w-4/5" />
                    </div>
                  ))}
                </div>
              )}
              {!isLoading &&
                filteredCards.map((card) => (
                  <motion.div
                    key={`card-${card.id}`}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-[22px] bg-white border-2 border-[#F1F5F9] p-4 shadow-sm"
                  >
                    {(() => {
                      const displayTags = visibleCardTags(card.tags).slice(0, 4);
                      return (
                        <>
                    {(() => {
                      const cardType = resolveCardType(card);
                      const style = cardTypeStyle(cardType);
                      return (
                    <div className="flex items-start justify-between gap-2">
                      <div className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-black ${style.badge}`}>
                        <BookCopy className="w-3.5 h-3.5" />
                        {style.label}
                      </div>
                      <span className="text-[11px] text-[#94A3B8] font-bold">{formatTime(card.updated_at || card.created_at)}</span>
                    </div>
                      );
                    })()}
                    <div className="mt-2 text-[14px] font-black text-[#334155] leading-[1.45] line-clamp-2">{card.title || "未命名卡片"}</div>
                    <div className="mt-2 rounded-[14px] bg-[#F8FAFC] border border-[#E2E8F0] px-3 py-2.5">
                      <div className="text-[11px] font-black text-[#6366F1]">重点速览</div>
                      <ul className="mt-1.5 space-y-1 text-[12px] font-semibold text-[#475569] leading-[1.45]">
                        {(cardHighlights[card.id] || []).map((point, index) => (
                          <li key={`${card.id}-point-${index}`} className="flex items-start gap-1.5">
                            <span className="mt-1 inline-block w-1.5 h-1.5 rounded-full bg-[#6366F1] shrink-0" />
                            <span>{point}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    {displayTags.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {displayTags.map((tag) => (
                          <span key={`${card.id}-${tag}`} className="text-[11px] font-bold text-[#0EA5E9] bg-[#ECFEFF] px-2 py-0.5 rounded-full">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => setSelectedCard(card)}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-[#EEF2FF] px-3 py-1.5 text-[12px] font-black text-[#4F46E5]"
                    >
                      查看全文
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                        </>
                      );
                    })()}
                  </motion.div>
                ))}
              {!isLoading &&
                filteredReviews.map((record) => (
                  <motion.div
                    key={`review-${record.id}`}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-[22px] bg-white border-2 border-[#F1F5F9] p-4 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 bg-[#FEF3C7] text-[#B45309] text-[11px] font-black">
                        <NotebookPen className="w-3.5 h-3.5" />
                        错题复盘
                      </div>
                      <span className="text-[11px] text-[#94A3B8] font-bold">{formatTime(record.created_at)}</span>
                    </div>
                    <div className="mt-2 text-[14px] font-black text-[#334155] leading-[1.45]">{record.focus_topic || "未命名复盘主题"}</div>
                    <div className="mt-2 text-[13px] text-[#475569] font-medium leading-[1.5] line-clamp-2">{record.source_question}</div>
                    <div className="mt-2 text-[12px] font-bold text-[#B45309] bg-[#FFFBEB] rounded-[12px] p-2.5 line-clamp-2">
                      {record.fix_action}
                    </div>
                  </motion.div>
                ))}
              {isEmpty && (
                <div className="rounded-[24px] bg-white border-2 border-dashed border-[#E2E8F0] p-6 text-center">
                  <div className="text-[16px] font-black text-[#334155]">还没有学习资产</div>
                  <p className="mt-2 text-[13px] font-medium text-[#64748B] leading-[1.5]">
                    去聊天里点一次“转学习卡片”，这里就会自动出现你的第一条学习沉淀。
                  </p>
                </div>
              )}
            </div>
            <AnimatePresence>
              {selectedCard && (
                <motion.div
                  initial={{ opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 24 }}
                  transition={{ duration: 0.2 }}
                  className="absolute inset-0 z-20 bg-[#FAFAF9]/95 backdrop-blur-sm flex flex-col"
                >
                  <div className="flex items-center justify-between p-6 pb-4">
                    <button
                      type="button"
                      onClick={() => setSelectedCard(null)}
                      className="inline-flex items-center gap-1.5 rounded-full bg-white border-2 border-[#EEF2FF] px-3 py-1.5 text-[12px] font-black text-[#4F46E5]"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                      返回列表
                    </button>
                    <span className="text-[11px] text-[#94A3B8] font-bold">{formatTime(selectedCard.updated_at || selectedCard.created_at)}</span>
                  </div>
                  <div className="px-6 pb-5 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                    <h3 className="text-[18px] font-black text-[#334155] leading-[1.4]">{selectedCard.title || "未命名卡片"}</h3>
                    {selectedCardStyle && (
                      <div className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-black ${selectedCardStyle.badge}`}>
                        <BookCopy className="w-3.5 h-3.5" />
                        {selectedCardStyle.label}
                      </div>
                    )}
                    <div className="mt-3 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          const next = !selfTestEnabled;
                          setSelfTestEnabled(next);
                          setSelfTestRevealed(false);
                        }}
                        className={`inline-flex items-center rounded-full px-3 py-1.5 text-[12px] font-black transition-colors ${
                          selfTestEnabled ? "bg-[#EDE9FE] text-[#6D28D9]" : "bg-[#EEF2FF] text-[#4F46E5]"
                        }`}
                      >
                        {selfTestEnabled ? "退出自测" : "一键自测"}
                      </button>
                      {selfTestEnabled && (
                        <span className="text-[11px] font-bold text-[#7C3AED]">先作答，再翻看参考</span>
                      )}
                    </div>
                    {visibleCardTags(selectedCard.tags).length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {visibleCardTags(selectedCard.tags).map((tag) => (
                          <span key={`${selectedCard.id}-detail-${tag}`} className="text-[11px] font-bold text-[#0EA5E9] bg-[#ECFEFF] px-2 py-0.5 rounded-full">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                    {selfTestEnabled && selfTestPrompt && !selfTestRevealed && (
                      <div className="mt-4 rounded-[18px] border-2 border-[#EDE9FE] bg-[#F5F3FF] px-4 py-4">
                        <div className="text-[12px] font-black text-[#7C3AED]">自测题</div>
                        <p className="mt-1.5 text-[14px] font-semibold leading-[1.65] text-[#4C1D95]">{selfTestPrompt.question}</p>
                        {selfTestPrompt.hints.length > 0 && (
                          <ul className="mt-2.5 space-y-1.5 text-[12px] font-semibold text-[#5B21B6]">
                            {selfTestPrompt.hints.map((hint, index) => (
                              <li key={`self-test-hint-${index}`} className="flex items-start gap-1.5">
                                <span className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-[#8B5CF6] shrink-0" />
                                <span>{hint}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                        <button
                          type="button"
                          onClick={() => setSelfTestRevealed(true)}
                          className="mt-3 inline-flex items-center rounded-full bg-[#7C3AED] px-3 py-1.5 text-[12px] font-black text-white"
                        >
                          我已作答，查看参考
                        </button>
                      </div>
                    )}
                    {(!selfTestEnabled || selfTestRevealed) && (
                      <div className="mt-4 rounded-[18px] border-2 border-white bg-white px-4 py-4 shadow-[0_8px_24px_rgba(99,102,241,0.08)]">
                        {renderRichTextContent(selectedCard.content)}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
