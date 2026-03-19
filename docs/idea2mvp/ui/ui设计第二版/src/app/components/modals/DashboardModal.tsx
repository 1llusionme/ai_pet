import { motion, AnimatePresence } from "motion/react";
import { X, Target, Flame, CheckCircle2, Award, TrendingDown, ArrowUpRight } from "lucide-react";

interface DashboardModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function DashboardModal({ isOpen, onClose }: DashboardModalProps) {
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
            initial={{ scale: 0.8, y: 50, rotate: 2 }}
            animate={{ scale: 1, y: 0, rotate: 0 }}
            exit={{ scale: 0.8, y: 50, rotate: -2 }}
            transition={{ type: "spring", damping: 20, stiffness: 350 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[360px] bg-[#FAFAF9] border-[4px] border-white shadow-[0_20px_60px_rgba(0,0,0,0.1),_0_0_0_1px_rgba(0,0,0,0.05)] rounded-[40px] flex flex-col relative overflow-hidden"
          >
            {/* Header */}
            <div className="flex justify-between items-center p-6 pb-4 relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#FF9A9E] rounded-[14px] flex items-center justify-center rotate-6 shadow-inner border-2 border-white">
                  <Target className="w-6 h-6 text-white" />
                </div>
                <h2 className="text-[20px] font-black text-[#334155] tracking-tight">
                  学习看板
                </h2>
              </div>
              <motion.button
                whileTap={{ scale: 0.8, rotate: 90 }}
                onClick={onClose}
                className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-[#64748B] hover:bg-[#F1F5F9] shadow-sm border-2 border-[#F1F5F9] transition-colors"
              >
                <X className="w-6 h-6 stroke-[3]" />
              </motion.button>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 pt-0 relative z-10 max-h-[65vh] overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              
              {/* Today's Plan */}
              <div className="bg-white p-5 rounded-[28px] border-2 border-[#F1F5F9] shadow-sm mb-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-bold text-[#475569] text-[15px] flex items-center gap-1.5">
                    <Flame className="w-4 h-4 text-[#F97316]" /> 今日计划
                  </span>
                  <span className="text-[12px] font-bold text-[#10B981] bg-[#D1FAE5] px-2 py-0.5 rounded-full">已打卡</span>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-[#10B981]" />
                    <span className="text-[14px] text-[#64748B] font-medium line-through">复习教育学核心概念</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-[#10B981]" />
                    <span className="text-[14px] text-[#64748B] font-medium line-through">完成 20 道选择题</span>
                  </div>
                </div>
              </div>

              {/* Weekly Goals */}
              <div className="bg-gradient-to-br from-[#E0F2FE] to-[#BAE6FD] p-5 rounded-[28px] border-2 border-white shadow-sm mb-4 relative overflow-hidden">
                <div className="absolute -right-4 -top-4 w-20 h-20 bg-white/20 rounded-full blur-xl" />
                <div className="flex items-center justify-between mb-4 relative z-10">
                  <span className="font-bold text-[#0284C7] text-[15px] flex items-center gap-1.5">
                    <Award className="w-4 h-4 text-[#0284C7]" /> 本周目标
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 relative z-10">
                  <div className="bg-white/60 backdrop-blur-sm p-3 rounded-[20px] text-center">
                    <div className="text-[24px] font-black text-[#0369A1]">85%</div>
                    <div className="text-[11px] font-bold text-[#0284C7] mt-1">任务完成率</div>
                  </div>
                  <div className="bg-white/60 backdrop-blur-sm p-3 rounded-[20px] text-center">
                    <div className="text-[24px] font-black text-[#10B981] flex items-center justify-center gap-0.5">
                      <TrendingDown className="w-5 h-5 stroke-[3]" /> 12%
                    </div>
                    <div className="text-[11px] font-bold text-[#059669] mt-1">复错下降率</div>
                  </div>
                </div>
              </div>

              {/* Strategy Stats */}
              <div className="bg-[#FAE8FF] p-5 rounded-[28px] border-2 border-white shadow-sm">
                <span className="font-bold text-[#7E22CE] text-[15px] flex items-center gap-1.5 mb-3">
                  <ArrowUpRight className="w-4 h-4 text-[#A855F7]" /> 学习轻推数据
                </span>
                <div className="flex items-center justify-between bg-white/50 p-3 rounded-[16px]">
                  <span className="text-[13px] font-bold text-[#9333EA]">回流成功率</span>
                  <span className="text-[15px] font-black text-[#7E22CE]">42.5%</span>
                </div>
                <div className="flex items-center justify-between bg-white/50 p-3 rounded-[16px] mt-2">
                  <span className="text-[13px] font-bold text-[#9333EA]">最佳触发策略</span>
                  <span className="text-[12px] font-bold text-white bg-[#A855F7] px-2 py-0.5 rounded-full">高频复错</span>
                </div>
              </div>

            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
