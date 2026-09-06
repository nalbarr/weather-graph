# Copyright (C) 2025 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
"""Vendored, patched subset of IBM's `kbel` package.

Upstream: https://github.com/IBM/kif-llm @ cb91defc42f9e3e4ebba776f8395b62746f8fd4d (2026-09-06),
subdirectory `kbel/src/kbel/`. License: Apache-2.0 (confirmed against that repo's root LICENSE
file, which is the Apache License 2.0 verbatim); the upstream SPDX headers are preserved in each
file below.

Why vendored: `kbel` is an *undeclared* runtime dependency of `llm_store` -- every `kb.filter()`
call unconditionally imports `kbel.disambiguators` -- yet nothing installs it alongside
`kif-llm-store`, and `kif-llm-store` itself is not installable in the first place (invalid TOML in
its own `pyproject.toml`, not on PyPI). Vendoring the two files actually needed sidesteps both.

What is here: `disambiguators/abc.py` and `disambiguators/simple.py` only. Deliberately NOT
vendored: `disambiguators/similarity.py` (pulls in `sentence-transformers`/`scikit-learn`/`numpy`)
and `disambiguators/llm/` (only reachable via `entity_linking_method=EntityLinkingMethod.LLM`,
which this repo never sets). Confirmed empirically that `abc.py` + `simple.py` import cleanly with
none of those heavy dependencies installed.

What was patched: `disambiguators/__init__.py` -- upstream re-exports only `Disambiguator`, so
`llm_store`'s own `from kbel.disambiguators import (Disambiguator, SimpleDisambiguator,
LLM_Disambiguator)` fails with `ImportError` on every filter call. `SimpleDisambiguator` is now
re-exported too; `LLM_Disambiguator` is not, since its module is not vendored (the matching change
is PATCH 3 in `../kif_llm_store/llm.py`). Every patch is marked with a `PATCH N (weather-graph
vendor)` comment at the edit site.

Full evidence, reproduction steps, and captured output: `analysis/kif_llm_analysis.md`.
"""
