# Copyright (C) 2025 IBM Corp.
# SPDX-License-Identifier: Apache-2.0

# PATCH 2 (weather-graph vendor): upstream re-exports only `Disambiguator` here, so
# `llm_store/llm.py`'s `from kbel.disambiguators import (Disambiguator, SimpleDisambiguator,
# LLM_Disambiguator)` raises ImportError on every kb.filter() call. `SimpleDisambiguator` is added
# below (importing it is also what registers the 'simple' plugin). `LLM_Disambiguator` is *not*
# re-exported: `llm/llm_disambiguator.py` was deliberately not vendored (unused at this repo's
# scope) -- see PATCH 3 in ../../kif_llm_store/llm.py. See analysis/kif_llm_analysis.md blocker #6.
from .abc import Disambiguator
from .simple import SimpleDisambiguator

__all__ = ('Disambiguator', 'SimpleDisambiguator')
