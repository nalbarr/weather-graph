"""Mellea generation layer (principles P1 + P2 from the original main.py demo).

`nl_to_sparql` is a Mellea `@generative` function: its signature + docstring instruct the LLM, and
its return-type annotation (`WeatherSparqlSpec`) is enforced via structured output. At call time we
attach natural-language `requirements` and a `RejectionSamplingStrategy`, which is Mellea's
instruct-validate-repair (IVR) loop. We then additionally hard-validate the produced SPARQL with our
own pure-Python validator and repair once more if needed.

API note: Mellea 0.7 changed the surface from the original template — `@generative` is a *bare*
decorator, requirements/strategy are passed at call time, and the generated function takes a
`MelleaSession` as its first argument.
"""

from __future__ import annotations

import functools
import os

from mellea import MelleaSession, generative, start_session
from mellea.stdlib.sampling import RejectionSamplingStrategy

from .models import ALLOWED_PREDICATES, WX, WeatherSparqlSpec
from .sparql import SparqlValidationError, validate_query

# Ollama model name as Ollama itself knows it (not the "ollama:" prefixed BeeAI form).
MELLEA_MODEL = os.environ.get("MELLEA_MODEL", "granite4:micro")

_REQUIREMENTS = [
    "The `sparql` field must be a single read-only SPARQL SELECT query.",
    f"It must declare PREFIX wx: <{WX}> .",
    f"It may only use these predicates: {', '.join('wx:' + p for p in ALLOWED_PREDICATES)}.",
    "It must always include a LIMIT clause (default LIMIT 10 when the user gives no count).",
    "It must never contain INSERT, DELETE, DROP, LOAD or any write operation.",
    "The `intent` field must restate the user's question in one sentence.",
]


@functools.lru_cache(maxsize=1)
def get_session() -> MelleaSession:
    """Create (once) a Mellea session backed by local Ollama granite4:micro."""
    return start_session(backend_name="ollama", model_id=MELLEA_MODEL, timeout=600.0)


@generative
def nl_to_sparql(question: str) -> WeatherSparqlSpec:
    """Translate a natural-language weather question into a structured, valid SPARQL spec.

    The graph describes cities with wx:name, wx:country, wx:temperatureC, wx:condition and
    wx:humidity. Produce a SELECT query that answers the question.
    """


def generate_spec(question: str, *, max_repairs: int = 1) -> WeatherSparqlSpec:
    """Generate a spec via Mellea (with IVR), then hard-validate; repair once more on failure."""
    m = get_session()
    spec: WeatherSparqlSpec = nl_to_sparql(
        m,
        requirements=_REQUIREMENTS,
        strategy=RejectionSamplingStrategy(loop_budget=3),
        question=question,
    )
    attempts = 0
    while attempts <= max_repairs:
        try:
            validate_query(spec.sparql)
            return spec
        except SparqlValidationError as exc:
            attempts += 1
            if attempts > max_repairs:
                raise
            spec = nl_to_sparql(
                m,
                requirements=_REQUIREMENTS,
                strategy=RejectionSamplingStrategy(loop_budget=3),
                question=(
                    f"{question}\n\nThe previous query was rejected: {exc}\n"
                    "Return a corrected query."
                ),
            )
    return spec
