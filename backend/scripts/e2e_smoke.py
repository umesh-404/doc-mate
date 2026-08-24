"""End-to-end smoke test for the Doc-mate backend.

Exercises the REAL HTTP API against a running backend, in stub (offline) LLM
mode, proving the full reception -> ingestion -> verify -> doctor-summary flow.

It assumes the stack is ALREADY UP and the backend env already points at it:

  * Postgres + pgvector reachable via ``DATABASE_URL``
  * MinIO (or S3) reachable via ``S3_ENDPOINT`` with the ``docmate`` bucket
  * Migrations applied (``alembic upgrade head``) and demo users seeded
    (``python -m scripts.seed``) — reception@demo / doctor@demo, pw ``demo1234``
  * The backend running at ``BASE_URL`` (default ``http://localhost:8000``),
    with LLM stub mode active (do NOT set ``LLM_PROVIDER``)

Configurable env (all optional):

  * ``E2E_BASE_URL``       backend base URL      (default http://localhost:8000)
  * ``E2E_RECEPTION_EMAIL``/``E2E_RECEPTION_PASSWORD``  (default reception@demo / demo1234)
  * ``E2E_DOCTOR_EMAIL``/``E2E_DOCTOR_PASSWORD``        (default doctor@demo / demo1234)
  * ``E2E_TIMEOUT``        per-poll wait budget, seconds (default 30)

Run (from backend/, with the venv active and env pointing at the stack)::

    python -m scripts.e2e_smoke

Exit code 0 => every step PASSED; non-zero => a step FAILED (details printed).
No external network or API keys are required; the stub LLM layer is used.
"""

from __future__ import annotations

import io
import os
import struct
import sys
import time
import uuid
import zlib
from typing import Any

import httpx

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000").rstrip("/")
RECEPTION_EMAIL = os.environ.get("E2E_RECEPTION_EMAIL", "reception@demo")
RECEPTION_PASSWORD = os.environ.get("E2E_RECEPTION_PASSWORD", "demo1234")
DOCTOR_EMAIL = os.environ.get("E2E_DOCTOR_EMAIL", "doctor@demo")
DOCTOR_PASSWORD = os.environ.get("E2E_DOCTOR_PASSWORD", "demo1234")
POLL_TIMEOUT = float(os.environ.get("E2E_TIMEOUT", "30"))
POLL_INTERVAL = 0.5


# ---------------------------------------------------------------------------
# Tiny reporting helpers
# ---------------------------------------------------------------------------
_step_no = 0


class SmokeError(AssertionError):
    """Raised when a step fails; message is printed as the FAIL reason."""


def step(title: str) -> None:
    global _step_no
    _step_no += 1
    print(f"\n[step {_step_no}] {title}")


def ok(msg: str) -> None:
    print(f"  PASS: {msg}")


def require(condition: bool, msg: str) -> None:
    if not condition:
        raise SmokeError(msg)
    ok(msg)


