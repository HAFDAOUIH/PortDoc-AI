"use client";

/* Manager-facing "what does it know?" view: the corpus rendered as a grid of
   glass cards, grouped by clearance. Fetches GET /documents. */

import { motion } from "framer-motion";
import { FileText, Layers, Library, ScanLine } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type DocumentMeta } from "@/lib/api";
import { ClrChip, glass } from "./ui";

const LANG: Record<string, string> = { fr: "Français", en: "English", ar: "العربية" };

function DocCard({ d, i }: { d: DocumentMeta; i: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(i * 0.03, 0.3) }}
      whileHover={{ y: -3 }}
      className={glass("flex flex-col p-4 transition-colors hover:border-cyan-500/30")}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/5">
          <FileText className="h-4 w-4 text-cyan-400" />
        </span>
        <ClrChip level={d.clearance} withLabel />
      </div>

      <h3 className="text-sm font-semibold leading-snug text-slate-100">
        {d.authority} {d.doc_type} {d.year}
      </h3>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="rounded border border-slate-600/40 bg-slate-700/30 px-1.5 py-0.5 text-[9px] font-medium uppercase text-slate-300">
          {LANG[d.lang] ?? d.lang}
        </span>
        {d.from_ocr && (
          <span className="inline-flex items-center gap-1 rounded border border-violet-500/30 bg-violet-500/15 px-1.5 py-0.5 text-[9px] font-medium text-violet-300">
            <ScanLine className="h-2.5 w-2.5" /> Scanned
          </span>
        )}
      </div>

      <div className="mt-auto flex items-center gap-1.5 pt-3 text-[11px] text-slate-500">
        <Layers className="h-3 w-3" />
        {d.n_chunks.toLocaleString()} indexed passages
      </div>
    </motion.div>
  );
}

export function DocumentLibrary() {
  const [docs, setDocs] = useState<DocumentMeta[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .documents()
      .then(setDocs)
      .catch(() => setError(true));
  }, []);

  if (error)
    return <div className="p-8 text-sm text-slate-500">Could not load the knowledge base.</div>;
  if (!docs) return <div className="p-8 text-sm text-slate-500">Loading…</div>;

  const totalPassages = docs.reduce((a, d) => a + d.n_chunks, 0);

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-1 flex items-center gap-2">
          <Library className="h-5 w-5 text-cyan-400" />
          <h1 className="text-lg font-bold">Knowledge base</h1>
        </div>
        <p className="mb-6 text-sm text-slate-400">
          {docs.length} official document{docs.length === 1 ? "" : "s"} ·{" "}
          {totalPassages.toLocaleString()} indexed passages — everything the assistant can draw on,
          held entirely on-premise.
        </p>

        {docs.length === 0 ? (
          <p className="text-sm text-slate-500">No documents indexed yet.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {docs.map((d, i) => (
              <DocCard key={d.doc_id} d={d} i={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
