"""Exercises the KIF LLM Store backend against a real local Ollama.

Skips (does not fail) when the `kif-llm` extra isn't installed or Ollama isn't reachable, so
`make test` stays offline-safe — the same two-layer invariant tests/test_kif.py enforces for
QLever. Runs for real once `uv sync --extra kif-llm` has been done and Ollama is serving
`KIF_LLM_MODEL`.

Assertions here are on **shape**, never on values, and that asymmetry with test_kif.py's
`== 21.0` / `== "Partly Cloudy"` / `hottest[0][0] == "Cairo"` is deliberate. This backend answers
from a language model's training data, not from `model/weather.ttl`, so it will essentially never
reproduce the synthetic fixture values — and it varies run to run besides. Pinning an expected
number here would be pinning one sample of a distribution. The divergence is the whole point of
plans/PLAN_KIF_LLM.md objective 5; see docs/learning_plan_kif_llm.md.
"""

from __future__ import annotations

import pytest

# Layer 1 — "not installed". The vendored kif_llm_store/kbel source always ships with the repo, so
# the only genuinely external, optional dependency left to gate on is nest-asyncio (imported at
# module scope by the vendored llm.py). `uv sync --extra kif-llm` installs it.
pytest.importorskip("nest_asyncio")

from weather_graph.kif import llm_store, wikidata_mapping


@pytest.fixture(scope="module")
def live_ollama():
    # Layer 2 — "not reachable". One real call; any failure at all means skip, not fail. Note the
    # asymmetry with test_kif.py's live_qlever, which has to special-case StopIteration: this
    # backend's wrappers already swallow their own no-answer case and return None, so an
    # exception escaping here really does mean the model/host is unavailable.
    try:
        llm_store.city_temperature("Chicago")
    except Exception as exc:  # noqa: BLE001 - any connection failure means "skip"
        pytest.skip(f"No reachable Ollama for the KIF LLM store: {exc}")


def test_city_temperature_shape(live_ollama):
    temperature = llm_store.city_temperature("Chicago")
    assert temperature is None or isinstance(temperature, float)


def test_city_condition_shape(live_ollama):
    condition = llm_store.city_condition("Chicago")
    assert condition is None or isinstance(condition, str)


def test_hottest_cities_shape(live_ollama):
    hottest = llm_store.hottest_cities(3)
    assert isinstance(hottest, list)
    # At most `limit`, but possibly fewer: cities the model declines to answer for are dropped.
    assert len(hottest) <= 3
    for entry in hottest:
        assert isinstance(entry, tuple) and len(entry) == 2
        name, temperature = entry
        assert name in wikidata_mapping.CITY_ITEMS
        assert isinstance(temperature, float)
    temperatures = [temperature for _, temperature in hottest]
    assert temperatures == sorted(temperatures, reverse=True)


def test_city_items_mirror_kif_city_names():
    """Pure structural check, no live backend — the analogue of test_kif.py's
    test_city_names_mirror_model_ttl. Imports `wikidata_mapping` directly rather than going
    through `base.KIFBackend`: per-backend vocabulary tables are deliberately outside that
    Protocol (plans/PLAN_KIF_LLM.md objective 7), so there is nothing generic to assert against.
    """
    from weather_graph.kif import kif

    assert len(wikidata_mapping.CITY_ITEMS) == 8
    # Same 8 display names as the SPARQL backend — only the subjects differ.
    assert set(wikidata_mapping.CITY_ITEMS) == set(kif.CITY_NAMES.values())
    # Real Wikidata subjects, and each carries the label LLM_Store's prompt builder requires.
    chicago = wikidata_mapping.city_item("Chicago")
    assert chicago.iri.content == "http://www.wikidata.org/entity/Q1297"
    assert wikidata_mapping.name_of(chicago) == "Chicago"