# ---------------------------------------------------------------------------
# Sample file generation (no external deps): a valid tiny PNG and a tiny PDF.
# ---------------------------------------------------------------------------
def make_png() -> bytes:
    """Build a minimal valid 1x1 opaque-red PNG in-memory."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(
            ">I", zlib.crc32(body) & 0xFFFFFFFF
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1, 8-bit RGB
    raw = b"\x00\xff\x00\x00"  # one filtered scanline: filter 0 + red pixel
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def make_pdf() -> bytes:
    """Build a minimal valid single-page PDF in-memory."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length 58 >>\nstream\nBT /F1 12 Tf 20 100 Td "
        b"(Doc-mate e2e sample) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n".encode()
    )
    out.write(f"startxref\n{xref_pos}\n%%EOF\n".encode())
    return out.getvalue()


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def login(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post(
        f"{BASE_URL}/auth/login", json={"email": email, "password": password}
    )
    require(
        resp.status_code == 200,
        f"login {email} -> 200 (got {resp.status_code}: {resp.text[:200]})",
    )
    token = resp.json().get("access_token")
    require(bool(token), f"login {email} returned an access_token")
    return token


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def poll_document_extracted(
    client: httpx.Client, headers: dict[str, str], doc_id: str
) -> dict[str, Any]:
    """Poll GET /documents/{id} until status is a terminal ingestion state."""
    deadline = time.time() + POLL_TIMEOUT
    last: dict[str, Any] = {}
    while time.time() < deadline:
        resp = client.get(f"{BASE_URL}/documents/{doc_id}", headers=headers)
        require(
            resp.status_code == 200,
            f"GET /documents/{doc_id} -> 200 (got {resp.status_code})",
        )
        last = resp.json()
        status = last.get("status")
        if status == "extracted":
            return last
        if status == "failed":
            raise SmokeError(
                f"document {doc_id} ingestion FAILED: {last.get('error')!r}"
            )
        time.sleep(POLL_INTERVAL)
    raise SmokeError(
        f"document {doc_id} not 'extracted' within {POLL_TIMEOUT}s "
        f"(last status={last.get('status')!r})"
    )


def poll_summary(
    client: httpx.Client, headers: dict[str, str], patient_id: str
) -> dict[str, Any]:
    """Poll GET /patients/{id}/summary until 200 with a body."""
    deadline = time.time() + POLL_TIMEOUT
    last_status = None
    while time.time() < deadline:
        resp = client.get(
            f"{BASE_URL}/patients/{patient_id}/summary", headers=headers
        )
        last_status = resp.status_code
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code not in (404,):
            raise SmokeError(
                f"GET summary unexpected status {resp.status_code}: "
                f"{resp.text[:200]}"
            )
        time.sleep(POLL_INTERVAL)
    raise SmokeError(
        f"summary for patient {patient_id} not ready within {POLL_TIMEOUT}s "
        f"(last status={last_status})"
    )


def upload_document(
    client: httpx.Client,
    headers: dict[str, str],
    patient_id: str,
    filename: str,
    content: bytes,
    content_type: str,
    doc_type: str,
) -> dict[str, Any]:
    files = {"file": (filename, content, content_type)}
    data = {"patient_id": patient_id, "doc_type": doc_type}
    resp = client.post(
        f"{BASE_URL}/documents", headers=headers, files=files, data=data
    )
    require(
        resp.status_code == 201,
        f"POST /documents ({filename}) -> 201 "
        f"(got {resp.status_code}: {resp.text[:200]})",
    )
    return resp.json()


# ---------------------------------------------------------------------------
# The flow
# ---------------------------------------------------------------------------
def run() -> None:
    client = httpx.Client(timeout=30.0)

    step("Reception logs in")
    reception_token = login(client, RECEPTION_EMAIL, RECEPTION_PASSWORD)
    rhead = auth(reception_token)

    step("Reception creates a patient")
    unique = uuid.uuid4().hex[:12]
    patient_payload = {
        "full_name": "E2E Smoke Patient",
        "age": 54,
        "sex": "female",
        "abha_id": f"E2E{unique}",
        "preferred_language": "en",
    }
    resp = client.post(
        f"{BASE_URL}/patients", headers=rhead, json=patient_payload
    )
    require(
        resp.status_code == 201,
        f"POST /patients -> 201 (got {resp.status_code}: {resp.text[:200]})",
    )
    patient = resp.json()
    patient_id = patient["id"]
    require(bool(patient_id), f"patient created with id={patient_id}")

    step("Reception uploads a PNG (scan film) and a PDF (lab report)")
    png_doc = upload_document(
        client, rhead, patient_id, "chest-xray.png",
        make_png(), "image/png", "scan_film",
    )
    pdf_doc = upload_document(
        client, rhead, patient_id, "lab-report.pdf",
        make_pdf(), "application/pdf", "lab_report",
    )
    doc_ids = [png_doc["id"], pdf_doc["id"]]
    require(
        all(doc_ids) and len(set(doc_ids)) == 2,
        f"two distinct documents created: {doc_ids}",
    )

    step("Ingestion completes (poll until status=extracted)")
    details: dict[str, dict[str, Any]] = {}
    for doc_id in doc_ids:
        detail = poll_document_extracted(client, rhead, doc_id)
        details[doc_id] = detail
        ok(f"document {doc_id} reached status=extracted")

    step("Extracted ClinicalItems exist with source_document_id + confidence")
    total_items = 0
    for doc_id, detail in details.items():
        items = detail.get("items") or []
        require(
            len(items) >= 1,
            f"document {doc_id} produced >=1 clinical item (got {len(items)})",
        )
        for it in items:
            require(
                str(it.get("source_document_id")) == str(doc_id),
                f"item {it.get('id')} references its source document {doc_id}",
            )
            require(
                isinstance(it.get("confidence"), (int, float)),
                f"item {it.get('id')} carries a numeric confidence "
                f"(got {it.get('confidence')!r})",
            )
        total_items += len(items)
    ok(f"total extracted clinical items across documents: {total_items}")

    step("Reception verifies both documents")
    for doc_id in doc_ids:
        resp = client.post(
            f"{BASE_URL}/documents/{doc_id}/verify", headers=rhead, json={}
        )
        require(
            resp.status_code == 200,
            f"POST /documents/{doc_id}/verify -> 200 "
            f"(got {resp.status_code}: {resp.text[:200]})",
        )
        body = resp.json()
        require(
            body.get("status") == "verified",
            f"document {doc_id} status is 'verified' (got {body.get('status')!r})",
        )
        require(
            all(it.get("verified") for it in (body.get("items") or [])),
            f"all clinical items on document {doc_id} are verified",
        )

    step("Doctor logs in")
    doctor_token = login(client, DOCTOR_EMAIL, DOCTOR_PASSWORD)
    dhead = auth(doctor_token)

    step("Doctor requests a summary (expect 202 Accepted)")
    resp = client.post(
        f"{BASE_URL}/patients/{patient_id}/summary", headers=dhead
    )
    require(
        resp.status_code == 202,
        f"POST /patients/{patient_id}/summary -> 202 "
        f"(got {resp.status_code}: {resp.text[:200]})",
    )

    step("Summary becomes available (poll GET until 200)")
    summary = poll_summary(client, dhead, patient_id)
    sections = summary.get("sections") or []
    require(len(sections) >= 1, f"summary has >=1 section (got {len(sections)})")
    section_keys = {s.get("key") for s in sections}
    ok(f"summary sections present: {sorted(k for k in section_keys if k)}")

    step("Every non-'flags' SummaryItem has a resolvable citation")
    resolvable_doc_ids = set(doc_ids)
    non_flag_items = 0
    cited_items = 0
    for section in sections:
        key = section.get("key")
        for item in section.get("items") or []:
            if key == "flags":
                continue
            non_flag_items += 1
            citations = item.get("citations") or []
            require(
                len(citations) >= 1,
                f"non-flags item in section '{key}' has >=1 citation "
                f"(text={item.get('text')!r})",
            )
            for cite in citations:
                cited_doc = str(cite.get("document_id"))
                require(
                    cited_doc in resolvable_doc_ids,
                    f"citation document_id {cited_doc} resolves to an "
                    f"uploaded document",
                )
            cited_items += 1
    require(
        non_flag_items >= 1,
        f"summary surfaced >=1 non-flags item (got {non_flag_items})",
    )
    ok(f"{cited_items} non-flags summary items all carry resolvable citations")

    client.close()


def main() -> int:
    print(f"Doc-mate e2e smoke test -> {BASE_URL}")
    started = time.time()
    try:
        run()
    except SmokeError as exc:
        print(f"\n  FAIL: {exc}")
        print("\n=== RESULT: FAIL ===")
        return 1
    except httpx.HTTPError as exc:
        print(f"\n  FAIL: HTTP transport error: {exc}")
        print("\n=== RESULT: FAIL (is the backend running at "
              f"{BASE_URL}?) ===")
        return 2
    elapsed = time.time() - started
    print(f"\n=== RESULT: PASS (all steps) in {elapsed:.1f}s ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
