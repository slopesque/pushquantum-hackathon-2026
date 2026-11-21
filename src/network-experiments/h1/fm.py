"""Factorization machine (FMQA) : substitut quadratique appris du score LP de `network`.

Une topologie est un vecteur binaire de taille ``n(n-1)``, une colonne par arc, dans l'ordre de
``qt.all_arcs(n)``. La FM de rang ``k`` (Rendle 2010) prédit

    y(x) = w0 + Σ_i w_i x_i + Σ_{i<j} <v_i, v_j> x_i x_j

ce qui est exactement l'énergie d'un QUBO : ``to_bqm`` la convertit en ``dimod.BQM``.
Implémentation numpy uniquement (Adam en mini-batch, perte MSE + L2), déterministe par ``seed``.
"""

from __future__ import annotations

from collections.abc import Iterable

import dimod
import numpy as np
from scipy.stats import rankdata

from hackathon.referee import qt


def _arc_index(n: int) -> dict[tuple[int, int], int]:
    return {a: v for v, a in enumerate(qt.all_arcs(n))}


def topologies_to_X(topologies: Iterable[Iterable[tuple[int, int]]], n: int) -> np.ndarray:
    """Topologies (listes d'arcs) → matrice ``(m, n(n-1))`` uint8, colonnes = ``qt.all_arcs(n)``."""
    index = _arc_index(n)
    topologies = list(topologies)
    X = np.zeros((len(topologies), n * (n - 1)), dtype=np.uint8)
    for r, arcs in enumerate(topologies):
        cols = [index[(int(i), int(j))] for i, j in arcs]
        X[r, cols] = 1
    return X


def X_to_arcs(x: np.ndarray, n: int) -> list[tuple[int, int]]:
    """Vecteur binaire (colonnes = ``qt.all_arcs(n)``) → liste des arcs à 1."""
    arcs = qt.all_arcs(n)
    return [arcs[v] for v in np.flatnonzero(np.asarray(x).ravel())]


def make_target(scores: np.ndarray, mode: str = "rank") -> np.ndarray:
    """Transformation monotone croissante du score (score bas → cible basse).

    * ``"rank"`` : rangs moyens (ex aequo) ramenés dans [0, 1] par ``/(m-1)`` (défaut) ;
    * ``"zscore"`` : ``(s - mean) / std`` ;
    * ``"minmax"`` : ``(s - min) / (max - min)``, très plat près de l'optimum.
    """
    s = np.asarray(scores, dtype=float)
    m = len(s)
    if mode == "rank":
        if m <= 1:
            return np.zeros(m)
        return (rankdata(s, method="average") - 1.0) / (m - 1)
    if mode == "zscore":
        std = s.std()
        return (s - s.mean()) / (std if std > 0 else 1.0)
    if mode == "minmax":
        span = s.max() - s.min() if m else 0.0
        return (s - s.min()) / (span if span > 0 else 1.0)
    raise ValueError(f"mode inconnu : {mode!r} (rank, zscore, minmax)")


class FactorizationMachine:
    """FM de second ordre sur entrées binaires, entraînée par Adam (MSE + ``l2``·‖w, V‖²)."""

    def __init__(
        self,
        n_vars: int,
        rank: int = 8,
        seed: int = 0,
        l2: float = 1e-4,
        lr: float = 0.01,
        init_std: float = 0.01,
    ):
        self.n_vars = n_vars
        self.rank = rank
        self.seed = seed
        self.l2 = l2
        self.lr = lr
        self.init_std = init_std
        self.rng = np.random.default_rng(seed)
        self._init_params()

    def _init_params(self) -> None:
        self.w0 = 0.0
        self.w = np.zeros(self.n_vars)
        self.V = self.rng.normal(0.0, self.init_std, size=(self.n_vars, self.rank))
        self._fitted = False
        # États Adam (moments) et compteur de pas.
        self._m = [0.0, np.zeros_like(self.w), np.zeros_like(self.V)]
        self._v = [0.0, np.zeros_like(self.w), np.zeros_like(self.V)]
        self._t = 0

    def _forward(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        XV = X @ self.V  # (B, k)
        x2v2 = (X * X) @ (self.V * self.V)  # (B, k)
        y = self.w0 + X @ self.w + 0.5 * (XV * XV - x2v2).sum(axis=1)
        return y, XV

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, dtype=float))
        return self._forward(X)[0]

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 200,
        batch_size: int = 256,
        warm_start: bool = True,
    ) -> FactorizationMachine:
        X = np.atleast_2d(np.asarray(X, dtype=float))
        y = np.asarray(y, dtype=float).ravel()
        if not warm_start:
            self._init_params()
        if not self._fitted:
            self.w0 = float(y.mean())  # démarre au niveau moyen : convergence plus rapide
            self._fitted = True
        b1, b2, eps = 0.9, 0.999, 1e-8
        m_rows = len(y)
        for _ in range(epochs):
            order = self.rng.permutation(m_rows)
            for start in range(0, m_rows, batch_size):
                idx = order[start : start + batch_size]
                Xb, yb = X[idx], y[idx]
                pred, XV = self._forward(Xb)
                r = 2.0 * (pred - yb) / len(idx)  # dL/dpred
                g0 = r.sum()
                gw = Xb.T @ r + 2.0 * self.l2 * self.w
                gV = Xb.T @ (r[:, None] * XV) - self.V * ((Xb * Xb).T @ r)[:, None]
                gV += 2.0 * self.l2 * self.V
                self._t += 1
                c1, c2 = 1.0 - b1**self._t, 1.0 - b2**self._t
                params = [self.w0, self.w, self.V]
                for p, g in enumerate((g0, gw, gV)):
                    self._m[p] = b1 * self._m[p] + (1 - b1) * g
                    self._v[p] = b2 * self._v[p] + (1 - b2) * g * g
                    step = self.lr * (self._m[p] / c1) / (np.sqrt(self._v[p] / c2) + eps)
                    params[p] = params[p] - step
                self.w0, self.w, self.V = float(params[0]), params[1], params[2]
        return self

    def to_bqm(self) -> dimod.BinaryQuadraticModel:
        """BQM BINARY sur les variables ``0..n_vars-1`` : énergie(x) == ``predict(x)``."""
        rows, cols = np.triu_indices(self.n_vars, k=1)
        Q = self.V @ self.V.T
        return dimod.BinaryQuadraticModel.from_numpy_vectors(
            linear=self.w.copy(),
            quadratic=(rows, cols, Q[rows, cols]),
            offset=self.w0,
            vartype=dimod.BINARY,
            variable_order=list(range(self.n_vars)),
        )


def learned_qubo(
    fm: FactorizationMachine, demand: np.ndarray, lam: float
) -> tuple[dimod.BinaryQuadraticModel, dimod.BinaryQuadraticModel]:
    """``(full, objective)`` : objectif FM sans offset normalisé à max|coeff| = 1, puis + λ·pénalité."""
    objective = fm.to_bqm()
    objective.offset = 0.0
    lin, (_, _, quad), _ = objective.to_numpy_vectors()
    scale = max(np.abs(lin).max(initial=0.0), np.abs(quad).max(initial=0.0))
    if scale > 0:
        objective.scale(1.0 / scale)
    penalty = qt.build_network_qubo(demand)[1]
    full = objective.copy()
    full.update(penalty * lam)
    return full, objective
