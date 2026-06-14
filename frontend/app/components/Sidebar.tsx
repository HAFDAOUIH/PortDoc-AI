"use client";

/* Left rail: brand, nav (Assistant / Knowledge base / Trust), conversation
   history (chat view only), persona switcher (drives live RBAC), the always-on
   sovereignty headline, and the roadmap teaser. */

import { AnimatePresence, motion } from "framer-motion";
import { BarChart3, ChevronsUpDown, Library, Lock, MessagesSquare } from "lucide-react";
import { useState } from "react";
import type { Health, Persona } from "@/lib/api";
import { ConversationList } from "./ConversationList";
import { Roadmap } from "./Roadmap";
import { Avatar, ClrChip, clr } from "./ui";
import type { Conversation, View } from "./types";

const NAV: { id: View; label: string; icon: typeof MessagesSquare }[] = [
  { id: "chat", label: "Assistant", icon: MessagesSquare },
  { id: "library", label: "Knowledge base", icon: Library },
  { id: "eval", label: "Trust & Evaluation", icon: BarChart3 },
];

export function Sidebar({
  personas,
  persona,
  setPersona,
  view,
  setView,
  health,
  convos,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: {
  personas: Persona[];
  persona: Persona | null;
  setPersona: (p: Persona) => void;
  view: View;
  setView: (v: View) => void;
  health: Health | null;
  convos: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-white/10 bg-slate-950/60 backdrop-blur-xl">
      <div className="border-b border-white/10 p-4">
        <div className="flex items-center gap-2 text-lg font-bold tracking-tight">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg shadow-cyan-900/30">
            <Lock className="h-3.5 w-3.5 text-white" />
          </span>
          PortDoc <span className="text-gradient">AI</span>
        </div>
        <div className="mt-1 text-[11px] text-slate-500">Sovereign Assistant · CIRES × Tanger Med</div>
      </div>

      <nav className="space-y-1 p-3">
        {NAV.map(({ id, label, icon: Icon }) => {
          const activeNav = view === id;
          return (
            <button
              key={id}
              onClick={() => setView(id)}
              className={`relative flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition ${
                activeNav ? "text-white" : "text-slate-400 hover:bg-white/5"
              }`}
            >
              {activeNav && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-lg border border-white/10 bg-white/10"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <Icon className="relative z-10 h-4 w-4" />
              <span className="relative z-10">{label}</span>
            </button>
          );
        })}
      </nav>

      {/* Conversation history lives in the chat view only. */}
      {view === "chat" && (
        <>
          <div className="mx-3 border-t border-white/10 pt-3" />
          <ConversationList
            convos={convos}
            activeId={activeId}
            onSelect={onSelect}
            onNew={onNew}
            onRename={onRename}
            onDelete={onDelete}
          />
        </>
      )}

      <div className="mt-auto space-y-3 p-3">
        {/* persona switcher → live RBAC */}
        <div>
          <div className="mb-1.5 px-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Signed in as
          </div>
          <div className="relative">
            <button
              onClick={() => setOpen((o) => !o)}
              className="flex w-full items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-2.5 text-left transition hover:border-white/20"
            >
              {persona && <Avatar initials={persona.initials} />}
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{persona?.name ?? "…"}</div>
                <div className="truncate text-[11px] text-slate-500">{persona?.role}</div>
              </div>
              {persona && <ClrChip level={persona.clearance} />}
              <ChevronsUpDown className="h-3.5 w-3.5 text-slate-500" />
            </button>
            <AnimatePresence>
              {open && (
                <motion.div
                  initial={{ opacity: 0, y: 8, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8, scale: 0.97 }}
                  transition={{ type: "spring", stiffness: 420, damping: 30 }}
                  className="absolute bottom-full mb-2 w-full overflow-hidden rounded-xl border border-white/10 bg-slate-900/95 shadow-2xl backdrop-blur-xl"
                >
                  {personas.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => {
                        setPersona(p);
                        setOpen(false);
                      }}
                      className="flex w-full items-center gap-3 border-b border-white/5 p-2.5 text-left transition last:border-0 hover:bg-white/5"
                    >
                      <Avatar initials={p.initials} />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm">{p.name}</div>
                        <div className="truncate text-[10px] text-slate-500">{p.department}</div>
                      </div>
                      <ClrChip level={p.clearance} />
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          {persona && (
            <p className="mt-1.5 px-1 text-[10px] text-slate-500">
              May consult{" "}
              <span className="text-slate-400">{clr(persona.clearance).label}</span> documents.
            </p>
          )}
        </div>

        {/* sovereignty headline — always visible, live from /health */}
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-[10px] leading-relaxed">
          <div className="flex items-center gap-1.5 font-semibold text-emerald-300">
            <Lock className="h-3 w-3" /> 100% on-premise · 0 documents leave the network
          </div>
          {health && (
            <div className="mt-1 font-mono text-[10px] text-slate-500">
              {health.llm_model} · {health.qdrant_points.toLocaleString()} indexed passages
            </div>
          )}
        </div>

        <Roadmap />
      </div>
    </aside>
  );
}
