"""LLM layer.

The ONLY place in the backend where LLM / embedding provider SDKs may be
imported or called (see PROJECT.md sections 5 and 10). Feature code must go
through the wrapper defined here rather than importing providers directly.
Provider integration (LiteLLM-based, env-driven, swappable) lands later.
"""
