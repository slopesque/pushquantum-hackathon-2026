"""L'évaluateur incrémental doit donner exactement l'objectif de notre modèle."""

import numpy as np
import pytest

from hackathon.solvers.portfolio import PortfolioProblem, PortfolioState, load_instance

CASES = [
    ("po_a003_t02_orig", 3, "1e-5"),
    ("po_a010_t10_orig", 4, "1e-4"),
    ("po_a010_t15_s01", 4, "5e-4"),
    ("po_a050_t10_orig", 20, "1e-3"),
]


@pytest.fixture(scope="module", params=CASES, ids=lambda c: f"{c[0]}-l{c[2]}")
def problem(request):
    name, budget, lam = request.param
    return PortfolioProblem(load_instance(name), budget, lam)


def random_v(problem: PortfolioProblem, rng: np.random.Generator, density: float) -> np.ndarray:
    v = rng.integers(-problem.ub, problem.ub + 1, size=(problem.T, problem.n))
    return np.where(rng.random(v.shape) < density, v, 0)


def random_feasible_v(problem: PortfolioProblem, rng: np.random.Generator, density: float):
    """Solution aléatoire rendue faisable en retirant des unités au hasard."""
    v = random_v(problem, rng, density)
    for t in range(problem.T):
        while not (
            np.abs(v[t]).sum() <= problem.budget
            and problem.net_min <= v[t].sum() <= problem.net_max
        ):
            nz = np.flatnonzero(v[t])
            if v[t].sum() > problem.net_max:
                nz = np.flatnonzero(v[t] > 0)
            elif v[t].sum() < problem.net_min:
                nz = np.flatnonzero(v[t] < 0)
            i = rng.choice(nz)
            v[t, i] -= np.sign(v[t, i])
    assert problem.is_feasible(v)
    return v


def random_changes(problem: PortfolioProblem, rng: np.random.Generator):
    """Mouvement aléatoire : simple, paire, bloc de jours, ou changements arbitraires."""
    T, n = problem.T, problem.n
    kind = rng.integers(4)
    t, i = int(rng.integers(T)), int(rng.integers(n))
    s = int(rng.choice([-1, 1]))
    if kind == 0:
        return [(t, i, s)]
    if kind == 1:
        return [(t, i, s), (t, int(rng.integers(n)), int(rng.choice([-1, 1])))]
    if kind == 2:
        t1 = int(rng.integers(T))
        return [(u, i, s) for u in range(t1, int(rng.integers(t1, T)) + 1)]
    return [
        (int(rng.integers(T)), int(rng.integers(n)), int(rng.integers(-2, 3)))
        for _ in range(int(rng.integers(1, 6)))
    ]


def test_delta_matches_full_objective(problem):
    rng = np.random.default_rng(1)
    for start in range(30):
        # Départ quelconque : la variation de l'objectif est exacte.
        # Départ faisable : la faisabilité après le mouvement l'est aussi.
        from_feasible = start % 2 == 0
        v0 = random_feasible_v(problem, rng, 0.1) if from_feasible else random_v(problem, rng, 0.1)
        state = PortfolioState(problem, v0)
        for _ in range(20):
            changes = random_changes(problem, rng)
            delta, feasible = state.delta(changes)
            v = state.v.copy()
            for t, i, d in changes:
                v[t, i] += d
            assert delta == problem.objective(v) - state.objective
            if from_feasible:
                assert feasible == problem.is_feasible(v)


def test_apply_keeps_state_consistent(problem):
    rng = np.random.default_rng(2)
    state = PortfolioState(problem)
    for _ in range(300):
        state.apply(random_changes(problem, rng))
    fresh = PortfolioState(problem, state.v)
    assert state.objective == fresh.objective == problem.objective(state.v)
    np.testing.assert_array_equal(state.Gv, fresh.Gv)
    np.testing.assert_array_equal(state.net, fresh.net)
    np.testing.assert_array_equal(state.total, fresh.total)


def test_vectorized_single_moves_match_delta(problem):
    rng = np.random.default_rng(3)
    for density in (0.0, 0.1, 0.3):
        state = PortfolioState(problem, random_feasible_v(problem, rng, density))
        deltas, ok = state.single_move_deltas()
        for k, s in enumerate((1, -1)):
            for t in range(problem.T):
                for i in range(problem.n):
                    delta, feasible = state.delta([(t, i, s)])
                    assert deltas[k, t, i] == delta, (s, t, i)
                    assert ok[k, t, i] == feasible, (s, t, i)
