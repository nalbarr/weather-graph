"""Vendored, patched third-party source — not weather-graph code.

Holds a minimal patched subset of IBM's `kif-llm` monorepo (`kif_llm_store/`, `kbel/`), vendored
because the upstream packages cannot currently be pip-installed at all. See each subpackage's
`__init__.py` header and `analysis/kif_llm_analysis.md` for the full evidence. Delete this whole
directory and depend on the real packages once `kif-llm-store` ships installable on PyPI.
"""
