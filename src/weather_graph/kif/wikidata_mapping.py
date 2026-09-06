"""The LLM backend's city vocabulary: display name -> real Wikidata `Item`.

This is the deliberate fork from `mapping.py`, and the single place the two KIF Store backends
genuinely diverge (plans/PLAN_KIF_LLM.md, objective 3). `mapping.py`'s `SPARQL_Mapping` binds
subjects to the **local** `wx:cityN` IRIs that actually exist in `model/weather.ttl`; `LLM_Store`
has no access to that data at all — it *is* the knowledge source — so a `wx:city0` subject would
be meaningless to it (the model has never seen that IRI). The same 8 cities are therefore
re-expressed here as the real Wikidata items the LLM can actually answer about.

Two shape differences from `kif.py`'s `CITY_NAMES`, both forced rather than stylistic:

- **No slug indirection.** `kif.py` keys on the local `city0`..`city7` slugs because those *are*
  the IRI fragments in `weather.ttl`. There is no local IRI here to slug from, so the table is
  keyed directly on the display name.
- **An explicit reverse table.** `kif.py`'s `_name_of()` recovers a display name by parsing the
  IRI fragment (`.../weather#city0` -> `city0`). Wikidata IRIs are opaque (`.../entity/Q1297`),
  so that trick does not carry over; `_NAME_BY_IRI` below is built as the literal inverse instead.

Why `wd.Q(<id>, "<Label>")` and not a bare `Item(IRI("http://www.wikidata.org/entity/Q..."))`:
`LLM_Store` builds an English prompt around the subject's **label** and asserts one exists
(`AssertionError: It was not possible to get the label for the entity ...` from
`filter_compiler.py`'s `build_task_prompt_template`). `wd.Q()` both constructs the `Item` and
registers that label in one call; a bare `Item(IRI(...))` does not, and fails. The SPARQL backend
never needed a label because an IRI alone is enough to match a triple pattern. Confirmed live —
see analysis/kif_llm_analysis.md, blocker #5.

Only Paris has a named `wd.<City>` constant: `kif_lib.vocabulary.wd` ships a small hand-curated
item subset, not a Wikidata mirror. Q-IDs for the other seven were each verified against
`wikidata.org/wiki/Special:EntityData/Q<id>.json`.
"""

from __future__ import annotations

from kif_lib import Item
from kif_lib.vocabulary import wd

#: Display name -> the Wikidata item `LLM_Store` is asked about. Same 8 cities, and same display
#: names, as `kif.CITY_NAMES` — only the subjects differ (real Q-IDs vs. local `wx:cityN` IRIs).
CITY_ITEMS: dict[str, Item] = {
    "Chicago": wd.Q(1297, "Chicago"),
    "Paris": wd.Paris,  # the one city with a named constant in kif_lib.vocabulary.wd
    "London": wd.Q(84, "London"),
    "Cairo": wd.Q(85, "Cairo"),
    "Tokyo": wd.Q(1490, "Tokyo"),
    "Oslo": wd.Q(585, "Oslo"),
    "Nairobi": wd.Q(3870, "Nairobi"),
    "Sydney": wd.Q(3130, "Sydney"),
}

#: Reverse lookup, keyed on the IRI string rather than the `Item` itself so a subject that comes
#: back from `kb.filter()` (a freshly built, unregistered `Item`) still resolves.
_NAME_BY_IRI = {item.iri.content: name for name, item in CITY_ITEMS.items()}


def city_item(name: str) -> Item:
    """The Wikidata `Item` to use as the `subject=` of a filter, for a display name."""
    return CITY_ITEMS[name]


def name_of(item: Item) -> str:
    """Display name for a Wikidata city `Item`, falling back to its raw IRI if unknown."""
    return _NAME_BY_IRI.get(item.iri.content, item.iri.content)
