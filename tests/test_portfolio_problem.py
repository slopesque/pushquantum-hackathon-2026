"""Notre modèle du problème de portefeuille, validé contre l'arbitre officiel.

C'est le seul endroit où l'arbitre sert : vérifier que notre formulation (données, coefficients,
objectif, contraintes, fichiers .sol) est bien celle du problème officiel.
"""

import numpy as np
import pytest

from hackathon.referee import qt
from hackathon.solvers.portfolio import PortfolioProblem, load_instance

CASES = [
    ("po_a003_t02_orig", 3, "1e-5"),  # T = 2 : cas limite des frais
    ("po_a010_t10_orig", 4, "1e-4"),
    ("po_a010_t10_orig", 4, "1e-2"),
    ("po_a010_t15_s01", 4, "5e-4"),
    ("po_a050_t10_orig", 20, "1e-3"),
    ("po_a050_t10_orig", 20, "0"),
    ("po_a200_t10_orig", 50, "1e-4"),
    ("po_a200_t10_orig", 50, "1e-2"),  # 2 arrondis recalculés exactement (proches d'un demi-entier)
]


@pytest.fixture(scope="module", params=CASES, ids=lambda c: f"{c[0]}-l{c[2]}")
def pair(request):
    name, budget, lam = request.param
    ours = PortfolioProblem(load_instance(name), budget, lam)
    official = qt.PortfolioModel(qt.load_portfolio_instance(name), budget=budget, lam=lam)
    return ours, official


def test_coefficients_match(pair):
    ours, official = pair
    assert ours.symbols == official.symbols
    np.testing.assert_array_equal(ours.R, official.risk)
    np.testing.assert_array_equal(ours.ret[: ours.T - 1], official.ret)
    np.testing.assert_array_equal(ours.tc, official.tc)
    np.testing.assert_array_equal(ours.sc, official.sc)
    assert ours.interest == list(official.interest)


def test_objective_and_constraints_match(pair):
    ours, official = pair
    rng = np.random.default_rng(0)
    for density in (0.0, 0.05, 0.2, 1.0):  # 1.0 donne surtout des solutions infaisables
        for _ in range(20):
            v = rng.integers(-ours.ub, ours.ub + 1, size=(ours.T, ours.n))
            v = np.where(rng.random(v.shape) < density, v, 0)
            score = official.score_arrays(np.maximum(v, 0), np.maximum(-v, 0))
            assert ours.breakdown(v) == score.breakdown
            assert ours.objective(v) == score.objective
            assert ours.is_feasible(v) == score.feasible


@pytest.mark.parametrize(
    ("name", "budget", "lam", "best"),
    [
        ("po_a010_t10_orig", 4, "1e-4", -69482),
        ("po_a010_t10_orig", 4, "1e-3", -8397),
        ("po_a050_t10_orig", 20, "1e-2", -37107),
    ],
)
def test_reference_solutions(tmp_path, name, budget, lam, best):
    problem = PortfolioProblem(load_instance(name), budget, lam)
    v = problem.read_solution(qt.fetch_portfolio_reference(name, budget, lam))
    assert problem.objective(v) == best
    assert problem.is_feasible(v)

    # Aller-retour par notre écriture de .sol, relue et notée par l'arbitre.
    path = tmp_path / problem.solution_filename
    path.write_text(problem.solution_text(v, comment="test"))
    header, positions = qt.read_portfolio_solution(path)
    assert header["instance"] == name and int(header["budget"]) == budget
    model = qt.PortfolioModel(qt.load_portfolio_instance(name), budget=budget, lam=header["lambda"])
    assert model.score(positions).objective == best


def test_solution_filename():
    problem = PortfolioProblem(load_instance("po_a010_t10_orig"), 4, "1e-4")
    assert problem.solution_filename == "po_a010_t10_orig_b004_l1e-4.sol"
    assert PortfolioProblem(problem.instance, 4, "0").lam_tag == "0"
    assert PortfolioProblem(problem.instance, 4, "5e-5").lam_tag == "5e-5"
