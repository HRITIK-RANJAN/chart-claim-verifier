"""Per-report memory (implementation.md §6.8)."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..retrieval.figure_index import FigureIndex
from ..schemas import ClaimTrace, Figure, Report


@dataclass
class ReportMemory:
    report: Report
    index: FigureIndex
    tables_used: set[tuple[str, str]] = field(default_factory=set)        # (tool, figure_id): already paid for
    failures: list[tuple[str, str, str, str]] = field(default_factory=list)   # (tool, figure_id, series, code)
    repaired: set[tuple[str, str, str]] = field(default_factory=set)      # (tool, figure_id, repair) already tried
    pending: Counter = field(default_factory=Counter)                     # figure_id -> claims still waiting on it
    checked: dict[str, ClaimTrace] = field(default_factory=dict)          # normalised sentence -> trace
    calls: Counter = field(default_factory=Counter)                       # logical tool calls per tool
    calls_saved: int = 0                                                  # lookups answered from memory
    plan: dict = field(default_factory=dict)                              # figure_id -> situation + usable tools

    def figure(self, figure_id: str) -> Figure | None:
        return next((f for f in self.report.figures if f.figure_id == figure_id), None)

    def note_failure(self, tool: str, figure_id: str, series: str, error: str) -> None:
        self.failures.append((tool, figure_id, series, error))

    def lift(self, tool: str, figure_id: str, codes: set[str]) -> None:
        """A repair removed the cause of these failures: the tool may be tried again on this figure."""
        self.failures = [f for f in self.failures if not (f[0] == tool and f[1] == figure_id and f[3] in codes)]

    def blocked(self, tool: str, figure_id: str, series: list[str], scope: dict[str, str]) -> str | None:
        """The earlier failure that makes `tool` pointless for these series on this figure, or None.

        `scope` is measured (tool profile, "failure_scope"): does a failure with this code repeat for the
        whole figure, the whole series, or only for the point it was seen on? A crash (a bug) blocks the figure.
        """
        for t, f, s, code in self.failures:
            reach = scope.get(code, "figure" if code.startswith("exception") else "point")
            if t == tool and f == figure_id and (reach == "figure" or (reach == "series" and s in series)):
                return code
        return None

    def context(self, max_chars: int = 1500) -> str:
        """Captions and chart text for the parser (UNTRUSTED: comes from the report)."""
        parts = [f"Figure {f.number}: {f.caption} | chart text: {'; '.join(f.text_lines[:25])}"
                 for f in self.report.figures]
        return "\n".join(parts)[:max_chars]
