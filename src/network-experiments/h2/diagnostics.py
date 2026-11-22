"""Diagnostics H2 du substitut : F1/F2 sur le jeu de test figé, F3 sur network05 (énumération).

Les énergies portent sur l'**objectif seul** (pénalités de degré exclues). Plus bas = meilleur.
"""

from __future__ import annotations

import itertools
import json
import math

import dimod
import numpy as np
from h0.instances import load_demand
from h0.testset import load_testset
from h1.diagnostics import qubo_energies, spearman_rho, surrogate_metrics
from h1.fm import topologies_to_X

from hackathon.referee import qt
from hackathon.utils import RESULTS_DIR

TESTSET_DIR = RESULTS_DIR / "network" / "testsets"
Arc = tuple[int, int]


def f1_f2_testset(objective_bqm: dimod.BinaryQuadraticModel, instance: str = "network12") -> dict:
    """``{"spearman_rho" (F1), "top10_precision" (F2)}`` sur ``results/network/testsets/<instance>``."""
    topos, scores = load_testset(instance)
    n = int(instance.removeprefix("network"))
    return surrogate_metrics(objective_bqm, topos, scores, n)


def _derangements(n: int) -> list[tuple[int, ...]]:
    return [p for p in itertools.permutations(range(n)) if all(p[i] != i for i in range(n))]


def enumerate_valid_topologies(n: int) -> list[list[Arc]]:
    """Toutes les topologies valides (degrés entrant et sortant 2, sans boucle), triées.

    Une topologie valide = deux dérangements qui ne coïncident jamais (cf. ``qt.random_topology``) ;
    on dédoublonne les paires. ``n ≤ 6`` (network05 : 216).
    """
    if n > 6:
        raise ValueError("énumération réservée à n ≤ 6")
    ders = _derangements(n)
    seen: set[frozenset[Arc]] = set()
    for p1 in ders:
        for p2 in ders:
            if any(p1[i] == p2[i] for i in range(n)):
                continue
            seen.add(frozenset([(i, p1[i]) for i in range(n)] + [(i, p2[i]) for i in range(n)]))
    return sorted(sorted(s) for s in seen)


def all_topologies_scored(n: int = 5) -> tuple[list[list[Arc]], np.ndarray]:
    """Topologies valides de ``network<n>`` et leur score LP, en cache
    ``results/network/testsets/network<NN>_all.json`` (clés ``arcs``, ``score``)."""
    path = TESTSET_DIR / f"network{n:02d}_all.json"
    if path.exists():
        data = json.loads(path.read_text())
        topos = [[(int(i), int(j)) for i, j in t] for t in data["arcs"]]
        return topos, np.asarray(data["score"], dtype=float)
    demand = load_demand(f"network{n:02d}")
    topos = enumerate_valid_topologies(n)
    scores = [qt.route_min_congestion(demand, t).objective for t in topos]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "arcs": [[list(a) for a in t] for t in topos],
                "score": [None if math.isinf(s) else int(s) for s in scores],
            }
        )
    )
    return topos, np.asarray(scores, dtype=float)


def f3_ref_percentile(objective_bqm: dimod.BinaryQuadraticModel, n: int = 5) -> dict:
    """F3 : rang de la meilleure topologie optimale dans l'ordre des énergies (toutes énumérées).

    Renvoie ``percentile`` = 100 · #{énergie < E*} / N (0 = meilleur, E* = plus basse énergie d'une
    topologie de score optimal), ``rank`` (= #{énergie < E*}), ``n_ties`` (autres topologies à
    énergie égale à E*, à 1e-9 près), ``n_topologies``, ``n_optimal`` et ``spearman_rho`` (sur toutes
    les topologies routables).
    """
    topos, scores = all_topologies_scored(n)
    scores = np.where(np.isnan(scores), np.inf, scores)
    energies = qubo_energies(objective_bqm, topologies_to_X(topos, n))
    best = scores.min()
    e_star = energies[scores == best].min()
    lower = int((energies < e_star - 1e-9).sum())
    ties = int((np.abs(energies - e_star) <= 1e-9).sum()) - 1
    finite = np.isfinite(scores)
    return {
        "percentile": 100.0 * lower / len(topos),
        "rank": lower,
        "n_ties": ties,
        "n_topologies": len(topos),
        "n_optimal": int((scores == best).sum()),
        "best_score": float(best),
        "spearman_rho": spearman_rho(energies[finite], scores[finite]),
    }
