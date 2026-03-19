import React, { useState, useRef, useEffect } from "react";
import { Plus, SendHorizontal } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

interface InputAreaProps {
  onSendMessage: (text: string) => void;
  onOpenOptions: () => void;
  isInputDisabled?: boolean;
}

export function InputArea({ onSendMessage, onOpenOptions, isInputDisabled }: InputAreaProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const minTextareaHeight = 44;
  const maxTextareaHeight = 88;

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      const nextHeight = Math.min(maxTextareaHeight, Math.max(minTextareaHeight, scrollHeight));
      textareaRef.current.style.height = `${nextHeight}px`;
      textareaRef.current.style.overflowY = scrollHeight > maxTextareaHeight ? "auto" : "hidden";
    }
  }, [text, maxTextareaHeight, minTextareaHeight]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (text.trim() && !isInputDisabled) {
      onSendMessage(text.trim());
      setText("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="px-3 sm:px-4 pb-[calc(12px+env(safe-area-inset-bottom))] pt-2 shrink-0 relative z-20 w-full bg-gradient-to-t from-[#FEF2F2] via-[#FEF2F2] to-transparent">
      <div className="bg-white/95 backdrop-blur-md border border-white shadow-[0_14px_36px_rgba(15,23,42,0.12)] rounded-[30px] p-2.5 flex items-end gap-2.5 relative">
        <div className="absolute -z-10 -bottom-2 -right-2 w-[95%] h-[100%] bg-gradient-to-r from-[#A855F7]/10 to-[#38BDF8]/10 rounded-[32px] blur-md" />

        <motion.button
          whileTap={{ scale: 0.85, rotate: -90 }}
          onClick={onOpenOptions}
          disabled={isInputDisabled}
          aria-label="打开更多功能"
          className="w-11 h-11 bg-[#F3E8FF] text-[#9333EA] hover:bg-[#E9D5FF] flex items-center justify-center shrink-0 mb-0.5 rounded-[18px] transition-colors disabled:opacity-50"
        >
          <Plus className="w-6 h-6 stroke-[2.75]" />
        </motion.button>

        <div className="flex-1 flex items-end min-h-11 mb-0.5 bg-[#F8FAFC] rounded-[22px] px-2 border-2 border-transparent focus-within:border-[#38BDF8]/40 focus-within:bg-white transition-colors">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="教编有关的都可以问我嗷💡"
            disabled={isInputDisabled}
            className="flex-1 bg-transparent border-none outline-none resize-none px-2 py-2.5 text-[16px] leading-[22px] placeholder-[#94A3B8] text-[#334155] font-bold overflow-y-hidden"
            rows={1}
          />
        </div>

        <AnimatePresence>
          {text.trim() ? (
            <motion.div
              initial={{ scale: 0, opacity: 0, rotate: -45 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              exit={{ scale: 0, opacity: 0, rotate: 45 }}
              transition={{ type: "spring", damping: 15, stiffness: 400 }}
              className="shrink-0 mb-0.5"
            >
              <motion.button
                whileTap={{ scale: 0.9 }}
                onClick={handleSubmit}
                disabled={isInputDisabled}
                aria-label="发送消息"
                className="w-11 h-11 bg-gradient-to-tr from-[#38BDF8] to-[#2DD4BF] text-white flex items-center justify-center rounded-[18px] shadow-[0_8px_18px_rgba(56,189,248,0.45)] disabled:opacity-50"
              >
                <SendHorizontal className="w-5.5 h-5.5 stroke-[2.5] -ml-0.5" />
              </motion.button>
            </motion.div>
          ) : (
             <div className="w-11 h-11 shrink-0 mb-0.5 rounded-[18px] bg-[#E2E8F0]/55" />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
