"""Baselines H0 : B0 (topologies aléatoires) et B1 (SA sur le substitut QUBO du kit).

Méthodes au format du harnais : ``method(demand, seed, scorer, **params) -> dict``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np
from dwave.samplers import SimulatedAnnealingSampler

from hackathon.referee import qt

from .scorer import Arc, BudgetExhausted, Scorer

B0_MAX_CONSECUTIVE_HITS = 2_000
B1_MAX_STALE_BATCHES = 20
SEED_STRIDE = 1_000_003


def b0_random(demand: np.ndarray, seed: int, scorer: Scorer) -> dict[str, Any]:
    """B0 : ``qt.random_topology(n, rng)`` notées par le scorer jusqu'au budget.

    Garde anti-boucle : arrêt après ``B0_MAX_CONSECUTIVE_HITS`` hits de cache consécutifs (network05
    n'a que 216 topologies valides).
    """
    n = len(demand)
    rng = np.random.default_rng(seed)
    hits = 0
    stalled = False
    try:
        while not scorer.exhausted:
            arcs = qt.random_topology(n, rng)
            if scorer.is_cached(arcs):
                hits += 1
                if hits >= B0_MAX_CONSECUTIVE_HITS:
                    stalled = True
                    break
            else:
                hits = 0
            scorer.score(arcs)
    except BudgetExhausted:
        pass
    return {"params": {"stalled": stalled}}


def batch_seed(seed: int, b: int) -> int:
    """Seed SA du lot ``b`` : ``(seed * 1_000_003 + b) mod 2**31`` (le sampler exige < 2**31)."""
    return (seed * SEED_STRIDE + b) % 2**31


def _sa_batches(
    demand: np.ndarray, seed: int, sa_reads: int, penalty: float
) -> Iterator[list[list[Arc]]]:
    """Lots SA successifs sur ``objective + penalty·pen`` : liste des arcs bruts de chaque lecture.

    Seed du lot ``b`` : ``batch_seed(seed, b)`` (voir ``b1_sa_kit``).
    """
    obj, pen, arcs = qt.build_network_qubo(demand)
    bqm = obj + penalty * pen
    sampler = SimulatedAnnealingSampler()
    order = list(range(len(arcs)))
    b = 0
    while True:
        ss = sampler.sample(bqm, num_reads=sa_reads, seed=batch_seed(seed, b))
        cols = [ss.variables.index(v) for v in order]
        samples = ss.record.sample[:, cols]
        yield [qt.decode_topology(row, arcs) for row in samples]
        b += 1


def _repair(
    n: int,
    raw: list[Arc],
    demand: np.ndarray,
    valid: bool,
    memo: dict[frozenset[Arc], list[Arc]],
) -> list[Arc]:
    """``qt.repair_topology`` mémoïsé ; une topologie déjà valide est son propre repair (optimum
    unique du MILP : elle garde ses 2n arcs), on évite donc le MILP."""
    key = frozenset((int(i), int(j)) for i, j in raw)
    if valid:
        return sorted(key)
    if key not in memo:
        memo[key] = [(int(i), int(j)) for i, j in qt.repair_topology(n, sorted(key), demand)]
    return memo[key]


def b1_sa_kit(
    demand: np.ndarray,
    seed: int,
    scorer: Scorer,
    sa_reads: int = 100,
    penalty: float = 1.0,
) -> dict[str, Any]:
    """B1 : pipeline du notebook §1.3 (SA sur le substitut du kit → repair → LP).

    ``bqm = objective + penalty·pen`` (``qt.build_network_qubo``), échantillonné par lots de
    ``sa_reads`` lectures. **Écart volontaire à hypothesis.md** (« seed du lot = seed + b ») : la seed
    du lot ``b`` est ``(seed * 1_000_003 + b) mod 2**31``, sinon les runs de seeds 0, 1, 2
    partageraient leurs lots (le modulo ne change rien pour les petites seeds).

    Chaque lecture : décodage → E1 (``is_valid_topology`` avant repair) → ``repair_topology`` → scorer.
    Arrêt au budget ou après ``B1_MAX_STALE_BATCHES`` lots consécutifs sans topologie nouvelle.
    ``feasible_mass`` = lectures valides brutes / lectures traitées (à jour même si le budget coupe un
    lot).
    """
    n = len(demand)
    reads = valid = n_batches = stale = 0
    memo: dict[frozenset[Arc], list[Arc]] = {}
    try:
        for batch in _sa_batches(demand, seed, sa_reads, penalty):
            n_batches += 1
            new = False
            for raw in batch:
                if scorer.exhausted:
                    raise BudgetExhausted
                reads += 1
                ok = qt.is_valid_topology(n, raw)
                valid += ok
                topo = _repair(n, raw, demand, ok, memo)
                if not scorer.is_cached(topo):
                    new = True
                scorer.score(topo)
            stale = 0 if new else stale + 1
            if stale >= B1_MAX_STALE_BATCHES:
                break
    except BudgetExhausted:
        pass
    return {
        "feasible_mass": valid / reads if reads else None,
        "params": {"sa_reads": sa_reads, "penalty": penalty, "n_batches": n_batches},
    }


def b1_topologies(
    demand: np.ndarray,
    seed: int,
    n_topologies: int,
    sa_reads: int = 100,
    penalty: float = 1.0,
) -> list[list[Arc]]:
    """Topologies B1 (mêmes lots SA + repair) **distinctes**, dans l'ordre d'apparition, sans LP.

    Peut en renvoyer moins de ``n_topologies`` si ``B1_MAX_STALE_BATCHES`` lots consécutifs
    n'apportent rien de nouveau.
    """
    return list(_b1_stream(demand, seed, sa_reads, penalty, limit=n_topologies))


def _b1_stream(
    demand: np.ndarray,
    seed: int,
    sa_reads: int = 100,
    penalty: float = 1.0,
    limit: int | None = None,
    exclude: set[frozenset[Arc]] | None = None,
) -> Iterator[list[Arc]]:
    """Topologies B1 réparées, distinctes (et hors ``exclude``), dans l'ordre d'apparition."""
    n = len(demand)
    seen: set[frozenset[Arc]] = set(exclude or ())
    memo: dict[frozenset[Arc], list[Arc]] = {}
    count = stale = 0
    for batch in _sa_batches(demand, seed, sa_reads, penalty):
        new = False
        for raw in batch:
            topo = sorted(_repair(n, raw, demand, qt.is_valid_topology(n, raw), memo))
            key = frozenset(topo)
            if key in seen:
                continue
            seen.add(key)
            new = True
            yield topo
            count += 1
            if limit is not None and count >= limit:
                return
        stale = 0 if new else stale + 1
        if stale >= B1_MAX_STALE_BATCHES:
            return


METHODS = {"b0_random": b0_random, "b1_sa_kit": b1_sa_kit}
