import { AnimatePresence, motion } from "motion/react";
import { X, Sparkles, CheckCircle2 } from "lucide-react";

interface StylePreferenceModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentStyle: "简洁版" | "详细版" | "速记版";
  onSelectStyle: (style: "简洁版" | "详细版" | "速记版") => void;
}

const STYLE_OPTIONS: Array<{
  value: "简洁版" | "详细版" | "速记版";
  title: string;
  description: string;
  colors: string;
}> = [
  {
    value: "简洁版",
    title: "简洁版",
    description: "先说结论，控制字数，适合快速刷题时看重点。",
    colors: "from-[#FEF3C7] to-[#FDE68A] text-[#B45309]",
  },
  {
    value: "详细版",
    title: "详细版",
    description: "保留结论与依据，解释更完整，适合系统理解。",
    colors: "from-[#E0F2FE] to-[#BAE6FD] text-[#0369A1]",
  },
  {
    value: "速记版",
    title: "速记版",
    description: "突出术语和口诀，句式更短，便于临考复盘。",
    colors: "from-[#F3E8FF] to-[#E9D5FF] text-[#7E22CE]",
  },
];

export function StylePreferenceModal({ isOpen, onClose, currentStyle, onSelectStyle }: StylePreferenceModalProps) {
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
            initial={{ scale: 0.86, y: 30, rotate: -2 }}
            animate={{ scale: 1, y: 0, rotate: 0 }}
            exit={{ scale: 0.86, y: 30, rotate: 2 }}
            transition={{ type: "spring", damping: 22, stiffness: 360 }}
            onClick={(event) => event.stopPropagation()}
            className="w-full max-w-[360px] bg-[#FAFAF9] border-[4px] border-white shadow-[0_20px_60px_rgba(0,0,0,0.1),_0_0_0_1px_rgba(0,0,0,0.05)] rounded-[40px] flex flex-col relative overflow-hidden"
          >
            <div className="flex justify-between items-center p-6 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#FDE68A] rounded-[14px] flex items-center justify-center -rotate-6 border-2 border-white shadow-inner">
                  <Sparkles className="w-5 h-5 text-[#B45309]" />
                </div>
                <div>
                  <h2 className="text-[20px] font-black text-[#334155] tracking-tight">回答风格</h2>
                  <p className="text-[12px] font-bold text-[#64748B]">选择你最顺手的讲解方式</p>
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
            <div className="px-6 pb-6 space-y-3">
              {STYLE_OPTIONS.map((item) => {
                const selected = currentStyle === item.value;
                return (
                  <motion.button
                    key={item.value}
                    type="button"
                    whileHover={{ y: -2 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => onSelectStyle(item.value)}
                    className={`w-full text-left rounded-[22px] border-2 px-4 py-3 transition-all ${
                      selected
                        ? "bg-white border-[#38BDF8] shadow-[0_10px_18px_rgba(56,189,248,0.2)]"
                        : "bg-white/80 border-white hover:border-[#E2E8F0]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <div className={`px-2.5 py-1 rounded-full bg-gradient-to-r text-[11px] font-black ${item.colors}`}>
                            {item.title}
                          </div>
                          {selected && (
                            <span className="text-[11px] font-black text-[#0EA5E9] bg-[#E0F2FE] rounded-full px-2 py-0.5">
                              当前
                            </span>
                          )}
                        </div>
                        <p className="mt-2 text-[13px] leading-[1.45] text-[#475569] font-medium">{item.description}</p>
                      </div>
                      <CheckCircle2
                        className={`w-5 h-5 mt-0.5 transition-colors ${selected ? "text-[#06B6D4]" : "text-[#CBD5E1]"}`}
                      />
                    </div>
                  </motion.button>
                );
              })}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
