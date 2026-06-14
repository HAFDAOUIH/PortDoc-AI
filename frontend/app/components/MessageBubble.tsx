"use client";

/* A single chat turn. User turns are simple bubbles; assistant turns carry the
   streaming step indicator, governance notice, grounded answer with clickable
   citations, source cards, the business-value ribbon, follow-up chips and feedback. */

import { motion } from "framer-motion";
import { Lock, ShieldOff, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import type { Persona, Source } from "@/lib/api";
import { SourceCard } from "./SourceCard";
import { ValueRibbon } from "./ValueRibbon";
import { useToast } from "./Toast";
import { clr } from "./ui";
import type { Msg } from "./types";

const FOLLOW_UPS = [
  "Donne plus de détails",
  "Quelles sont les exceptions ?",
  "Et au niveau de sûreté inférieur ?",
];

function Citations({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  return (
    <>
      {text.split(/(\[\d+\])/g).map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        return m ? (
          <button
            key={i}
            onClick={() => onCite(Number(m[1]))}
            className="mx-0.5 -translate-y-0.5 rounded bg-cyan-500/20 px-1 align-super text-[10px] font-bold text-cyan-300 transition hover:bg-cyan-500/40"
          >
            {m[1]}
          </button>
        ) : (
          <span key={i}>{p}</span>
        );
      })}
    </>
  );
}

/** Plain-language governance line: who's signed in + what they may consult. */
function GovernanceContext({ persona }: { persona?: Persona }) {
  if (!persona) return null;
  return (
    <p className="text-[11px] text-slate-500">
      Signed in as <span className="text-slate-300">{persona.name}</span> · {persona.role} — you may
      consult <span className="text-slate-300">{clr(persona.clearance).label}</span> documents.
    </p>
  );
}

function Feedback({ msgKey }: { msgKey: string }) {
  const toast = useToast();
  const [picked, setPicked] = useState<null | "up" | "down">(null);

  const vote = (v: "up" | "down") => {
    setPicked(v);
    try {
      // → DB in production. For the demo we keep a simple localStorage log.
      const KEY = "portdoc.feedback.v1";
      const log = JSON.parse(window.localStorage.getItem(KEY) || "{}");
      log[msgKey] = { vote: v, at: Date.now() };
      window.localStorage.setItem(KEY, JSON.stringify(log));
    } catch {
      /* non-fatal */
    }
    toast("Merci — retour enregistré");
  };

  return (
    <div className="flex items-center gap-1.5" title="Your feedback helps the assistant improve">
      <button
        onClick={() => vote("up")}
        aria-label="Helpful"
        className={`rounded-lg p-1.5 transition hover:bg-white/5 ${
          picked === "up" ? "text-emerald-400" : "text-slate-500 hover:text-slate-300"
        }`}
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => vote("down")}
        aria-label="Not helpful"
        className={`rounded-lg p-1.5 transition hover:bg-white/5 ${
          picked === "down" ? "text-rose-400" : "text-slate-500 hover:text-slate-300"
        }`}
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function MessageBubble({
  m,
  idx,
  highlight,
  onCite,
  onOpenSource,
  onFollowUp,
  isLast,
  busy,
}: {
  m: Msg;
  idx: number;
  highlight: { msg: number; n: number } | null;
  onCite: (msg: number, n: number) => void;
  onOpenSource: (s: Source) => void;
  onFollowUp: (q: string) => void;
  isLast: boolean;
  busy: boolean;
}) {
  if (m.role === "user") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="mb-5 flex justify-end"
      >
        <div className="max-w-[80%] rounded-2xl rounded-br-sm border border-cyan-400/20 bg-gradient-to-br from-cyan-600 to-blue-600 px-4 py-2.5 text-sm text-white shadow-lg shadow-cyan-900/20">
          {m.content}
        </div>
      </motion.div>
    );
  }

  const completed = m.done && !m.refused;
  const showFollowUps = completed && isLast && !busy;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mb-6 space-y-2.5"
    >
      {m.step && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <span className="h-2 w-2 animate-ping rounded-full bg-cyan-400" />
          <span className="shimmer">{m.step}</span>
        </div>
      )}

      {/* Access control as governance — plain language, least-privilege framing. */}
      {m.hidden !== undefined && m.hidden > 0 && (
        <div className="space-y-1 rounded-xl border border-rose-500/25 bg-rose-500/5 px-3.5 py-2.5">
          <div className="flex items-center gap-2 text-xs font-medium text-rose-300">
            <Lock className="h-3.5 w-3.5" />
            {m.hidden} document{m.hidden === 1 ? "" : "s"} beyond your role {m.hidden === 1 ? "was" : "were"} excluded
          </div>
          <GovernanceContext persona={m.persona} />
        </div>
      )}

      {m.content && (
        <div
          className={`rounded-2xl rounded-bl-sm border px-4 py-3 text-sm leading-relaxed backdrop-blur-sm ${
            m.refused
              ? "border-amber-500/30 bg-amber-500/10 text-amber-100"
              : "border-white/10 bg-white/5 text-slate-200"
          }`}
        >
          {m.refused ? (
            <div className="flex items-start gap-2">
              <ShieldOff className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
              <div>
                <div className="font-medium">No answer</div>
                <p className="mt-0.5 text-amber-100/80">
                  This isn&apos;t in the documents available at your clearance.
                </p>
              </div>
            </div>
          ) : (
            <Citations text={m.content} onCite={(n) => onCite(idx, n)} />
          )}
        </div>
      )}

      {m.sources && m.sources.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {m.sources.map((s, i) => (
            <SourceCard
              key={s.chunk_id}
              s={s}
              index={i}
              hot={highlight?.msg === idx && highlight?.n === s.n}
              onOpen={onOpenSource}
            />
          ))}
        </div>
      )}

      {completed && (
        <>
          <ValueRibbon nSources={m.citations?.length ?? m.sources?.length ?? 0} tookMs={m.took_ms ?? 0} />
          <div className="flex items-center justify-between pt-0.5">
            <span className="text-[10px] text-slate-600">Was this helpful?</span>
            <Feedback msgKey={`${idx}:${m.content.slice(0, 24)}`} />
          </div>
        </>
      )}

      {showFollowUps && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
          className="flex flex-wrap gap-2 pt-1"
        >
          {FOLLOW_UPS.map((q) => (
            <button
              key={q}
              onClick={() => onFollowUp(q)}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] text-slate-300 transition hover:border-cyan-500/40 hover:text-cyan-200"
            >
              {q}
            </button>
          ))}
        </motion.div>
      )}
    </motion.div>
  );
}
