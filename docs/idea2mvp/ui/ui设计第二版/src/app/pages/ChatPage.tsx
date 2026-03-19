import React, { useState, useRef, useEffect } from "react";
import { SmilePlus, Sparkles, Target, Beaker } from "lucide-react";
import { MessageBubble, type Message } from "../components/ui/MessageBubble";
import { InputArea } from "../components/ui/InputArea";
import { PasteModal } from "../components/modals/PasteModal";
import { NudgeNotification } from "../components/ui/NudgeNotification";
import { DashboardModal } from "../components/modals/DashboardModal";
import { EvalModal } from "../components/modals/EvalModal";
import { motion } from "motion/react";

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "ai",
      content: "哈喽呀！我是你的学习搭子，今天我们要搞定什么神仙知识？✨",
      timestamp: new Date(),
    },
  ]);

  const [isTyping, setIsTyping] = useState(false);
  const [isPasteModalOpen, setIsPasteModalOpen] = useState(false);
  const [isDashboardOpen, setIsDashboardOpen] = useState(false);
  const [isEvalOpen, setIsEvalOpen] = useState(false);
  const [nudgeMessage, setNudgeMessage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSendMessage = (text: string) => {
    const newUserMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newUserMessage]);
    setIsTyping(true);

    setTimeout(() => {
      setIsTyping(false);
      const newAiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "ai",
        content: getSimulatedResponse(text),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, newAiMessage]);
    }, 1200 + Math.random() * 800);
  };

  const handleLearn = (content: string, isImage?: boolean) => {
    const systemMsg: Message = {
      id: Date.now().toString(),
      role: "system",
      content: isImage ? `图片摄入完毕 📸` : `知识吸收完毕 💖`,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, systemMsg]);
    setIsTyping(true);

    setTimeout(() => {
      setIsTyping(false);
      const newAiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "ai",
        content: isImage 
          ? "我看清楚啦！这张图里的信息我已经掌握，有不懂的随时问我哦~ 🔍"
          : "我看完了！感觉这块知识点超有意思的，我已经把它贴在小本本上了，晚点我们再来考考你！🚀",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, newAiMessage]);
    }, 1500);
  };

  const getSimulatedResponse = (text: string) => {
    const lower = text.toLowerCase();
    if (lower.includes("你好") || lower.includes("hi")) {
      return "嗨咯~ 随时准备好帮你理清思路啦！冲冲冲！";
    }
    if (lower.includes("图片") || lower.includes("图")) {
      return "图片里包含了很棒的信息！需要我帮你解析里面的核心概念吗？";
    }
    if (lower.includes("不懂") || lower.includes("太难") || lower.includes("卡住")) {
      return "摸摸头，这题确实有点小调皮！我们把它拆成两半来看怎么样？或者我给你打个比方？";
    }
    if (lower.includes("谢谢") || lower.includes("懂了")) {
      return "太棒啦！给你一朵小红花 🌸，我们继续保持！";
    }
    return "收到收到！我先记下啦，有不懂的随时戳我哦。";
  };

  const triggerNudge = () => {
    setNudgeMessage("嘿！关于你早上看的那些内容... 猜猜如果倒过来想会怎样？是不是发现了新大陆？😎");
  };

  const handleNudgeClick = () => {
    if (nudgeMessage) {
      const msg: Message = {
        id: Date.now().toString(),
        role: "ai",
        content: nudgeMessage,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, msg]);
      setNudgeMessage(null);
    }
  };

  return (
    <div className="flex flex-col h-screen w-full bg-[#FEF2F2] sm:p-6 md:p-10 overflow-hidden items-center justify-center font-sans">
      
      {/* Playful Background Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
         <motion.div 
           animate={{ y: [0, -20, 0], rotate: [0, 5, 0] }} 
           transition={{ duration: 6, repeat: Infinity }}
           className="absolute top-[10%] left-[20%] w-[400px] h-[400px] bg-[#FFE4E6] rounded-full mix-blend-multiply blur-3xl opacity-60" 
         />
         <motion.div 
           animate={{ y: [0, 20, 0], rotate: [0, -5, 0] }} 
           transition={{ duration: 8, repeat: Infinity }}
           className="absolute bottom-[10%] right-[15%] w-[500px] h-[500px] bg-[#E0E7FF] rounded-full mix-blend-multiply blur-3xl opacity-60" 
         />
      </div>

      {/* iOS App Container Simulation (Dopamine Style) */}
      <div className="relative w-full h-full sm:max-w-[400px] sm:max-h-[850px] bg-[#FAFAF9] sm:border-[12px] sm:border-white overflow-hidden flex flex-col sm:rounded-[56px] z-10 isolate shadow-[0_20px_50px_rgba(0,0,0,0.05),_0_0_0_1px_rgba(0,0,0,0.02)]">
        
        {/* Dynamic Island Area */}
        <div className="absolute top-0 w-full h-10 z-50 flex justify-center hidden sm:flex pt-3 pointer-events-none">
          <div className="w-[100px] h-[26px] bg-[#1E293B] rounded-full shadow-sm" />
        </div>

        {/* Floating Bubble Header (Instead of full width header) */}
        <div className="absolute top-12 sm:top-14 left-4 z-40">
          <motion.div 
            whileHover={{ scale: 1.05, y: -2 }}
            className="group bg-white/90 backdrop-blur-md px-4 py-2.5 rounded-[24px] shadow-[0_8px_20px_rgba(0,0,0,0.04)] hover:shadow-[0_12px_25px_rgba(244,114,182,0.15)] border-2 border-white flex items-center gap-3 cursor-pointer transition-all"
          >
            <div className="relative">
              <motion.div 
                animate={{ rotate: [3, -3, 3] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                className="w-9 h-9 bg-gradient-to-tr from-[#A855F7] to-[#F472B6] rounded-[14px] flex items-center justify-center shadow-inner relative z-10"
              >
                 <SmilePlus className="w-5 h-5 text-white" />
              </motion.div>
              {/* Emotion Blinking Dots */}
              <motion.div
                animate={{ scale: [1, 1.5, 1], opacity: [0, 1, 0] }}
                transition={{ duration: 1.5, repeat: Infinity, delay: 0.5 }}
                className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-[#FDE047] rounded-full z-20"
              />
              <motion.div
                animate={{ scale: [1, 1.5, 1], opacity: [0, 1, 0] }}
                transition={{ duration: 1.5, repeat: Infinity, delay: 1 }}
                className="absolute -bottom-0.5 -left-1 w-2 h-2 bg-[#38BDF8] rounded-full z-20"
              />
            </div>
            <div className="flex flex-col">
              <span className="text-[16px] font-black text-[#334155] tracking-tight leading-none group-hover:text-[#F472B6] transition-colors">MindShadow</span>
              <motion.span 
                animate={{ opacity: [0.7, 1, 0.7] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="text-[11px] font-bold text-[#F472B6] mt-1 flex items-center gap-1"
              >
                在线待命中 <span className="inline-block w-1.5 h-1.5 bg-[#34D399] rounded-full" />
              </motion.span>
            </div>
          </motion.div>
        </div>

        {/* Floating Side Tools Toolbar */}
        <div className="absolute top-12 sm:top-14 right-4 z-40 flex flex-col gap-3">
          <motion.button
            whileHover={{ scale: 1.1, rotate: 10 }}
            whileTap={{ scale: 0.9 }}
            onClick={triggerNudge}
            title="触发轻推 (戳我!)"
            className="w-11 h-11 bg-white/90 backdrop-blur-md rounded-[16px] shadow-[0_8px_20px_rgba(0,0,0,0.04)] border-[2px] border-white flex items-center justify-center text-[#FBBF24] hover:bg-[#FEF9C3] transition-colors"
          >
            <Sparkles className="w-5 h-5 fill-[#FDE047]" />
          </motion.button>

          <motion.button
            whileHover={{ scale: 1.1, rotate: -5 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setIsDashboardOpen(true)}
            title="周目标看板"
            className="w-11 h-11 bg-white/90 backdrop-blur-md rounded-[16px] shadow-[0_8px_20px_rgba(0,0,0,0.04)] border-[2px] border-white flex items-center justify-center text-[#FF9A9E] hover:bg-[#FFE4E6] transition-colors"
          >
            <Target className="w-5 h-5 stroke-[2.5]" />
          </motion.button>

          <motion.button
            whileHover={{ scale: 1.1, rotate: 5 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setIsEvalOpen(true)}
            title="A/B 评测台"
            className="w-11 h-11 bg-white/90 backdrop-blur-md rounded-[16px] shadow-[0_8px_20px_rgba(0,0,0,0.04)] border-[2px] border-white flex items-center justify-center text-[#38BDF8] hover:bg-[#E0F2FE] transition-colors"
          >
            <Beaker className="w-5 h-5 stroke-[2.5]" />
          </motion.button>
        </div>

        {/* Nudge Notification (Pop-up bubble style) */}
        <NudgeNotification
          isOpen={!!nudgeMessage}
          message={nudgeMessage || ""}
          onClose={() => setNudgeMessage(null)}
          onClick={handleNudgeClick}
        />

        {/* Chat Area - Playful Zigzag Layout */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden px-4 pt-[140px] pb-4 scroll-smooth flex flex-col z-10 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {isTyping && (
            <MessageBubble
              message={{
                id: "typing",
                role: "ai",
                content: "",
                timestamp: new Date(),
                isTyping: true,
              }}
            />
          )}
          <div ref={messagesEndRef} className="h-4 shrink-0" />
        </div>

        {/* Floating Playful Input Area */}
        <InputArea
          onSendMessage={handleSendMessage}
          onOpenOptions={() => setIsPasteModalOpen(true)}
          isInputDisabled={isTyping}
        />

        {/* Overlays - Pop-up Cards */}
        <PasteModal
          isOpen={isPasteModalOpen}
          onClose={() => setIsPasteModalOpen(false)}
          onLearn={handleLearn}
        />
        <DashboardModal 
          isOpen={isDashboardOpen} 
          onClose={() => setIsDashboardOpen(false)} 
        />
        <EvalModal 
          isOpen={isEvalOpen} 
          onClose={() => setIsEvalOpen(false)} 
        />

      </div>
    </div>
  );
}
