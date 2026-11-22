"""Méthodes H2 au format du harnais H0 : ``method(demand, seed, scorer, **params) -> dict``.

* ``h2_sa_phys`` : pipeline B1 (``h0.baselines.b1_sa_kit``) sur le substitut H2 ;
* ``h2_fm_phys`` : boucle H1 (``h1.loop.h1_fm``) avec l'objectif H2 comme a priori.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np
from dwave.samplers import SimulatedAnnealingSampler
from h0.baselines import B1_MAX_STALE_BATCHES, _repair, batch_seed
from h0.scorer import Arc, BudgetExhausted, Scorer
from h1.loop import h1_fm

from hackathon.referee import qt

from .surrogate import lambda_rule, physics_qubo

PRIOR_FN = "h2.surrogate:physics_objective"


def effective_lambda(
    demand: np.ndarray,
    alpha: float,
    beta2: float,
    gamma: float,
    lam: float,
    lam_rule: str | None,
) -> float:
    """λ effectif : ``lam`` si ``lam_rule`` est None, sinon ``lambda_rule(objectif H2, lam_rule)``."""
    if lam_rule is None:
        return float(lam)
    _, objective = physics_qubo(demand, alpha, beta2, gamma, 1.0)
    return lambda_rule(objective, lam_rule)


def _sa_batches(bqm, n_vars: int, seed: int, sa_reads: int) -> Iterator[list[list[Arc]]]:
    """Lots SA successifs (seed du lot ``b`` : ``batch_seed(seed, b)``), arcs bruts par lecture."""
    n = round((1 + np.sqrt(1 + 4 * n_vars)) / 2)
    arcs = qt.all_arcs(n)
    sampler = SimulatedAnnealingSampler()
    order = list(range(n_vars))
    b = 0
    while True:
        ss = sampler.sample(bqm, num_reads=sa_reads, seed=batch_seed(seed, b))
        cols = [ss.variables.index(v) for v in order]
        yield [qt.decode_topology(row, arcs) for row in ss.record.sample[:, cols]]
        b += 1


def h2_sa_phys(
    demand: np.ndarray,
    seed: int,
    scorer: Scorer,
    alpha: float = 1.0,
    beta2: float = 0.5,
    gamma: float = 0.0,
    lam: float = 1.0,
    lam_rule: str | None = None,
    sa_reads: int = 100,
) -> dict[str, Any]:
    """Pipeline B1 sur ``physics_qubo`` : SA par lots → E1 → repair mémoïsé → LP.

    Même logique que ``h0.baselines.b1_sa_kit`` : seed du lot ``batch_seed(seed, b)``, repair sauté
    pour les lectures valides, arrêt au budget ou après ``B1_MAX_STALE_BATCHES`` lots sans nouveauté.
    """
    n = len(demand)
    lam_eff = effective_lambda(demand, alpha, beta2, gamma, lam, lam_rule)
    full, _ = physics_qubo(demand, alpha, beta2, gamma, lam_eff)
    reads = valid = n_batches = stale = 0
    memo: dict[frozenset[Arc], list[Arc]] = {}
    try:
        for batch in _sa_batches(full, n * (n - 1), seed, sa_reads):
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
        "params": {"lam_effective": lam_eff, "n_batches": n_batches},
    }


def h2_fm_phys(
    demand: np.ndarray,
    seed: int,
    scorer: Scorer,
    alpha: float = 1.0,
    beta2: float = 0.5,
    gamma: float = 0.0,
    **h1_params: Any,
) -> dict[str, Any]:
    """Boucle H1 (``h1_fm``) avec l'objectif H2 ``physics_objective(alpha, beta2, gamma)`` comme a
    priori (poids ``beta`` de H1) au lieu de l'objectif du kit."""
    prior = {"fn": PRIOR_FN, "kwargs": {"alpha": alpha, "beta2": beta2, "gamma": gamma}}
    return h1_fm(demand, seed, scorer, prior=prior, **h1_params)


METHODS = {"h2_sa_phys": h2_sa_phys, "h2_fm_phys": h2_fm_phys}
