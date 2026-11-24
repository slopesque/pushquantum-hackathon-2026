"""Le problème de portefeuille QOBLIB 06, modélisé en encodage entier (pistes P1 et P2).

Une solution est une matrice ``v`` de forme ``(T, n)`` à valeurs dans ``{-ub, …, ub}`` :
``v > 0`` = long de ``v`` unités, ``v < 0`` = court de ``|v|`` unités. Être long et court sur la
même case ne sert jamais (frais et budget sans gain), donc ce sous-espace contient les solutions utiles.

Modèle (``bqp_u3_c10.zpl`` de QOBLIB). Une unité de l'action i vaut ``P[t,i] = unit · p[t,i] / p[0,i]``.
Objectif à minimiser, en coefficients entiers arrondis comme Zimpl (demi-entier loin de zéro) :

* risque          ``Σ_t v_t^T R_t v_t``, ``R_t[i,j] = round(λ · cov_t[i,j] · P[t,i] · P[t,j])``
* rendement       ``-Σ_{t<T-1} ret[t] · v_t``, ``ret[t,i] = round(P[t+1,i] - P[t,i])``
* transaction     ``tc_0·|v_0| + Σ_{t=1}^{T-2} tc_t·|v_t - v_{t-1}|``, ``tc = round(δ·P)``
* intérêts cash   ``-I(C - net_t)`` : bits du slack de cash pondérés par ``round(ν·unit·2^k)``
* coût du court   ``Σ sc · max(-v, 0)``, ``sc = round(ρ·P)``
* liquidation     ``tc_{T-1}·|v_{T-1}|``

Contraintes par jour : ``Σ_i |v| <= B`` et ``0 <= C - net_t <= 2^cash_slack_bits - 1``.

Propriété du modèle officiel, conservée volontairement : le passage du jour T-2 au jour T-1 n'est pas
facturé, seule la liquidation l'est.
"""

from __future__ import annotations

import gzip
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
import requests

from hackathon.utils import ROOT

QOBLIB_RAW = "https://raw.githubusercontent.com/ZIB-AOPT/QOBLIB/main"
DATA_DIR = ROOT / "data" / "qoblib"

# Arrondis recalculés exactement quand la valeur flottante tombe à moins de ça d'un demi-entier.
_HALF_TOLERANCE = 1e-6


# ════════════════════════════════════════════════════════════════════════
# Données
# ════════════════════════════════════════════════════════════════════════


def fetch(rel_path: str) -> Path:
    """Télécharge ``rel_path`` du dépôt QOBLIB une seule fois et renvoie la copie locale."""
    dest = DATA_DIR / rel_path
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(f"{QOBLIB_RAW}/{rel_path}", timeout=120)
        response.raise_for_status()
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(response.content)
        tmp.replace(dest)
    return dest


def _rows(path: Path) -> Iterator[list[str]]:
    with gzip.open(path, "rt") as f:
        for line in f:
            if line[0] != "#" and (parts := line.split()):
                yield parts


@dataclass
class PortfolioInstance:
    """Données brutes d'une instance : cours et covariances, jour par jour."""

    name: str
    symbols: list[str]
    prices: list[list[str]]
    """``prices[t][i]`` : cours de l'action i au jour t, tel qu'écrit dans le fichier (exact)."""
    cov: np.ndarray
    """``cov[t, i, j]`` : covariance des rendements de i et j au jour t (flottants)."""

    @property
    def n_periods(self) -> int:
        return len(self.prices)

    @property
    def n_assets(self) -> int:
        return len(self.symbols)

    def _path(self, kind: str) -> Path:
        return fetch(f"06-portfolio/instances/{self.name}/{kind}.txt.gz")

    def exact_cov(self, cells: set[tuple[int, int, int]]) -> dict[tuple[int, int, int], Fraction]:
        """Covariances exactes (fractions) pour quelques cellules ``(t, i, j)`` : relit le fichier."""
        index = {s: k for k, s in enumerate(self.symbols)}
        out = {}
        for day, s1, s2, value in _rows(self._path("covariance_matrices")):
            key = (int(day), index.get(s1, -1), index.get(s2, -1))
            if key in cells:
                out[key] = Fraction(value)
        return out


