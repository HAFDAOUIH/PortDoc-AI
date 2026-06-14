"use client";

/* Tiny transient-toast system. A provider holds a queue; useToast() pushes a
   message that auto-dismisses. Used for the answer-feedback confirmation. */

import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";

type ToastItem = { id: number; message: string };
type ToastCtx = (message: string) => void;

const Ctx = createContext<ToastCtx>(() => {});

export function useToast() {
  return useContext(Ctx);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((message: string) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs, { id, message }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 2400);
  }, []);

  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 flex-col items-center gap-2">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.96 }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              className="pointer-events-auto flex items-center gap-2 rounded-full border border-white/10 bg-slate-900/90 px-4 py-2 text-sm text-slate-100 shadow-xl backdrop-blur-md"
            >
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              {t.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </Ctx.Provider>
  );
}
