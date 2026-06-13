"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  api, streamChat, type EvalData, type Health, type Persona, type Source, type StreamEvent,
} from "@/lib/api";

/* ---------- helpers ---------- */
const CLR = [
  { label: "Public", chip: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", dot: "bg-emerald-400" },
  { label: "Internal", chip: "bg-amber-500/15 text-amber-300 border-amber-500/30", dot: "bg-amber-400" },
  { label: "Restricted", chip: "bg-rose-500/15 text-rose-300 border-rose-500/30", dot: "bg-rose-400" },
];

type Msg = {
  role: "user" | "assistant";
  content: string;
  persona?: Persona;
  sources?: Source[];
  hidden?: number;
  step?: string;
  done?: boolean;
  refused?: boolean;
  citations?: number[];
  hallucinated?: number[];
  uncited?: number;
  took_ms?: number;
};

function Citations({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  return (
    <>
      {text.split(/(\[\d+\])/g).map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        return m ? (
          <button key={i} onClick={() => onCite(Number(m[1]))}
            className="mx-0.5 -translate-y-0.5 rounded bg-cyan-500/20 px-1 align-super text-[10px] font-bold text-cyan-300 hover:bg-cyan-500/40">
            {m[1]}
          </button>
        ) : <span key={i}>{p}</span>;
      })}
    </>
  );
}

/* ---------- root ---------- */
export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState<Persona | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [view, setView] = useState<"chat" | "eval">("chat");

  useEffect(() => {
    api.personas().then((p) => { setPersonas(p); setPersona(p.find((x) => x.id === "salma") ?? p[0]); }).catch(() => {});
    api.health().then(setHealth).catch(() => {});
  }, []);

  return (
    <div className="flex h-screen">
      <Sidebar personas={personas} persona={persona} setPersona={setPersona} view={view} setView={setView} health={health} />
      <main className="flex-1 overflow-hidden bg-slate-950">
        {view === "chat" ? <Chat persona={persona} /> : <EvalView />}
      </main>
    </div>
  );
}

