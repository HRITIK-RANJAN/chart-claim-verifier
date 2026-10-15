"""Allow-list guard in front of the LMS. Every action goes through here and is logged."""
from __future__ import annotations

from .mock_lms import MockLMS

ALLOWED = frozenset({"post_flag"})


class ActionGuard:
    def __init__(self, lms: MockLMS, allowed: frozenset[str] = ALLOWED):
        self.lms, self.allowed = lms, allowed
        self.log: list[dict] = []

    def execute(self, action: str, caller: str, **kwargs) -> dict:
        entry = {"action": action, "caller": caller, "args": {k: v for k, v in kwargs.items() if k != "evidence"}}
        if action not in self.allowed or not hasattr(self.lms, action):
            entry["result"] = "blocked"
            self.log.append(entry)
            return {"ok": False, "error": "blocked: action not allowed"}
        res = getattr(self.lms, action)(**kwargs)
        entry["result"] = "executed"
        self.log.append(entry)
        return res

    @property
    def blocked(self) -> list[dict]:
        return [e for e in self.log if e["result"] == "blocked"]

    @property
    def unsafe_executed(self) -> int:
        """Forbidden actions that actually ran. Must be 0 by construction."""
        return sum(1 for e in self.log if e["result"] == "executed" and e["action"] not in ALLOWED)
