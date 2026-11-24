"""Évaluateur incrémental de l'objectif (piste P2).

``PortfolioState`` contient une solution ``v`` (encodage entier, voir ``problem.py``) et les quantités qui
permettent d'évaluer un mouvement en O(1) au lieu de recalculer tout l'objectif.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from hackathon.solvers.portfolio.problem import PortfolioProblem

Change = tuple[int, int, int]
"""Un changement élémentaire ``(t, i, d)`` : ``v[t, i] += d``."""


class PortfolioState:
    """Une solution ``v`` et les quantités maintenues pour évaluer un mouvement en O(1).

    Maintenu : ``Gv[t] = G_t v_t`` (gradient du risque), ``net[t]``, ``total[t]`` et l'objectif.
    Un mouvement accepté coûte O(n) par jour touché (mise à jour d'une colonne de ``G``).
    """

    def __init__(self, problem: PortfolioProblem, v: np.ndarray | None = None):
        self.problem = problem
        shape = (problem.T, problem.n)
        self.v = np.zeros(shape, dtype=np.int64) if v is None else v.astype(np.int64)
        if self.v.shape != shape:
            raise ValueError(f"v doit être de forme {shape}")
        self.recompute()

    def recompute(self) -> None:
        d, v = self.problem, self.v
        self.Gv = np.einsum("tij,tj->ti", d.G, v)
        self.net = v.sum(axis=1)
        self.total = np.abs(v).sum(axis=1)
        self.objective = d.objective(v)

    def copy(self) -> PortfolioState:
        new = object.__new__(PortfolioState)
        new.problem, new.v, new.Gv = self.problem, self.v.copy(), self.Gv.copy()
        new.net, new.total, new.objective = self.net.copy(), self.total.copy(), self.objective
        return new

    @property
    def feasible(self) -> bool:
        return self.problem.is_feasible(self.v)

    # ── mouvements génériques ────────────────────────────────────────────

    def delta(self, changes: Iterable[Change]) -> tuple[int, bool]:
        """Variation de l'objectif et faisabilité après ``changes``, sans les appliquer.

        ``changes`` est une petite liste de ``(t, i, d)`` ; une même case peut apparaître plusieurs
        fois (les ``d`` s'additionnent). Coût : O(k² + k·T) pour k changements.

        La faisabilité n'est vérifiée que sur les cases et les jours touchés : elle est exacte si la
        solution courante est faisable, ce qui est le cas pendant une recherche locale. La variation
        de l'objectif, elle, est toujours exacte.
        """
        d = self.problem
        by_cell: dict[tuple[int, int], int] = {}
        for t, i, dv in changes:
            if dv:
                by_cell[t, i] = by_cell.get((t, i), 0) + dv
        by_cell = {k: x for k, x in by_cell.items() if x}
        if not by_cell:
            return 0, True

        v = self.v
        delta = 0
        feasible = True
        by_day: dict[int, list[tuple[int, int]]] = {}
        assets: set[int] = set()
        for (t, i), dv in by_cell.items():
            new = v[t, i] + dv
            if abs(new) > d.ub:
                feasible = False
            by_day.setdefault(t, []).append((i, dv))
            assets.add(i)
            delta -= int(d.ret[t, i]) * dv
            delta += int(d.sc[t, i]) * (max(-new, 0) - max(-v[t, i], 0))

        for t, cells in by_day.items():
            # Risque : (v+δ)ᵀR(v+δ) - vᵀRv = δᵀ G v + δᵀ R δ.
            for i, di in cells:
                delta += di * int(self.Gv[t, i])
                for j, dj in cells:
                    delta += di * dj * int(d.R[t, i, j])
            # Budget, capital et intérêts du jour t.
            dnet = sum(di for _, di in cells)
            dtotal = sum(abs(v[t, i] + di) - abs(v[t, i]) for i, di in cells)
            net = self.net[t] + dnet
            if self.total[t] + dtotal > d.budget or not d.net_min <= net <= d.net_max:
                feasible = False
            delta -= int(d.interest_of_slack(d.capital - net))
            delta += int(d.interest_of_slack(d.capital - self.net[t]))

        # Frais : recalcul en O(T) de chaque action touchée.
        cols = np.fromiter(assets, dtype=np.int64)
        old = v[:, cols]
        new = old.copy()
        col_index = {a: k for k, a in enumerate(cols)}
        for (t, i), dv in by_cell.items():
            new[t, col_index[i]] += dv
        tc = d.tc[:, cols]
        delta += int((d.transaction_cost_cols(new, tc) - d.transaction_cost_cols(old, tc)).sum())
        return delta, feasible

    def apply(self, changes: Iterable[Change]) -> int:
        """Applique ``changes`` (sans vérifier la faisabilité) et renvoie la variation de l'objectif."""
        changes = list(changes)
        delta, _ = self.delta(changes)
        d = self.problem
        for t, i, dv in changes:
            if not dv:
                continue
            self.Gv[t] += dv * d.G[t, :, i]
            self.total[t] += abs(self.v[t, i] + dv) - abs(self.v[t, i])
            self.net[t] += dv
            self.v[t, i] += dv
        self.objective += delta
        return delta

    # ── tous les mouvements simples d'un coup (vectorisé) ────────────────

    def single_move_deltas(self) -> tuple[np.ndarray, np.ndarray]:
        """Variation de l'objectif et faisabilité de chaque mouvement simple ``v[t,i] += s``.

        Renvoie ``(delta, feasible)``, deux tableaux de forme ``(2, T, n)`` : l'indice 0 correspond à
        ``s = +1``, l'indice 1 à ``s = -1``. Coût : O(T·n), sans boucle Python.
        """
        d, v, T = self.problem, self.v, self.problem.T
        out = np.empty((2, T, d.n), dtype=np.int64)
        ok = np.empty((2, T, d.n), dtype=bool)
        for k, s in enumerate((1, -1)):
            new = v + s
            delta = s * self.Gv + d.R_diag  # risque (s² = 1)
            delta -= s * d.ret  # rendement
            delta += d.sc * (np.maximum(-new, 0) - np.maximum(-v, 0))  # court
            # Frais : termes d'extrémité et transitions touchés par la case (t, i).
            delta[0] += d.tc[0] * (np.abs(new[0]) - np.abs(v[0]))
            delta[T - 1] += d.tc[T - 1] * (np.abs(new[T - 1]) - np.abs(v[T - 1]))
            if T > 2:
                diff = np.diff(v, axis=0)  # diff[t-1] = v[t] - v[t-1]
                # Transition entrante (t-1 → t), facturée pour 1 <= t <= T-2.
                inc = d.tc[1 : T - 1] * (np.abs(diff[: T - 2] + s) - np.abs(diff[: T - 2]))
                delta[1 : T - 1] += inc
                # Transition sortante (t → t+1), facturée pour 1 <= t+1 <= T-2, soit t <= T-3.
                outg = d.tc[1 : T - 1] * (np.abs(diff[: T - 2] - s) - np.abs(diff[: T - 2]))
                delta[: T - 2] += outg
            # Intérêts et capital : dépendent seulement du jour.
            net = self.net + s
            net_ok = (net >= d.net_min) & (net <= d.net_max)
            d_interest = d.interest_of_slack(d.capital - self.net) - d.interest_of_slack(
                d.capital - net
            )
            delta += d_interest[:, None]
            # Budget.
            total = self.total[:, None] + np.abs(new) - np.abs(v)
            ok[k] = (np.abs(new) <= d.ub) & (total <= d.budget) & net_ok[:, None]
            out[k] = delta
        return out, ok
