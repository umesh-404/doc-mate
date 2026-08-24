"""Standalone smoke test for the LLM layer's REAL provider path.

Run it from the repo root::

    python backend/scripts/test_llm.py

Behaviour:
  * If real mode is configured (LLM_PROVIDER points at a real provider AND the
    matching <PROVIDER>_API_KEY is present in the environment), it runs a tiny
    real extraction on a generated sample image, a summary, and an embedding,
    then prints the resulting shapes.
  * Otherwise it prints a clear "stub mode / no key -- skipping real test"
    message and exits 0. It NEVER fails just because no key is configured.

This is a developer smoke test, not part of the pytest suite. It makes real,
billable provider calls only when real mode is configured.
"""

from __future__ import annotations

import io
import os
import sys
import uuid

# Make ``app`` importable when run as ``python backend/scripts/test_llm.py``.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.core.config import settings  # noqa: E402
from app.llm import service as llm  # noqa: E402


def _sample_prescription_png() -> bytes:
    """Generate a tiny synthetic prescription image (PIL, always available).

    Synthetic demo content only — no real patient data.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "City General Hospital - OP Prescription",
        "Patient: Demo Patient   Age: 54   Sex: F",
        "Date: 2026-05-12",
        "",
        "Rx:",
        "1) Metformin 500mg   1-0-1  x 30 days",
        "2) Amlodipine 5mg    1-0-0  x 30 days",
        "Allergy: Penicillin",
    ]
    y = 20
    for line in lines:
        draw.text((20, y), line, fill="black")
        y += 34
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _run_real_test() -> int:
    print(f"Real mode ACTIVE  provider={settings.llm_provider!r}")
    print(f"  multimodal model = {settings.llm_model_multimodal!r}")
    print(f"  reasoning  model = {settings.llm_model_reasoning!r}")
    print(f"  embedding  model = {settings.embedding_model!r}  dim={settings.embedding_dim}")
    print("-" * 60)

    # 1) Extraction on a generated sample image.
    print("[1/3] extract_document (vision, sample prescription image) ...")
    image = _sample_prescription_png()
    extraction = llm.extract_document(image, "image/png", "prescription", seed="smoke")
    items = extraction.get("items", [])
    print(f"      extracted_text: {len(extraction.get('extracted_text', ''))} chars")
    print(f"      items: {len(items)}")
    for it in items[:8]:
        print(
            f"        - {it.get('kind'):<11} {it.get('label')!r} "
            f"value={it.get('value')!r} unit={it.get('unit')!r} "
            f"conf={it.get('confidence')}"
        )

    # 2) Summary over grounded, cited facts.
    print("[2/3] generate_summary (structured, cited) ...")
    doc_id = str(uuid.uuid4())
    context = []
    for it in items:
        context.append(
            {
                **it,
                "verified": True,
                "document_id": doc_id,
                "citation_label": "Rx - 12 May",
            }
        )
    if not context:
        # Ensure the summary call has at least one grounded fact to work with.
        context = [
            {
                "kind": "medication",
                "label": "Metformin 500mg",
                "value": "1-0-1",
                "unit": None,
                "date": "2026-05-12",
                "confidence": 0.9,
                "verified": True,
                "document_id": doc_id,
                "citation_label": "Rx - 12 May",
            }
        ]
    patient = {"full_name": "Demo Patient", "age": 54, "sex": "F", "preferred_language": "en"}
    sections = llm.generate_summary(patient, context)
    print(f"      sections: {[s.get('key') for s in sections]}")
    for s in sections:
        if s.get("items"):
            print(f"        {s['key']}: {len(s['items'])} item(s)")

    # 3) Embedding a couple of chunks.
    print("[3/3] embed (2 chunks) ...")
    vectors = llm.embed(["chronic hypertension follow-up", "HbA1c 7.8 percent"])
    dims = [len(v) for v in vectors]
    print(f"      vectors: {len(vectors)}  dims={dims}  (EMBEDDING_DIM={settings.embedding_dim})")

    print("-" * 60)
    print("Real-mode smoke test completed OK.")
    return 0


def main() -> int:
    if llm.is_stub_mode():
        reason = (
            "no LLM_PROVIDER set"
            if not (settings.llm_provider or "").strip()
            else f"provider '{settings.llm_provider}' has no API key in the environment"
        )
        print(f"Stub mode / no key -- skipping real test ({reason}).")
        print("To enable real mode, set LLM_PROVIDER, the model vars, and the")
        print("matching <PROVIDER>_API_KEY (see docs/LLM.md). Exiting 0.")
        return 0

    try:
        return _run_real_test()
    except Exception as exc:  # noqa: BLE001 — smoke test: report, do not traceback-dump
        print(f"Real-mode smoke test FAILED: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
