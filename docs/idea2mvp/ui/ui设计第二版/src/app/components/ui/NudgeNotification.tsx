import { motion, AnimatePresence } from "motion/react";
import { Zap } from "lucide-react";

interface NudgeNotificationProps {
  isOpen: boolean;
  message: string;
  onClose: () => void;
  onClick: () => void;
}

export function NudgeNotification({ isOpen, message, onClose, onClick }: NudgeNotificationProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ y: -100, x: -50, opacity: 0, rotate: -10 }}
          animate={{ y: 0, x: 0, opacity: 1, rotate: 0 }}
          exit={{ y: -100, x: 50, opacity: 0, rotate: 10 }}
          transition={{ type: "spring", damping: 15, stiffness: 350 }}
          className="absolute top-16 right-4 z-[100] cursor-pointer w-[280px]"
          onClick={() => {
            onClick();
            onClose();
          }}
        >
          {/* Speech bubble tail */}
          <div className="absolute -top-3 right-6 w-6 h-6 bg-white transform rotate-45 border-l-[3px] border-t-[3px] border-white shadow-[-4px_-4px_10px_rgba(0,0,0,0.02)] z-0 rounded-sm" />
          
          <div className="bg-white p-4 rounded-[28px] shadow-[0_15px_35px_rgba(0,0,0,0.08),_0_0_0_3px_#fff] relative z-10 flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-[#FDE047] rounded-full flex items-center justify-center shrink-0">
                <motion.div
                   animate={{ scale: [1, 1.2, 1], rotate: [0, 15, -15, 0] }}
                   transition={{ duration: 0.6, repeat: Infinity, repeatDelay: 2 }}
                >
                  <Zap className="text-[#CA8A04] w-5 h-5 fill-[#CA8A04]" />
                </motion.div>
              </div>
              <span className="font-black text-[15px] text-[#334155] tracking-tight">灵光一闪！</span>
            </div>
            
            <div className="bg-[#F8FAFC] rounded-[18px] p-3">
              <p className="text-[14px] text-[#475569] leading-[1.5] font-medium">
                {message}
              </p>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