def load_instance(name: str) -> PortfolioInstance:
    """Charge une instance QOBLIB, par ex. ``po_a010_t10_orig`` (10 actions, 10 jours)."""
    base = f"06-portfolio/instances/{name}"
    symbols: list[str] = []
    index: dict[str, int] = {}
    entries = []
    for day, sym, price in _rows(fetch(f"{base}/stock_prices.txt.gz")):
        if sym not in index:
            index[sym] = len(symbols)
            symbols.append(sym)
        entries.append((int(day), index[sym], price))
    T, n = max(t for t, _, _ in entries) + 1, len(symbols)
    grid: list[list[str | None]] = [[None] * n for _ in range(T)]
    for t, i, p in entries:
        grid[t][i] = p
    prices = [[p for p in row if p is not None] for row in grid]
    if any(len(row) != n for row in prices):
        raise ValueError(f"{name}: cours manquants")

    cov = np.full((T, n, n), np.nan)
    for day, s1, s2, value in _rows(fetch(f"{base}/covariance_matrices.txt.gz")):
        t, i, j = int(day), index.get(s1), index.get(s2)
        if i is not None and j is not None and t < T:
            cov[t, i, j] = float(value)
    if np.isnan(cov).any():
        raise ValueError(f"{name}: covariances manquantes")
    return PortfolioInstance(name, symbols, prices, cov)


# ════════════════════════════════════════════════════════════════════════
# Modèle
# ════════════════════════════════════════════════════════════════════════


def zround(x: Fraction) -> int:
    """Arrondi de Zimpl : demi-entier arrondi loin de zéro."""
    shifted = x - Fraction(1, 2) if x < 0 else x + Fraction(1, 2)
    return int(shifted)


def _zround_array(x: np.ndarray) -> np.ndarray:
    return (np.sign(x) * np.floor(np.abs(x) + 0.5)).astype(np.int64)


