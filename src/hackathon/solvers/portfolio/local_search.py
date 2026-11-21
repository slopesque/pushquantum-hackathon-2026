"""Recherche locale à voisinages multiples (piste P4).

On part d'une solution faisable et on applique des mouvements qui font baisser l'objectif, jusqu'à un
optimum local. Les voisinages (voir ``formalisations/portfolio/pistes.typ``, section P4) :

* ``block`` : ``v[t, i] += s`` pour tous les jours ``t`` d'un intervalle ``[t1, t2]``. Le mouvement simple
  du kit est le cas ``t1 = t2``. Sur un bloc, seuls les frais d'entrée (jour ``t1``) et de sortie (jour
  ``t2 + 1``) changent : on n'y paie l'aller-retour qu'une fois.
* ``pair`` : le même bloc appliqué à deux actions à la fois, ``(i, s_i)`` et ``(j, s_j)``, avec ``j`` pris
  dans les partenaires de ``i`` qui le couvrent le mieux (corrélés si ``s_i s_j = -1``, anti-corrélés si
  ``s_i s_j = +1``). C'est le mouvement des grands λ.
* ``swap`` : sur un jour, retirer une unité d'une case détenue et ajouter une unité à n'importe quelle autre
  action (tous signes). Il est le seul mouvement possible quand le budget est saturé.

Mise en œuvre : à chaque passe, *tous* les mouvements d'un voisinage sont évalués d'un coup avec numpy
(sommes cumulées sur les jours pour les blocs). On trie les mouvements améliorants, puis on les applique
dans l'ordre en revérifiant chacun exactement avec :meth:`PortfolioState.delta`, car ceux déjà appliqués
ont pu changer la donne. Le résultat est toujours exact et faisable.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import numpy as np

from hackathon.solvers.portfolio.evaluator import Change, PortfolioState
from hackathon.solvers.portfolio.problem import PortfolioProblem

NEIGHBORHOODS = ("block", "pair", "swap")
SIGNS = (1, -1)


# ════════════════════════════════════════════════════════════════════════
# Partenaires de couverture
# ════════════════════════════════════════════════════════════════════════


def hedge_partners(problem: PortfolioProblem, k: int = 15) -> tuple[np.ndarray, np.ndarray]:
    """Listes de partenaires ``(C, A)``, chacune de forme ``(n, k)``.

    Avec ``R`` la matrice de risque symétrisée et moyennée sur les jours, le risque propre de la paire
    ``(i, s_i), (j, s_j)`` vaut ``h = R_ii + R_jj + 2 s_i s_j R_ij``.

    * ``C[i]`` : les ``k`` actions ``j`` qui minimisent ``h`` pour ``s_i s_j = -1`` (corrélées) ;
    * ``A[i]`` : les ``k`` actions ``j`` qui minimisent ``h`` pour ``s_i s_j = +1`` (anti-corrélées).
    """
    n = problem.n
    k = min(k, n - 1)
    R = problem.R.astype(float)
    R = ((R + R.transpose(0, 2, 1)) / 2).mean(axis=0)
    diag = np.diag(R)
    out = []
    for sign in (-1, 1):
        h = diag[:, None] + diag[None, :] + 2 * sign * R
        np.fill_diagonal(h, np.inf)
        part = np.argpartition(h, k - 1, axis=1)[:, :k]
        order = np.take_along_axis(h, part, axis=1).argsort(axis=1)
        out.append(np.take_along_axis(part, order, axis=1))
    return out[0], out[1]


# ════════════════════════════════════════════════════════════════════════
# Termes élémentaires d'un mouvement
# ════════════════════════════════════════════════════════════════════════


@dataclass
class _Terms:
    """Contributions d'un changement ``v[t, i] += s`` décomposées pour être recombinées.

    Pour chaque signe ``s`` (indice 0 : +1, 1 : -1), tableaux ``(T, n)`` :

    * ``base`` : risque propre (``s·Gv + R_ii``), rendement, coût du court, frais d'achat (jour 0) et de
      liquidation (jour T-1) ;
    * ``fee_in[t]`` : variation des frais de la transition ``t-1 → t`` si ``t`` est le premier jour du bloc ;
    * ``fee_out[t]`` : variation des frais de la transition ``t → t+1`` si ``t`` est le dernier jour ;
    * ``dabs`` : variation de ``|v|`` (budget) ; ``cell_ok`` : ``|v + s| <= ub``.

    Et, pour une variation ``dn ∈ {-2..2}`` de la position nette d'un jour, tableaux ``(T,)`` :
    ``interest[dn]`` (variation des intérêts) et ``net_ok[dn]``.
    """

    base: list[np.ndarray]
    fee_in: list[np.ndarray]
    fee_out: list[np.ndarray]
    dabs: list[np.ndarray]
    cell_ok: list[np.ndarray]
    interest: dict[int, np.ndarray] = field(default_factory=dict)
    net_ok: dict[int, np.ndarray] = field(default_factory=dict)


def _terms(state: PortfolioState) -> _Terms:
    p, v, T = state.problem, state.v, state.problem.T
    base, fee_in, fee_out, dabs, cell_ok = [], [], [], [], []
    diff = np.diff(v, axis=0)  # diff[t-1] = v[t] - v[t-1]
    for s in SIGNS:
        new = v + s
        b = s * state.Gv + p.R_diag - s * p.ret
        b += p.sc * (np.maximum(-new, 0) - np.maximum(-v, 0))
        b[0] += p.tc[0] * (np.abs(new[0]) - np.abs(v[0]))
        b[T - 1] += p.tc[T - 1] * (np.abs(new[T - 1]) - np.abs(v[T - 1]))
        fi = np.zeros_like(v)
        fo = np.zeros_like(v)
        if T > 2:  # transitions t-1 → t facturées pour 1 <= t <= T-2
            d = diff[: T - 2]
            fi[1 : T - 1] = p.tc[1 : T - 1] * (np.abs(d + s) - np.abs(d))
            fo[: T - 2] = p.tc[1 : T - 1] * (np.abs(d - s) - np.abs(d))
        base.append(b)
        fee_in.append(fi)
        fee_out.append(fo)
        dabs.append(np.abs(new) - np.abs(v))
        cell_ok.append(np.abs(new) <= p.ub)
    terms = _Terms(base, fee_in, fee_out, dabs, cell_ok)
    for dn in range(-2, 3):
        net = state.net + dn
        terms.interest[dn] = p.interest_of_slack(p.capital - state.net) - p.interest_of_slack(
            p.capital - net
        )
        terms.net_ok[dn] = (net >= p.net_min) & (net <= p.net_max)
    return terms


def _block_sums(node: np.ndarray, bad: np.ndarray, max_len: int) -> tuple[np.ndarray, np.ndarray]:
    """Pour chaque intervalle ``[t1, t2]`` : somme de ``node`` et faisabilité (aucun jour ``bad``).

    ``node`` et ``bad`` ont la forme ``(T, …)`` ; le résultat a la forme ``(T, T, …)`` indexée par
    ``(t1, t2)``, avec ``+inf`` / ``False`` hors du triangle ``t1 <= t2 < t1 + max_len``.
    """
    T = node.shape[0]
    zeros = np.zeros((1, *node.shape[1:]), dtype=node.dtype)
    c = np.concatenate([zeros, np.cumsum(node, axis=0)])
    cb = np.concatenate([zeros.astype(np.int64), np.cumsum(bad, axis=0, dtype=np.int64)])
    sums = c[None, 1:] - c[:-1, None]
    nbad = cb[None, 1:] - cb[:-1, None]
    t1, t2 = np.meshgrid(np.arange(T), np.arange(T), indexing="ij")
    valid = (t2 >= t1) & (t2 - t1 < max_len)
    valid = valid.reshape(T, T, *([1] * (node.ndim - 1)))
    return sums, valid & (nbad == 0)


# ════════════════════════════════════════════════════════════════════════
# Voisinages : chaque fonction renvoie (deltas, faisables, décodeur)
# ════════════════════════════════════════════════════════════════════════


@dataclass
class _Candidates:
    delta: np.ndarray
    """Variations de l'objectif, aplaties ; ``inf`` pour les mouvements infaisables."""
    decode: Callable[[int], list[Change]]
    """``decode(index aplati) → liste de changements (t, i, d)``."""


