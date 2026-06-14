"use client";

/* localStorage-backed conversation store.  → DB in production.
   Persists the full message list + the persona per conversation so a resumed
   chat restores the exact clearance context it was created under. */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Conversation, Msg } from "./types";

const KEY = "portdoc.conversations.v1";

function load(): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Conversation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function save(convos: Conversation[]) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(convos));
  } catch {
    /* quota / private mode — non-fatal */
  }
}

export function titleFrom(content: string): string {
  const t = content.trim().replace(/\s+/g, " ");
  if (!t) return "New chat";
  return t.length > 40 ? t.slice(0, 40).trimEnd() + "…" : t;
}

export function useConversations() {
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const hydrated = useRef(false);

  // hydrate once on mount (client only — avoids SSR mismatch)
  useEffect(() => {
    const loaded = load();
    setConvos(loaded);
    setActiveId(loaded[0]?.id ?? null);
    hydrated.current = true;
  }, []);

  // persist after hydration
  useEffect(() => {
    if (hydrated.current) save(convos);
  }, [convos]);

  const active = convos.find((c) => c.id === activeId) ?? null;

  const newConversation = useCallback((personaId: string | null) => {
    const id = `c_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const convo: Conversation = {
      id,
      title: "New chat",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      personaId,
      messages: [],
    };
    setConvos((xs) => [convo, ...xs]);
    setActiveId(id);
    return id;
  }, []);

  /** Replace the message list of a conversation (and refresh title/timestamp).
      Creates the conversation lazily if it doesn't exist yet. */
  const setMessages = useCallback(
    (id: string, updater: (prev: Msg[]) => Msg[], personaId: string | null) => {
      setConvos((xs) => {
        const idx = xs.findIndex((c) => c.id === id);
        if (idx === -1) return xs;
        const prev = xs[idx];
        const messages = updater(prev.messages);
        const firstUser = messages.find((m) => m.role === "user");
        const title =
          prev.title === "New chat" && firstUser ? titleFrom(firstUser.content) : prev.title;
        const updated: Conversation = {
          ...prev,
          messages,
          title,
          personaId: personaId ?? prev.personaId,
          updatedAt: Date.now(),
        };
        const next = [...xs];
        next.splice(idx, 1);
        return [updated, ...next]; // bubble most-recent to top
      });
    },
    [],
  );

  const rename = useCallback((id: string, title: string) => {
    const clean = title.trim();
    if (!clean) return;
    setConvos((xs) => xs.map((c) => (c.id === id ? { ...c, title: clean } : c)));
  }, []);

  const remove = useCallback(
    (id: string) => {
      setConvos((xs) => {
        const next = xs.filter((c) => c.id !== id);
        if (id === activeId) setActiveId(next[0]?.id ?? null);
        return next;
      });
    },
    [activeId],
  );

  return {
    convos,
    active,
    activeId,
    setActiveId,
    newConversation,
    setMessages,
    rename,
    remove,
  };
}
