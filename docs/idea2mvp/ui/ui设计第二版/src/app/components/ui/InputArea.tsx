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

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [text]);

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
    <div className="px-4 pb-6 pt-2 shrink-0 relative z-20 w-full bg-gradient-to-t from-[#FEF2F2] via-[#FEF2F2] to-transparent">
      <div className="bg-white border-[3px] border-white shadow-[0_10px_30px_rgba(0,0,0,0.05)] rounded-[32px] p-2 flex items-end gap-2 relative">
        {/* Floating background decorative shape behind input */}
        <div className="absolute -z-10 -bottom-2 -right-2 w-[95%] h-[100%] bg-gradient-to-r from-[#A855F7]/10 to-[#38BDF8]/10 rounded-[32px] blur-md" />

        <motion.button
          whileTap={{ scale: 0.85, rotate: -90 }}
          onClick={onOpenOptions}
          className="w-12 h-12 bg-[#F3E8FF] text-[#A855F7] hover:bg-[#E9D5FF] flex items-center justify-center shrink-0 mb-0.5 rounded-[20px] transition-colors"
        >
          <Plus className="w-7 h-7 stroke-[3]" />
        </motion.button>
        
        <div className="flex-1 flex items-center min-h-[52px] mb-0.5 bg-[#F8FAFC] rounded-[24px] px-2 py-1 border-2 border-transparent focus-within:border-[#38BDF8]/30 transition-colors">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="有什么好玩的想法？"
            disabled={isInputDisabled}
            className="flex-1 bg-transparent border-none outline-none resize-none px-2 py-2.5 text-[16px] placeholder-[#94A3B8] text-[#334155] font-bold overflow-hidden"
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
                className="w-12 h-12 bg-gradient-to-tr from-[#38BDF8] to-[#2DD4BF] text-white flex items-center justify-center rounded-[20px] shadow-[0_4px_15px_rgba(56,189,248,0.4)] disabled:opacity-50"
              >
                <SendHorizontal className="w-6 h-6 stroke-[2.5] -ml-0.5" />
              </motion.button>
            </motion.div>
          ) : (
             <div className="w-12 h-12 shrink-0 mb-0.5" />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