def _block_moves(state: PortfolioState, terms: _Terms, max_len: int) -> _Candidates:
    p, T = state.problem, state.problem.T
    out = np.full((2, T, T, p.n), np.inf)
    for k, s in enumerate(SIGNS):
        node = terms.base[k] + terms.interest[s][:, None]
        bad = ~(
            terms.cell_ok[k]
            & (state.total[:, None] + terms.dabs[k] <= p.budget)
            & terms.net_ok[s][:, None]
        )
        sums, ok = _block_sums(node, bad, max_len)
        sums = sums + terms.fee_in[k][:, None, :] + terms.fee_out[k][None, :, :]
        out[k] = np.where(ok, sums, np.inf)

    def decode(idx: int) -> list[Change]:
        k, t1, t2, i = np.unravel_index(idx, out.shape)
        return [(t, int(i), SIGNS[k]) for t in range(int(t1), int(t2) + 1)]

    return _Candidates(out.ravel(), decode)


def _pair_moves(
    state: PortfolioState, terms: _Terms, partners: tuple[np.ndarray, np.ndarray], max_len: int
) -> _Candidates:
    """Paires ``(i, s_i), (j, s_j)`` sur un bloc de jours, ``j`` dans les partenaires de ``i``."""
    p, T, n = state.problem, state.problem.T, state.problem.n
    corr, anti = partners
    kk = corr.shape[1]
    rows = np.arange(n)[:, None]
    out = np.full((4, T, T, n, kk), np.inf)
    combos = [(si, sj) for si in SIGNS for sj in SIGNS]
    for c, (si, sj) in enumerate(combos):
        J = corr if si * sj == -1 else anti  # (n, kk)
        ki, kj = SIGNS.index(si), SIGNS.index(sj)
        g = state.problem.G[:, rows, J]  # (T, n, kk) : G[t, i, J[i, m]]
        node = (
            terms.base[ki][:, :, None]
            + terms.base[kj][:, J]
            + si * sj * g
            + terms.interest[si + sj][:, None, None]
        )
        ok_day = (
            terms.cell_ok[ki][:, :, None]
            & terms.cell_ok[kj][:, J]
            & (
                state.total[:, None, None] + terms.dabs[ki][:, :, None] + terms.dabs[kj][:, J]
                <= p.budget
            )
            & terms.net_ok[si + sj][:, None, None]
        )
        sums, ok = _block_sums(node, ~ok_day, max_len)
        fin = terms.fee_in[ki][:, :, None] + terms.fee_in[kj][:, J]  # (T, n, kk)
        fout = terms.fee_out[ki][:, :, None] + terms.fee_out[kj][:, J]
        sums = sums + fin[:, None] + fout[None, :]
        out[c] = np.where(ok, sums, np.inf)

    def decode(idx: int) -> list[Change]:
        c, t1, t2, i, m = (int(x) for x in np.unravel_index(idx, out.shape))
        si, sj = combos[c]
        j = int((corr if si * sj == -1 else anti)[i, m])
        days = range(t1, t2 + 1)
        return [(t, i, si) for t in days] + [(t, j, sj) for t in days]

    return _Candidates(out.ravel(), decode)


