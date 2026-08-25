"""Model + graph sanity tests (no LLM)."""

from pathlib import Path

from rdflib import Graph as RdflibGraph

from weather_graph import __version__
from weather_graph.graph_data import get_graph
from weather_graph.models import QueryResult

_MODEL_DIR = Path(__file__).resolve().parent.parent / "model"


def test_version():
    assert __version__ == "0.1.0"


def test_graph_has_all_cities():
    g = get_graph()
    expected = RdflibGraph()
    for path in sorted(_MODEL_DIR.glob("*.ttl")):
        expected.parse(path, format="turtle")
    # Cross-checks against the checked-in model/*.ttl files rather than a hard-coded count.
    assert len(g) == len(expected)
    assert len(g) > 0


def test_query_result_summary():
    r = QueryResult(sparql="SELECT ...", columns=["name"], rows=[{"name": "Paris"}])
    assert "Paris" in r.summary()
