"""Real provider calls via LiteLLM.

This is the ONLY module permitted to import a provider SDK / LiteLLM (see
PROJECT.md section 10). Everything here is reached exclusively through
:mod:`app.llm.service`, and only when a provider + API key are configured;
otherwise the deterministic stubs in :mod:`app.llm.stub` are used.

LiteLLM (and every optional parsing dependency) is imported lazily inside each
function so the app still imports and starts with the packages absent (offline /
stub-only deployments never pay for them, and a missing key never crashes at
import).

Real-mode safety rules (PROJECT.md section 4):
  * Never fabricate clinical values — the model is instructed to extract only
    what is literally present; unreadable fields are omitted, never guessed.
  * Imaging/scan films get a neutral caption + embedded text only, never a
    pathology read.
  * Every summary line must cite a real source document; lines whose citations
    do not resolve to a provided document id are dropped here, not trusted.
  * On unrecoverable model/parse failure we raise, so the pipeline marks the
    document ``failed`` (faithful status reporting) rather than inventing data.
"""

from __future__ import annotations

import base64
import json
import logging
import re

from app.core.config import settings

logger = logging.getLogger("docmate.llm")

# Conservative generation limits. Kept here (not in global config) because they
# are provider-call tuning, not app configuration.
_COMPLETION_TIMEOUT = 90  # seconds per model call
_NUM_RETRIES = 2  # LiteLLM-level retries for transient (network / 5xx) errors
_MAX_ITEMS = 60  # guardrail: never accept an unbounded item list from a model
_ALLOWED_KINDS = {
    "observation",
    "medication",
    "allergy",
    "condition",
    "procedure",
}
_SECTION_TITLES: dict[str, str] = {
    "complaint": "Current complaint / reason for visit",
    "problems": "Active problems & chronic conditions",
    "allergies": "Allergies",
    "medications": "Current medications",
    "labs": "Recent labs & trends",
    "encounters": "Past encounters / procedures",
    "flags": "Flags & things to verify",
}
_SECTION_ORDER = list(_SECTION_TITLES.keys())


class LLMProviderError(RuntimeError):
    """Raised when a real provider call fails unrecoverably.

    The message deliberately carries only provider/model/parse context — never
    document content — so it is safe to surface as a document ``error_reason``.
    """


def _model(name: str | None, fallback: str) -> str:
    return (name or "").strip() or fallback


# ---------------------------------------------------------------------------
# JSON extraction / repair
# ---------------------------------------------------------------------------
def _loads_lenient(text: str) -> dict:
    """Parse a JSON object out of a model reply that may be wrapped/noisy.

    Handles the common ways a model breaks strict JSON: markdown ```json
    fences, leading/trailing prose, and a trailing comma. Raises
    :class:`ValueError` if no object can be recovered.
    """
    if not text or not text.strip():
        raise ValueError("empty model reply")

    candidate = text.strip()

    # Strip a fenced code block if present (```json ... ``` or ``` ... ```).
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost brace-delimited object.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        inner = candidate[start : end + 1]
        # Drop trailing commas before a closing brace/bracket.
        inner = re.sub(r",\s*([}\]])", r"\1", inner)
        return json.loads(inner)

    raise ValueError("no JSON object found in model reply")


