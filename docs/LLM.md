# LLM layer

The `backend/app/llm/` package is the **only** place in the backend where an
LLM / embedding provider is called (PROJECT.md §5, §10). Feature code
(ingestion, RAG) imports from `app.llm.service` and never touches a provider SDK
directly. Providers are reached through **LiteLLM**, so they are swappable by
environment variables alone — cloud today, self-hosted for the government
privacy story tomorrow, with no code change.

## Layout

| File | Role |
|------|------|
| `service.py` | Public API. Decides stub vs real and delegates. This is the import surface for the rest of the backend. |
| `stub.py` | Deterministic, offline synthetic generators. No network, no key. **The default.** |
| `provider.py` | Real LiteLLM calls (multimodal extraction, summary, embeddings). Imported lazily; only reached in real mode. |
| `__init__.py` | Re-exports the public API. |

### Public contract (stable — callers depend on these exact shapes)

```python
extract_document(file_bytes, mime, doc_type, seed=None)
  -> {"extracted_text": str,
      "items": [ {kind, label, value, unit, date, confidence, data}, ... ]}
      # kind ∈ observation | medication | allergy | condition | procedure

generate_summary(patient, items)
  -> [ {key, title, items:[ {text, severity, trend, confidence, verified,
                             citations:[{document_id, label}]} ]}, ... ]
      # key ∈ complaint | problems | allergies | medications | labs |
      #       encounters | flags  (always all seven, in this order)

embed(texts) -> list[list[float]]   # each vector length == EMBEDDING_DIM

is_stub_mode() -> bool
```

Both stub and real paths return **identical shapes**, so the pipeline and RAG
layer behave the same either way.

## Stub mode vs real mode

**Stub mode is the default and is fully self-contained.** It produces realistic,
deterministic (seeded) demo extractions, summaries, and local pseudo-embeddings
with no provider and no key, so the whole ingestion + summary pipeline runs
offline. Stub output is deliberately marked with modest confidence and a
`data.stub = True` flag; it must never be presented as real clinical data.

`is_stub_mode()` (defined in `app/core/config.py`) returns **True** — i.e. stubs
are used — whenever **any** of these hold:

- `LLM_PROVIDER` is empty, or set to `stub`; or
- the provider's API key (`<PROVIDER>_API_KEY`) is **absent** from the
  environment.

So real mode is active **only** when `LLM_PROVIDER` names a real provider **and**
its key is present. A missing key silently and safely falls back to stubs — the
app never crashes at import for a missing key.

## Enabling real mode

Set these environment variables (see `backend/.env.example`):

| Var | Meaning |
|-----|---------|
| `LLM_PROVIDER` | Provider id, e.g. `gemini`, `openai`, `ollama`, `vllm`. Non-empty and non-`stub` to leave stub mode. |
| `LLM_MODEL_MULTIMODAL` | Vision-capable model for extraction (scans, photos, handwriting). |
| `LLM_MODEL_REASONING` | Text model for structured summary generation. |
| `EMBEDDING_MODEL` | Embedding model for chunk vectors. |
| `EMBEDDING_DIM` | Vector width. **Must match** what `EMBEDDING_MODEL` emits and the pgvector column. |
| `<PROVIDER>_API_KEY` | The key LiteLLM reads, named for the provider in uppercase, e.g. `GEMINI_API_KEY`. |

The `<PROVIDER>_API_KEY` name is derived from `LLM_PROVIDER` uppercased +
`_API_KEY` (`gemini` → `GEMINI_API_KEY`, `openai` → `OPENAI_API_KEY`).

### Recommended default: Google Gemini

Strong multimodal reading of messy scans/handwriting, low cost, generous
context. LiteLLM routes `gemini/<model>` to the Google AI Studio API.

```bash
LLM_PROVIDER=gemini
LLM_MODEL_MULTIMODAL=gemini/gemini-2.0-flash
LLM_MODEL_REASONING=gemini/gemini-2.0-flash
EMBEDDING_MODEL=gemini/text-embedding-004
EMBEDDING_DIM=768          # text-embedding-004 emits 768 dims — set the pgvector column to match
GEMINI_API_KEY=your-google-ai-studio-key
```

Caveat: the app default `EMBEDDING_DIM` is `1536` (an OpenAI width). Gemini
`text-embedding-004` returns **768** — set `EMBEDDING_DIM=768` **and** the
pgvector column width to 768 before enabling. The real `embed()` raises a clear
error if a returned vector width does not match `EMBEDDING_DIM`, rather than
letting a wrong-width vector fail cryptically at the database.