def _swap_moves(state: PortfolioState, terms: _Terms) -> _Candidates:
    """Sur un jour : retirer une unité d'une case détenue ``i``, ajouter ``±1`` à une autre action ``j``."""
    p, n = state.problem, state.problem.n
    v = state.v
    single = [terms.base[k] + terms.fee_in[k] + terms.fee_out[k] for k in range(2)]  # (T, n)
    days, held = np.nonzero(v)
    if len(days) == 0:
        return _Candidates(np.empty(0), lambda idx: [])
    si = -np.sign(v[days, held])  # réduire |v_i|
    ki = np.where(si == 1, 0, 1)
    out = np.full((len(days), n, 2), np.inf)
    base_i = single[0][days, held] * (ki == 0) + single[1][days, held] * (ki == 1)
    dabs_i = np.where(ki == 0, terms.dabs[0][days, held], terms.dabs[1][days, held])
    g = p.G[days, held, :]  # (m, n) : G[t, i, j]
    for kj, sj in enumerate(SIGNS):
        dn = si + sj  # -2, 0 ou 2
        interest = np.stack([terms.interest[d] for d in (-2, -1, 0, 1, 2)])[dn + 2, days]  # (m,)
        net_ok = np.stack([terms.net_ok[d] for d in (-2, -1, 0, 1, 2)])[dn + 2, days]
        delta = base_i[:, None] + single[kj][days] + (si * sj)[:, None] * g + interest[:, None]
        ok = (
            terms.cell_ok[kj][days]
            & (state.total[days, None] + dabs_i[:, None] + terms.dabs[kj][days] <= p.budget)
            & net_ok[:, None]
        )
        ok[np.arange(len(days)), held] = False  # j != i
        out[:, :, kj] = np.where(ok, delta, np.inf)

    def decode(idx: int) -> list[Change]:
        m, j, kj = (int(x) for x in np.unravel_index(idx, out.shape))
        return [(int(days[m]), int(held[m]), int(si[m])), (int(days[m]), j, SIGNS[kj])]

    return _Candidates(out.ravel(), decode)


