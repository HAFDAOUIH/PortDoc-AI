"use client";

/* Trust & Evaluation tab — the technical audit panel. Same data and metrics as
   before (retrieval sweep, RBAC leakage shield, RAG triad, refusal discipline),
   restyled to the glass system with count-up numbers and bars that fill in.
   This is the one place ML jargon (MRR/nDCG/etc.) is allowed. */

import { motion, useReducedMotion } from "framer-motion";
import { Trophy } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type EvalData } from "@/lib/api";
import { CountUp, glass } from "./ui";

function TriadBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number | null;
  color: string;
}) {
  const reduce = useReducedMotion();
  const pct = value == null ? 0 : Math.round(value * 100);
  return (
    <div className="rounded-lg border border-white/10 bg-slate-950/40 p-3">
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] text-slate-400">{label}</span>
        <span className="text-sm font-bold text-slate-200">
          {value == null ? "—" : <CountUp value={pct} suffix="%" duration={0.9} />}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <motion.div
          className={`h-full rounded-full ${color}`}
          initial={{ width: reduce ? `${pct}%` : 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

export function EvalView() {
  const [data, setData] = useState<EvalData | null>(null);
  useEffect(() => {
    api.eval().then(setData).catch(() => {});
  }, []);

  if (!data?.sweep) return <div className="p-8 text-sm text-slate-500">Loading…</div>;

  const chart = data.sweep.rows.map((r) => ({
    name: `${r.mode}${r.rerank ? "+rr" : ""}`,
    "hit@5": r["hit@5"] as number,
    MRR: r["mrr"] as number,
    "nDCG@10": r["ndcg@10"] as number,
  }));

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-lg font-bold">Trust &amp; Evaluation</h1>
        <p className="mb-5 text-sm text-slate-400">
          Audit panel — deterministic metrics and access control, measured on a labelled question
          set.
        </p>

        <div className="grid gap-4 md:grid-cols-3">
          <div className={glass("md:col-span-2 p-4")}>
            <h2 className="mb-3 text-sm font-semibold">
              Retrieval sweep · {data.sweep.n_questions} questions
            </h2>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <YAxis domain={[0, 1]} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    background: "#0f172a",
                    border: "1px solid #334155",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="hit@5" fill="#22d3ee" radius={[3, 3, 0, 0]} />
                <Bar dataKey="MRR" fill="#34d399" radius={[3, 3, 0, 0]} />
                <Bar dataKey="nDCG@10" fill="#a78bfa" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-3 rounded-lg bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-400">
              {data.sweep.conclusion.replace(/\*\*/g, "")}
            </p>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-5 text-center backdrop-blur-md">
              <div className="text-xs uppercase tracking-wide text-emerald-400">RBAC Leakage</div>
              <div className="my-2 text-5xl font-black text-emerald-400">
                {data.leakage ? (
                  <CountUp value={Math.round(data.leakage.leakage_rate * 100)} suffix="%" />
                ) : (
                  "—"
                )}
              </div>
              <div className="text-xs text-slate-400">
                {data.leakage?.leaks ?? 0} leak(s) across {data.leakage?.n_queries ?? 0} queries at
                clearance 0
              </div>
              <div className="mt-2 text-[11px] text-emerald-300">Enforced at retrieval</div>
            </div>

            <div className={glass("p-4")}>
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Trophy className="h-4 w-4 text-amber-400" /> Winning config
              </div>
              <div className="mt-1 font-mono text-cyan-400">
                {data.sweep.winner.mode} · rerank {data.sweep.winner.rerank ? "on" : "off"}
              </div>
            </div>
          </div>
        </div>

        {data.generation && (
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div className={glass("md:col-span-2 p-4")}>
              <h2 className="text-sm font-semibold">
                RAG triad · {data.generation.n_questions} questions
              </h2>
              <p className="mb-3 text-[11px] text-slate-500">
                Generated by {data.generation.served_model} · judged by {data.generation.judge_model}{" "}
                ({data.generation.judge_backend})
              </p>
              <div className="grid gap-3 sm:grid-cols-3">
                <TriadBar
                  label="Context relevance"
                  value={data.generation.context_relevance}
                  color="bg-cyan-400"
                />
                <TriadBar
                  label="Faithfulness"
                  value={data.generation.faithfulness}
                  color="bg-emerald-400"
                />
                <TriadBar
                  label="Answer relevance"
                  value={data.generation.answer_relevance}
                  color="bg-violet-400"
                />
              </div>
              <p className="mt-3 rounded-lg bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-400">
                {data.generation.claims_supported}/{data.generation.claims_total} extracted claims
                supported by the cited sources.
              </p>
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4 backdrop-blur-md">
                <div className="text-xs uppercase tracking-wide text-emerald-400">
                  Refusal discipline
                </div>
                <div className="my-2 text-4xl font-black text-emerald-400">
                  <CountUp value={data.generation.refuse_correct} />
                  <span className="text-2xl text-slate-500">/{data.generation.refuse_total}</span>
                </div>
                <div className="text-xs text-slate-400">
                  correctly refused (no answer for out-of-scope questions)
                </div>
              </div>

              <div className={glass("p-4 text-sm")}>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Hallucinated</span>
                  <span
                    className={`font-mono ${
                      data.generation.hallucinated.length ? "text-rose-400" : "text-emerald-400"
                    }`}
                  >
                    {data.generation.hallucinated.length}
                  </span>
                </div>
                <div className="mt-1.5 flex items-center justify-between">
                  <span className="text-slate-400">Over-refusals</span>
                  <span
                    className={`font-mono ${
                      data.generation.over_refusals.length ? "text-amber-400" : "text-emerald-400"
                    }`}
                  >
                    {data.generation.over_refusals.length}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