### OpenAI (alternative)

```bash
LLM_PROVIDER=openai
LLM_MODEL_MULTIMODAL=gpt-4o-mini
LLM_MODEL_REASONING=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
OPENAI_API_KEY=sk-...
```

### Self-hosted / offline (the government-privacy story)

Because everything goes through LiteLLM, a self-hosted open model can drop in
with no code change — the deployment story for privacy-sensitive government
sites where patient data must not leave the premises. Run an open multimodal
model (e.g. a Llama/Qwen vision model, or MedGemma) plus an open embedding model
on **Ollama** or **vLLM**, and point the same env vars at the local endpoint:

```bash
# Ollama example (LiteLLM talks to a local Ollama server)
LLM_PROVIDER=ollama
LLM_MODEL_MULTIMODAL=ollama/llama3.2-vision
LLM_MODEL_REASONING=ollama/llama3.1
EMBEDDING_MODEL=ollama/nomic-embed-text
EMBEDDING_DIM=768
OLLAMA_API_KEY=local          # any non-empty value; leaves stub mode
OLLAMA_API_BASE=http://localhost:11434
```

`OLLAMA_API_KEY` (or `VLLM_API_KEY`) only needs to be non-empty so the layer
leaves stub mode — the value is not a real secret for a local server. Confirm
your LiteLLM version's exact base-URL variable (`OLLAMA_API_BASE` /
`OPENAI_API_BASE` for vLLM's OpenAI-compatible endpoint).

## How the real path works (`provider.py`)

- **Extraction** — images are sent to the multimodal model as base64 `data:`
  URLs. PDFs are rendered to page images via **PyMuPDF** when it is installed
  (best for scanned/photographed PDFs and handwriting); otherwise text is
  extracted with **pypdf** and sent as text. The model is prompted to return
  strict JSON matching the extraction contract. Parsing is lenient (tolerates
  markdown fences and surrounding prose) with **one repair round-trip** if the
  first reply is not valid JSON; an unrecoverable failure raises
  `LLMProviderError` so the pipeline marks the document `failed` — it never
  fabricates. Items are guarded: unknown `kind`, missing `label`, and
  out-of-range confidences are dropped/clamped; absent fields stay `null`.
- **Summary** — the patient's citation-tagged facts are sent as JSON. The model
  may cite **only** document ids present in the payload; any non-`flags` item
  whose citations don't resolve is dropped (enforced here **and** again in the
  RAG layer). Output is normalized to the canonical seven sections in order.
- **Embeddings** — one call to `EMBEDDING_MODEL`; each returned vector is
  validated against `EMBEDDING_DIM`.

## Safety (PROJECT.md §4)

- Prompts forbid inventing values — unreadable → omit / low confidence, never
  guess.
- Scan films get a **neutral caption + embedded text only**, never a pathology
  read.
- No diagnosis or treatment language in summaries — organize and surface only.
- **Every** non-`flags` summary item carries at least one resolvable citation,
  or it is dropped.
- Failures are loud: the document becomes `status=failed` with a reason, never a
  silently-dropped or fabricated result.
- No PHI in logs — only ids, model names, and exception **types** are logged.

## Cost / latency notes

- Extraction is the expensive call (image tokens). Gemini Flash class models are
  the cheapest credible multimodal option; keep image DPI modest (PDF pages are
  rendered at ~150 DPI) and cap pages (default 8).
- Summary and embedding calls are text-only and cheap.
- `temperature=0` for reproducibility; `num_retries` handles transient
  network/5xx errors; a 90s per-call timeout bounds latency.
- Ingestion is async (background worker), so extraction latency never blocks the
  upload request; the doctor's summary is generated on demand.

## Testing

- `pytest backend/tests/test_llm_stub.py` — exercises the stub path and the
  shared shapes (runs offline, no key).
- `python backend/scripts/test_llm.py` — real-mode smoke test on a generated
  sample image. In stub mode (no key) it prints a skip message and exits 0.

## Offline / self-hosted (MedGemma & open models)

Government hospitals often cannot send patient data to a third-party cloud. The
whole point of the LiteLLM abstraction (PROJECT.md §5, §8) is that the exact same
Doc-mate build runs **fully on-premise** — extraction, summary, embeddings,
translation, and voice — with **no data leaving the hospital network**. This
section is the concrete recipe.

### Why on-prem (the privacy rationale)

- **PHI never leaves the premises.** No image, lab value, or note is sent to an
  external API. This is the honest answer to "is patient data safe?" for a
  government deployment.
