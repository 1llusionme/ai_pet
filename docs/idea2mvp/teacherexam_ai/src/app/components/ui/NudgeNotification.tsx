import { useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Zap } from "lucide-react";

interface NudgeNotificationProps {
  isOpen: boolean;
  message: string;
  onClose: () => void;
  onClick: () => void;
}

export function NudgeNotification({ isOpen, message, onClose, onClick }: NudgeNotificationProps) {
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const timer = window.setTimeout(() => onClose(), 5200);
    return () => window.clearTimeout(timer);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ y: 16, opacity: 0, scale: 0.96 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          exit={{ y: 14, opacity: 0, scale: 0.98 }}
          transition={{ type: "spring", damping: 24, stiffness: 320 }}
          className="fixed left-1/2 bottom-[100px] -translate-x-1/2 z-[110] w-[min(92vw,420px)] cursor-pointer"
          onClick={() => {
            onClick();
            onClose();
          }}
        >
          <div className="bg-white/95 backdrop-blur-md border border-white/90 rounded-[20px] px-3 py-3 shadow-[0_10px_26px_rgba(15,23,42,0.12)] flex items-start gap-2.5">
            <div className="w-8 h-8 bg-[#FEF3C7] rounded-full flex items-center justify-center shrink-0 mt-0.5">
              <motion.div animate={{ scale: [1, 1.12, 1] }} transition={{ duration: 1.2, repeat: Infinity, repeatDelay: 1.2 }}>
                <Zap className="text-[#D97706] w-4.5 h-4.5 fill-[#D97706]" />
              </motion.div>
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-black text-[13px] text-[#334155] tracking-tight leading-none">学习节奏提醒</span>
                <span className="text-[11px] text-[#94A3B8] font-semibold">点击可一键提问</span>
              </div>
              <p className="mt-1 text-[13px] text-[#475569] leading-[1.45] font-semibold line-clamp-2">
                {message}
              </p>
            </div>
            <div className="shrink-0 text-[11px] text-[#A855F7] font-bold pt-0.5">去练习</div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
