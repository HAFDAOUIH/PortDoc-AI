"use client";

/* Sidebar conversation history: grouped Today / Earlier, click-to-resume,
   inline rename, delete, and "+ New chat". Backed by useConversations (localStorage). */

import { AnimatePresence, motion } from "framer-motion";
import { Check, MessageSquare, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { Conversation } from "./types";

function isToday(ts: number) {
  const d = new Date(ts);
  const n = new Date();
  return (
    d.getFullYear() === n.getFullYear() &&
    d.getMonth() === n.getMonth() &&
    d.getDate() === n.getDate()
  );
}

export function ConversationList({
  convos,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: {
  convos: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const today = convos.filter((c) => isToday(c.updatedAt));
  const earlier = convos.filter((c) => !isToday(c.updatedAt));

  const startEdit = (c: Conversation) => {
    setEditing(c.id);
    setDraft(c.title);
  };
  const commit = (id: string) => {
    onRename(id, draft);
    setEditing(null);
  };

  const Row = ({ c }: { c: Conversation }) => {
    const active = c.id === activeId;
    const isEditing = editing === c.id;
    return (
      <motion.div
        layout
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, height: 0 }}
        className={`group flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition ${
          active ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5"
        }`}
      >
        <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
        {isEditing ? (
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit(c.id);
              if (e.key === "Escape") setEditing(null);
            }}
            className="min-w-0 flex-1 rounded border border-cyan-500/50 bg-slate-900 px-1.5 py-0.5 text-xs outline-none"
          />
        ) : (
          <button
            onClick={() => onSelect(c.id)}
            className="min-w-0 flex-1 truncate text-left"
            title={c.title}
          >
            {c.title}
          </button>
        )}

        <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition group-hover:opacity-100">
          {isEditing ? (
            <>
              <button onClick={() => commit(c.id)} aria-label="Save" className="rounded p-1 hover:bg-white/10">
                <Check className="h-3 w-3 text-emerald-400" />
              </button>
              <button onClick={() => setEditing(null)} aria-label="Cancel" className="rounded p-1 hover:bg-white/10">
                <X className="h-3 w-3 text-slate-400" />
              </button>
            </>
          ) : (
            <>
              <button onClick={() => startEdit(c)} aria-label="Rename" className="rounded p-1 hover:bg-white/10">
                <Pencil className="h-3 w-3" />
              </button>
              <button onClick={() => onDelete(c.id)} aria-label="Delete" className="rounded p-1 hover:bg-white/10">
                <Trash2 className="h-3 w-3 text-rose-400/80" />
              </button>
            </>
          )}
        </div>
      </motion.div>
    );
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <button
        onClick={onNew}
        className="mx-3 flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-cyan-500/40 hover:text-cyan-100"
      >
        <Plus className="h-4 w-4" /> New chat
      </button>

      <div className="mt-2 min-h-0 flex-1 space-y-3 overflow-y-auto px-3 pb-2">
        {convos.length === 0 && (
          <p className="px-1 pt-4 text-center text-[11px] text-slate-600">
            No conversations yet.
          </p>
        )}
        {today.length > 0 && (
          <div>
            <div className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
              Today
            </div>
            <AnimatePresence initial={false}>
              {today.map((c) => (
                <Row key={c.id} c={c} />
              ))}
            </AnimatePresence>
          </div>
        )}
        {earlier.length > 0 && (
          <div>
            <div className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
              Earlier
            </div>
            <AnimatePresence initial={false}>
              {earlier.map((c) => (
                <Row key={c.id} c={c} />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
