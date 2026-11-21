"""Les méthodes de résolution enregistrées pour le banc d'essai (``--methods`` du script)."""

from __future__ import annotations

import time

import numpy as np

from hackathon.solvers.portfolio.benchmark import register
from hackathon.solvers.portfolio.evaluator import PortfolioState
from hackathon.solvers.portfolio.lns import divi_solver, enum_solver, lns, sa_solver
from hackathon.solvers.portfolio.local_search import local_search
from hackathon.solvers.portfolio.problem import PortfolioProblem


def _descent(problem: PortfolioProblem, time_limit: float, **kwargs) -> np.ndarray:
    state = PortfolioState(problem)  # départ : portefeuille vide
    local_search(state, time_limit=time_limit, **kwargs)
    return state.v


@register("ls-single")
def ls_single(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """Mouvements simples ±1 seulement : l'équivalent de la recherche locale du kit."""
    return _descent(problem, time_limit, neighborhoods=["block"], max_block=1)


@register("ls-block")
def ls_block(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """+ blocs de jours consécutifs (frais payés une seule fois)."""
    return _descent(problem, time_limit, neighborhoods=["block"])


@register("ls-pair")
def ls_pair(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """+ paires couvertes sur des blocs de jours."""
    return _descent(problem, time_limit, neighborhoods=["block", "pair"])


@register("ls-full")
def ls_full(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """+ échanges (budget saturé)."""
    return _descent(problem, time_limit, neighborhoods=["block", "pair", "swap"])


@register("ls-full-b20")
def ls_full_b20(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """Comme ``ls-full``, mais applique jusqu'à 20 mouvements par passe : bien plus rapide sur a400."""
    return _descent(problem, time_limit, neighborhoods=["block", "pair", "swap"], batch=20)


# ── LNS (piste P7) : même boucle, sous-solveurs différents ──────────────
#
# Fenêtres « larges et courtes » (stratégie ``wide`` : beaucoup d'actions sur peu de jours), la forme qui
# fonctionne d'après nos mesures (voir formalisations/portfolio/lns.typ). La taille dépend de ce que le
# sous-solveur sait traiter : 20 bits pour l'énumération, 16 qubits pour QAOA en local, 200 bits (environ
# 20 qubits) pour PCE et le recuit simulé.

LNS_PENALTY = 0.2


def _lns(
    problem: PortfolioProblem,
    rng: np.random.Generator,
    time_limit: float,
    sub_solver,
    n_assets: int,
    n_days: int | tuple[int, ...],
) -> np.ndarray:
    """Recherche locale ``ls-full`` puis LNS jusqu'à la limite de temps, puis une dernière descente."""
    start = time.perf_counter()
    state = PortfolioState(problem)
    batch = (
        1 if problem.n * problem.T <= 1000 else 20
    )  # voir P4 : lots de 20 sur les grandes instances
    local_search(state, time_limit=time_limit, batch=batch)
    remaining = time_limit - (time.perf_counter() - start)
    if remaining > 0:
        lns(
            state,
            sub_solver,
            rng,
            time_limit=remaining,
            n_assets=n_assets,
            n_days=n_days,
            penalty_scale=LNS_PENALTY,
        )
        local_search(state, time_limit=max(1.0, 0.1 * time_limit), batch=batch)
    return state.v


@register("lns-enum")
def lns_enum(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """LNS, fenêtres 10 actions × 1 jour (20 bits), QUBO résolu exactement par énumération."""
    return _lns(problem, rng, time_limit, enum_solver(), n_assets=10, n_days=1)


@register("lns-sa")
def lns_sa(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """LNS, fenêtres 50 actions × 1 ou 2 jours (jusqu'à 200 bits), recuit simulé : la référence de PCE."""
    return _lns(problem, rng, time_limit, sa_solver(num_reads=32, num_sweeps=1000), 50, (1, 2))


@register("lns-sa-small")
def lns_sa_small(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """LNS, fenêtres 8 actions × 1 jour (16 bits), recuit simulé : la référence de QAOA, à taille égale."""
    return _lns(problem, rng, time_limit, sa_solver(num_reads=32, num_sweeps=1000), 8, 1)


@register("lns-qaoa")
def lns_qaoa(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """LNS, fenêtres 8 actions × 1 jour (16 qubits), QAOA (Divi, simulateur local)."""
    return _lns(problem, rng, time_limit, divi_solver("qaoa"), n_assets=8, n_days=1)


@register("lns-pce")
def lns_pce(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """LNS, fenêtres 50 actions × 1 ou 2 jours (jusqu'à 200 bits sur environ 20 qubits), PCE (Divi)."""
    return _lns(problem, rng, time_limit, divi_solver("pce"), n_assets=50, n_days=(1, 2))
