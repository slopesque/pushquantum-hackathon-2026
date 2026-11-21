"""Data loaders, official scorers and QUBO builders for the Qoro x QOBLIB hackathon.

The scoring functions are Python ports of QOBLIB's own solution checkers
(``06-portfolio/check`` and ``08-network/check`` in
https://github.com/ZIB-AOPT/QOBLIB, Apache-2.0) and reproduce their numbers
exactly. Treat them as the referee: change your models and solvers, not these.

Sections:
    * Downloading QOBLIB files
    * 06 - Portfolio optimisation: instance, official model/score, QUBO builder
    * 08 - Network design: demand, exact routing LP, checker, QUBO builder
"""
from __future__ import annotations

import gzip
import itertools
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import dimod
import numpy as np
import requests
import scipy.sparse as sps
from scipy.optimize import Bounds, linprog, milp
from scipy.optimize import LinearConstraint as _LPConstraint

QOBLIB_RAW = "https://raw.githubusercontent.com/ZIB-AOPT/QOBLIB/main"
DATA_DIR = Path(__file__).resolve().parent / "qoblib_data"


# ════════════════════════════════════════════════════════════════════════
# Downloading QOBLIB files
# ════════════════════════════════════════════════════════════════════════


def fetch_qoblib_file(rel_path: str) -> Path:
    """Download ``rel_path`` from the QOBLIB repo once and return the local copy."""
    dest = DATA_DIR / rel_path
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(f"{QOBLIB_RAW}/{rel_path}", timeout=60)
        response.raise_for_status()
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(response.content)
        tmp.replace(dest)
    return dest


def _data_rows(path: Path) -> Iterable[list[str]]:
    """Whitespace-split, non-comment lines of a (possibly gzipped) text file."""
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                yield line.split()


# ════════════════════════════════════════════════════════════════════════
# 06 - Portfolio optimisation
# ════════════════════════════════════════════════════════════════════════


def _zround(x: Fraction) -> int:
    """Zimpl's ``round()``: round half away from zero, on exact rationals."""
    shifted = x - Fraction(1, 2) if x < 0 else x + Fraction(1, 2)
    return int(shifted)  # int() truncates toward zero


@dataclass
class PortfolioInstance:
    """Raw market data of one QOBLIB portfolio instance."""

    name: str
    symbols: list[str]
    """Asset symbols, in the order of the ``stock_prices`` file."""
    n_periods: int
    prices: list[list[Fraction]]
    """``prices[i][t]`` — exact share price of asset ``i`` on day ``t``."""
    cov: dict[tuple[int, int, int], Fraction] = field(repr=False)
    """``cov[i, j, t]`` — return covariance of assets ``i`` and ``j`` on day ``t``."""

    @property
    def n_assets(self) -> int:
        return len(self.symbols)


def load_portfolio_instance(name: str = "po_a010_t10_orig") -> PortfolioInstance:
    """Download (once) and parse a QOBLIB portfolio instance, e.g. ``po_a010_t10_orig``."""
    base = f"06-portfolio/instances/{name}"
    symbols: list[str] = []
    index: dict[str, int] = {}
    entries = []
    for day, sym, price in _data_rows(fetch_qoblib_file(f"{base}/stock_prices.txt.gz")):
        if sym not in index:
            index[sym] = len(symbols)
            symbols.append(sym)
        entries.append((index[sym], int(day), Fraction(price)))
    n_periods = max(t for _, t, _ in entries) + 1
    prices: list[list[Fraction | None]] = [[None] * n_periods for _ in symbols]
    for i, t, p in entries:
        prices[i][t] = p
    if any(p is None for row in prices for p in row):
        raise ValueError(f"{name}: missing prices")

    cov = {}
    for day, s1, s2, value in _data_rows(
        fetch_qoblib_file(f"{base}/covariance_matrices.txt.gz")
    ):
        t = int(day)
        if s1 in index and s2 in index and t < n_periods:
            cov[index[s1], index[s2], t] = Fraction(value)
    return PortfolioInstance(name, symbols, n_periods, prices, cov)


@dataclass
class PortfolioScore:
    """Result of :meth:`PortfolioModel.score` — what QOBLIB's checker reports."""

    objective: int
    feasible: bool
    breakdown: dict[str, int]
    violations: list[str]

    def __str__(self) -> str:
        status = "feasible" if self.feasible else "INFEASIBLE"
        parts = ", ".join(f"{k}={v}" for k, v in self.breakdown.items())
        return f"objective={self.objective} ({status}; {parts})"


Positions = Mapping[tuple[int, str], tuple[int, int]]
"""Canonical portfolio solution: ``{(period, symbol): (long_units, short_units)}``."""


