"""Smoke tests : l'arbitre s'importe et reproduit les références publiées (télécharge depuis QOBLIB)."""

from hackathon.referee import qt


def test_portfolio_reference_solution_scores_best_known():
    path = qt.fetch_portfolio_reference("po_a010_t10_orig", 4, "1e-4")
    header, positions = qt.read_portfolio_solution(path)
    model = qt.PortfolioModel(
        qt.load_portfolio_instance(header["instance"]),
        budget=int(header["budget"]),
        lam=header["lambda"],
    )
    result = model.score(positions)
    assert result.feasible
    assert round(float(result.objective)) == -69482


def test_network_demand_loads():
    demand = qt.load_network_demand(12)
    assert demand.shape == (12, 12)
