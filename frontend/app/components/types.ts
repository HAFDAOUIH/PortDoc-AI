import type { Persona, Source } from "@/lib/api";

/* Shared chat/conversation types. A Conversation owns its messages and the
   persona it was started with, so resuming a past chat restores the right
   clearance context. */

export type Msg = {
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

export type View = "chat" | "library" | "eval";

export type Conversation = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  personaId: string | null;
  messages: Msg[];
};
