"use client";

/* Trust-first source card: leads with the DOCUMENT identity, carries a green
   "Verified source" badge + clearance badge, and demotes the numeric relevance
   score to a muted mono detail. Clicking opens the source drawer. */

import { motion } from "framer-motion";
import { ScanLine, Table2 } from "lucide-react";
import type { Source } from "@/lib/api";
import { ClrChip, Tag, VerifiedBadge } from "./ui";

export function SourceCard({
  s,
  hot,
  index,
  onOpen,
}: {
  s: Source;
  hot: boolean;
  index: number;
  onOpen: (s: Source) => void;
}) {
  return (
    <motion.button
      type="button"
      onClick={() => onOpen(s)}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: Math.min(index * 0.04, 0.2) }}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.98 }}
      className={`group w-full rounded-xl border p-3 text-left backdrop-blur-sm transition-colors ${
        hot
          ? "border-cyan-400/60 bg-cyan-500/10 shadow-[0_0_0_1px_rgba(34,211,238,0.3)]"
          : "border-white/10 bg-white/5 hover:border-cyan-500/30"
      }`}
    >
      <div className="mb-1.5 flex items-center gap-1.5">
        <span className="flex h-5 w-5 items-center justify-center rounded bg-cyan-500/15 font-mono text-[10px] font-bold text-cyan-300">
          {s.n}
        </span>
        <VerifiedBadge />
        <ClrChip level={s.clearance} />
        <span className="ml-auto font-mono text-[9px] text-slate-600">
          rel {s.score.toFixed(2)}
        </span>
      </div>

      <div className="text-[11px] font-medium text-slate-200">
        {s.authority} · {s.doc_type} {s.year} · p.{s.page_start}
      </div>

      <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-slate-400">{s.snippet}</p>

      {(s.from_ocr || s.is_table) && (
        <div className="mt-1.5 flex gap-1">
          {s.from_ocr && (
            <Tag tone="violet">
              <span className="inline-flex items-center gap-0.5">
                <ScanLine className="h-2.5 w-2.5" /> OCR
              </span>
            </Tag>
          )}
          {s.is_table && (
            <Tag tone="sky">
              <span className="inline-flex items-center gap-0.5">
                <Table2 className="h-2.5 w-2.5" /> TABLE
              </span>
            </Tag>
          )}
        </div>
      )}
    </motion.button>
  );
}
