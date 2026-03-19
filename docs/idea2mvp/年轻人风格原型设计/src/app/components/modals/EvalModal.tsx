import { motion, AnimatePresence } from "motion/react";
import { X, Beaker, Trophy, Sparkles, Scale } from "lucide-react";
import type { EvaluationCase, EvaluationTrendSummary } from "../../services/api";

interface EvalResult {
  winner: string;
  delta: number;
  scoreA: number;
  scoreB: number;
}

interface EvalModalProps {
  isOpen: boolean;
  onClose: () => void;
  cases: EvaluationCase[];
  selectedCaseId: string;
  onSelectCase: (id: string) => void;
  variantALabel: string;
  onVariantALabelChange: (value: string) => void;
  variantBLabel: string;
  onVariantBLabelChange: (value: string) => void;
  variantAAnswer: string;
  onVariantAAnswerChange: (value: string) => void;
  variantBAnswer: string;
  onVariantBAnswerChange: (value: string) => void;
  isComparing: boolean;
  onCompare: () => void;
  result: EvalResult | null;
  trendSummary: EvaluationTrendSummary | null;
  selectedCaseQuestion: string;
}

export function EvalModal({
  isOpen,
  onClose,
  cases,
  selectedCaseId,
  onSelectCase,
  variantALabel,
  onVariantALabelChange,
  variantBLabel,
  onVariantBLabelChange,
  variantAAnswer,
  onVariantAAnswerChange,
  variantBAnswer,
  onVariantBAnswerChange,
  isComparing,
  onCompare,
  result,
  trendSummary,
  selectedCaseQuestion,
}: EvalModalProps) {
  const canCompare = Boolean(selectedCaseId && variantAAnswer.trim() && variantBAnswer.trim());

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="absolute inset-0 z-50 flex items-center justify-center bg-white/40 backdrop-blur-md rounded-[inherit] p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.8, y: 50, rotate: -2 }}
            animate={{ scale: 1, y: 0, rotate: 0 }}
            exit={{ scale: 0.8, y: 50, rotate: 2 }}
            transition={{ type: "spring", damping: 20, stiffness: 350 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[360px] bg-white border-[4px] border-white shadow-[0_20px_60px_rgba(0,0,0,0.1),_0_0_0_1px_rgba(0,0,0,0.05)] rounded-[40px] flex flex-col relative overflow-hidden"
          >
            <div className="flex justify-between items-center p-6 pb-2 relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#38BDF8] rounded-[14px] flex items-center justify-center -rotate-6 shadow-inner border-2 border-white">
                  <Beaker className="w-6 h-6 text-white" />
                </div>
                <h2 className="text-[20px] font-black text-[#334155] tracking-tight">A/B 评测台</h2>
              </div>
              <motion.button
                whileTap={{ scale: 0.8, rotate: 90 }}
                onClick={onClose}
                className="w-10 h-10 bg-[#F1F5F9] rounded-full flex items-center justify-center text-[#64748B] hover:bg-[#E2E8F0] transition-colors"
              >
                <X className="w-6 h-6 stroke-[3]" />
              </motion.button>
            </div>
            <div className="flex-1 p-6 relative z-10 max-h-[65vh] overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              {!result ? (
                <div className="flex flex-col gap-4">
                  <select
                    value={selectedCaseId}
                    onChange={(event) => onSelectCase(event.target.value)}
                    className="w-full rounded-[16px] border-2 border-[#E2E8F0] px-3 py-2 text-[13px] text-[#334155] bg-[#F8FAFC] font-bold"
                  >
                    {cases.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.case_code} · {item.focus_topic} · {item.difficulty}
                      </option>
                    ))}
                  </select>
                  <div className="text-[13px] font-bold text-[#64748B] bg-[#F8FAFC] p-3 rounded-[16px] border-2 border-[#E2E8F0]">
                    {selectedCaseQuestion || "请选择评测题"}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      value={variantALabel}
                      onChange={(event) => onVariantALabelChange(event.target.value)}
                      className="rounded-[14px] border-2 border-[#FFE4E6] bg-[#FFF1F2] px-3 py-2 text-[12px] text-[#BE185D] font-bold"
                    />
                    <input
                      value={variantBLabel}
                      onChange={(event) => onVariantBLabelChange(event.target.value)}
                      className="rounded-[14px] border-2 border-[#D1FAE5] bg-[#F0FDF4] px-3 py-2 text-[12px] text-[#047857] font-bold"
                    />
                  </div>
                  <div className="flex gap-3">
                    <div className="flex-1 bg-[#FFF1F2] border-2 border-[#FFE4E6] p-3 rounded-[20px] relative">
                      <div className="absolute -top-3 -left-2 w-6 h-6 bg-[#FF6B9E] rounded-full text-white font-black flex items-center justify-center text-[12px] border-2 border-white shadow-sm">
                        A
                      </div>
                      <textarea
                        value={variantAAnswer}
                        onChange={(event) => onVariantAAnswerChange(event.target.value)}
                        rows={5}
                        className="w-full bg-transparent resize-none focus:outline-none text-[12px] text-[#475569] font-medium mt-1"
                        placeholder="填入A方案回答"
                      />
                    </div>
                    <div className="flex-1 bg-[#F0FDF4] border-2 border-[#D1FAE5] p-3 rounded-[20px] relative">
                      <div className="absolute -top-3 -right-2 w-6 h-6 bg-[#10B981] rounded-full text-white font-black flex items-center justify-center text-[12px] border-2 border-white shadow-sm">
                        B
                      </div>
                      <textarea
                        value={variantBAnswer}
                        onChange={(event) => onVariantBAnswerChange(event.target.value)}
                        rows={5}
                        className="w-full bg-transparent resize-none focus:outline-none text-[12px] text-[#475569] font-medium mt-1"
                        placeholder="填入B方案回答"
                      />
                    </div>
                  </div>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={onCompare}
                    disabled={isComparing || !canCompare}
                    className="w-full mt-1 py-4 bg-[#38BDF8] text-white font-black text-[16px] tracking-wide rounded-[24px] shadow-[0_8px_20px_rgba(56,189,248,0.3)] hover:shadow-[0_12px_25px_rgba(56,189,248,0.4)] transition-all disabled:opacity-50 flex justify-center items-center gap-2"
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
                  {trendSummary?.variants?.length ? (
                    <div className="text-[12px] text-[#475569] bg-[#F8FAFC] rounded-[16px] px-3 py-2 border-2 border-[#E2E8F0]">
                      当前最佳策略：{trendSummary.best_variant}（总评测 {trendSummary.total_runs} 次）
                    </div>
                  ) : null}
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
                    <h3 className="text-[24px] font-black text-[#334155] mb-1">方案 {result.winner} 胜出！</h3>
                    <p className="text-[13px] font-bold text-[#64748B]">
                      分数：{Math.round(result.scoreA * 100) / 100} <span className="text-[#94A3B8] font-normal">vs</span>{" "}
                      {Math.round(result.scoreB * 100) / 100}
                    </p>
                  </div>
                  <p className="text-[13px] text-[#475569] bg-[#F8FAFC] p-3 rounded-[16px] border-2 border-[#E2E8F0] font-medium leading-relaxed text-left">
                    <Sparkles className="w-4 h-4 text-[#F59E0B] inline-block mr-1" />
                    分差 {Math.round(result.delta * 100) / 100}，可继续优化弱势方案并再次评测。
                  </p>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={onClose}
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
