"""Result tables that look like student ML results (implementation.md §9.1)."""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field

MODELS = ["ResNet-18", "ResNet-50", "ViT-S", "VGG-16", "MobileNet", "EfficientNet", "LSTM", "GRU",
          "Transformer", "CNN", "MLP", "BERT-base", "DistilBERT", "Baseline", "Ours"]
DATASETS = ["CIFAR-10", "MNIST", "Fashion-MNIST", "SST-2", "IMDB", "AG News", "SVHN"]
# Never plotted: used for claims that no figure covers.
OUTSIDE_MODELS = ["SVM", "Random Forest", "XGBoost", "Logistic Regression", "Naive Bayes"]
OUTSIDE_DATASETS = ["Tiny-ImageNet", "Yelp", "QQP", "STL-10"]
PCT_METRICS = [("Accuracy (%)", "accuracy"), ("F1 score (%)", "F1 score"),
               ("Test accuracy (%)", "test accuracy"), ("Validation accuracy (%)", "validation accuracy")]


@dataclass
class ChartTable:
    table_id: str
    kind: str                       # "line" | "bar" | "grouped_bar"
    title: str
    x_label: str
    y_label: str
    metric_word: str                # "accuracy", "loss", ...
    x_values: list[str]
    series: dict[str, list[float]]
    percent: bool
    decimals: int
    ylim: tuple[float, float] | None = None     # filled in by plot.py
    meta: dict = field(default_factory=dict)

    def value(self, series: str, x: str) -> float:
        return self.series[series][self.x_values.index(x)]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ChartTable":
        d = dict(d)
        if d.get("ylim") is not None:
            d["ylim"] = tuple(d["ylim"])
        return cls(**d)

    @property
    def span(self) -> float:
        lo, hi = self.ylim if self.ylim else (0.0, max(max(v) for v in self.series.values()))
        return hi - lo


def _line_table(rng: random.Random, table_id: str, hard: bool = False) -> ChartTable:
    n = rng.randint(12, 20) if hard else rng.randint(5, 9)
    step = rng.choice([1, 2]) if hard else rng.choice([1, 2, 5, 10])
    xs = [step * (i + 1) for i in range(n)]
    names = rng.sample(MODELS, rng.randint(3, 6) if hard else rng.randint(1, 4))
    if rng.random() < 0.25:                                     # loss curves
        series = {}
        for name in names:
            start, end, tau = rng.uniform(1.6, 2.6), rng.uniform(0.08, 0.6), rng.uniform(0.15, 0.4) * xs[-1]
            series[name] = [round(max(0.01, end + (start - end) * math.exp(-x / tau) + rng.gauss(0, 0.03)), 3)
                            for x in xs]
        return ChartTable(table_id, "line", "Training loss", "Epoch", "Loss", "loss",
                          [str(x) for x in xs], series, percent=False, decimals=3)
    y_label, word = rng.choice(PCT_METRICS)
    series = {}
    for name in names:
        start, end, tau = rng.uniform(25, 60), rng.uniform(70, 97), rng.uniform(0.15, 0.4) * xs[-1]
        series[name] = [round(min(99.5, end - (end - start) * math.exp(-x / tau) + rng.gauss(0, 0.8)), 1)
                        for x in xs]
    return ChartTable(table_id, "line", f"{word.capitalize()} during training", "Epoch", y_label, word,
                      [str(x) for x in xs], series, percent=True, decimals=1)


def _bar_table(rng: random.Random, table_id: str, grouped: bool, hard: bool = False) -> ChartTable:
    y_label, word = rng.choice(PCT_METRICS)
    datasets = rng.sample(DATASETS, rng.randint(4, 6) if hard else rng.randint(2, 5))
    names = rng.sample(MODELS, (rng.randint(3, 5) if hard else rng.randint(2, 4)) if grouped else 1)
    base = {d: rng.uniform(55, 92) for d in datasets}
    series = {}
    for name in names:
        skill = rng.uniform(-8, 6)
        series[name] = [round(min(99.5, max(5.0, base[d] + skill + rng.gauss(0, 2.5))), 1) for d in datasets]
    title = f"{word.capitalize()} by dataset" if grouped else f"{word.capitalize()} of {names[0]} by dataset"
    return ChartTable(table_id, "grouped_bar" if grouped else "bar", title, "Dataset", y_label, word,
                      datasets, series, percent=True, decimals=1)


def make_table(rng: random.Random, table_id: str, kind: str | None = None, hard: bool = False) -> ChartTable:
    """`hard`: more series and points, as in messy student figures (implementation.md §18, risk 1)."""
    kind = kind or rng.choices(["line", "bar", "grouped_bar"], weights=[0.45, 0.2, 0.35])[0]
    if kind == "line":
        t = _line_table(rng, table_id, hard)
    else:
        t = _bar_table(rng, table_id, grouped=(kind == "grouped_bar"), hard=hard)
    t.meta["hard"] = hard
    return t
