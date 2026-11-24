"""Recherche locale : chaque mouvement évalué en vectorisé doit coïncider avec l'évaluation exacte."""

import numpy as np
import pytest

from hackathon.solvers.portfolio import PortfolioProblem, PortfolioState, load_instance
from hackathon.solvers.portfolio.local_search import (
    _block_moves,
    _pair_moves,
    _swap_moves,
    _terms,
    hedge_partners,
    local_search,
)

CASES = [
    ("po_a003_t02_orig", 3, "1e-5"),
    ("po_a010_t10_orig", 4, "1e-3"),
    ("po_a050_t10_orig", 20, "1e-2"),
]


@pytest.fixture(scope="module", params=CASES, ids=lambda c: f"{c[0]}-l{c[2]}")
def problem(request):
    name, budget, lam = request.param
    return PortfolioProblem(load_instance(name), budget, lam)


def feasible_states(problem, n_states=4):
    """Quelques solutions faisables variées : vide, puis obtenues par descente partielle + bruit."""
    rng = np.random.default_rng(0)
    states = [PortfolioState(problem)]
    for _ in range(n_states - 1):
        st = PortfolioState(problem)
        for _ in range(60):
            t, i, s = (
                int(rng.integers(problem.T)),
                int(rng.integers(problem.n)),
                int(rng.choice([-1, 1])),
            )
            _, ok = st.delta([(t, i, s)])
            if ok:
                st.apply([(t, i, s)])
        assert st.feasible
        states.append(st)
    return states


def check(state, cand, rng, n_samples=400):
    finite = np.flatnonzero(np.isfinite(cand.delta))
    infinite = np.flatnonzero(~np.isfinite(cand.delta))
    for idx in rng.choice(finite, size=min(n_samples, len(finite)), replace=False):
        delta, ok = state.delta(cand.decode(int(idx)))
        assert ok and delta == cand.delta[idx]
    # Un mouvement marqué infaisable doit l'être vraiment (sauf hors du triangle t1 <= t2 des blocs).
    for idx in rng.choice(infinite, size=min(n_samples, len(infinite)), replace=False):
        changes = cand.decode(int(idx))
        cells = [(t, i) for t, i, _ in changes]
        if changes and len(set(cells)) == len(cells):  # j = i est exclu volontairement
            _, ok = state.delta(changes)
            assert not ok


def test_block_moves_exact(problem):
    rng = np.random.default_rng(1)
    for state in feasible_states(problem):
        cand = _block_moves(state, _terms(state), max_len=problem.T)
        finite = np.flatnonzero(np.isfinite(cand.delta))
        for idx in rng.choice(finite, size=min(400, len(finite)), replace=False):
            delta, ok = state.delta(cand.decode(int(idx)))
            assert ok and delta == cand.delta[idx]


def test_pair_moves_exact(problem):
    rng = np.random.default_rng(2)
    partners = hedge_partners(problem, 5)
    for state in feasible_states(problem):
        cand = _pair_moves(state, _terms(state), partners, max_len=problem.T)
        finite = np.flatnonzero(np.isfinite(cand.delta))
        for idx in rng.choice(finite, size=min(400, len(finite)), replace=False):
            delta, ok = state.delta(cand.decode(int(idx)))
            assert ok and delta == cand.delta[idx]


def test_swap_moves_exact(problem):
    rng = np.random.default_rng(3)
    for state in feasible_states(problem)[1:]:
        cand = _swap_moves(state, _terms(state))
        check(state, cand, rng)


def test_local_search_improves_and_stays_feasible(problem):
    results = {}
    for name, kwargs in {
        "single": {"neighborhoods": ["block"], "max_block": 1},
        "block": {"neighborhoods": ["block"]},
        "full": {"neighborhoods": ["block", "pair", "swap"]},
    }.items():
        state = PortfolioState(problem)
        local_search(state, time_limit=30, **kwargs)
        assert state.feasible
        assert state.objective == problem.objective(state.v)
        results[name] = state.objective
    assert results["single"] <= problem.objective(np.zeros((problem.T, problem.n), dtype=int))
    assert results["full"] <= results["single"]


def test_partners_exclude_self(problem):
    corr, anti = hedge_partners(problem, 5)
    for lst in (corr, anti):
        assert not (lst == np.arange(problem.n)[:, None]).any()