def _completion_json(model: str, system: str, user_content) -> dict:
    """Call a chat model and return a parsed JSON object.

    Strategy for production robustness:
      1. Ask for a JSON object via ``response_format`` when the provider
         supports it; retry once without it if the provider rejects the param.
      2. Parse leniently (fences / surrounding prose tolerated).
      3. On a parse failure, make ONE repair round-trip that hands the model its
         own malformed output and asks for strict JSON only.
      4. Anything still unparseable raises :class:`LLMProviderError`.
    """
    import litellm  # lazy: provider SDK confined to this module

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    def _call(msgs, use_json_mode: bool) -> str:
        kwargs = dict(
            model=model,
            messages=msgs,
            temperature=0.0,
            timeout=_COMPLETION_TIMEOUT,
            num_retries=_NUM_RETRIES,
        )
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = litellm.completion(**kwargs)
        return response["choices"][0]["message"]["content"] or ""

    # 1. Primary attempt (JSON mode first, falling back if unsupported).
    try:
        raw = _call(messages, use_json_mode=True)
    except Exception as exc:  # provider may reject response_format
        logger.info(
            "json-mode completion rejected (%s); retrying without response_format",
            type(exc).__name__,
        )
        try:
            raw = _call(messages, use_json_mode=False)
        except Exception as exc2:  # noqa: BLE001 — surface as clean provider error
            raise LLMProviderError(
                f"completion failed for model '{model}': {type(exc2).__name__}"
            ) from exc2

    try:
        return _loads_lenient(raw)
    except ValueError:
        logger.info("model reply was not valid JSON; attempting one repair pass")

    # 3. Repair round-trip: feed the bad output back and demand strict JSON.
    repair_messages = messages + [
        {"role": "assistant", "content": raw},
        {
            "role": "user",
            "content": (
                "Your previous reply was not valid JSON. Reply again with ONLY a "
                "single valid JSON object and no other text, no markdown fences."
            ),
        },
    ]
    try:
        repaired = _call(repair_messages, use_json_mode=False)
        return _loads_lenient(repaired)
    except Exception as exc:  # noqa: BLE001
        raise LLMProviderError(
            f"could not parse JSON from model '{model}': {type(exc).__name__}"
        ) from exc


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
_EXTRACT_SYSTEM = (
    "You are a clinical document extraction engine for an Indian government "
    "hospital intake desk. Extract ONLY facts literally present in the "
    "document. NEVER guess or infer medication names, doses, lab values, units, "
    "or dates. If a value is unreadable or absent, omit that field (leave it "
    "null) or omit the item entirely — do not fabricate. Lower the confidence "
    "for anything faint, handwritten, or ambiguous. For imaging/scan films "
    "(X-ray, MRI, CT, ultrasound) return ONLY a neutral one-line caption plus "
    "any text printed on the film — never a pathology reading, impression, or "
    "diagnosis. Do not add clinical interpretation of any kind.\n\n"
    "Respond with a SINGLE JSON object (no prose, no markdown) of the form:\n"
    "{\n"
    '  "extracted_text": string,   // faithful transcription of readable text\n'
    '  "items": [\n'
    "    {\n"
    '      "kind": "observation" | "medication" | "allergy" | "condition" | '
    '"procedure",\n'
    '      "label": string,        // e.g. "HbA1c", "Metformin 500mg"\n'
    '      "value": string | null, // e.g. "7.8", "1-0-1"\n'
    '      "unit": string | null,  // e.g. "%", "mg/dL"\n'
    '      "date": string | null,  // ISO 8601 (YYYY-MM-DD) if present\n'
    '      "confidence": number    // 0..1, your reading certainty\n'
    "    }\n"
    "  ]\n"
    "}"
)


def _clamp_confidence(value) -> float | None:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return None
    if conf < 0.0:
        return 0.0
    if conf > 1.0:
        return 1.0
    return round(conf, 3)


def _normalize_items(raw_items) -> list[dict]:
    """Guard/normalize model items to the pipeline contract shape.

    Drops anything without a valid ``kind`` in the allowed set or without a
    ``label``. Never invents missing values — absent fields stay ``None``.
    """
    norm: list[dict] = []
    if not isinstance(raw_items, list):
        return norm
    for raw in raw_items[:_MAX_ITEMS]:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "").strip().lower()
        label = raw.get("label")
        if kind not in _ALLOWED_KINDS or not label:
            continue

        def _clean(field):
            v = raw.get(field)
            if v is None:
                return None
            v = str(v).strip()
            return v or None

        norm.append(
            {
                "kind": kind,
                "label": str(label).strip(),
                "value": _clean("value"),
                "unit": _clean("unit"),
                "date": _clean("date"),
                "confidence": _clamp_confidence(raw.get("confidence")),
                "data": {"stub": False},
            }
        )
    return norm


