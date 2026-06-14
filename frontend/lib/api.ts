// Typed client for the PortDoc FastAPI backend.
// Default: same-origin "/api" proxy (see next.config.mjs rewrites) so one tunnel exposes
// the whole app. Override with NEXT_PUBLIC_API_BASE to call the backend directly.
const BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

export type Source = {
  n: number;
  chunk_id: string;
  doc_id: string;
  authority: string;
  doc_type: string;
  year: number;
  page_start: number;
  clearance: number;
  is_table: boolean;
  from_ocr: boolean;
  score: number;
  snippet: string;
};

export type Health = {
  status: string;
  sovereign: boolean;
  llm_backend: string;
  llm_model: string;
  dense_model: string;
  sparse_model: string;
  reranker_model: string;
  reranker_enabled: boolean;
  qdrant_points: number;
};

// One row per document in the corpus — powers the Knowledge-base view (GET /documents).
export type DocumentMeta = {
  doc_id: string;
  authority: string;
  doc_type: string;
  year: number;
  lang: string;
  clearance: number;
  from_ocr: boolean;
  n_chunks: number;
};

export type RetrieveResponse = { sources: Source[]; hidden_by_clearance: number; took_ms: number };
export type AskResponse = {
  answer: string;
  refused: boolean;
  sources: Source[];
  hallucinated_citations: number[];
  uncited_sentences: number;
  took_ms: number;
};

export type EvalData = {
  sweep: {
    n_questions: number;
    rows: { mode: string; rerank: boolean; [k: string]: number | string | boolean }[];
    winner: { mode: string; rerank: boolean };
    conclusion: string;
  } | null;
  leakage: { n_queries: number; leaks: number; restricted_questions: number; leakage_rate: number } | null;
  generation?: {
    served_model: string;
    judge_model: string;
    judge_backend: string;
    n_questions: number;
    grounded_total: number;
    grounded_answered: number;
    over_refusals: string[];
    refuse_total: number;
    refuse_correct: number;
    hallucinated: string[];
    context_relevance: number | null;
    answer_relevance: number | null;
    faithfulness: number | null;
    claims_total: number;
    claims_supported: number;
  } | null;
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

export type Persona = {
  id: string;
  name: string;
  role: string;
  department: string;
  clearance: number;
  initials: string;
};

export type StreamEvent =
  | { type: "step"; stage: string; label: string }
  | { type: "sources"; sources: Source[]; hidden_by_clearance: number; retrieve_ms: number }
  | { type: "token"; text: string }
  | { type: "done"; refused: boolean; citations: number[]; hallucinated: number[]; uncited: number; took_ms: number };

export const api = {
  health: (): Promise<Health> => fetch(`${BASE}/health`).then((r) => r.json()),
  personas: (): Promise<Persona[]> => fetch(`${BASE}/personas`).then((r) => r.json()),
  retrieve: (query: string, user_clearance: number): Promise<RetrieveResponse> =>
    post("/retrieve", { query, user_clearance }),
  eval: (): Promise<EvalData> => fetch(`${BASE}/eval`).then((r) => r.json()),
  documents: (): Promise<DocumentMeta[]> => fetch(`${BASE}/documents`).then((r) => r.json()),
};

// Stream the chat pipeline (NDJSON: step → sources → token* → done).
export async function streamChat(
  query: string,
  persona_id: string,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, persona_id }),
    signal,
  });
  if (!r.body) throw new Error("no stream");
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (line) onEvent(JSON.parse(line) as StreamEvent);
    }
  }
}
