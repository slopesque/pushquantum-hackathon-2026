"""Agrégation des runs (``metrics.md`` §1) et tableau Markdown au format de ``result.md``.

``PYTHONPATH=src/network-experiments uv run python -m h0.report --hypothesis h0 [h1 …]
--instance network12 [--methods …] [--seeds 0 1 2]``
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Iterable
from typing import Any

from hackathon.utils import gap

from . import harness

HEADER = (
    "| Instance | Méthode | min (gap) | médiane (gap) | max | lp_calls | wall_time_s "
    "| max_qubits | backend |\n|---|---|---|---|---|---|---|---|---|"
)


def load_records(hypotheses: Iterable[str]) -> list[dict[str, Any]]:
    """Toutes les lignes de ``results/network/bench/<hyp>/*.jsonl``, dans l'ordre des fichiers."""
    records = []
    for hyp in hypotheses:
        for path in sorted((harness.BENCH_DIR / hyp).glob("*.jsonl")):
            records += [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    return records


def aggregate(records: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Par ``(instance, méthode)`` : dernier record par seed, puis statistiques sur les seeds.

    Valeur : ``seeds``, ``scores``, ``min``, ``median``, ``max`` (+ ``gap_min``, ``gap_median``,
    ``gap_max``), ``lp_calls`` et ``wall_time_s`` (médianes), ``max_qubits`` (max), ``backend``
    (valeurs distinctes jointes par ``,``), ``best_known``, ``best_record`` (record du min).
    Les runs sans score (aucune topologie valide) comptent dans ``seeds`` mais pas dans les scores.
    """
    last: dict[tuple[str, str], dict[int, dict[str, Any]]] = {}
    for rec in records:
        last.setdefault((rec["instance"], rec["method"]), {})[rec["seed"]] = rec
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, by_seed in last.items():
        recs = [by_seed[s] for s in sorted(by_seed)]
        scored = [r for r in recs if r.get("score") is not None]
        scores = [r["score"] for r in scored]
        bk = recs[0]["best_known"]
        agg: dict[str, Any] = {
            "seeds": sorted(by_seed),
            "scores": scores,
            "best_known": bk,
            "lp_calls": statistics.median(r["lp_calls"] for r in recs),
            "wall_time_s": statistics.median(r["wall_time_s"] for r in recs),
            "max_qubits": max(r.get("max_qubits", 0) or 0 for r in recs),
            "backend": ",".join(sorted({r.get("backend", "none") for r in recs})),
            "min": None,
            "median": None,
            "max": None,
            "gap_min": None,
            "gap_median": None,
            "gap_max": None,
            "best_record": None,
        }
        if scores:
            agg["min"], agg["median"], agg["max"] = (
                min(scores),
                statistics.median(scores),
                max(scores),
            )
            for stat in ("min", "median", "max"):
                agg[f"gap_{stat}"] = gap(agg[stat], bk)
            agg["best_record"] = min(scored, key=lambda r: r["score"])
        out[key] = agg
    return out


def _num(x: float | None) -> str:
    if x is None:
        return "—"
    if float(x).is_integer():
        return f"{int(x):,}".replace(",", "\u202f")
    return f"{x:,.1f}".replace(",", "\u202f")


def _pct(g: float | None) -> str:
    return "—" if g is None else f"{g * 100:+.2f} %"


def markdown_table(agg: dict[tuple[str, str], dict[str, Any]]) -> str:
    lines = [HEADER]
    for (instance, method), a in sorted(agg.items()):
        lines.append(
            f"| {instance} | {method} | {_num(a['min'])} ({_pct(a['gap_min'])}) "
            f"| {_num(a['median'])} ({_pct(a['gap_median'])}) | {_num(a['max'])} "
            f"| {_num(a['lp_calls'])} | {a['wall_time_s']:.1f} | {a['max_qubits']} "
            f"| {a['backend']} |"
        )
    return "\n".join(lines)


def filter_records(
    records: Iterable[dict[str, Any]],
    instance: str | None = None,
    methods: Iterable[str] | None = None,
    seeds: Iterable[int] | None = None,
) -> list[dict[str, Any]]:
    methods = set(methods) if methods else None
    seeds = set(seeds) if seeds is not None else None
    return [
        r
        for r in records
        if (instance is None or r["instance"] == instance)
        and (methods is None or r["method"] in methods)
        and (seeds is None or r["seed"] in seeds)
    ]


def main(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser(prog="h0.report", description=__doc__)
    parser.add_argument("--hypothesis", nargs="+", default=["h0"])
    parser.add_argument("--instance", default=None)
    parser.add_argument("--methods", nargs="+", default=None)
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    args = parser.parse_args(argv)
    records = filter_records(load_records(args.hypothesis), args.instance, args.methods, args.seeds)
    table = markdown_table(aggregate(records))
    print(table)
    return table


if __name__ == "__main__":
    main()