class PortfolioModel:
    """QOBLIB's reference portfolio model (``bqp_u3_c10.zpl``) for one instance.

    Fixes the instance, the budget ``B`` (max open positions per period) and the
    risk weight ``λ``. Every objective coefficient is pre-rounded exactly like
    Zimpl does, so :meth:`score` returns the same integer as QOBLIB's checker.

    The decision is, per period ``t`` and asset ``i``, how many *units* to hold
    long and short (each ``0..ub``). One unit is worth ``unit`` cash at ``t=0``.
    Per period: ``0 <= C - (longs - shorts) <= 2**cash_slack_bits - 1`` with
    ``C = cash / unit`` and ``0 <= B - (longs + shorts) <= 2**count_slack_bits - 1``.
    """

    def __init__(
        self,
        instance: PortfolioInstance,
        budget: int,
        lam: float | str,
        *,
        ub: int = 3,
        cash: int = 1_000_000,
        unit: int = 100_000,
        delta: str = "0.001",
        nu: str = "0.0001",
        rho: str = "0.000025",
        cash_slack_bits: int = 4,
        count_slack_bits: int = 7,
    ):
        if cash % unit:
            raise ValueError("cash must be a multiple of unit")
        self.instance = instance
        self.budget = int(budget)
        self.lam = Fraction(str(lam))
        self.ub = ub
        self.capital = cash // unit
        self.cash_slack_bits = cash_slack_bits
        self.count_slack_bits = count_slack_bits
        n, T = instance.n_assets, instance.n_periods
        if T < 2:
            raise ValueError("the portfolio model needs at least two periods")
        delta, nu, rho = Fraction(delta), Fraction(nu), Fraction(rho)

        # Value of one unit of asset i at time t.
        P = [[row[t] * unit / row[0] for t in range(T)] for row in instance.prices]
        self.unit_prices = P

        # Integer coefficient tables (exactly the Zimpl-rounded LP coefficients).
        self.risk = np.zeros((T, n, n), dtype=np.int64)
        if self.lam != 0:
            for t in range(T):
                for i in range(n):
                    for j in range(n):
                        c = instance.cov.get((i, j, t))
                        if c is None:
                            raise ValueError(f"missing covariance ({i}, {j}, {t})")
                        self.risk[t, i, j] = _zround(self.lam * c * P[i][t] * P[j][t])
        self.ret = np.array(
            [[_zround(P[i][t + 1] - P[i][t]) for i in range(n)] for t in range(T - 1)],
            dtype=np.int64,
        )
        self.tc = np.array(
            [[_zround(delta * P[i][t]) for i in range(n)] for t in range(T)],
            dtype=np.int64,
        )
        self.sc = np.array(
            [[_zround(rho * P[i][t]) for i in range(n)] for t in range(T)],
            dtype=np.int64,
        )
        self.interest = np.array(
            [_zround(nu * unit * 2**k) for k in range(cash_slack_bits)], dtype=np.int64
        )

    # ── conversions ──────────────────────────────────────────────────────

    @property
    def symbols(self) -> list[str]:
        return self.instance.symbols

    @property
    def n_periods(self) -> int:
        return self.instance.n_periods

    def to_arrays(self, positions: Positions) -> tuple[np.ndarray, np.ndarray]:
        """``positions`` → ``(long, short)`` integer arrays of shape ``(T, n)``."""
        index = {s: i for i, s in enumerate(self.symbols)}
        L = np.zeros((self.n_periods, len(self.symbols)), dtype=np.int64)
        S = np.zeros_like(L)
        for (t, sym), (lo, sh) in positions.items():
            L[t, index[sym]] = lo
            S[t, index[sym]] = sh
        return L, S

    def to_positions(self, L: np.ndarray, S: np.ndarray) -> dict:
        """``(long, short)`` arrays → canonical ``{(t, symbol): (long, short)}``."""
        return {
            (t, sym): (int(L[t, i]), int(S[t, i]))
            for t in range(self.n_periods)
            for i, sym in enumerate(self.symbols)
            if L[t, i] or S[t, i]
        }

    # ── the official score ───────────────────────────────────────────────

    def score(self, positions: Positions) -> PortfolioScore:
        """Objective and feasibility of a solution, exactly as QOBLIB's checker computes them."""
        return self.score_arrays(*self.to_arrays(positions))

    def score_arrays(self, L: np.ndarray, S: np.ndarray) -> PortfolioScore:
        """:meth:`score` for ``(long, short)`` arrays of shape ``(T, n)``."""
        T = self.n_periods
        violations = []
        if (L < 0).any() or (S < 0).any() or (L > self.ub).any() or (S > self.ub).any():
            violations.append(f"unit counts must lie in 0..{self.ub}")
        v = L - S
        net, total = v.sum(axis=1), (L + S).sum(axis=1)
        cash_slack = self.capital - net
        count_slack = self.budget - total
        max_cash, max_count = 2**self.cash_slack_bits - 1, 2**self.count_slack_bits - 1
        for t in range(T):
            if not 0 <= cash_slack[t] <= max_cash:
                violations.append(
                    f"t={t}: net position {net[t]} outside [{self.capital - max_cash}, {self.capital}]"
                )
            if not 0 <= count_slack[t] <= max_count:
                violations.append(
                    f"t={t}: {total[t]} open positions exceeds budget {self.budget}"
                )

        interest = 0
        for t in range(T):
            if cash_slack[t] >= 0:
                bits = [(int(cash_slack[t]) >> k) & 1 for k in range(self.cash_slack_bits)]
                interest -= int(np.dot(bits, self.interest))
        moves = np.abs(np.diff(L, axis=0)) + np.abs(np.diff(S, axis=0))  # (T-1, n)
        breakdown = {
            "risk": int(np.einsum("ti,tij,tj->", v, self.risk, v)),
            "return": -int((self.ret * v[:-1]).sum()),
            "transaction": int((self.tc[0] * (L[0] + S[0])).sum())
            + int((self.tc[1 : T - 1] * moves[: T - 2]).sum()),
            "cash_interest": interest,
            "short_cost": int((self.sc * S).sum()),
            "liquidation": int((self.tc[T - 1] * (L[T - 1] + S[T - 1])).sum()),
        }
        return PortfolioScore(
            objective=sum(breakdown.values()),
            feasible=not violations,
            breakdown=breakdown,
            violations=violations,
        )

    # ── repair & local search (classical post-processing) ────────────────

    def repair(self, positions: Positions) -> dict:
        """Make a solution feasible by greedily dropping the least valuable units."""
        L, S = self.to_arrays(positions)
        L, S = np.clip(L, 0, self.ub), np.clip(S, 0, self.ub)
        max_cash = 2**self.cash_slack_bits - 1
        for t in range(self.n_periods):
            while True:
                net, total = (L[t] - S[t]).sum(), (L[t] + S[t]).sum()
                drop_long = net > self.capital or total > self.budget
                drop_short = net < self.capital - max_cash or total > self.budget
                if not (drop_long or drop_short):
                    break
                best = None
                for arr, allowed in ((L, drop_long), (S, drop_short)):
                    if not allowed:
                        continue
                    for i in np.flatnonzero(arr[t]):
                        arr[t, i] -= 1
                        obj = self.score_arrays(L, S).objective
                        arr[t, i] += 1
                        if best is None or obj < best[0]:
                            best = (obj, arr, i)
                _, arr, i = best
                arr[t, i] -= 1
        return self.to_positions(L, S)

    def local_search(self, positions: Positions, max_rounds: int = 1000) -> dict:
        """Best-improvement descent over single-unit moves (+/-1 long or short).

        Starts from :meth:`repair` of ``positions`` and only accepts feasible moves.
        """
        L, S = self.to_arrays(self.repair(positions))
        best = self.score_arrays(L, S).objective
        for _ in range(max_rounds):
            move = None
            for arr, t, i, d in itertools.product(
                (L, S), range(self.n_periods), range(len(self.symbols)), (1, -1)
            ):
                if not 0 <= arr[t, i] + d <= self.ub:
                    continue
                arr[t, i] += d
                result = self.score_arrays(L, S)
                arr[t, i] -= d
                if result.feasible and result.objective < best:
                    best, move = result.objective, (arr, t, i, d)
            if move is None:
                break
            arr, t, i, d = move
            arr[t, i] += d
        return self.to_positions(L, S)

    def brute_force(self, max_configs: int = 5000) -> tuple[dict, int]:
        """Exact optimum of a *tiny* instance (e.g. 3 assets) by dynamic programming.

        Enumerates every ``(long, short)`` configuration of one period and chains
        periods through the rebalancing cost. Returns ``(positions, objective)``.
        """
        n, T, ub = len(self.symbols), self.n_periods, self.ub
        if (ub + 1) ** (2 * n) > max_configs:
            raise ValueError("instance too large to brute force")
        cfg = np.array(list(itertools.product(range(ub + 1), repeat=2 * n))).reshape(-1, n, 2)
        L, S = cfg[:, :, 0], cfg[:, :, 1]
        v, total = L - S, L + S
        cash = self.capital - v.sum(axis=1)
        feasible = (cash >= 0) & (cash < 2**self.cash_slack_bits)
        feasible &= (self.budget - total.sum(axis=1) >= 0)
        interest = sum(
            self.interest[k] * ((np.maximum(cash, 0) >> k) & 1)
            for k in range(self.cash_slack_bits)
        )
        stage = []  # per-period cost of each configuration
        for t in range(T):
            g = np.einsum("ki,ij,kj->k", v, self.risk[t], v) - interest + S @ self.sc[t]
            if t < T - 1:
                g = g - v @ self.ret[t]
            if t in (0, T - 1):
                g = g + total @ self.tc[t]
            stage.append(np.where(feasible, g, np.iinfo(np.int64).max // 4))
        best, back = stage[0], []
        for t in range(1, T):
            trans = 0
            if t < T - 1:  # rebalancing cost between t-1 and t
                trans = (
                    np.abs(L[:, None] - L[None]) + np.abs(S[:, None] - S[None])
                ) @ self.tc[t]
            total_cost = best[:, None] + trans + stage[t][None, :]
            back.append(total_cost.argmin(axis=0))
            best = total_cost.min(axis=0)
        k = int(best.argmin())
        objective, chosen = int(best[k]), [k]
        for b in reversed(back):
            chosen.append(int(b[chosen[-1]]))
        chosen.reverse()
        positions = self.to_positions(L[chosen], S[chosen])
        return positions, objective

    # ── solution files ───────────────────────────────────────────────────

    def write_solution(self, path: str | Path, positions: Positions, comment: str = ""):
        """Write a solution in QOBLIB's canonical ``.sol`` format (ready to submit)."""
        result = self.score(positions)
        lines = [f"# {line}" for line in comment.splitlines()]
        lines += [
            f"instance {self.instance.name}",
            f"budget {self.budget}",
            f"lambda {_format_decimal(self.lam)}",
            f"objective {result.objective}",
            "# period symbol long short",
        ]
        for (t, sym), (lo, sh) in sorted(positions.items()):
            if lo or sh:
                lines.append(f"{t} {sym} {lo} {sh}")
        Path(path).write_text("\n".join(lines) + "\n")
        return result


def _format_decimal(x: Fraction) -> str:
    return format(float(x), "g") if x else "0"


def read_portfolio_solution(path: str | Path) -> tuple[dict, dict]:
    """Read a canonical portfolio ``.sol`` file → ``(header, positions)``."""
    header, positions = {}, {}
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        toks = line.split()
        if len(toks) == 4 and toks[0].isdigit():
            positions[int(toks[0]), toks[1]] = (int(toks[2]), int(toks[3]))
        elif len(toks) == 2:
            header[toks[0]] = toks[1]
    return header, positions


def fetch_portfolio_reference(instance: str, budget: int, lam_tag: str) -> Path:
    """Download a curated reference solution, e.g. ``("po_a010_t10_orig", 4, "1e-4")``.

    ``lam_tag`` uses the file-name spelling: ``"0"``, ``"1e-6"``, ``"5e-5"``, ``"1e-4"``...
    """
    folder = f"06-portfolio/solutions/{instance}"
    stem = f"{instance}_b{budget:03d}_l{lam_tag}"
    for kind in ("opt", "bst"):
        try:
            return fetch_qoblib_file(f"{folder}/{stem}.{kind}.sol")
        except requests.HTTPError:
            continue
    raise FileNotFoundError(f"no reference solution for {stem}")


class PortfolioQUBO:
    """The portfolio model as a QUBO: ``objective`` + ``penalty`` binary quadratic models.

    Variables are integers ``0..n_vars-1`` in QOBLIB's flat order
    (``asset → copy m → direction (+1, -1) → period``, then the cash and budget
    slack registers), so bitstrings are compatible with QOBLIB's own
    ``lp_sol_to_canonical.py`` when the default encoding is used.

    With the defaults this is exactly ``bqp_u3_c10.zpl`` with its two equality
    constraints moved into ``penalty``. The keyword arguments are modelling
    knobs; the score is always computed by the official :class:`PortfolioModel`:

    Args:
        model: The official model (instance, budget, λ).
        ub: Unit copies per (asset, direction, period). Smaller = fewer qubits,
            but positions above ``ub`` become unreachable.
        cash_slack_bits: Bits of the cash slack register (official: 4).
        count_slack_bits: Bits of the budget slack register (official: 7;
            ``ceil(log2(B + 1))`` already covers every feasible slack value).
    """

    def __init__(
        self,
        model: PortfolioModel,
        *,
        ub: int | None = None,
        cash_slack_bits: int | None = None,
        count_slack_bits: int | None = None,
    ):
        self.model = model
        self.ub = model.ub if ub is None else ub
        if not 1 <= self.ub <= model.ub:
            raise ValueError(f"ub must lie in 1..{model.ub}")
        self.cash_bits = cash_slack_bits or model.cash_slack_bits
        self.count_bits = count_slack_bits or model.count_slack_bits
        if self.cash_bits > model.cash_slack_bits or self.count_bits > model.count_slack_bits:
            raise ValueError("slack registers cannot be wider than the official model's")
        n, T, ub = len(model.symbols), model.n_periods, self.ub

        # Flat variable order.
        self.labels: list[tuple] = []
        for i, sym in enumerate(model.symbols):
            for m in range(ub):
                for tau in (1, -1):
                    for t in range(T):
                        self.labels.append(("x", sym, m, tau, t))
        self.n_x = len(self.labels)
        self.labels += [("y", k, t) for k in range(self.cash_bits) for t in range(T)]
        self.labels += [("s", c, t) for c in range(self.count_bits) for t in range(T)]
        self.n_vars = len(self.labels)

        def x(i, m, tau, t):
            return ((i * ub + m) * 2 + (0 if tau == 1 else 1)) * T + t

        def y(k, t):
            return self.n_x + k * T + t

        def s(c, t):
            return self.n_x + self.cash_bits * T + c * T + t

        self._x, self._y, self._s = x, y, s
        self.objective = self._build_objective()
        self.penalty = self._build_penalty()

    def _build_objective(self) -> dimod.BinaryQuadraticModel:
        model, T, ub = self.model, self.model.n_periods, self.ub
        n, x = len(model.symbols), self._x
        linear = np.zeros(self.n_vars)
        rows, cols, vals = [], [], []

        # Local (asset, copy, direction) layout within one period.
        loc = [(i, m, tau) for i in range(n) for m in range(ub) for tau in (1, -1)]
        asset = np.array([i for i, _, _ in loc])
        sign = np.array([tau for _, _, tau in loc])
        for t in range(T):
            glob = np.array([x(i, m, tau, t) for i, m, tau in loc])
            # Risk: sum over ordered pairs of variables, x_a * x_a = x_a.
            M = np.outer(sign, sign) * model.risk[t][np.ix_(asset, asset)]
            linear[glob] += np.diag(M)
            upper = np.triu(M + M.T, k=1)
            a, b = np.nonzero(upper)
            rows.append(glob[a]), cols.append(glob[b]), vals.append(upper[a, b])

            for (i, m, tau), g in zip(loc, glob):
                if tau == -1:
                    linear[g] += model.sc[t, i]  # short-selling cost
                if t < T - 1:
                    linear[g] -= tau * model.ret[t, i]  # return
                if t == 0 or t == T - 1:
                    linear[g] += model.tc[t, i]  # buy-in / liquidation
                elif t < T - 1:  # rebalancing: x_{t-1} XOR x_t
                    prev = x(i, m, tau, t - 1)
                    linear[g] += model.tc[t, i]
                    linear[prev] += model.tc[t, i]
                    rows.append([prev]), cols.append([g])
                    vals.append([-2 * model.tc[t, i]])
            for k in range(self.cash_bits):  # cash interest on the slack digits
                linear[self._y(k, t)] -= model.interest[k]

        quad = (
            np.concatenate(rows).astype(np.int64),
            np.concatenate(cols).astype(np.int64),
            np.concatenate(vals).astype(float),
        )
        return dimod.BinaryQuadraticModel.from_numpy_vectors(
            linear, quad, 0.0, dimod.BINARY
        )

    def _build_penalty(self) -> dimod.BinaryQuadraticModel:
        model, T, ub = self.model, self.model.n_periods, self.ub
        n = len(model.symbols)
        bqm = dimod.BinaryQuadraticModel.from_numpy_vectors(
            np.zeros(self.n_vars), ([], [], []), 0.0, dimod.BINARY
        )
        for t in range(T):
            xs = [
                (self._x(i, m, tau, t), tau)
                for i in range(n)
                for m in range(ub)
                for tau in (1, -1)
            ]
            capital = xs + [(self._y(k, t), 2**k) for k in range(self.cash_bits)]
            bqm.add_linear_equality_constraint(capital, 1.0, -model.capital)
            budget = [(v, 1) for v, _ in xs]
            budget += [(self._s(c, t), 2**c) for c in range(self.count_bits)]
            bqm.add_linear_equality_constraint(budget, 1.0, -model.budget)
        return bqm

    # ── sample <-> positions ─────────────────────────────────────────────

    def decode(self, sample) -> dict:
        """Bit assignment (dict or array in label order) → canonical positions."""
        bits = _as_bit_array(sample, self.n_vars)
        model, T = self.model, self.model.n_periods
        L = np.zeros((T, len(model.symbols)), dtype=np.int64)
        S = np.zeros_like(L)
        for idx in np.flatnonzero(bits[: self.n_x]):
            _, sym, _, tau, t = self.labels[idx]
            i = model.symbols.index(sym)
            (L if tau == 1 else S)[t, i] += 1
        return model.to_positions(L, S)

    def encode(self, positions: Positions) -> np.ndarray:
        """Canonical positions → bit array (copies filled from slot 0, exact slacks)."""
        model, T = self.model, self.model.n_periods
        L, S = model.to_arrays(positions)
        if (L > self.ub).any() or (S > self.ub).any():
            raise ValueError(f"positions exceed this encoding's ub={self.ub}")
        bits = np.zeros(self.n_vars, dtype=np.int8)
        for t in range(T):
            for i in range(len(model.symbols)):
                for m in range(L[t, i]):
                    bits[self._x(i, m, 1, t)] = 1
                for m in range(S[t, i]):
                    bits[self._x(i, m, -1, t)] = 1
            cash = model.capital - (L[t] - S[t]).sum()
            count = model.budget - (L[t] + S[t]).sum()
            for k in range(self.cash_bits):
                bits[self._y(k, t)] = (cash >> k) & 1 if cash >= 0 else 0
            for c in range(self.count_bits):
                bits[self._s(c, t)] = (count >> c) & 1 if count >= 0 else 0
        return bits

    def bitstring(self, positions: Positions) -> str:
        """:meth:`encode` as a ``'0101…'`` string (e.g. for ``reference_states``)."""
        return "".join(map(str, self.encode(positions)))


def _as_bit_array(sample, n_vars: int) -> np.ndarray:
    if isinstance(sample, str):
        return np.array([int(b) for b in sample], dtype=np.int8)
    if isinstance(sample, Mapping):
        return np.array([int(sample[v]) for v in range(n_vars)], dtype=np.int8)
    return np.asarray(sample, dtype=np.int8)


# ════════════════════════════════════════════════════════════════════════
# 08 - Network design
# ════════════════════════════════════════════════════════════════════════

INTSCALE = 1000  # QOBLIB stores flows and the objective in units of 1/1000


def load_network_demand(n: int) -> np.ndarray:
    """Demand matrix of ``networkNN`` — the top-left ``n x n`` block of ``demand.txt``.

    Returned 0-indexed: ``demand[k, i]`` is the traffic from node ``k`` to node ``i``.
    """
    rows = {}
    for line in fetch_qoblib_file("08-network/instances/demand.txt").read_text().splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|(.*?)\|?\s*$", line.strip())
        if m:
            rows[int(m.group(1))] = [int(v) for v in m.group(2).split(",") if v.strip()]
    return np.array([rows[k][:n] for k in range(1, n + 1)], dtype=np.int64)


def all_arcs(n: int) -> list[tuple[int, int]]:
    """Every possible arc ``(i, j)``, ``i != j`` — one binary variable each."""
    return [(i, j) for i in range(n) for j in range(n) if i != j]


def is_valid_topology(n: int, arcs: Iterable[tuple[int, int]]) -> bool:
    """Simple digraph on ``n`` nodes where every node has in- and out-degree 2."""
    arcs = set(arcs)
    if any(i == j or not (0 <= i < n and 0 <= j < n) for i, j in arcs):
        return False
    out_deg, in_deg = np.zeros(n, int), np.zeros(n, int)
    for i, j in arcs:
        out_deg[i] += 1
        in_deg[j] += 1
    return bool((out_deg == 2).all() and (in_deg == 2).all())


def repair_topology(
    n: int, arcs: Iterable[tuple[int, int]], demand: np.ndarray | None = None
) -> list[tuple[int, int]]:
    """Closest valid topology to any arc set: keeps as many of ``arcs`` as possible.

    Solves a small degree-constrained matching exactly (out- and in-degree 2,
    no self-loops); ties are broken towards links with more direct demand.
    """
    chosen = set(arcs)
    candidates = all_arcs(n)
    tie = np.zeros((n, n)) if demand is None else demand / max(demand.max(), 1) * 1e-3
    c = -np.array([float((i, j) in chosen) + tie[i, j] for i, j in candidates])
    rows, cols = [], []
    for v, (i, j) in enumerate(candidates):
        rows += [i, n + j]  # out-degree row of i, in-degree row of j
        cols += [v, v]
    A = sps.csr_array((np.ones(len(rows)), (rows, cols)), shape=(2 * n, len(candidates)))
    res = milp(
        c,
        constraints=[_LPConstraint(A, 2.0, 2.0)],
        integrality=np.ones(len(candidates)),
        bounds=Bounds(0, 1),
    )
    if res.x is None:
        raise RuntimeError(f"topology repair failed: {res.message}")
    return [a for a, y in zip(candidates, res.x) if y > 0.5]


def random_topology(n: int, rng: np.random.Generator) -> list[tuple[int, int]]:
    """Uniform-ish random valid topology: two derangements that never agree."""
    while True:
        p1, p2 = rng.permutation(n), rng.permutation(n)
        idx = np.arange(n)
        if (p1 != idx).all() and (p2 != idx).all() and (p1 != p2).all():
            return [(i, int(p1[i])) for i in range(n)] + [(i, int(p2[i])) for i in range(n)]


@dataclass
class NetworkRouting:
    """Optimal routing of all demand on a fixed topology."""

    objective: float
    """QOBLIB objective: max aggregate arc flow in 1/1000 units (``inf`` if unroutable)."""
    z_lp: float
    """Exact LP optimum (fractional flows), in the same units."""
    arcs: list[tuple[int, int]]
    flows: dict[tuple[int, int, int], int] | None = None
    """Integer flows ``{(k, i, j): f}`` — only filled in by :func:`route_integral`."""


def _routing_lp(demand: np.ndarray, arcs: list[tuple[int, int]]):
    """Min-congestion multicommodity flow (one commodity per source), QOBLIB's model."""
    n = len(demand)
    var = {}
    for k in range(n):
        for a, (i, j) in enumerate(arcs):
            if j != k:  # no flow back into the source
                var[k, a] = len(var)
    z = len(var)
    n_cols = z + 1
    eq_r, eq_c, eq_v, b_eq = [], [], [], []
    row = 0
    for k in range(n):
        for node in range(n):
            if node == k:
                continue
            for a, (i, j) in enumerate(arcs):
                if (k, a) not in var:
                    continue
                if j == node:
                    eq_r.append(row), eq_c.append(var[k, a]), eq_v.append(1.0)
                elif i == node:
                    eq_r.append(row), eq_c.append(var[k, a]), eq_v.append(-1.0)
            b_eq.append(float(demand[k, node] * INTSCALE))
            row += 1
    ub_r, ub_c, ub_v = [], [], []
    for a in range(len(arcs)):
        for k in range(n):
            if (k, a) in var:
                ub_r.append(a), ub_c.append(var[k, a]), ub_v.append(1.0)
        ub_r.append(a), ub_c.append(z), ub_v.append(-1.0)
    A_eq = sps.csr_array((eq_v, (eq_r, eq_c)), shape=(row, n_cols))
    A_ub = sps.csr_array((ub_v, (ub_r, ub_c)), shape=(len(arcs), n_cols))
    c = np.zeros(n_cols)
    c[z] = 1.0
    return var, c, A_ub, A_eq, np.array(b_eq)


def route_min_congestion(demand: np.ndarray, arcs: Iterable[tuple[int, int]]) -> NetworkRouting:
    """Score a topology: solve the routing LP and round up to QOBLIB's integer objective.

    The integer-flow optimum equals ``ceil`` of the LP optimum on every published
    QOBLIB instance, so this is the score your topology will get.
    """
    arcs = sorted(set(arcs))
    var, c, A_ub, A_eq, b_eq = _routing_lp(demand, arcs)
    res = linprog(
        c, A_ub=A_ub, b_ub=np.zeros(A_ub.shape[0]), A_eq=A_eq, b_eq=b_eq,
        bounds=(0, None), method="highs",
    )
    if res.status != 0:
        return NetworkRouting(math.inf, math.inf, arcs)
    return NetworkRouting(float(math.ceil(res.fun - 1e-6)), float(res.fun), arcs)


def route_integral(
    demand: np.ndarray, arcs: Iterable[tuple[int, int]], time_limit: float = 60.0
) -> NetworkRouting:
    """Integer flows achieving the topology's score (needed to write a solution file)."""
    arcs = sorted(set(arcs))
    var, c, A_ub, A_eq, b_eq = _routing_lp(demand, arcs)
    lp = route_min_congestion(demand, arcs)
    if math.isinf(lp.objective):
        return lp
    lower = np.zeros(len(c))
    lower[-1] = lp.objective  # the LP bound, rounded up, is a valid lower bound
    integrality = np.ones(len(c))
    res = milp(
        c,
        constraints=[
            _LPConstraint(A_ub, -np.inf, 0.0),
            _LPConstraint(A_eq, b_eq, b_eq),
        ],
        integrality=integrality,
        bounds=Bounds(lower, np.full(len(c), np.inf)),
        options={"time_limit": time_limit},
    )
    if res.x is None:
        raise RuntimeError(f"integral routing failed: {res.message}")
    x = np.round(res.x).astype(np.int64)
    flows = {(k, *arcs[a]): int(x[idx]) for (k, a), idx in var.items() if x[idx]}
    arc_load = {a: 0 for a in arcs}
    for (k, i, j), f in flows.items():
        arc_load[i, j] += f
    return NetworkRouting(float(max(arc_load.values())), lp.z_lp, arcs, flows)


def write_network_solution(path: str | Path, n: int, routing: NetworkRouting) -> int:
    """Write a QOBLIB/Gurobi-style ``.sol`` file (1-indexed) and return its objective."""
    if routing.flows is None:
        raise ValueError("compute integer flows first with route_integral()")
    arcs = set(routing.arcs)
    z = int(routing.objective)
    lines = ["# Solution for model obj", f"# Objective value = {z}", f"z {z}"]
    lines += [f"x#{i + 1}#{j + 1} {int((i, j) in arcs)}" for i, j in all_arcs(n)]
    lines += [
        f"f#{k + 1}#{i + 1}#{j + 1} {f}" for (k, i, j), f in sorted(routing.flows.items())
    ]
    Path(path).write_text("\n".join(lines) + "\n")
    return z


def read_network_solution(path: str | Path) -> tuple[int, list, dict]:
    """Read a network ``.sol`` file → ``(z, arcs, flows)``, 0-indexed."""
    z, arcs, flows = 0, [], {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if m := re.match(r"^z\s+(\d+)$", line):
            z = int(m.group(1))
        elif m := re.match(r"^x#(\d+)#(\d+)\s+(\d+)$", line):
            if int(m.group(3)):
                arcs.append((int(m.group(1)) - 1, int(m.group(2)) - 1))
        elif m := re.match(r"^f#(\d+)#(\d+)#(\d+)\s+(\d+)$", line):
            k, i, j, f = (int(g) for g in m.groups())
            if f:
                flows[k - 1, i - 1, j - 1] = f
    return z, arcs, flows


def check_network_solution(path: str | Path, n: int, demand: np.ndarray) -> tuple[bool, int, str]:
    """Port of QOBLIB's ``check_network``: ``(valid, max_flow, message)``."""
    z, arcs, flows = read_network_solution(path)
    arcset = set(arcs)
    out_deg = [sum((i, j) in arcset for j in range(n) if j != i) for i in range(n)]
    in_deg = [sum((i, j) in arcset for i in range(n) if i != j) for j in range(n)]
    if any(d != 2 for d in out_deg + in_deg):
        return False, 0, "degree constraint violated"
    for k in range(n):
        for i in range(n):
            if i == k:
                continue
            inflow = sum(flows.get((k, j, i), 0) for j in range(n) if j != i)
            outflow = sum(flows.get((k, i, j), 0) for j in range(n) if j not in (i, k))
            if inflow - outflow != demand[k, i] * INTSCALE:
                return False, 0, f"flow conservation violated (commodity {k + 1}, node {i + 1})"
    for (k, i, j), f in flows.items():
        if f and k != j and (i, j) not in arcset:
            return False, 0, f"flow on missing arc ({i + 1}, {j + 1})"
    load = {}
    for (k, i, j), f in flows.items():
        if k != j:
            load[i, j] = load.get((i, j), 0) + f
    max_flow = max(load.values(), default=0)
    note = "" if max_flow == z else f" (file claims z={z})"
    return True, max_flow, "valid" + note


def build_network_qubo(demand: np.ndarray) -> tuple[dimod.BinaryQuadraticModel, dimod.BinaryQuadraticModel, list]:
    """A *starter* QUBO for the topology: ``(objective, penalty, arcs)``.

    One binary variable per possible arc (``arcs[v]`` is variable ``v``).

    * ``objective`` — a surrogate, not the real score: reward arcs that carry
      their own demand directly, ``-Σ t_ij x_ij`` (scaled to max |coeff| = 1).
      The real score needs the routing LP, which is not a QUBO.
    * ``penalty`` — ``Σ_i (outdeg_i - 2)² + Σ_j (indeg_j - 2)²``, zero exactly on
      valid topologies.

    Improving the surrogate is a big part of the challenge.
    """
    n = len(demand)
    arcs = all_arcs(n)
    scale = float(demand.max()) or 1.0
    objective = dimod.BinaryQuadraticModel(
        {v: -demand[i, j] / scale for v, (i, j) in enumerate(arcs)}, {}, 0.0, dimod.BINARY
    )
    penalty = dimod.BinaryQuadraticModel(
        {v: 0.0 for v in range(len(arcs))}, {}, 0.0, dimod.BINARY
    )
    for node in range(n):
        out_terms = [(v, 1) for v, (i, _) in enumerate(arcs) if i == node]
        in_terms = [(v, 1) for v, (_, j) in enumerate(arcs) if j == node]
        penalty.add_linear_equality_constraint(out_terms, 1.0, -2)
        penalty.add_linear_equality_constraint(in_terms, 1.0, -2)
    return objective, penalty, arcs


def decode_topology(sample, arcs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Bit assignment (dict, array or bitstring in variable order) → chosen arcs."""
    bits = _as_bit_array(sample, len(arcs))
    return [arcs[v] for v in np.flatnonzero(bits)]
