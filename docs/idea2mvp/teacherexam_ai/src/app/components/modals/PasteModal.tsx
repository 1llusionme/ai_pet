import { motion, AnimatePresence } from "motion/react";
import { X, Rocket } from "lucide-react";
import { useState, useRef } from "react";

interface PasteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLearn: (content: string) => void;
  onPickImage: (file: File) => Promise<void> | void;
}

export function PasteModal({ isOpen, onClose, onLearn, onPickImage }: PasteModalProps) {
  const [content, setContent] = useState("");
  const [view, setView] = useState<"options" | "paste" | "image">("options");
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [selectedImageFile, setSelectedImageFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleLearn = () => {
    if (view === "paste" && content.trim()) {
      onLearn(content.trim());
      closeModal();
    }
  };

  const handleImageLearn = async () => {
    if (!selectedImageFile) {
      return;
    }
    await onPickImage(selectedImageFile);
    closeModal();
  };

  const closeModal = () => {
    setContent("");
    setPreviewImage(null);
    setSelectedImageFile(null);
    setView("options");
    onClose();
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setPreviewImage(url);
      setSelectedImageFile(file);
      setView("image");
    }
    e.target.value = "";
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
          onClick={closeModal}
        >
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-[10%] left-[10%] w-8 h-8 bg-[#FF6B9E] rounded-full opacity-20 blur-sm" />
            <div className="absolute top-[30%] right-[20%] w-12 h-12 bg-[#38BDF8] rounded-full opacity-20 blur-sm" />
            <div className="absolute bottom-[20%] left-[30%] w-16 h-16 bg-[#FCD34D] rounded-full opacity-20 blur-sm" />
          </div>

          <motion.div
            initial={{ scale: 0.8, y: 50, rotate: -5 }}
            animate={{ scale: 1, y: 0, rotate: 0 }}
            exit={{ scale: 0.8, y: 50, rotate: 5 }}
            transition={{ type: "spring", damping: 20, stiffness: 350 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[360px] bg-white border-[4px] border-white shadow-[0_20px_60px_rgba(0,0,0,0.1),_0_0_0_1px_rgba(0,0,0,0.05)] rounded-[40px] flex flex-col relative overflow-hidden"
          >
            <div className="flex justify-end items-center p-4 pb-0 relative z-10">
              <motion.button
                whileTap={{ scale: 0.8, rotate: 90 }}
                onClick={closeModal}
                className="w-10 h-10 bg-[#F1F5F9] rounded-full flex items-center justify-center text-[#64748B] hover:bg-[#E2E8F0] transition-colors"
              >
                <X className="w-6 h-6 stroke-[3]" />
              </motion.button>
            </div>
            <div className="flex-1 p-6 pt-4 relative z-10 max-h-[60vh] overflow-y-auto">
              {view === "options" ? (
                <div className="grid grid-cols-2 gap-4">
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    ref={fileInputRef}
                    onChange={handleImageChange}
                  />
                  <motion.button
                    whileHover={{ y: -4 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => fileInputRef.current?.click()}
                    className="flex flex-col items-center justify-center gap-3 bg-[#FEF3C7] p-6 rounded-[32px] text-center transition-all col-span-2 sm:col-span-1 border-2 border-transparent hover:border-[#FCD34D]"
                  >
                    <div className="w-16 h-16 bg-white rounded-[20px] flex items-center justify-center text-[#D97706] shadow-sm rotate-3">
                      <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
                    </div>
                    <div>
                      <h3 className="text-[18px] font-black text-[#B45309]">拍一下</h3>
                      <p className="text-[12px] font-bold text-[#D97706] mt-1">记录书本难题</p>
                    </div>
                  </motion.button>
                  <motion.button
                    whileHover={{ y: -4 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setView("paste")}
                    className="flex flex-col items-center justify-center gap-3 bg-[#E0F2FE] p-6 rounded-[32px] text-center transition-all col-span-2 sm:col-span-1 border-2 border-transparent hover:border-[#7DD3FC]"
                  >
                    <div className="w-16 h-16 bg-white rounded-[20px] flex items-center justify-center text-[#38BDF8] shadow-sm -rotate-3">
                      <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
                    </div>
                    <div>
                      <h3 className="text-[18px] font-black text-[#0284C7]">传文件</h3>
                      <p className="text-[12px] font-bold text-[#0EA5E9] mt-1">导入相册或文本</p>
                    </div>
                  </motion.button>
                </div>
              ) : view === "paste" ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex flex-col gap-4 h-[300px]"
                >
                  <div className="relative flex-1">
                    <textarea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      placeholder="把笔记粘贴在这里吧！(最多5000字)"
                      className="w-full h-full p-5 bg-[#F8FAFC] border-2 border-[#E2E8F0] rounded-[28px] resize-none focus:outline-none focus:border-[#38BDF8] focus:bg-white text-[#334155] font-medium leading-relaxed transition-all"
                      maxLength={5000}
                    />
                    <div className="absolute bottom-3 right-3 text-[13px] font-bold text-[#94A3B8] bg-white px-3 py-1 rounded-full shadow-sm">
                      {content.length}/5000
                    </div>
                  </div>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={handleLearn}
                    disabled={!content.trim()}
                    className="w-full py-4 bg-[#FF6B9E] text-white font-black text-[18px] tracking-wide rounded-[24px] shadow-[0_8px_20px_rgba(255,107,158,0.3)] hover:shadow-[0_12px_25px_rgba(255,107,158,0.4)] transition-all disabled:opacity-50 flex justify-center items-center gap-2"
                  >
                    <Rocket className="w-6 h-6 stroke-[2.5]" />
                    发射知识！
                  </motion.button>
                </motion.div>
              ) : (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex flex-col gap-4 h-[300px]"
                >
                  <div className="relative flex-1 bg-[#F8FAFC] border-2 border-[#E2E8F0] rounded-[28px] overflow-hidden flex items-center justify-center p-2">
                    {previewImage ? (
                      <img src={previewImage} alt="Preview" className="max-w-full max-h-full rounded-[20px] object-contain shadow-sm" />
                    ) : (
                      <span className="text-[#94A3B8] font-bold">没有图片</span>
                    )}
                  </div>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={handleImageLearn}
                    disabled={!selectedImageFile}
                    className="w-full py-4 bg-[#A855F7] text-white font-black text-[18px] tracking-wide rounded-[24px] shadow-[0_8px_20px_rgba(168,85,247,0.3)] hover:shadow-[0_12px_25px_rgba(168,85,247,0.4)] transition-all disabled:opacity-50 flex justify-center items-center gap-2"
                  >
                    <Rocket className="w-6 h-6 stroke-[2.5]" />
                    开始看图！
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
