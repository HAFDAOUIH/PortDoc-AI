"use client";

/* App shell. State: current view + selected persona + live /health. Conversation
   state is owned by useConversations (localStorage). Views animate in/out with
   AnimatePresence. The whole tree is wrapped in ToastProvider for feedback toasts. */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { api, type Health, type Persona } from "@/lib/api";
import { Chat } from "./components/Chat";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { EvalView } from "./components/EvalView";
import { Sidebar } from "./components/Sidebar";
import { ToastProvider } from "./components/Toast";
import { useConversations } from "./components/useConversations";
import type { View } from "./components/types";

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState<Persona | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [view, setView] = useState<View>("chat");

  const convo = useConversations();

  useEffect(() => {
    api
      .personas()
      .then((p) => {
        setPersonas(p);
        setPersona(p.find((x) => x.id === "salma") ?? p[0] ?? null);
      })
      .catch(() => {});
    api.health().then(setHealth).catch(() => {});
  }, []);

  // When resuming a conversation, restore the persona it was created with.
  useEffect(() => {
    if (!convo.active?.personaId || personas.length === 0) return;
    const p = personas.find((x) => x.id === convo.active!.personaId);
    if (p && p.id !== persona?.id) setPersona(p);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [convo.activeId, personas]);

  // Lazily create a conversation when the user first sends a message.
  const { activeId, newConversation } = convo;
  const ensureConversation = useMemo(
    () => () => activeId ?? newConversation(persona?.id ?? null),
    [activeId, newConversation, persona?.id],
  );

  const messages = convo.active?.messages ?? [];

  return (
    <ToastProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar
          personas={personas}
          persona={persona}
          setPersona={setPersona}
          view={view}
          setView={setView}
          health={health}
          convos={convo.convos}
          activeId={convo.activeId}
          onSelect={convo.setActiveId}
          onNew={() => convo.newConversation(persona?.id ?? null)}
          onRename={convo.rename}
          onDelete={convo.remove}
        />
        <main className="relative flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={view}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              {view === "chat" && (
                <Chat
                  persona={persona}
                  messages={messages}
                  onMessages={convo.setMessages}
                  ensureConversation={ensureConversation}
                />
              )}
              {view === "library" && <DocumentLibrary />}
              {view === "eval" && <EvalView />}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </ToastProvider>
  );
}
