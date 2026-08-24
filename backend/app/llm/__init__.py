"""LLM layer.

The ONLY place in the backend where LLM / embedding provider SDKs may be
imported or called (see PROJECT.md sections 5 and 10). Feature code must go
through :mod:`app.llm.service` rather than importing providers directly.

Provider integration is LiteLLM-based, env-driven, and swappable. When no
provider/key is configured the layer falls back to deterministic offline stubs
so the whole pipeline runs with no credentials (the default).
"""

from __future__ import annotations

from app.llm.service import embed, extract_document, generate_summary, is_stub_mode

__all__ = ["extract_document", "generate_summary", "embed", "is_stub_mode"]
