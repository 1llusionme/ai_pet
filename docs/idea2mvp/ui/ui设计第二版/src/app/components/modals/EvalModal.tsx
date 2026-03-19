import { motion, AnimatePresence } from "motion/react";
import { X, Beaker, Trophy, Sparkles, Scale } from "lucide-react";
import { useState } from "react";

interface EvalModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function EvalModal({ isOpen, onClose }: EvalModalProps) {
  const [isComparing, setIsComparing] = useState(false);
  const [result, setResult] = useState<null | 'A' | 'B'>(null);

  const handleCompare = () => {
    setIsComparing(true);
    setTimeout(() => {
      setIsComparing(false);
      setResult('A'); // Mocking result
    }, 1500);
  };

  const reset = () => {
    setResult(null);
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="absolute inset-0 z-50 flex items-center justify-center bg-white/40 backdrop-blur-md rounded-[inherit] p-4"
          onClick={reset}
        >
          <motion.div
            initial={{ scale: 0.8, y: 50, rotate: -2 }}
            animate={{ scale: 1, y: 0, rotate: 0 }}
            exit={{ scale: 0.8, y: 50, rotate: 2 }}
            transition={{ type: "spring", damping: 20, stiffness: 350 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[360px] bg-white border-[4px] border-white shadow-[0_20px_60px_rgba(0,0,0,0.1),_0_0_0_1px_rgba(0,0,0,0.05)] rounded-[40px] flex flex-col relative overflow-hidden"
          >
            {/* Header */}
            <div className="flex justify-between items-center p-6 pb-2 relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#38BDF8] rounded-[14px] flex items-center justify-center -rotate-6 shadow-inner border-2 border-white">
                  <Beaker className="w-6 h-6 text-white" />
                </div>
                <h2 className="text-[20px] font-black text-[#334155] tracking-tight">
                  A/B 评测台
                </h2>
              </div>
              <motion.button
                whileTap={{ scale: 0.8, rotate: 90 }}
                onClick={reset}
                className="w-10 h-10 bg-[#F1F5F9] rounded-full flex items-center justify-center text-[#64748B] hover:bg-[#E2E8F0] transition-colors"
              >
                <X className="w-6 h-6 stroke-[3]" />
              </motion.button>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 relative z-10">
              {!result ? (
                <div className="flex flex-col gap-4">
                  <div className="text-[13px] font-bold text-[#64748B] bg-[#F8FAFC] p-3 rounded-[16px] border-2 border-[#E2E8F0]">
                    评测题：如何向 8 岁小孩解释“黑洞”？
                  </div>

                  <div className="flex gap-3">
                    <div className="flex-1 bg-[#FFF1F2] border-2 border-[#FFE4E6] p-3 rounded-[20px] relative">
                      <div className="absolute -top-3 -left-2 w-6 h-6 bg-[#FF6B9E] rounded-full text-white font-black flex items-center justify-center text-[12px] border-2 border-white shadow-sm">A</div>
                      <p className="text-[12px] text-[#475569] font-medium mt-1">黑洞是宇宙里的超级吸尘器，引力非常大，连光都跑不掉...</p>
                    </div>
                    <div className="flex-1 bg-[#F0FDF4] border-2 border-[#D1FAE5] p-3 rounded-[20px] relative">
                      <div className="absolute -top-3 -right-2 w-6 h-6 bg-[#10B981] rounded-full text-white font-black flex items-center justify-center text-[12px] border-2 border-white shadow-sm">B</div>
                      <p className="text-[12px] text-[#475569] font-medium mt-1">根据广义相对论，黑洞是时空曲率大到光都无法逃脱的天体区...</p>
                    </div>
                  </div>

                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={handleCompare}
                    disabled={isComparing}
                    className="w-full mt-2 py-4 bg-[#38BDF8] text-white font-black text-[16px] tracking-wide rounded-[24px] shadow-[0_8px_20px_rgba(56,189,248,0.3)] hover:shadow-[0_12px_25px_rgba(56,189,248,0.4)] transition-all disabled:opacity-50 flex justify-center items-center gap-2"
                  >
                    {isComparing ? (
                      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}>
                        <Scale className="w-5 h-5" />
                      </motion.div>
                    ) : (
                      <>
                        <Scale className="w-5 h-5 stroke-[2.5]" /> 开始对决！
                      </>
                    )}
                  </motion.button>
                </div>
              ) : (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex flex-col items-center text-center gap-4 py-4"
                >
                  <div className="w-20 h-20 bg-gradient-to-tr from-[#FFD700] to-[#FDB931] rounded-full flex items-center justify-center shadow-[0_10px_30px_rgba(253,185,49,0.4)] border-[4px] border-white">
                    <Trophy className="w-10 h-10 text-white fill-white" />
                  </div>
                  <div>
                    <h3 className="text-[24px] font-black text-[#334155] mb-1">方案 A 胜出！</h3>
                    <p className="text-[13px] font-bold text-[#64748B]">分数：8.5 <span className="text-[#94A3B8] font-normal">vs</span> 6.0</p>
                  </div>
                  <p className="text-[13px] text-[#475569] bg-[#F8FAFC] p-3 rounded-[16px] border-2 border-[#E2E8F0] font-medium leading-relaxed text-left">
                    <Sparkles className="w-4 h-4 text-[#F59E0B] inline-block mr-1" />
                    <strong className="text-[#334155]">点评：</strong>方案 A 使用了“超级吸尘器”的比喻，更符合 8 岁小孩的认知模型，通俗易懂（Actionability 维度得分高）。
                  </p>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={reset}
                    className="w-full mt-2 py-3 bg-[#F1F5F9] text-[#64748B] font-bold text-[15px] rounded-[20px] hover:bg-[#E2E8F0] transition-colors"
                  >
                    完成评测
                  </motion.button>
                </motion.div>
              )}
            </div>
            
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