class PortfolioProblem:
    """Une instance avec son budget ``B`` et son poids de risque ``λ``, en encodage entier."""

    def __init__(
        self,
        instance: PortfolioInstance,
        budget: int,
        lam: str,
        *,
        ub: int = 3,
        cash: int = 1_000_000,
        unit: int = 100_000,
        delta: str = "0.001",
        nu: str = "0.0001",
        rho: str = "0.000025",
        cash_slack_bits: int = 4,
    ):
        if cash % unit:
            raise ValueError("cash doit être un multiple de unit")
        self.instance = instance
        self.lam_str = lam
        self.lam = Fraction(lam)
        self.budget = int(budget)
        self.ub = ub
        self.symbols = instance.symbols
        self.T, self.n = instance.n_periods, instance.n_assets
        if self.T < 2:
            raise ValueError("il faut au moins deux jours")
        self.capital = cash // unit
        self.max_cash_slack = 2**cash_slack_bits - 1
        self.net_min, self.net_max = self.capital - self.max_cash_slack, self.capital
        T, n = self.T, self.n

        # Valeur exacte d'une unité, P[t][i] = unit · p[t,i] / p[0,i].
        p = [[Fraction(x) for x in row] for row in instance.prices]
        P = [[unit * p[t][i] / p[0][i] for i in range(n)] for t in range(T)]
        delta_, rho_, nu_ = Fraction(delta), Fraction(rho), Fraction(nu)
        self.ret = np.zeros((T, n), dtype=np.int64)  # le dernier jour ne rapporte rien
        for t in range(T - 1):
            self.ret[t] = [zround(P[t + 1][i] - P[t][i]) for i in range(n)]
        self.tc = np.array([[zround(delta_ * P[t][i]) for i in range(n)] for t in range(T)])
        self.sc = np.array([[zround(rho_ * P[t][i]) for i in range(n)] for t in range(T)])
        self.interest = [zround(nu_ * unit * 2**k) for k in range(cash_slack_bits)]
        self.R = self._risk_matrix(P)
        self.G = self.R + self.R.transpose(0, 2, 1)  # gradient du risque : ∇(vᵀRv) = G v
        self.R_diag = np.einsum("tii->ti", self.R)

    def _risk_matrix(self, P: list[list[Fraction]]) -> np.ndarray:
        """``R[t,i,j] = round(λ · cov · P[t,i] · P[t,j])``, exact.

        Calcul en flottants, puis recalcul en fractions des seules valeurs proches d'un demi-entier,
        où l'erreur d'arrondi flottante pourrait changer le résultat.
        """
        T, n = self.T, self.n
        if self.lam == 0:
            return np.zeros((T, n, n), dtype=np.int64)
        Pf = np.array([[float(x) for x in row] for row in P])  # (T, n)
        x = float(self.lam) * self.instance.cov * Pf[:, :, None] * Pf[:, None, :]
        R = _zround_array(x)
        frac = np.abs(x) - np.floor(np.abs(x))
        risky = np.argwhere(np.abs(frac - 0.5) < _HALF_TOLERANCE)
        if len(risky):
            cells = {(int(t), int(i), int(j)) for t, i, j in risky}
            exact = self.instance.exact_cov(cells)
            for (t, i, j), c in exact.items():
                R[t, i, j] = zround(self.lam * c * P[t][i] * P[t][j])
        return R

    # ── objectif ─────────────────────────────────────────────────────────

    def interest_of_slack(self, c):
        """Intérêts gagnés pour un slack de cash ``c = C - net`` (entier ou tableau ; 0 si c < 0)."""
        c = np.asarray(c, dtype=np.int64)
        safe = np.maximum(c, 0)
        total = sum(((safe >> k) & 1) * w for k, w in enumerate(self.interest))
        return np.where(c >= 0, total, 0)

    def transaction_cost_cols(self, v: np.ndarray, tc: np.ndarray) -> np.ndarray:
        """Frais (achat, rebalancement, liquidation) par colonne de ``v`` : forme ``(k,)``."""
        T = self.T
        a = np.abs(v)
        cost = tc[0] * a[0] + tc[T - 1] * a[T - 1]
        if T > 2:
            cost = cost + (tc[1 : T - 1] * np.abs(np.diff(v[: T - 1], axis=0))).sum(axis=0)
        return cost

    def breakdown(self, v: np.ndarray) -> dict[str, int]:
        T = self.T
        net = v.sum(axis=1)
        moves = 0
        if T > 2:
            moves = int((self.tc[1 : T - 1] * np.abs(np.diff(v[: T - 1], axis=0))).sum())
        return {
            "risk": int(np.einsum("ti,tij,tj->", v, self.R, v)),
            "return": -int((self.ret * v).sum()),
            "transaction": int((self.tc[0] * np.abs(v[0])).sum()) + moves,
            "cash_interest": -int(self.interest_of_slack(self.capital - net).sum()),
            "short_cost": int((self.sc * np.maximum(-v, 0)).sum()),
            "liquidation": int((self.tc[T - 1] * np.abs(v[T - 1])).sum()),
        }

    def objective(self, v: np.ndarray) -> int:
        return sum(self.breakdown(v).values())

    def violations(self, v: np.ndarray) -> list[str]:
        out = []
        if (np.abs(v) > self.ub).any():
            out.append(f"|v| > {self.ub}")
        net, total = v.sum(axis=1), np.abs(v).sum(axis=1)
        for t in np.flatnonzero((net < self.net_min) | (net > self.net_max)):
            out.append(f"t={t}: position nette {net[t]} hors de [{self.net_min}, {self.net_max}]")
        for t in np.flatnonzero(total > self.budget):
            out.append(f"t={t}: {total[t]} unités ouvertes > budget {self.budget}")
        return out

    def is_feasible(self, v: np.ndarray) -> bool:
        return not self.violations(v)

    # ── fichiers de solution (format canonique QOBLIB) ───────────────────

    @property
    def lam_tag(self) -> str:
        """``λ`` tel qu'écrit dans les noms de fichiers QOBLIB : ``0``, ``1e-4``, ``5e-5``…"""
        if self.lam == 0:
            return "0"
        mantissa, exponent = f"{float(self.lam):.0e}".split("e")
        return f"{mantissa}e{int(exponent)}"

    @property
    def solution_filename(self) -> str:
        return f"{self.instance.name}_b{self.budget:03d}_l{self.lam_tag}.sol"

    def solution_text(self, v: np.ndarray, comment: str = "") -> str:
        lines = [f"# {line}" for line in comment.splitlines()]
        lines += [
            f"instance {self.instance.name}",
            f"budget {self.budget}",
            f"lambda {format(float(self.lam), 'g') if self.lam else '0'}",
            f"objective {self.objective(v)}",
            "# period symbol long short",
        ]
        for t, i in zip(*np.nonzero(v), strict=True):
            x = int(v[t, i])
            lines.append(f"{t} {self.symbols[i]} {max(x, 0)} {max(-x, 0)}")
        return "\n".join(lines) + "\n"

    def read_solution(self, path: str | Path) -> np.ndarray:
        index = {s: k for k, s in enumerate(self.symbols)}
        v = np.zeros((self.T, self.n), dtype=np.int64)
        for line in Path(path).read_text().splitlines():
            toks = line.split("#", 1)[0].split()
            if len(toks) == 4 and toks[0].isdigit():
                long_, short = int(toks[2]), int(toks[3])
                if long_ and short:
                    raise ValueError(f"{line!r} : long et court sur la même case")
                v[int(toks[0]), index[toks[1]]] = long_ - short
        return v
