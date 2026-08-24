"""Ingestion pipeline package.

Classify -> extract (vision-LLM / stub) -> structure -> chunk -> embed -> index
(see PROJECT.md section 6a). The orchestrator lives in :mod:`app.ingestion.pipeline`.
"""
