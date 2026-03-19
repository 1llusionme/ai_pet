import { motion } from "motion/react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { Sparkle, Heart } from "lucide-react";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type MessageRole = "user" | "ai" | "system";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  isTyping?: boolean;
}

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === "system") {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.8, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="w-full flex justify-center my-6"
      >
        <div className="flex items-center gap-1.5 px-4 py-2 bg-white/60 backdrop-blur-md rounded-full shadow-[0_4px_12px_rgba(255,107,158,0.15)] border-2 border-white">
          <Sparkle className="w-4 h-4 text-[#FF6B9E]" />
          <span className="text-[13px] font-bold text-[#FF6B9E] tracking-wider uppercase">
            {message.content}
          </span>
        </div>
      </motion.div>
    );
  }

  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 30, rotate: isUser ? 2 : -2 }}
      animate={{ opacity: 1, y: 0, rotate: 0 }}
      transition={{ type: "spring", damping: 20, stiffness: 400 }}
      className={cn(
        "flex w-full mb-6",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div className={cn(
        "relative max-w-[80%] flex flex-col group",
        isUser ? "items-end" : "items-start"
      )}>
        {/* Avatar badge floating on top corner */}
        {!isUser && (
          <div className="absolute -top-4 -left-3 z-10 w-9 h-9 bg-[#A855F7] rounded-[12px] rotate-[-6deg] flex items-center justify-center border-[3px] border-white shadow-md">
            <span className="text-white font-black text-[16px]">M</span>
          </div>
        )}
        {isUser && (
          <div className="absolute -top-4 -right-3 z-10 w-9 h-9 bg-[#FF6B9E] rounded-[12px] rotate-[6deg] flex items-center justify-center border-[3px] border-white shadow-md">
            <Heart className="w-5 h-5 text-white fill-white" />
          </div>
        )}

        {/* Bubble container */}
        <div
          className={cn(
            "px-5 py-4 text-[16px] font-medium leading-[1.5] border-[3px] border-white relative",
            isUser
              ? "bg-gradient-to-br from-[#FF9A9E] to-[#FF6B9E] text-white rounded-[28px] rounded-tr-[10px] shadow-[4px_6px_0px_rgba(255,107,158,0.3)] mt-2 mr-2"
              : "bg-white text-[#4A4A68] rounded-[28px] rounded-tl-[10px] shadow-[4px_6px_0px_rgba(168,85,247,0.2)] mt-2 ml-2"
          )}
        >
          {message.isTyping ? (
            <div className="flex items-center space-x-1.5 h-6 px-2">
              <motion.div
                animate={{ y: [0, -8, 0], scale: [1, 1.2, 1] }}
                transition={{ repeat: Infinity, duration: 0.8, delay: 0 }}
                className="w-3 h-3 bg-[#A855F7] rounded-full"
              />
              <motion.div
                animate={{ y: [0, -8, 0], scale: [1, 1.2, 1] }}
                transition={{ repeat: Infinity, duration: 0.8, delay: 0.15 }}
                className="w-3 h-3 bg-[#38BDF8] rounded-full"
              />
              <motion.div
                animate={{ y: [0, -8, 0], scale: [1, 1.2, 1] }}
                transition={{ repeat: Infinity, duration: 0.8, delay: 0.3 }}
                className="w-3 h-3 bg-[#FF6B9E] rounded-full"
              />
            </div>
          ) : (
            message.content
          )}
        </div>
      </div>
    </motion.div>
  );
}
