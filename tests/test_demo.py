"""Smoke test for `demo.py`'s question loop (no LLM / no network).

`demo.build_agent` is stubbed directly, so this only proves `demo.run()`'s own loop/print wiring
(it asks every question in `QUESTIONS` and prints each answer). Backend *selection* itself
(`AGENT_BACKEND` -> the right module) is covered separately in `test_agents_dispatch.py`; together
the two files cover the dispatch path end-to-end without requiring a live LLM or the optional
`beeai` extra.
"""

from __future__ import annotations

import asyncio

from weather_graph import demo


class _FakeAgent:
    def __init__(self) -> None:
        self.questions: list[str] = []

    async def answer(self, question: str) -> str:
        self.questions.append(question)
        return f"answer to: {question}"


def test_run_asks_every_question_and_prints_answers(monkeypatch, capsys):
    fake = _FakeAgent()
    monkeypatch.setattr(demo, "build_agent", lambda: fake)

    asyncio.run(demo.run())

    assert fake.questions == demo.QUESTIONS
    out = capsys.readouterr().out
    for question in demo.QUESTIONS:
        assert question in out
        assert f"answer to: {question}" in out
