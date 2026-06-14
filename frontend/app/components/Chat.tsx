"use client";

/* The streaming chat surface. Reads/writes its message list through the
   conversation store (localStorage-persisted) so switching conversations is
   transparent to the streaming logic — each stream targets a captured
   conversation id, never a moving "current index". */

import { motion } from "framer-motion";
import { ArrowUp, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat, type Persona, type Source, type StreamEvent } from "@/lib/api";
import { MessageBubble } from "./MessageBubble";
import { SourceDrawer } from "./SourceDrawer";
import type { Msg } from "./types";

const EXAMPLES = [
  "Que doit faire l'installation portuaire au niveau de sûreté 3 ?",
  "Comment notifier un navire transportant des marchandises dangereuses ?",
  "Quelle pièce d'identité est requise pour accéder au port ?",
];

export function Chat({
  persona,
  messages,
  onMessages,
  ensureConversation,
}: {
  persona: Persona | null;
  messages: Msg[];
  // updater + the persona id the conversation is bound to
  onMessages: (id: string, updater: (prev: Msg[]) => Msg[], personaId: string | null) => void;
  // returns the active conversation id, creating one if needed
  ensureConversation: () => string;
}) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [highlight, setHighlight] = useState<{ msg: number; n: number } | null>(null);
  const [drawer, setDrawer] = useState<Source | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" });
  }, [messages]);

  const send = useCallback(
    async (q: string) => {
      if (!q.trim() || !persona || busy) return;
      setInput("");
      setBusy(true);

      const convoId = ensureConversation();
      const pid = persona.id;
      const set = (updater: (prev: Msg[]) => Msg[]) => onMessages(convoId, updater, pid);

      const userMsg: Msg = { role: "user", content: q, persona };
      const placeholder: Msg = { role: "assistant", content: "", step: "…", persona };
      // append both; the assistant turn is always the LAST element of this convo
      set((prev) => [...prev, userMsg, placeholder]);

      // patch the last message (the streaming assistant turn)
      const patchLast = (patch: Partial<Msg>) =>
        set((prev) => prev.map((mm, i) => (i === prev.length - 1 ? { ...mm, ...patch } : mm)));
      const appendToken = (text: string) =>
        set((prev) =>
          prev.map((mm, i) =>
            i === prev.length - 1 ? { ...mm, content: mm.content + text, step: undefined } : mm,
          ),
        );

      try {
        await streamChat(q, pid, (e: StreamEvent) => {
          if (e.type === "step") patchLast({ step: e.label });
          else if (e.type === "sources")
            patchLast({ sources: e.sources, hidden: e.hidden_by_clearance });
          else if (e.type === "token") appendToken(e.text);
          else if (e.type === "done")
            patchLast({
              done: true,
              step: undefined,
              refused: e.refused,
              citations: e.citations,
              hallucinated: e.hallucinated,
              uncited: e.uncited,
              took_ms: e.took_ms,
            });
        });
      } catch {
        patchLast({ content: "API connection error.", done: true });
      } finally {
        setBusy(false);
      }
    },
    [persona, busy, ensureConversation, onMessages],
  );

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-5 py-6">
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-16 text-center"
            >
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
                <ShieldCheck className="h-6 w-6 text-cyan-400" />
              </div>
              <div className="text-2xl font-semibold">
                Hello {persona?.name?.split(" ")[0] ?? ""}
              </div>
              <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">
                Ask about the port documents in plain language. Every answer is backed by official
                sources and filtered to what your role is allowed to see.
              </p>
              <div className="mt-6 grid gap-2">
                {EXAMPLES.map((ex, i) => (
                  <motion.button
                    key={ex}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 + i * 0.05 }}
                    onClick={() => send(ex)}
                    className="rounded-xl border border-white/10 bg-white/5 p-3 text-left text-sm text-slate-300 backdrop-blur-sm transition hover:border-cyan-500/40 hover:text-cyan-100"
                  >
                    {ex}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {messages.map((m, i) => (
            <MessageBubble
              key={i}
              m={m}
              idx={i}
              highlight={highlight}
              busy={busy}
              isLast={i === messages.length - 1}
              onCite={(msg, n) => {
                setHighlight({ msg, n });
                const src = messages[msg]?.sources?.find((s) => s.n === n);
                if (src) setDrawer(src);
              }}
              onOpenSource={setDrawer}
              onFollowUp={send}
            />
          ))}
        </div>
      </div>

      <div className="border-t border-white/10 bg-slate-950/60 p-4 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            placeholder={persona ? `Message as ${persona.name}…` : "Loading…"}
            className="max-h-32 flex-1 resize-none rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none backdrop-blur-sm transition placeholder:text-slate-500 focus:border-cyan-500/60 focus:bg-white/[0.07]"
          />
          <motion.button
            whileTap={{ scale: 0.94 }}
            onClick={() => send(input)}
            disabled={busy || !input.trim()}
            className="flex h-[46px] w-[46px] items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-900/30 transition hover:brightness-110 disabled:opacity-40"
            aria-label="Send"
          >
            {busy ? (
              <span className="h-2 w-2 animate-ping rounded-full bg-white" />
            ) : (
              <ArrowUp className="h-5 w-5" />
            )}
          </motion.button>
        </div>
        <p className="mx-auto mt-2 max-w-3xl text-center text-[10px] text-slate-600">
          Answers are generated on-premise and cited. Verify critical decisions against the source
          document.
        </p>
      </div>

      <SourceDrawer source={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