def extract_document(
    file_bytes: bytes,
    mime: str | None,
    doc_type: str,
    seed: str | None = None,
) -> dict:
    """Extract text + structured clinical items from a document.

    Images (and PDF pages, when they can be rendered) are sent to a
    vision-capable model as base64 data URLs — the multimodal path that handles
    scans and handwriting. Text-bearing PDFs / plain text are decoded and sent
    as text. Returns ``{"extracted_text": str, "items": [...]}`` matching the
    LLM-layer contract. Raises :class:`LLMProviderError` on unrecoverable
    failure so the pipeline can mark the document ``failed`` rather than
    fabricate.
    """
    model = _model(settings.llm_model_multimodal, "gpt-4o-mini")
    mime = (mime or "application/octet-stream").lower()
    hint = (
        f"Document type hint: {doc_type}. Transcribe readable text and extract "
        "clinical facts. Follow the safety rules exactly."
    )

    user_content: object
    if mime.startswith("image/"):
        user_content = [
            {"type": "text", "text": hint},
            _image_part(file_bytes, mime),
        ]
    elif mime == "application/pdf":
        images = _pdf_page_images(file_bytes)
        if images:
            # Prefer the multimodal path: it survives scanned / photographed PDFs
            # and handwriting that text extraction cannot read.
            user_content = [{"type": "text", "text": hint}, *images]
        else:
            text = _decode_text(file_bytes, mime)
            user_content = f"{hint}\n\nDocument text:\n\n{text}"
    else:
        text = _decode_text(file_bytes, mime)
        user_content = f"{hint}\n\nDocument text:\n\n{text}"

    data = _completion_json(model, _EXTRACT_SYSTEM, user_content)
    return {
        "extracted_text": str(data.get("extracted_text") or ""),
        "items": _normalize_items(data.get("items")),
    }


def _image_part(image_bytes: bytes, mime: str) -> dict:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}"},
    }


def _pdf_page_images(file_bytes: bytes, max_pages: int = 8) -> list[dict]:
    """Render PDF pages to PNG image parts for the vision model.

    Uses PyMuPDF if it is installed; returns ``[]`` when it is not, so the
    caller falls back to text extraction. Never raises — rendering is a
    best-effort enhancement.
    """
    try:
        import io

        import fitz  # PyMuPDF — optional; absent in minimal installs
    except Exception:
        return []

    parts: list[dict] = []
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
            for page in pdf[:max_pages]:
                pix = page.get_pixmap(dpi=150)
                png = pix.tobytes("png")
                parts.append(_image_part(png, "image/png"))
    except Exception as exc:  # noqa: BLE001 — fall back to text on any failure
        logger.info("pdf->image render failed (%s); using text path", type(exc).__name__)
        return []
    _ = io  # keep import local/obvious even if unused directly
    return parts


def _decode_text(file_bytes: bytes, mime: str) -> str:
    """Best-effort text extraction for PDFs / plain text."""
    if mime == "application/pdf":
        try:
            import io

            from pypdf import PdfReader  # lazy optional dep

            reader = PdfReader(io.BytesIO(file_bytes))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            if text.strip():
                return text
        except Exception:
            logger.info("pdf text extraction failed; falling back to raw decode")
    return file_bytes.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------
_SUMMARY_SYSTEM = (
    "You assemble a structured, citation-backed patient snapshot for a doctor "
    "to read in under a minute. You may ONLY use the clinical facts provided in "
    "the payload; never add outside knowledge. You NEVER state a diagnosis, an "
    "impression, or a treatment recommendation — you organize and surface, the "
    "doctor concludes. Every item in every section EXCEPT 'flags' MUST cite at "
    "least one of the provided document ids; if you cannot cite a fact, omit "
    "it. Put uncertain, unverified, contradictory, or missing-data notes under "
    "'flags'. Write all human-readable text in the requested language code.\n\n"
    "Respond with a SINGLE JSON object (no prose, no markdown):\n"
    "{\n"
    '  "sections": [\n'
    "    {\n"
    '      "key": "complaint" | "problems" | "allergies" | "medications" | '
    '"labs" | "encounters" | "flags",\n'
    '      "title": string,\n'
    '      "items": [\n'
    "        {\n"
    '          "text": string,\n'
    '          "severity": "high" | "med" | "low" | null,\n'
    '          "trend": "up" | "down" | "flat" | null,\n'
    '          "confidence": number | null,\n'
    '          "verified": boolean | null,\n'
    '          "citations": [ { "document_id": string, "label": string } ]\n'
    "        }\n"
    "      ]\n"
    "    }\n"
    "  ]\n"
    "}"
)


