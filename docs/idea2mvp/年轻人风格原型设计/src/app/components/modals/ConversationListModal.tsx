import { AnimatePresence, motion } from "motion/react";
import { Clock3, MessageSquarePlus, Rows2, X } from "lucide-react";

export interface ConversationListItem {
  id: string;
  title: string;
  updatedAt: string;
}

interface ConversationListModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: ConversationListItem[];
  activeSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onCreateSession: () => void;
}

function formatRelativeTime(value: string) {
  const ts = new Date(value).getTime();
  if (!Number.isFinite(ts)) {
    return "刚刚";
  }
  const diff = Date.now() - ts;
  if (diff < 60000) {
    return "刚刚";
  }
  if (diff < 3600000) {
    return `${Math.max(1, Math.floor(diff / 60000))}分钟前`;
  }
  if (diff < 86400000) {
    return `${Math.max(1, Math.floor(diff / 3600000))}小时前`;
  }
  return `${Math.max(1, Math.floor(diff / 86400000))}天前`;
}

export function ConversationListModal({
  isOpen,
  onClose,
  sessions,
  activeSessionId,
  onSelectSession,
  onCreateSession,
}: ConversationListModalProps) {
  const sortedSessions = [...sessions].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.22 }}
          className="absolute inset-0 z-50 flex items-center justify-center bg-white/40 backdrop-blur-md rounded-[inherit] p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.88, y: 22, rotate: 1.5 }}
            animate={{ scale: 1, y: 0, rotate: 0 }}
            exit={{ scale: 0.88, y: 22, rotate: -1.5 }}
            transition={{ type: "spring", damping: 24, stiffness: 380 }}
            onClick={(event) => event.stopPropagation()}
            className="w-full max-w-[360px] max-h-[78vh] bg-[#FAFAF9] border-[4px] border-white shadow-[0_20px_60px_rgba(0,0,0,0.1),_0_0_0_1px_rgba(0,0,0,0.05)] rounded-[40px] flex flex-col relative overflow-hidden"
          >
            <div className="flex justify-between items-center px-6 pt-6 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#99F6E4] rounded-[14px] flex items-center justify-center rotate-[-6deg] border-2 border-white shadow-inner">
                  <Rows2 className="w-5 h-5 text-[#0F766E]" />
                </div>
                <div>
                  <h2 className="text-[20px] font-black text-[#334155] tracking-tight">会话列表</h2>
                  <p className="text-[12px] font-bold text-[#64748B]">快速切换到任意对话</p>
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
            <div className="px-6 pb-4">
              <motion.button
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.98 }}
                onClick={onCreateSession}
                className="w-full rounded-[22px] bg-gradient-to-r from-[#E0F2FE] to-[#F3E8FF] border-2 border-white px-4 py-3 flex items-center justify-between shadow-[0_10px_20px_rgba(59,130,246,0.12)]"
              >
                <span className="text-[14px] font-black text-[#334155]">创建新对话</span>
                <MessageSquarePlus className="w-5 h-5 text-[#0EA5E9]" />
              </motion.button>
            </div>
            <div className="px-6 pb-6 overflow-y-auto space-y-2 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              {sortedSessions.length === 0 ? (
                <div className="rounded-[20px] bg-white/80 border-2 border-white px-4 py-6 text-center text-[13px] font-bold text-[#64748B]">
                  还没有历史会话，先发一条消息吧
                </div>
              ) : (
                sortedSessions.map((item) => {
                  const active = item.id === activeSessionId;
                  return (
                    <motion.button
                      key={item.id}
                      whileHover={{ y: -1.5 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => onSelectSession(item.id)}
                      className={`w-full text-left rounded-[20px] border-2 px-4 py-3 transition-all ${
                        active
                          ? "bg-white border-[#0EA5E9] shadow-[0_10px_18px_rgba(14,165,233,0.2)]"
                          : "bg-white/80 border-white hover:border-[#E2E8F0]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-[14px] font-black text-[#334155] truncate">{item.title || "新对话"}</p>
                          <div className="mt-1 flex items-center gap-1.5 text-[11px] font-bold text-[#64748B]">
                            <Clock3 className="w-3.5 h-3.5" />
                            <span>{formatRelativeTime(item.updatedAt)}</span>
                          </div>
                        </div>
                        {active && (
                          <span className="text-[11px] font-black text-[#0EA5E9] bg-[#E0F2FE] rounded-full px-2 py-0.5">
                            当前
                          </span>
                        )}
                      </div>
                    </motion.button>
                  );
                })
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
