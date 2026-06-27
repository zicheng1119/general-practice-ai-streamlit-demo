from __future__ import annotations

from collections import defaultdict
from itertools import count


class InMemoryStore:
    def __init__(self) -> None:
        self._counters = defaultdict(lambda: count(1))
        self.triage_sessions: dict[str, dict] = {}
        self.appointments: dict[str, dict] = {}
        self.encounters: dict[str, dict] = {}
        self.reminders: dict[str, dict] = {}
        self.feedback: dict[str, list[dict]] = defaultdict(list)

    def next_id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._counters[prefix]):03d}"


store = InMemoryStore()
