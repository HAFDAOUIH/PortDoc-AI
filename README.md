# PortDoc AI

Sovereign RAG over port security & operational documents. Everything runs
locally — no document ever leaves the host (the CIRES data-sovereignty posture).

> Build in progress, slice by slice. This README grows with the system.

## Quickstart

```bash
make install     # uv sync
make fetch       # download + sha256-verify the corpus (see data/corpus/manifest.yaml)
make test        # unit tests
```

## Corpus

11 public Moroccan port documents (FR + EN), fingerprinted in `data/corpus/manifest.yaml`.
Several official sources block automated download, so the files ship in `corpus/raw/`
and are verified by sha256 (`make fetch`). The scanned circular is synthesized from the
Casablanca regulation via `scripts/make_scan.sh` to exercise the OCR pipeline.

Clearance gradient (powers the RBAC retrieval filter): 7 public (0) · 1 internal (1, the
scan) · 3 restricted port-security procedures (2: ISPS code, ILO security guide, sûreté dossier).

## Status

- [x] Slice 1 — reproducible foundation: config, corpus manifest, integrity-checked fetch, real corpus
- [ ] Slice 2 — parse routing + OCR bake-off
- [ ] Slice 3 — chunking
- [ ] Slice 4 — embedding + Qdrant hybrid retrieval
- [ ] Slice 5 — rerank + RBAC clearance filter
- [ ] Slice 6 — generation: citation grammar + sentinel refusal
- [ ] Slice 7 — evaluation + the sweep
- [ ] Slice 8 — API + UI + docker compose
