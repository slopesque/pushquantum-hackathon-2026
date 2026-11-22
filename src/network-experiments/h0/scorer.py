"""Scorer LP mémoïsé avec compteur, budget LP et plafond de temps (métriques Q1, C1, C2)."""

from __future__ import annotations

import math
import time
from collections.abc import Iterable

import numpy as np

from hackathon.referee import qt

Arc = tuple[int, int]


class BudgetExhausted(RuntimeError):
    """Levée quand une topologie *nouvelle* doit être notée alors que le budget est épuisé."""


class Scorer:
    """Note des topologies avec le LP de routage de l'arbitre (``qt.route_min_congestion``).

    - Mémoïsé sur ``frozenset(arcs)`` : un hit de cache ne compte pas dans ``lp_calls``.
    - Une topologie invalide vaut ``inf`` sans appel LP (et n'est pas comptée).
    - Budget : ``max_lp_calls`` résolutions LP et ``time_limit_s`` secondes depuis la création. Une
      topologie nouvelle demandée après épuisement du budget LP lève ``BudgetExhausted`` ; après le
      plafond de temps, tout appel lève ``BudgetExhausted`` (même un hit de cache).
    - Garde la meilleure topologie vue (``best_score``, ``best_arcs``).
    """

    def __init__(
        self,
        demand: np.ndarray,
        max_lp_calls: int | None = None,
        time_limit_s: float | None = None,
    ) -> None:
        self.demand = demand
        self.n = len(demand)
        self.max_lp_calls = max_lp_calls
        self.time_limit_s = time_limit_s
        self.lp_calls = 0
        self.cache: dict[frozenset[Arc], float] = {}
        self.best_score = math.inf
        self.best_arcs: list[Arc] | None = None
        self.t0 = time.perf_counter()

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.t0

    @property
    def exhausted(self) -> bool:
        if self.max_lp_calls is not None and self.lp_calls >= self.max_lp_calls:
            return True
        return self.time_limit_s is not None and self.elapsed >= self.time_limit_s

    @property
    def remaining(self) -> int | None:
        """Résolutions LP restantes (``None`` si pas de budget LP)."""
        if self.max_lp_calls is None:
            return None
        return max(self.max_lp_calls - self.lp_calls, 0)

    def is_cached(self, arcs: Iterable[Arc]) -> bool:
        return frozenset(arcs) in self.cache

    def score(self, arcs: Iterable[Arc]) -> float:
        if self.time_limit_s is not None and self.elapsed >= self.time_limit_s:
            raise BudgetExhausted(f"plafond de temps atteint ({self.elapsed:.1f} s)")
        key = frozenset((int(i), int(j)) for i, j in arcs)
        if key in self.cache:
            return self.cache[key]
        if not qt.is_valid_topology(self.n, key):
            return math.inf
        if self.exhausted:
            raise BudgetExhausted(f"budget épuisé ({self.lp_calls} LP, {self.elapsed:.1f} s)")
        value = qt.route_min_congestion(self.demand, sorted(key)).objective
        self.lp_calls += 1
        self.cache[key] = value
        if value < self.best_score:
            self.best_score = value
            self.best_arcs = sorted(key)
        return value