# ════════════════════════════════════════════════════════════════════════
# La boucle
# ════════════════════════════════════════════════════════════════════════


@dataclass
class SearchStats:
    passes: int = 0
    applied: dict[str, int] = field(default_factory=dict)
    stopped_by_time: bool = False


def local_search(
    state: PortfolioState,
    neighborhoods: Iterable[str] = NEIGHBORHOODS,
    time_limit: float = 60.0,
    max_block: int | None = None,
    n_partners: int = 15,
    batch: int = 1,
) -> SearchStats:
    """Descend jusqu'à un optimum local pour les voisinages donnés (modifie ``state`` en place).

    ``max_block`` limite la longueur des blocs de jours (``1`` = mouvements simples seulement, comme le kit).
    ``batch`` : nombre maximal de mouvements appliqués par passe avant de tout réévaluer. ``1`` (défaut)
    est la descente « meilleur mouvement d'abord », qui donne les meilleurs optima locaux ; des lots plus
    grands vont plus vite mais s'arrêtent plus haut (−56 058 au lieu de −69 372 sur a010_t10_orig, λ = 1e-4,
    en mouvements simples).
    """
    neighborhoods = list(neighborhoods)
    unknown = set(neighborhoods) - set(NEIGHBORHOODS)
    if unknown:
        raise ValueError(f"voisinages inconnus : {unknown}")
    if not state.feasible:
        raise ValueError("la recherche locale doit partir d'une solution faisable")
    p = state.problem
    max_len = p.T if max_block is None else max_block
    partners = hedge_partners(p, n_partners) if "pair" in neighborhoods and p.n > 1 else None
    stats = SearchStats(applied={nb: 0 for nb in neighborhoods})
    deadline = time.perf_counter() + time_limit

    while True:
        if time.perf_counter() > deadline:
            stats.stopped_by_time = True
            break
        stats.passes += 1
        terms = _terms(state)
        pools: list[tuple[str, _Candidates]] = []
        if "block" in neighborhoods:
            pools.append(("block", _block_moves(state, terms, max_len)))
        if "pair" in neighborhoods and partners is not None:
            pools.append(("pair", _pair_moves(state, terms, partners, max_len)))
        if "swap" in neighborhoods:
            pools.append(("swap", _swap_moves(state, terms)))

        # Les meilleurs mouvements améliorants de chaque voisinage, fusionnés et triés.
        ranked: list[tuple[float, str, list[Change]]] = []
        for name, cand in pools:
            improving = np.flatnonzero(cand.delta < 0)
            if len(improving) > batch:
                improving = improving[np.argpartition(cand.delta[improving], batch)[:batch]]
            ranked += [(float(cand.delta[i]), name, cand.decode(int(i))) for i in improving]
        if not ranked:
            break
        ranked.sort(key=lambda x: x[0])

        applied = 0
        for _, name, changes in ranked:
            delta, feasible = state.delta(changes)
            if feasible and delta < 0:
                state.apply(changes)
                stats.applied[name] += 1
                applied += 1
                if applied >= batch:
                    break
        if applied == 0:
            break
    return stats
