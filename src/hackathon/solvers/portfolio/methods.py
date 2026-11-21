"""Les méthodes de résolution enregistrées pour le banc d'essai (``--methods`` du script)."""

from __future__ import annotations

import numpy as np

from hackathon.solvers.portfolio.benchmark import register
from hackathon.solvers.portfolio.evaluator import PortfolioState
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
