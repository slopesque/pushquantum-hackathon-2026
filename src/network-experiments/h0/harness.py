"""Harnais commun des runs (H0, réutilisé par H1) : budget, chrono, ligne JSONL, ``save_run``.

Une *méthode* est une fonction ``method(demand, seed, scorer, **params) -> dict`` qui propose des
topologies au ``scorer`` jusqu'à épuisement du budget (elle peut laisser remonter
``BudgetExhausted``, attrapée ici). Elle renvoie les métriques qu'elle seule connaît, parmi :
``feasible_mass``, ``n_circuits``, ``max_qubits``, ``backend``, ``score_raw``, ``score_after_ls``,
``spearman_rho``, ``top10_precision``, et toute clé supplémentaire (ajoutée telle quelle).
"""

from __future__ import annotations

import json
import math
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from hackathon.referee import qt
from hackathon.utils import RESULTS_DIR, gap, git_hash, save_run

from .instances import best_known, budget, load_demand, n_nodes
from .scorer import BudgetExhausted, Scorer

MethodFn = Callable[..., dict[str, Any]]

BENCH_DIR = RESULTS_DIR / "network" / "bench"

OPTIONAL_KEYS = (
    "feasible_mass",
    "score_raw",
    "score_after_ls",
    "spearman_rho",
    "top10_precision",
)


def run_method(
    hypothesis: str,
    method_name: str,
    method: MethodFn,
    instance: str,
    seed: int,
    params: dict[str, Any] | None = None,
    max_lp_calls: int | None = None,
    time_limit_s: float | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Lance ``method`` avec le budget de l'instance, écrit la ligne JSONL et la renvoie.

    ``max_lp_calls`` / ``time_limit_s`` remplacent le budget standard (``metrics.md`` §2), à
    n'utiliser que pour des essais (``write=False`` conseillé).
    """
    params = dict(params or {})
    demand = load_demand(instance)
    lp_budget, time_budget = budget(instance)
    lp_budget = max_lp_calls if max_lp_calls is not None else lp_budget
    time_budget = time_limit_s if time_limit_s is not None else time_budget
    scorer = Scorer(demand, max_lp_calls=lp_budget, time_limit_s=time_budget)
    extras: dict[str, Any] = {}
    try:
        extras = method(demand, seed, scorer, **params) or {}
    except BudgetExhausted:
        pass
    wall = scorer.elapsed
    record = build_record(
        hypothesis,
        method_name,
        instance,
        seed,
        params,
        (lp_budget, time_budget),
        scorer,
        wall,
        extras,
    )
    if write:
        append_jsonl(hypothesis, method_name, record)
    return record


def build_record(
    hypothesis: str,
    method_name: str,
    instance: str,
    seed: int,
    params: dict[str, Any],
    budget_: tuple[int, float],
    scorer: Scorer,
    wall_time_s: float,
    extras: dict[str, Any],
) -> dict[str, Any]:
    """Ligne JSON au schéma de ``metrics.md`` §4 (+ ``best_arcs`` et ``git``)."""
    n = n_nodes(instance)
    bk = best_known(instance)
    score = scorer.best_score
    extras = dict(extras)
    record: dict[str, Any] = {
        "hypothesis": hypothesis,
        "method": method_name,
        "instance": instance,
        "seed": seed,
        "params": params | extras.pop("params", {}),
        "budget": {"lp_calls": budget_[0], "time_s": budget_[1]},
        "score": None if math.isinf(score) else int(score),
        "best_known": bk,
        "gap": None if math.isinf(score) else round(gap(score, bk), 6),
        "lp_calls": scorer.lp_calls,
        "wall_time_s": round(wall_time_s, 2),
        "n_circuits": extras.pop("n_circuits", 0),
        "backend": extras.pop("backend", "none"),
        "n_vars": n * (n - 1),
        "max_qubits": extras.pop("max_qubits", 0),
    }
    for key in OPTIONAL_KEYS:
        record[key] = extras.pop(key, None)
    record.update(extras)
    record["best_arcs"] = [list(a) for a in scorer.best_arcs] if scorer.best_arcs else None
    record["git"] = git_hash()
    return record


def append_jsonl(hypothesis: str, method_name: str, record: dict[str, Any]) -> Path:
    path = BENCH_DIR / hypothesis / f"{method_name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, default=_json_default) + "\n")
    return path


def read_jsonl(hypothesis: str, method_name: str) -> list[dict[str, Any]]:
    path = BENCH_DIR / hypothesis / f"{method_name}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save_solution(record: dict[str, Any]) -> Path:
    """Routage entier, ``.sol``, vérification par l'arbitre, puis ``save_run`` (métadonnées = record).

    Lève ``AssertionError`` si l'arbitre refuse le fichier ou si son score diffère de Q1.
    """
    instance = record["instance"]
    n = n_nodes(instance)
    demand = load_demand(instance)
    arcs = [tuple(a) for a in record["best_arcs"]]
    routing = qt.route_integral(demand, arcs)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{instance}.sol"
        qt.write_network_solution(path, n, routing)
        valid, max_flow, msg = qt.check_network_solution(path, n, demand)
        assert valid, f"solution refusée par l'arbitre : {msg}"
        assert max_flow == record["score"], f"score arbitre {max_flow} != Q1 {record['score']}"
        sol_text = path.read_text()
    meta = {k: v for k, v in record.items() if k != "best_arcs"}
    return save_run("network", f"{instance}.sol", sol_text, meta)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (set, frozenset, tuple)):
        return list(obj)
    raise TypeError(f"non sérialisable : {type(obj)}")
