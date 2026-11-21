"""LNS : le QUBO d'une fenêtre, les sous-solveurs, la réparation et la boucle."""

import numpy as np
import pytest

from hackathon.solvers.portfolio import PortfolioProblem, PortfolioState, load_instance
from hackathon.solvers.portfolio.lns import (
    Window,
    WindowSampler,
    build_window_qubo,
    choose_signs,
    divi_solver,
    enum_solver,
    lns,
    repair,
    sa_solver,
)
from hackathon.solvers.portfolio.local_search import local_search

CASES = [
    ("po_a010_t10_orig", 4, "1e-4"),
    ("po_a010_t10_orig", 4, "1e-3"),
    ("po_a050_t10_orig", 20, "1e-3"),
]


@pytest.fixture(scope="module", params=CASES, ids=lambda c: f"{c[0]}-l{c[2]}")
def problem(request):
    name, budget, lam = request.param
    return PortfolioProblem(load_instance(name), budget, lam)


def small_state(problem, rng):
    """Solution faisable avec v ∈ {-1, 0, 1} : les approximations du QUBO sont alors exactes pour m ∈ {0, 1}."""
    state = PortfolioState(problem)
    for _ in range(4 * problem.n):
        t, i, s = (
            int(rng.integers(problem.T)),
            int(rng.integers(problem.n)),
            int(rng.choice([-1, 1])),
        )
        if abs(state.v[t, i] + s) <= 1:
            _, ok = state.delta([(t, i, s)])
            if ok:
                state.apply([(t, i, s)])
    assert state.feasible
    return state


def test_window_qubo_is_exact_when_approximations_do_not_bind(problem):
    rng = np.random.default_rng(0)
    for _ in range(10):
        state = small_state(problem, rng)
        sampler = WindowSampler(state, n_assets=3, n_days=4)
        cells = sampler.sample(state, rng)
        window = Window(cells, choose_signs(state, cells, rng, flip=0.3))
        q = build_window_qubo(state, window)
        for _ in range(30):
            m = rng.integers(0, 2, size=window.size)  # quantités 0 ou 1 : écarts <= 1
            delta, feasible = state.delta(q.changes(state, m))
            # Exact sur les solutions faisables (hors bornes, les intérêts ne sont plus linéaires ;
            # ces affectations sont réparées avant toute décision).
            if feasible:
                assert q.objective_energy(m) == pytest.approx(delta, abs=1e-6)


def test_bits_and_bqm_energies_agree(problem):
    rng = np.random.default_rng(1)
    state = PortfolioState(problem)
    local_search(state, batch=20, time_limit=10)
    cells = WindowSampler(state, 3, 3).sample(state, rng)
    q = build_window_qubo(state, Window(cells, choose_signs(state, cells, rng, 0.2)))
    bqm = q.to_bqm()
    assert list(bqm.variables) == list(range(q.window.n_bits))
    linear, quad = q.bits_matrices()
    for _ in range(50):
        bits = rng.integers(0, 2, size=q.window.n_bits)
        e = q.energy(q.bits_to_m(bits))
        assert q.offset + bits @ linear + bits @ quad @ bits == pytest.approx(e)
        assert bqm.energy(dict(enumerate(bits))) == pytest.approx(e)


def test_enum_finds_the_qubo_minimum():
    problem = PortfolioProblem(load_instance("po_a010_t10_orig"), 4, "1e-3")
    rng = np.random.default_rng(2)
    state = PortfolioState(problem)
    local_search(state, batch=20, time_limit=10)
    cells = WindowSampler(state, 2, 3).sample(state, rng)
    q = build_window_qubo(state, Window(cells, choose_signs(state, cells, rng, 0.2)))
    best = enum_solver(n_candidates=5)(q, rng)[0]
    all_m = np.array(np.meshgrid(*[range(4)] * q.window.size)).reshape(q.window.size, -1).T
    assert q.energy(q.bits_to_m(best)) == pytest.approx(min(q.energy(m) for m in all_m))


def test_repair_makes_candidates_feasible(problem):
    rng = np.random.default_rng(3)
    state = PortfolioState(problem)
    local_search(state, batch=20, time_limit=10)
    for _ in range(20):
        cells = WindowSampler(state, 3, 3).sample(state, rng)
        q = build_window_qubo(state, Window(cells, choose_signs(state, cells, rng, 0.2)))
        m, delta, ok = repair(state, q, np.full(q.window.size, 3))  # tout au maximum
        if ok:
            d, f = state.delta(q.changes(state, m))
            assert f and d == delta


@pytest.mark.parametrize("solver", ["enum", "sa"])
def test_lns_never_worsens_and_stays_exact(problem, solver):
    rng = np.random.default_rng(4)
    state = PortfolioState(problem)
    local_search(state, batch=20, time_limit=10)
    before = state.objective
    sub = enum_solver() if solver == "enum" else sa_solver(num_reads=16, num_sweeps=200)
    stats = lns(state, sub, rng, time_limit=30, n_assets=2, n_days=3, max_iterations=15)
    assert state.feasible
    assert state.objective == problem.objective(state.v) <= before
    assert stats.iterations == 15
    assert [o for _, o in stats.trace] == sorted((o for _, o in stats.trace), reverse=True)


@pytest.mark.parametrize("routine", ["qaoa", "pce"])
def test_divi_solvers_on_a_small_window(routine):
    problem = PortfolioProblem(load_instance("po_a010_t10_orig"), 4, "1e-4")
    rng = np.random.default_rng(5)
    state = PortfolioState(problem)
    local_search(state, batch=20, time_limit=10)
    cells = WindowSampler(state, 2, 2).sample(state, rng)  # 4 cases = 8 bits
    q = build_window_qubo(state, Window(cells, choose_signs(state, cells, rng, 0.0)))
    solver = divi_solver(routine, n_layers=1, population=6, iterations=2, shots=500)
    cands = solver(q, rng)
    assert cands and all(len(c) == q.window.n_bits for c in cands)
    assert solver.info.qubits >= 1 and solver.info.circuits > 0
