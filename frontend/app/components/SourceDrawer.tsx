"use client";

/* Right-side slide-in drawer showing the full source passage.
   Opens from a citation [n] or a source card; closes on ✕ / Esc / backdrop click. */

import { AnimatePresence, motion } from "framer-motion";
import { FileText, Hash, ScanLine, Table2, X } from "lucide-react";
import { useEffect } from "react";
import type { Source } from "@/lib/api";
import { ClrChip, Tag, VerifiedBadge } from "./ui";

export function SourceDrawer({
  source,
  onClose,
}: {
  source: Source | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!source) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [source, onClose]);

  return (
    <AnimatePresence>
      {source && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          />
          <motion.aside
            key="drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 360, damping: 36 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-white/10 bg-slate-950/95 shadow-2xl backdrop-blur-xl"
            role="dialog"
            aria-modal="true"
          >
            <header className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-500/15 font-mono text-xs font-bold text-cyan-300">
                  {source.n}
                </span>
                <span className="text-sm font-semibold">Source detail</span>
              </div>
              <button
                onClick={onClose}
                aria-label="Close"
                className="rounded-lg p-1.5 text-slate-400 transition hover:bg-white/5 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
              <div>
                <div className="mb-2 flex items-center gap-2 text-slate-200">
                  <FileText className="h-4 w-4 text-cyan-400" />
                  <span className="text-sm font-semibold">
                    {source.authority} · {source.doc_type} {source.year}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <VerifiedBadge />
                  <ClrChip level={source.clearance} withLabel />
                  <span className="inline-flex items-center gap-1 rounded border border-slate-600/40 bg-slate-700/30 px-1.5 py-0.5 text-[10px] text-slate-300">
                    <Hash className="h-3 w-3" /> p.{source.page_start}
                  </span>
                  {source.from_ocr && (
                    <Tag tone="violet">
                      <span className="inline-flex items-center gap-1">
                        <ScanLine className="h-3 w-3" /> Scanned (OCR)
                      </span>
                    </Tag>
                  )}
                  {source.is_table && (
                    <Tag tone="sky">
                      <span className="inline-flex items-center gap-1">
                        <Table2 className="h-3 w-3" /> Table
                      </span>
                    </Tag>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-wide text-slate-500">
                  <span>Cited passage</span>
                  <span className="font-mono text-slate-600">
                    relevance {source.score.toFixed(2)}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
                  {source.snippet}
                </p>
              </div>

              <p className="text-[11px] leading-relaxed text-slate-500">
                This passage is part of an official document held on-premise. The assistant only
                answers from passages like this — nothing is generated without a source.
              </p>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
