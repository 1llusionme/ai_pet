import { motion, AnimatePresence } from "motion/react";
import { X, Target, Award, TrendingDown } from "lucide-react";
import type { NudgeStrategySummary, WeeklyReport } from "../../services/api";

interface DashboardModalProps {
  isOpen: boolean;
  onClose: () => void;
  weeklyReport: WeeklyReport | null;
  isWeeklyLoading: boolean;
  nudgeStrategy: NudgeStrategySummary | null;
  isNudgeStrategyLoading: boolean;
}

function toPercent(value: number | undefined) {
  const raw = Math.round((value || 0) * 1000) / 10;
  return Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 0;
}

function pickSimpleSentence(text: string | undefined, maxLength: number = 34) {
  const cleaned = String(text || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) {
    return "";
  }
  const first = cleaned.split(/[。！？!?]/)[0]?.trim() || cleaned;
  if (first.length <= maxLength) {
    return first;
  }
  return `${first.slice(0, maxLength)}…`;
}

function getActionItems(report: WeeklyReport | null) {
  if (!report) {
    return [];
  }
  const source = [...(report.highlights || []), ...(report.next_week_focus || [])];
  const deduped = source
    .map((item) => String(item || "").replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .reduce<string[]>((acc, item) => {
      if (!acc.includes(item)) {
        acc.push(item);
      }
      return acc;
    }, []);
  return deduped.slice(0, 3);
}

function getWeeklyHeadline(loading: boolean, stats: WeeklyReport["stats_snapshot"] | undefined) {
  if (loading) {
    return "正在整理你本周的学习进展";
  }
  if (!stats) {
    return "先完成 1 次练习，系统会自动生成看板";
  }
  if (stats.is_weekly_goal_met) {
    return "本周目标已达成，保持当前节奏";
  }
  if (!stats.has_repeat_baseline) {
    return "任务推进不错，先累计错题样本再看复错趋势";
  }
  return "当前还在冲刺阶段，优先补齐本周核心目标";
}

function getTaskTargetHint(completionPercent: number, targetPercent: number) {
  if (completionPercent >= targetPercent) {
    return "已达标";
  }
  const gap = Math.max(0, Math.round((targetPercent - completionPercent) * 10) / 10);
  return `还差 ${gap}% 达标`;
}

function getRepeatTargetHint(
  hasBaseline: boolean | undefined,
  repeatDropPercent: number,
  repeatTargetPercent: number,
) {
  if (!hasBaseline) {
    return "样本不足，先记录错题";
  }
  if (repeatDropPercent >= repeatTargetPercent) {
    return "达标";
  }
  const gap = Math.max(0, Math.round((repeatTargetPercent - repeatDropPercent) * 10) / 10);
  return `还差 ${gap}%`;
}

export function DashboardModal({
  isOpen,
  onClose,
  weeklyReport,
  isWeeklyLoading,
}: DashboardModalProps) {
  const weeklyStats = weeklyReport?.stats_snapshot;
  const completionPercent = toPercent(weeklyStats?.task_completion_rate);
  const repeatDropPercent = toPercent(weeklyStats?.repeat_mistake_drop_ratio);
  const completionTarget = toPercent(weeklyStats?.task_completion_target);
  const repeatTarget = toPercent(weeklyStats?.repeat_mistake_drop_target);
  const statusSummary = pickSimpleSentence(weeklyReport?.summary, 36);
  const coachTip = pickSimpleSentence(weeklyReport?.coach_message, 28);
  const actionItems = getActionItems(weeklyReport);
  const weeklyHeadline = getWeeklyHeadline(isWeeklyLoading, weeklyStats);
  const taskTargetHint = getTaskTargetHint(completionPercent, completionTarget);
  const repeatTargetHint = getRepeatTargetHint(weeklyStats?.has_repeat_baseline, repeatDropPercent, repeatTarget);

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
            <div className="flex justify-between items-center p-6 pb-4 relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#FF9A9E] rounded-[14px] flex items-center justify-center rotate-6 shadow-inner border-2 border-white">
                  <Target className="w-6 h-6 text-white" />
                </div>
                <h2 className="text-[20px] font-black text-[#334155] tracking-tight">学习看板</h2>
              </div>
              <motion.button
                whileTap={{ scale: 0.8, rotate: 90 }}
                onClick={onClose}
                className="w-10 h-10 bg-white rounded-full flex items-center justify-center text-[#64748B] hover:bg-[#F1F5F9] shadow-sm border-2 border-[#F1F5F9] transition-colors"
              >
                <X className="w-6 h-6 stroke-[3]" />
              </motion.button>
            </div>
            <div className="flex-1 p-6 pt-0 relative z-10 max-h-[65vh] overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              <div className="bg-white p-5 rounded-[28px] border-2 border-[#F1F5F9] shadow-sm mb-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-bold text-[#475569] text-[15px]">本周状态</span>
                  <span className="text-[12px] font-bold text-[#10B981] bg-[#D1FAE5] px-2 py-0.5 rounded-full">
                    {isWeeklyLoading ? "更新中" : weeklyStats?.is_weekly_goal_met ? "本周达标" : "本周冲刺中"}
                  </span>
                </div>
                <div className="text-[15px] text-[#334155] font-bold leading-snug">{weeklyHeadline}</div>
                <div className="text-[13px] text-[#64748B] font-medium leading-relaxed mt-2">
                  {statusSummary || "还没有周报数据，继续做题和复盘后会自动生成。"}
                </div>
                {actionItems.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {actionItems.map((item) => (
                      <div key={item} className="text-[12px] text-[#475569] bg-[#F8FAFC] rounded-xl px-3 py-2">
                        {item}
                      </div>
                    ))}
                  </div>
                )}
                {coachTip && <div className="mt-3 text-[12px] text-[#0F766E] font-semibold">教练提示：{coachTip}</div>}
              </div>
              <div className="bg-gradient-to-br from-[#E0F2FE] to-[#BAE6FD] p-5 rounded-[28px] border-2 border-white shadow-sm mb-4 relative overflow-hidden">
                <div className="absolute -right-4 -top-4 w-20 h-20 bg-white/20 rounded-full blur-xl" />
                <div className="flex items-center justify-between mb-4 relative z-10">
                  <span className="font-bold text-[#0284C7] text-[15px] flex items-center gap-1.5">
                    <Award className="w-4 h-4 text-[#0284C7]" /> 本周目标
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 relative z-10">
                  <div className="bg-white/60 backdrop-blur-sm p-3 rounded-[20px] text-center">
                    <div className="text-[24px] font-black text-[#0369A1]">{completionPercent}%</div>
                    <div className="text-[11px] font-bold text-[#0284C7] mt-1">任务完成率</div>
                    <div className="text-[11px] text-[#0369A1] font-semibold mt-1">{taskTargetHint}</div>
                  </div>
                  <div className="bg-white/60 backdrop-blur-sm p-3 rounded-[20px] text-center">
                    <div className="text-[24px] font-black text-[#10B981] flex items-center justify-center gap-0.5">
                      <TrendingDown className="w-5 h-5 stroke-[3]" /> {weeklyStats?.has_repeat_baseline ? `${repeatDropPercent}%` : "待生成"}
                    </div>
                    <div className="text-[11px] font-bold text-[#059669] mt-1">复错下降率</div>
                    <div className="text-[11px] text-[#047857] font-semibold mt-1">{repeatTargetHint}</div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