- **No per-call cost and no internet dependency.** Rural / intermittent-network
  sites keep working.
- **Auditable + swappable.** Providers are reached only through `app/llm/`, so
  moving from a cloud pilot to a self-hosted rollout is an **env-var change**,
  not a rewrite.

### MedGemma 1.5 (open-weight, multimodal)

MedGemma is Google's open-weight, medically-tuned Gemma variant; the **1.5**
release (open weights, Jan 2026) is multimodal — it reads scans, photographed
documents, and handwriting — which makes it a strong fit for Doc-mate's
extraction path. It is licensed for local deployment. Serve it behind an
OpenAI-compatible endpoint with **Ollama** or **vLLM**, then point the standard
env vars at the local server.

> Honesty note: real MedGemma inference **requires a GPU** (see hardware below).
> If you have no GPU, Doc-mate still runs end-to-end in **stub mode** (the
> default) with zero model dependencies — nothing below is needed for the
> offline demo path. Stub mode is for demos, not real clinical reading.

#### Option A — Ollama (simplest)

```bash
# On the box that has the GPU:
ollama pull medgemma-1.5            # multimodal open weights
ollama pull nomic-embed-text        # open embedding model (768-dim)

# Doc-mate env (backend/.env):
LLM_PROVIDER=ollama
LLM_MODEL_MULTIMODAL=ollama/medgemma-1.5     # extraction (scans/photos/handwriting)
LLM_MODEL_REASONING=ollama/medgemma-1.5      # summary + translation + simplification
EMBEDDING_MODEL=ollama/nomic-embed-text
EMBEDDING_DIM=768                            # MUST match the model + pgvector column
OLLAMA_API_KEY=local                         # any non-empty value → leaves stub mode
OLLAMA_API_BASE=http://localhost:11434
```

#### Option B — vLLM (higher throughput, OpenAI-compatible)

```bash
# Serve MedGemma with vLLM's OpenAI-compatible server (GPU host):
python -m vllm.entrypoints.openai.api_server \
  --model google/medgemma-1.5 --port 8000

# Doc-mate env:
LLM_PROVIDER=vllm
LLM_MODEL_MULTIMODAL=openai/google/medgemma-1.5
LLM_MODEL_REASONING=openai/google/medgemma-1.5
EMBEDDING_MODEL=ollama/nomic-embed-text      # or a vLLM-served embedding model
EMBEDDING_DIM=768
VLLM_API_KEY=local                           # any non-empty value → leaves stub mode
OPENAI_API_BASE=http://localhost:8000/v1     # vLLM speaks the OpenAI protocol
```

Confirm your LiteLLM version's exact base-URL variable (`OLLAMA_API_BASE` for
Ollama; `OPENAI_API_BASE` for vLLM's OpenAI endpoint). `EMBEDDING_DIM` **must**
equal what the embedding model emits **and** the pgvector column width — the real
`embed()` raises a clear error on a mismatch rather than failing at the DB.

### Multilingual + voice on-prem

The multilingual (`app/language/`) and voice (`app/voice/`) layers follow the
same stub-first / real-optional pattern and honor the same switch:

- **Translation & plain-language** — real mode routes through this same `app/llm`
  layer (so MedGemma or any open text model does the translating on-prem, with a
  prompt that preserves numbers/doses/drug names); the default is an offline
  **glossary** (bundled, no model) for the fixed section titles and common
  clinical phrases. Full sentence-level MT needs real mode.
- **Voice intake** — real mode uses **`faster-whisper`** (`small` / `base`)
  running **on-device** (CPU is fine; a GPU is faster), so intake audio never
  leaves the premises either. With the library or model absent it returns a
  deterministic stub transcription so the flow still works offline.

### Hardware notes (be honest with judges)

| Component | Stub mode | Real on-prem |
|-----------|-----------|--------------|
| MedGemma 1.5 (multimodal extraction + reasoning) | none | **GPU required** — ~16–24 GB VRAM for a quantized/small config; more for full precision. Ollama Q4 lowers the bar; vLLM maximizes throughput. |
| Open embeddings (e.g. `nomic-embed-text`) | none | CPU-workable; GPU faster |
| Whisper voice (`faster-whisper` small/base) | none | CPU fine (int8); GPU faster |
| Postgres + pgvector, MinIO | required | required |

Bottom line: **stub mode needs nothing** (no GPU, no keys, no internet) and is
the default; a real on-prem deployment of MedGemma **requires a GPU**, but buys
the privacy guarantee that makes Doc-mate credible for government hospitals.
