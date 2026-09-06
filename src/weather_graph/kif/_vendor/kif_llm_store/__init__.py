# Copyright (C) 2025 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
"""Vendored, patched subset of IBM's `kif-llm-store` (`LLM_Store`).

Upstream: https://github.com/IBM/kif-llm @ cb91defc42f9e3e4ebba776f8395b62746f8fd4d (2026-09-06),
subdirectory `llm_store/` (note: https://github.com/IBM/kif-llm-store 301-redirects there).
License: Apache-2.0 (confirmed against that repo's root LICENSE file, which is the Apache License
2.0 verbatim); the upstream SPDX headers are preserved in each file below.

Why vendored rather than depended on: the package is not installable, on any branch, as of that
commit. Its own `pyproject.toml` is invalid TOML (a trailing comma on line 17), so `uv pip install
"kif-llm-store @ git+..."` fails at the build-metadata step, and it is not published to PyPI. See
`analysis/kif_llm_analysis.md` for the reproductions.

What is here: everything under `llm_store/` EXCEPT `context_generator/` and `query_to_question/`,
neither of which is imported by any module retained here nor reachable from this repo's fixed
weather questions. `utils.py` is kept verbatim for fidelity even though nothing retained imports
it (its `torch`/`sentence-transformers` imports are function-local, so it costs nothing).

What was patched -- three edits, each marked in place with a `PATCH N (weather-graph vendor)`
comment:

  1. `compiler/llm/filter_compiler.py` -- upstream's absolute `from llm_store.constants import ...`
     made relative (`from ...constants import ...`). Upstream only resolves if the package is
     installed under the directory name `llm_store`, contradicting its own documented import name
     `kif_llm_store`; relative import works under either name.
  2. `../kbel/disambiguators/__init__.py` -- missing `SimpleDisambiguator` re-export added (see
     that file's own header).
  3. `llm.py` `_disambiguate()` -- the top-level `from kbel.disambiguators import ...` retargeted
     at the vendored `kbel` subset (`from ..kbel.disambiguators import ...`) and the unused
     `LLM_Disambiguator` name dropped, since its module is not vendored. Consequence, stated
     plainly: `entity_linking_method=EntityLinkingMethod.LLM` would now fail with "no such
     disambiguator plugin 'llm'" instead of working. This repo never sets it (its properties are
     quantity/string-valued, which skip disambiguation entirely).

Not patched, but worth knowing about when using this: `LLM_Store.__init__` requires `target_store`
and `searcher` positionally (its README's own quickstart omits them and raises `TypeError`), and
`model_params=None` -- its own default -- crashes `_init_model`. Both are worked around at the call
site in `../../llm_store.py` rather than by editing upstream code. `output_parsers.py` can also
raise an uncaught `decimal.InvalidOperation` when the model's answer contains no digits; that too
is handled at the call site.

Delete this directory once `kif-llm-store` ships installable on PyPI; the three PATCH markers above
are what to diff against. Full evidence: `analysis/kif_llm_analysis.md`.
"""

from .llm import LLM_Store, PromptExample

__all__ = ('LLM_Store', 'PromptExample')
