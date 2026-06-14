"use client";

/* Shared UI primitives + the clearance colour system, reused across the app.
   The clearance palette (0 emerald/Public · 1 amber/Internal · 2 rose/Restricted)
   matches the original `CLR` helper exactly. */

import { animate, useReducedMotion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export const CLR = [
  {
    label: "Public",
    chip: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    dot: "bg-emerald-400",
  },
  {
    label: "Internal",
    chip: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    dot: "bg-amber-400",
  },
  {
    label: "Restricted",
    chip: "bg-rose-500/15 text-rose-300 border-rose-500/30",
    dot: "bg-rose-400",
  },
] as const;

export function clr(level: number) {
  return CLR[level] ?? CLR[0];
}

/** Clearance badge: coloured dot + numeric level (compact form used everywhere). */
export function ClrChip({ level, withLabel = false }: { level: number; withLabel?: boolean }) {
  const c = clr(level);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold ${c.chip}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {withLabel ? c.label : level}
    </span>
  );
}

/** "Verified source" trust badge (lucide ShieldCheck). */
export function VerifiedBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-medium text-emerald-300">
      <ShieldCheck className="h-3 w-3" />
      Verified source
    </span>
  );
}

/** Small metadata tag (OCR / TABLE etc.). */
export function Tag({
  children,
  tone = "slate",
}: {
  children: React.ReactNode;
  tone?: "violet" | "sky" | "slate";
}) {
  const tones = {
    violet: "border-violet-500/30 bg-violet-500/15 text-violet-300",
    sky: "border-sky-500/30 bg-sky-500/15 text-sky-300",
    slate: "border-slate-600/40 bg-slate-700/30 text-slate-300",
  } as const;
  return (
    <span className={`rounded border px-1 py-0.5 text-[9px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

/** Glass card surface — the signature container of the design system. */
export function glass(extra = "") {
  return `rounded-2xl border border-white/10 bg-white/5 shadow-lg shadow-black/20 backdrop-blur-md ${extra}`;
}

/** Number that animates from 0 to `value` once on mount (respects reduced motion). */
export function CountUp({
  value,
  decimals = 0,
  suffix = "",
  duration = 1.1,
}: {
  value: number;
  decimals?: number;
  suffix?: string;
  duration?: number;
}) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(reduce ? value : 0);
  const last = useRef(value);

  useEffect(() => {
    if (reduce) {
      setDisplay(value);
      return;
    }
    const controls = animate(last.current, value, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(v),
    });
    last.current = value;
    return () => controls.stop();
  }, [value, duration, reduce]);

  return (
    <span>
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/** Avatar bubble for a persona, gradient-filled with initials. */
export function Avatar({ initials, size = 8 }: { initials: string; size?: number }) {
  return (
    <div
      style={{ width: `${size * 4}px`, height: `${size * 4}px` }}
      className="flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-blue-700 text-[11px] font-bold text-white shadow-inner"
    >
      {initials}
    </div>
  );
}