def generate_summary(patient: dict, items: list[dict]) -> list[dict]:
    """Generate citation-backed summary sections from grounded facts.

    ``items`` are normalized clinical facts, each carrying ``document_id`` and
    ``citation_label``. The model may only cite ids present here; any item whose
    citations do not resolve (in a non-``flags`` section) is dropped. Output is
    normalized to the canonical seven sections in order so the shape matches the
    stub and the frontend, regardless of what the model returns.
    """
    model = _model(settings.llm_model_reasoning, "gpt-4o-mini")
    language = patient.get("preferred_language") or patient.get("language") or "en"
    allowed_ids = {str(it.get("document_id")) for it in items if it.get("document_id")}

    payload = {
        "patient": {
            "full_name": patient.get("full_name"),
            "age": patient.get("age"),
            "sex": patient.get("sex"),
            "language": language,
        },
        "facts": items,
        "instruction": (
            f"Write every title and text in language code '{language}'. Only "
            "cite document ids that appear in facts[].document_id. Do not state "
            "a diagnosis or treatment."
        ),
    }
    data = _completion_json(
        model, _SUMMARY_SYSTEM, json.dumps(payload, default=str, ensure_ascii=False)
    )

    raw_sections = data.get("sections")
    by_key: dict[str, dict] = {}
    if isinstance(raw_sections, list):
        for section in raw_sections:
            if not isinstance(section, dict):
                continue
            key = str(section.get("key") or "").strip().lower()
            if key not in _SECTION_TITLES:
                continue
            by_key[key] = section

    # Rebuild in canonical order, enforcing citation grounding.
    sections: list[dict] = []
    for key in _SECTION_ORDER:
        section = by_key.get(key, {})
        title = str(section.get("title") or "").strip() or _SECTION_TITLES[key]
        kept: list[dict] = []
        for item in section.get("items", []) or []:
            if not isinstance(item, dict) or not item.get("text"):
                continue
            cites = [
                {"document_id": str(c.get("document_id")), "label": c.get("label") or "Source"}
                for c in (item.get("citations") or [])
                if isinstance(c, dict) and str(c.get("document_id")) in allowed_ids
            ]
            if not cites and key != "flags":
                continue  # citation rule: no source -> not shown
            kept.append(
                {
                    "text": str(item["text"]),
                    "severity": item.get("severity"),
                    "trend": item.get("trend"),
                    "confidence": _clamp_confidence(item.get("confidence")),
                    "verified": item.get("verified"),
                    "citations": cites,
                }
            )
        sections.append({"key": key, "title": title, "items": kept})
    return sections


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
def embed(texts: list[str]) -> list[list[float]]:
    """Embed texts via the configured embedding model.

    Returns one vector per input text, each of length ``EMBEDDING_DIM``. Raises
    :class:`LLMProviderError` if the provider returns a different dimensionality
    than configured — a wrong-width vector cannot be stored in the pgvector
    column, so failing loudly here (with a clear message) beats a cryptic DB
    error later. The deterministic local fallback for stub mode lives in
    :mod:`app.llm.stub`.
    """
    if not texts:
        return []

    import litellm  # lazy: provider SDK confined to this module

    model = _model(settings.embedding_model, "text-embedding-3-small")
    expected = settings.embedding_dim

    try:
        response = litellm.embedding(
            model=model,
            input=texts,
            timeout=_COMPLETION_TIMEOUT,
            num_retries=_NUM_RETRIES,
        )
    except Exception as exc:  # noqa: BLE001
        raise LLMProviderError(
            f"embedding call failed for model '{model}': {type(exc).__name__}"
        ) from exc

    vectors = [row["embedding"] for row in response["data"]]
    for vec in vectors:
        if len(vec) != expected:
            raise LLMProviderError(
                f"embedding model '{model}' returned dim {len(vec)} but "
                f"EMBEDDING_DIM is {expected}; set EMBEDDING_DIM to match the "
                "model (and the pgvector column) before enabling real mode"
            )
    return vectors
