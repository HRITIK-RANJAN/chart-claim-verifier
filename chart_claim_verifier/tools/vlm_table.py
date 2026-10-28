"""Tool 2: the VLM converts the whole chart into a JSON table (base model or LoRA)."""
from __future__ import annotations

from ..models.vlm import LLM, extract_json
from ..schemas import Figure
from .base import Table, TableTool, ToolError

PROMPT = (
    "Convert this chart into a data table. Return only a JSON object that maps each series "
    "(legend entry; use the y-axis title if there is no legend) to an object mapping each x-axis "
    "label to its numeric value, read as precisely as you can from the axis. Example: "
    '{"ResNet-50": {"CIFAR-10": 91.2, "MNIST": 99.1}}'
)


def parse_table(answer: str) -> Table:
    try:
        data = extract_json(answer)
    except ValueError:
        raise ToolError("bad_json") from None
    if not isinstance(data, dict):
        raise ToolError("bad_json")
    table: Table = {}
    for series, row in data.items():
        if not isinstance(row, dict):
            continue
        clean = {}
        for x, v in row.items():
            try:
                clean[str(x)] = float(str(v).rstrip("%"))
            except ValueError:
                continue
        if clean:
            table[str(series)] = clean
    if not table:
        raise ToolError("empty_table")
    return table


class VlmTableTool(TableTool):
    name = "vlm_table"
    cost = 4.0
    kind = "neural"

    def __init__(self, llm: LLM, cache=None):
        super().__init__(cache)
        self.llm = llm
        self.version = f"v1:{llm.name}"       # LoRA vs base -> different cache entries

    def extract_table(self, fig: Figure) -> Table:
        return parse_table(self.llm.generate(PROMPT, [fig.image_path], max_new_tokens=768, adapter=True)[0])
