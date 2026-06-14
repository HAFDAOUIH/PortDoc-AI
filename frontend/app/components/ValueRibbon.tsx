"use client";

/* Business-value ribbon under a completed answer. Plain language for managers:
   how many official documents backed the answer, how fast, and a rough estimate
   of manual research time saved. No RAG/ML jargon. */

import { motion } from "framer-motion";
import { CheckCircle2, Clock, Sparkles } from "lucide-react";

export function ValueRibbon({
  nSources,
  tookMs,
}: {
  nSources: number;
  tookMs: number;
}) {
  const sec = Math.max(1, Math.round((tookMs || 0) / 1000));
  // Rough, deliberately conservative estimate of manual search time displaced.
  const estMinutes = Math.min(30, 12 + 4 * nSources);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: 0.05 }}
      className="flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3.5 py-2 text-[11px] text-slate-300"
    >
      <span className="inline-flex items-center gap-1.5 font-medium text-emerald-300">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Sourced from {nSources} official document{nSources === 1 ? "" : "s"}
      </span>
      <span className="inline-flex items-center gap-1.5 text-slate-400">
        <Clock className="h-3.5 w-3.5" />
        {sec}s
      </span>
      <span className="inline-flex items-center gap-1.5 text-slate-400">
        <Sparkles className="h-3.5 w-3.5 text-cyan-400" />≈ {estMinutes} min of manual search saved
      </span>
    </motion.div>
  );
}
