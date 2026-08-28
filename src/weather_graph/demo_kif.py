"""Runnable demo: the same 3 weather questions as demo.py, answered via fixed KIF queries
against the existing QLever server instead of an LLM agent over SPARQL (see plans/PLAN_KIF.md).

Run: `uv run weather-graph-kif`
(requires `make qlever-up` first — see docs/QUICKSTART.md).
"""

from __future__ import annotations

from .kif import kif


def run() -> None:
    print("\n=== Q: What is the weather like in Chicago right now, and is it warm?")
    temperature = kif.city_temperature("Chicago")
    condition = kif.city_condition("Chicago")
    print(f"A: Chicago is {temperature}°C and {condition!r}.")

    print("\n=== Q: Is Chicago one of the three hottest cities in the data?")
    hottest = kif.hottest_cities(3)
    names = [name for name, _ in hottest]
    print(f"A: Top 3 hottest: {', '.join(names)}. Chicago is hottest-3: {'Chicago' in names}.")

    print("\n=== Q: Is it currently raining or snowing in Chicago?")
    condition = kif.city_condition("Chicago")
    print(f"A: Condition is {condition!r} (raining/snowing: {condition in ('Rainy', 'Snowy')}).")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
