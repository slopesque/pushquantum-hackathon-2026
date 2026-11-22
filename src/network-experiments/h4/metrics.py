"""H4 : métriques d'échantillonnage (E1 avant repair, masse des degrés sortants, p_opt, rang).

``all_scores`` : ``{frozenset(arcs): score LP}`` de toutes les topologies valides (network05 : 216,
voir ``all_valid_scores``, cache ``results/network/testsets/network05_all.json``).
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

from hackathon.referee import qt
from hackathon.utils import RESULTS_DIR

TESTSET_DIR = RESULTS_DIR / "network" / "testsets"

Arc = tuple[int, int]


def enumerate_valid_topologies(n: int) -> list[list[Arc]]:
    """Toutes les topologies valides (deux dérangements disjoints), par énumération des lignes.

    Énumère C(n−1, 2)^n choix de lignes : réservé aux petits n (n ≤ 6).
    """
    if n > 6:
        raise ValueError("énumération réservée à n ≤ 6")
    rows = [list(itertools.combinations([j for j in range(n) if j != i], 2)) for i in range(n)]
    out = []
    for choice in itertools.product(*rows):
        indeg = np.zeros(n, dtype=int)
        for js in choice:
            indeg[list(js)] += 1
        if (indeg == 2).all():
            out.append([(i, j) for i, js in enumerate(choice) for j in js])
    return out


def all_valid_scores(n: int, demand: np.ndarray, cache: Path | None = None) -> dict:
    """``{frozenset(arcs): score}`` de toutes les topologies valides, avec cache JSON."""
    path = cache or TESTSET_DIR / f"network{n:02d}_all.json"
    if path.exists():
        data = json.loads(path.read_text())
        if isinstance(data, dict):  # format de H2 / metrics.md : {"arcs": [...], "score": [...]}
            data = [{"arcs": a, "score": sc} for a, sc in zip(data["arcs"], data["score"])]
        return {frozenset(tuple(a) for a in d["arcs"]): float(d["score"]) for d in data}
    topos = enumerate_valid_topologies(n)
    data = [
        {"arcs": sorted(t), "score": float(qt.route_min_congestion(demand, t).objective)}
        for t in topos
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return {frozenset(tuple(a) for a in d["arcs"]): d["score"] for d in data}


def decode(bits: np.ndarray, n: int) -> list[Arc]:
    arcs = qt.all_arcs(n)
    return [arcs[v] for v in np.flatnonzero(bits)]


def feasibility_metrics(
    samples: np.ndarray,
    probs: np.ndarray | None,
    n: int,
    demand: np.ndarray,
    all_scores: dict | None = None,
) -> dict:
    """Métriques d'un échantillon brut (avant repair).

    - ``feasible_mass`` : masse des topologies valides (E1) ;
    - ``outdeg_mass`` : masse des échantillons dont chaque ligne a exactement 2 uns ;
    - ``p_opt`` : masse des topologies valides de score optimal (``all_scores`` requis) ;
    - ``rank_best`` : rang (1 = meilleur, rang de compétition) du meilleur échantillon valide parmi
      toutes les topologies valides (``all_scores`` requis ; ``None`` si aucun valide) ;
    - ``n_distinct`` : nombre d'échantillons distincts.
    """
    samples = np.asarray(samples, dtype=np.uint8)
    r = len(samples)
    w = np.full(r, 1.0 / max(r, 1)) if probs is None else np.asarray(probs, dtype=float)
    total = w.sum() or 1.0
    w = w / total
    rows = samples.reshape(r, n, n - 1).sum(axis=2) if r else np.zeros((0, n))
    out_ok = (rows == 2).all(axis=1)
    valid = np.array([bool(out_ok[k]) and qt.is_valid_topology(n, decode(s, n)) for k, s in
                      enumerate(samples)], dtype=bool)  # fmt: skip
    res: dict = {
        "feasible_mass": float(w[valid].sum()),
        "outdeg_mass": float(w[out_ok].sum()),
        "n_distinct": len({s.tobytes() for s in samples}),
        "p_opt": None,
        "rank_best": None,
    }
    if all_scores is not None:
        values = np.array(sorted(all_scores.values()))
        opt = values[0]
        p_opt, best = 0.0, np.inf
        for k in np.flatnonzero(valid):
            sc = all_scores[frozenset(decode(samples[k], n))]
            best = min(best, sc)
            if sc == opt:
                p_opt += w[k]
        res["p_opt"] = float(p_opt)
        res["rank_best"] = None if np.isinf(best) else int((values < best).sum() + 1)
    return res