/* ---------- sidebar ---------- */
function Sidebar({ personas, persona, setPersona, view, setView, health }: {
  personas: Persona[]; persona: Persona | null; setPersona: (p: Persona) => void;
  view: "chat" | "eval"; setView: (v: "chat" | "eval") => void; health: Health | null;
}) {
  const [open, setOpen] = useState(false);
  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-slate-800 bg-slate-900/50">
      <div className="border-b border-slate-800 p-4">
        <div className="text-lg font-bold tracking-tight">PortDoc <span className="text-cyan-400">AI</span></div>
        <div className="text-[11px] text-slate-500">Sovereign Assistant · CIRES × Tanger Med</div>
      </div>

      <nav className="space-y-1 p-3">
        {([["chat", "💬 Assistant"], ["eval", "📊 Trust & Evaluation"]] as const).map(([v, label]) => (
          <button key={v} onClick={() => setView(v)}
            className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
              view === v ? "bg-slate-800 text-white" : "text-slate-400 hover:bg-slate-800/50"}`}>
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-auto p-3">
        <div className="mb-1.5 px-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Signed in as</div>
        <div className="relative">
          <button onClick={() => setOpen(!open)}
            className="flex w-full items-center gap-3 rounded-lg border border-slate-800 bg-slate-900 p-2.5 text-left hover:border-slate-700">
            {persona && <Avatar p={persona} />}
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{persona?.name ?? "…"}</div>
              <div className="truncate text-[11px] text-slate-500">{persona?.role}</div>
            </div>
            {persona && <ClrChip clr={persona.clearance} />}
          </button>
          {open && (
            <div className="absolute bottom-full mb-2 w-full overflow-hidden rounded-lg border border-slate-700 bg-slate-900 shadow-xl">
              {personas.map((p) => (
                <button key={p.id} onClick={() => { setPersona(p); setOpen(false); }}
                  className="flex w-full items-center gap-3 border-b border-slate-800 p-2.5 text-left last:border-0 hover:bg-slate-800">
                  <Avatar p={p} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{p.name}</div>
                    <div className="truncate text-[10px] text-slate-500">{p.department}</div>
                  </div>
                  <ClrChip clr={p.clearance} />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="mt-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-2.5 text-[10px] leading-relaxed text-emerald-300/90">
          🔒 <b>100% local</b> · 0 bytes leave the network<br />
          {health && <span className="text-slate-500">{health.llm_model} · {health.qdrant_points.toLocaleString()} chunks · Qdrant</span>}
        </div>
      </div>
    </aside>
  );
}

const Avatar = ({ p }: { p: Persona }) => (
  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-cyan-600 to-blue-700 text-[11px] font-bold">
    {p.initials}
  </div>
);
const ClrChip = ({ clr }: { clr: number }) => (
  <span className={`flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold ${CLR[clr].chip}`}>
    <span className={`h-1.5 w-1.5 rounded-full ${CLR[clr].dot}`} />{clr}
  </span>
);

/* ---------- chat ---------- */
const EXAMPLES = [
  "Que doit faire l'installation portuaire au niveau de sûreté 3 ?",
  "Comment notifier un navire transportant des marchandises dangereuses ?",
  "Quelle pièce d'identité est requise pour accéder au port ?",
];

function Chat({ persona }: { persona: Persona | null }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [highlight, setHighlight] = useState<{ msg: number; n: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }); }, [msgs]);

  const send = useCallback(async (q: string) => {
    if (!q.trim() || !persona || busy) return;
    setInput("");
    setBusy(true);
    const userMsg: Msg = { role: "user", content: q, persona };
    const aIdx = msgs.length + 1;
    setMsgs((m) => [...m, userMsg, { role: "assistant", content: "", step: "…" }]);
    const upd = (patch: Partial<Msg>) =>
      setMsgs((m) => m.map((mm, i) => (i === aIdx ? { ...mm, ...patch } : mm)));
    try {
      await streamChat(q, persona.id, (e: StreamEvent) => {
        if (e.type === "step") upd({ step: e.label });
        else if (e.type === "sources") upd({ sources: e.sources, hidden: e.hidden_by_clearance });
        else if (e.type === "token") setMsgs((m) => m.map((mm, i) => i === aIdx ? { ...mm, content: mm.content + e.text, step: undefined } : mm));
        else if (e.type === "done") upd({ done: true, step: undefined, refused: e.refused, citations: e.citations, hallucinated: e.hallucinated, uncited: e.uncited, took_ms: e.took_ms });
      });
    } catch { upd({ content: "API connection error.", done: true }); }
    finally { setBusy(false); }
  }, [persona, busy, msgs.length]);

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-5 py-6">
          {msgs.length === 0 && (
            <div className="mt-20 text-center">
              <div className="text-2xl font-semibold">Hello {persona?.name?.split(" ")[0]} 👋</div>
              <p className="mt-2 text-sm text-slate-400">Ask a question about the port documents. Answers are cited and filtered by your clearance.</p>
              <div className="mt-6 grid gap-2">
                {EXAMPLES.map((ex) => (
                  <button key={ex} onClick={() => send(ex)}
                    className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 text-left text-sm text-slate-300 hover:border-cyan-700">
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}
          {msgs.map((m, i) => (
            <Bubble key={i} m={m} idx={i} highlight={highlight} setHighlight={setHighlight} />
          ))}
        </div>
      </div>

      <div className="border-t border-slate-800 bg-slate-950 p-4">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={1}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
            placeholder={`Message as ${persona?.name ?? ""}…`}
            className="max-h-32 flex-1 resize-none rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm outline-none focus:border-cyan-500" />
          <button onClick={() => send(input)} disabled={busy || !input.trim()}
            className="rounded-xl bg-cyan-600 px-4 py-3 text-sm font-medium hover:bg-cyan-500 disabled:opacity-40">
            {busy ? "…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Bubble({ m, idx, highlight, setHighlight }: {
  m: Msg; idx: number; highlight: { msg: number; n: number } | null;
  setHighlight: (h: { msg: number; n: number } | null) => void;
}) {
  if (m.role === "user")
    return (
      <div className="mb-5 flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-cyan-600/90 px-4 py-2.5 text-sm">{m.content}</div>
      </div>
    );
  return (
    <div className="mb-6 space-y-2 pop-in">
      {m.step && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <span className="h-2 w-2 animate-ping rounded-full bg-cyan-400" /> <span className="shimmer">{m.step}</span>
        </div>
      )}
      {m.hidden !== undefined && m.hidden > 0 && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300">
          🔒 {m.hidden} restricted source(s) hidden at your clearance
        </div>
      )}
      {m.content && (
        <div className={`rounded-2xl rounded-bl-sm border px-4 py-3 text-sm leading-relaxed ${
          m.refused ? "border-amber-500/30 bg-amber-500/10 text-amber-100" : "border-slate-800 bg-slate-900/60 text-slate-200"}`}>
          <Citations text={m.content} onCite={(n) => setHighlight({ msg: idx, n })} />
        </div>
      )}
      {m.sources && m.sources.length > 0 && (
        <div className="grid gap-1.5 sm:grid-cols-2">
          {m.sources.map((s) => (
            <SourceCard key={s.chunk_id} s={s} hot={highlight?.msg === idx && highlight?.n === s.n} />
          ))}
        </div>
      )}
      {m.done && !m.refused && (
        <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">
          <Chip ok={m.uncited === 0}>{m.uncited === 0 ? `✓ Grounded · ${m.citations?.length ?? 0} citations` : `⚠ ${m.uncited} uncited sentence(s)`}</Chip>
          {!!m.hallucinated?.length && <Chip ok={false}>⚠ {m.hallucinated.length} invented citation(s) removed</Chip>}
          <span className="rounded-full border border-slate-800 px-2 py-0.5">⏱ {((m.took_ms ?? 0) / 1000).toFixed(0)}s · local</span>
        </div>
      )}
    </div>
  );
}

const Chip = ({ ok, children }: { ok: boolean; children: React.ReactNode }) => (
  <span className={`rounded-full border px-2 py-0.5 ${ok ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"}`}>{children}</span>
);

function SourceCard({ s, hot }: { s: Source; hot: boolean }) {
  return (
    <div className={`rounded-lg border p-2.5 transition ${hot ? "border-cyan-500 bg-cyan-500/5" : "border-slate-800 bg-slate-900/40"}`}>
      <div className="mb-1 flex items-center gap-1.5 text-[10px]">
        <span className="font-mono text-cyan-400">[{s.n}]</span>
        <span className={`rounded border px-1 py-0.5 font-semibold ${CLR[s.clearance].chip}`}>{CLR[s.clearance].label}</span>
        {s.from_ocr && <span className="rounded border border-violet-500/30 bg-violet-500/15 px-1 py-0.5 text-violet-300">OCR</span>}
        {s.is_table && <span className="rounded border border-sky-500/30 bg-sky-500/15 px-1 py-0.5 text-sky-300">TABLE</span>}
        <span className="ml-auto font-mono text-slate-600">{s.score.toFixed(2)}</span>
      </div>
      <div className="text-[10px] text-slate-500">{s.authority} · {s.doc_type} · {s.year} · p.{s.page_start}</div>
      <p className="mt-1 line-clamp-3 text-[11px] leading-snug text-slate-400">{s.snippet}</p>
    </div>
  );
}

/* ---------- eval ---------- */
function EvalView() {
  const [data, setData] = useState<EvalData | null>(null);
  useEffect(() => { api.eval().then(setData).catch(() => {}); }, []);
  if (!data?.sweep) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  const chart = data.sweep.rows.map((r) => ({
    name: `${r.mode}${r.rerank ? "+rr" : ""}`,
    "hit@5": r["hit@5"] as number, MRR: r["mrr"] as number, "nDCG@10": r["ndcg@10"] as number,
  }));
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-lg font-bold">Trust & Evaluation</h1>
        <p className="mb-5 text-sm text-slate-400">Audit panel — deterministic metrics and access control, measured on a labelled question set.</p>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="md:col-span-2 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <h2 className="mb-3 text-sm font-semibold">Retrieval sweep · {data.sweep.n_questions} questions</h2>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <YAxis domain={[0, 1]} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="hit@5" fill="#22d3ee" radius={[3, 3, 0, 0]} />
                <Bar dataKey="MRR" fill="#34d399" radius={[3, 3, 0, 0]} />
                <Bar dataKey="nDCG@10" fill="#a78bfa" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-3 rounded-lg bg-slate-950 p-3 text-xs leading-relaxed text-slate-400">{data.sweep.conclusion.replace(/\*\*/g, "")}</p>
          </div>
          <div className="space-y-4">
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5 text-center">
              <div className="text-xs uppercase tracking-wide text-emerald-400">RBAC Leakage</div>
              <div className="my-2 text-5xl font-black text-emerald-400">{data.leakage ? `${(data.leakage.leakage_rate * 100).toFixed(0)}%` : "—"}</div>
              <div className="text-xs text-slate-400">{data.leakage?.leaks ?? 0} leak(s) across {data.leakage?.n_queries ?? 0} queries at clearance 0</div>
              <div className="mt-2 text-[11px] text-emerald-300">✅ Enforced at retrieval</div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="text-sm font-semibold">🏆 Winning config</div>
              <div className="mt-1 font-mono text-cyan-400">{data.sweep.winner.mode} · rerank {data.sweep.winner.rerank ? "on" : "off"}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
