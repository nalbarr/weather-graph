"""Runnable demo: the same 3 weather questions, answered by *both* KIF Store backends side by side.

Run: `uv run weather-graph-kif-llm`
(requires `make qlever-up` for the SPARQL side, a local Ollama with `KIF_LLM_MODEL` pulled for the
LLM side, and `uv sync --extra kif-llm` — see docs/QUICKSTART.md).

The comparison *is* the demo (plans/PLAN_KIF_LLM.md, objective 5). Both backends are called through
the identical `base.KIFBackend` shape in a single question loop — the call sites below cannot tell
which store they are talking to — yet `[SPARQL/QLever]` answers from `model/weather.ttl`'s
synthetic triples while `[LLM Store]` answers from what `granite4:micro` believes about the real
world. Same interface, different epistemics. Expect the two columns to disagree; that is the
finding, not a failure.

The LLM side may also answer `None` (its parser raises on any reply without digits in it, and it
is non-deterministic run to run), so every print below tolerates a missing answer rather than
letting one unlucky sample crash the demo.
"""

from __future__ import annotations

from .kif import kif, llm_store
from .kif.base import KIFBackend

BACKENDS: list[tuple[str, KIFBackend]] = [
    ("SPARQL/QLever", kif),
    ("LLM Store", llm_store),
]


def _answer_weather(backend: KIFBackend) -> str:
    temperature = backend.city_temperature("Chicago")
    condition = backend.city_condition("Chicago")
    if temperature is None and condition is None:
        return "no answer."
    degrees = "unknown" if temperature is None else f"{temperature}°C"
    return f"Chicago is {degrees} and {condition!r}."


def _answer_hottest(backend: KIFBackend) -> str:
    hottest = backend.hottest_cities(3)
    if not hottest:
        return "no answer."
    names = [name for name, _ in hottest]
    return f"Top 3 hottest: {', '.join(names)}. Chicago is hottest-3: {'Chicago' in names}."


def _answer_precipitation(backend: KIFBackend) -> str:
    condition = backend.city_condition("Chicago")
    if condition is None:
        return "no answer."
    return f"Condition is {condition!r} (raining/snowing: {condition in ('Rainy', 'Snowy')})."


QUESTIONS = [
    ("What is the weather like in Chicago right now, and is it warm?", _answer_weather),
    ("Is Chicago one of the three hottest cities in the data?", _answer_hottest),
    ("Is it currently raining or snowing in Chicago?", _answer_precipitation),
]


def run() -> None:
    for question, answer_fn in QUESTIONS:
        print(f"\n=== Q: {question}")
        for label, backend in BACKENDS:
            try:
                answer = answer_fn(backend)
            except Exception as exc:  # noqa: BLE001 - a dead backend must not hide the other one
                answer = f"unavailable ({type(exc).__name__}: {exc})"
            print(f"A: [{label}] {answer}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
