"use client";

/* Vision / roadmap teaser — elegantly DISABLED items only. These are NOT built;
   they communicate product direction to evaluators. (No Arabic support — excluded.) */

import { BellRing, KeyRound, LineChart, UploadCloud } from "lucide-react";

const ITEMS = [
  { icon: KeyRound, label: "SSO / Active-Directory sign-in" },
  { icon: LineChart, label: "Admin analytics — adoption & hours saved" },
  { icon: UploadCloud, label: "Self-service document onboarding" },
  { icon: BellRing, label: "Regulation-change alerts" },
];

export function Roadmap() {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="mb-2 flex items-center gap-2 px-0.5">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          Roadmap
        </span>
        <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-[8px] font-semibold uppercase text-cyan-300">
          Bientôt
        </span>
      </div>
      <ul className="space-y-1">
        {ITEMS.map(({ icon: Icon, label }) => (
          <li
            key={label}
            className="flex cursor-not-allowed items-center gap-2 rounded-lg px-1.5 py-1.5 text-[11px] text-slate-500 opacity-70"
            title="Coming soon"
          >
            <Icon className="h-3.5 w-3.5 shrink-0 opacity-60" />
            <span className="truncate">{label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
