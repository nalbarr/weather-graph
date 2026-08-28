"""Exercises the KIF queries against the real QLever server.

Skips (does not fail) when the QLever endpoint isn't reachable, so `make test` stays
offline-safe — the same invariant tests/conftest.py enforces for the RDF backends and
tests/test_neo4j.py enforces for the Neo4j backend. Runs for real once `make qlever-up` has been
done locally.
"""

from __future__ import annotations

import pytest

kif_lib = pytest.importorskip("kif_lib")

from weather_graph.kif import kif


@pytest.fixture(scope="module")
def live_qlever():
    try:
        next(kif.get_store().filter(property=kif_lib.vocabulary.wd.temperature, limit=1))
    except StopIteration:
        pass
    except Exception as exc:  # noqa: BLE001 - any connection failure means "skip"
        pytest.skip(f"No reachable QLever endpoint: {exc}")


def test_city_temperature_returns_chicago(live_qlever):
    assert kif.city_temperature("Chicago") == 21.0


def test_hottest_cities_returns_cairo_first(live_qlever):
    hottest = kif.hottest_cities(3)
    assert len(hottest) == 3
    assert hottest[0][0] == "Cairo"


def test_city_condition_for_chicago(live_qlever):
    assert kif.city_condition("Chicago") == "Partly Cloudy"


def test_city_names_mirror_model_ttl():
    assert kif.CITY_NAMES["city0"] == "Chicago"
    assert len(kif.CITY_NAMES) == 8
