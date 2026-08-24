"""Real provider calls via LiteLLM.

This is the ONLY module permitted to import a provider SDK / LiteLLM (see
PROJECT.md section 10). Everything here is reached exclusively through
:mod:`app.llm.service`, and only when a provider + API key are configured;
otherwise the deterministic stubs in :mod:`app.llm.stub` are used.

LiteLLM is imported lazily inside each function so the app still imports and
starts with the package absent (offline / stub-only deployments).

Real-mode safety rules (PROJECT.md section 4):
  * Never fabricate clinical values — the model is instructed to extract only.
  * Every summary line must cite a real source document; lines whose citations
    do not resolve to a provided document id are dropped here, not trusted.
"""

from __future__ import annotations

import base64
import json
import logging

from app.core.config import settings

logger = logging.getLogger("docmate.llm")


def _model(name: str | None, fallback: str) -> str:
    return (name or "").strip() or fallback


def _completion_json(model: str, system: str, user_content) -> dict:
    """Call a chat model and parse a JSON object from its reply."""
    import litellm  # lazy: provider SDK confined to this module

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    text = response["choices"][0]["message"]["content"]
    return json.loads(text)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
_EXTRACT_SYSTEM = (
    "You are a clinical document extraction engine for an Indian hospital "
    "intake desk. Extract ONLY facts that are literally present in the "
    "document. Never guess or infer medication names, doses, lab values, or "
    "dates. If a value is unreadable, omit it. For imaging/scan films, return "
    "only a neutral caption and any embedded text — never a pathology reading. "
    "Respond as a JSON object with keys 'extracted_text' (string) and 'items' "
    "(array). Each item has: kind (one of observation|medication|allergy|"
    "condition|procedure), label (string), value (string|null), unit "
    "(string|null), date (ISO 8601 string|null), confidence (0..1 number)."
)


def extract_document(
    file_bytes: bytes,
    mime: str | None,
    doc_type: str,
    seed: str | None = None,
) -> dict:
    """Extract structured clinical items from a document via a vision model."""
    model = _model(settings.llm_model_multimodal, "gpt-4o-mini")
    mime = mime or "application/octet-stream"

    user_content: object
    if mime.startswith("image/"):
        b64 = base64.b64encode(file_bytes).decode("ascii")
        user_content = [
            {
                "type": "text",
                "text": f"Document type hint: {doc_type}. Extract clinical facts.",
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            },
        ]
    else:
        # Text-bearing formats: hand the decoded text to the model.
        text = _decode_text(file_bytes, mime)
        user_content = (
            f"Document type hint: {doc_type}. Extract clinical facts from the "
            f"following document text:\n\n{text}"
        )

    data = _completion_json(model, _EXTRACT_SYSTEM, user_content)
    items = data.get("items") or []
    # Normalize/guard the shape; never invent values that are missing.
    norm_items: list[dict] = []
    for raw in items:
        if not isinstance(raw, dict) or not raw.get("kind") or not raw.get("label"):
            continue
        norm_items.append(
            {
                "kind": str(raw["kind"]),
                "label": str(raw["label"]),
                "value": raw.get("value"),
                "unit": raw.get("unit"),
                "date": raw.get("date"),
                "confidence": raw.get("confidence"),
                "data": {"stub": False},
            }
        )
    return {
        "extracted_text": str(data.get("extracted_text") or ""),
        "items": norm_items,
    }


def _decode_text(file_bytes: bytes, mime: str) -> str:
    """Best-effort text extraction for PDFs / plain text."""
    if mime == "application/pdf":
        try:
            import io

            from pypdf import PdfReader  # lazy optional dep

            reader = PdfReader(io.BytesIO(file_bytes))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            logger.warning("pdf text extraction failed; falling back to raw decode")
    return file_bytes.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------
_SUMMARY_SYSTEM = (
    "You assemble a structured, citation-backed patient snapshot for a doctor. "
    "You may ONLY use the clinical facts provided; never add outside knowledge, "
    "never state a diagnosis or treatment. Every summary item MUST cite at "
    "least one of the provided document ids. Respond as a JSON object with key "
    "'sections' (array). Each section has key (one of complaint|problems|"
    "allergies|medications|labs|encounters|flags), title (string), and items "
    "(array). Each item has text (string), severity (high|med|low|null), trend "
    "(up|down|flat|null), confidence (0..1|null), verified (bool|null), and "
    "citations (array of {document_id, label})."
)


def generate_summary(patient: dict, items: list[dict]) -> list[dict]:
    """Generate summary sections from grounded clinical facts via a model."""
    model = _model(settings.llm_model_reasoning, "gpt-4o-mini")
    language = patient.get("preferred_language", "en")
    allowed_ids = {str(it["document_id"]) for it in items}

    payload = {
        "patient": {
            "full_name": patient.get("full_name"),
            "age": patient.get("age"),
            "sex": patient.get("sex"),
            "language": language,
        },
        "facts": items,
        "instruction": (
            f"Write the snapshot in language code '{language}'. Only cite "
            "document ids from the provided facts."
        ),
    }
    data = _completion_json(model, _SUMMARY_SYSTEM, json.dumps(payload, default=str))

    sections = data.get("sections") or []
    # Enforce citation grounding: drop any non-flag item whose citations do not
    # resolve to a provided document id.
    for section in sections:
        key = section.get("key")
        kept = []
        for item in section.get("items", []):
            cites = [
                c
                for c in (item.get("citations") or [])
                if str(c.get("document_id")) in allowed_ids
            ]
            if not cites and key != "flags":
                continue
            item["citations"] = cites
            kept.append(item)
        section["items"] = kept
    return sections


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
def embed(texts: list[str]) -> list[list[float]]:
    """Embed texts via the configured embedding model."""
    import litellm  # lazy: provider SDK confined to this module

    model = _model(settings.embedding_model, "text-embedding-3-small")
    response = litellm.embedding(model=model, input=texts)
    return [row["embedding"] for row in response["data"]]
