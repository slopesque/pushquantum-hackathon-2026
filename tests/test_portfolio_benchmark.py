"""Banc d'essai : grille des cas, meilleurs connus, exécution, CSV et graphes."""

from dataclasses import replace

from hackathon.solvers.portfolio.benchmark import (
    SETS,
    Case,
    best_known,
    best_known_table,
    read_csv,
    run_benchmark,
    summarize,
    write_csv,
)
from hackathon.solvers.portfolio.plots import plot_all


def test_grid_and_sets():
    assert len(SETS["full"]) == 256
    assert len(SETS["known"]) == 128 and len(SETS["large"]) == 128
    assert all(c.budget == {10: 4, 50: 20, 200: 50, 400: 100}[c.n_assets] for c in SETS["full"])
    case = Case("po_a400_t15_orig", "1e-4")
    assert (case.n_assets, case.n_periods, case.budget) == (400, 15, 100)
    assert (case.n_vars_int, case.n_vars_qubo) == (6000, 36165)


def test_best_known_values():
    table = best_known_table()
    assert len(table) == 128
    assert best_known(Case("po_a010_t10_orig", "1e-4"), table).value == -69482
    assert best_known(Case("po_a010_t10_orig", "0"), table).status == "optimal"
    assert best_known(Case("po_a050_t10_orig", "1e-2"), table).value == -37107
    # Toutes les instances a010/a050 ont un meilleur connu, aucune a200/a400.
    assert all(best_known(c, table) for c in SETS["known"])
    assert not any(best_known(c, table) for c in SETS["large"])


def test_run_empty_portfolio_and_csv_roundtrip(tmp_path):
    cases = [Case("po_a010_t10_orig", "1e-4"), Case("po_a010_t15_s01", "0")]
    runs = run_benchmark(cases, ["empty"], seeds=[0, 1], time_limit=1.0)
    assert len(runs) == 4
    for r in runs:
        assert r.feasible
        assert r.objective == -100 * r.case.n_periods  # intérêts sur le cash seuls
        assert r.gap == (r.objective - r.best_known) / abs(r.best_known)
    path = tmp_path / "runs.csv"
    write_csv(runs, path)
    assert read_csv(path) == runs
    (s,) = [s for s in summarize(runs) if s.case == cases[0]]
    assert (s.best, s.n_runs, s.n_feasible) == (-1000, 2, 2)


def test_plots_with_several_methods(tmp_path):
    cases = [Case("po_a010_t10_orig", lam) for lam in ("1e-4", "1e-3", "1e-2")]
    cases.append(Case("po_a200_t10_orig", "1e-4"))  # sans meilleur connu
    runs = run_benchmark(cases, ["empty"], seeds=[0], time_limit=1.0)
    # Une deuxième « méthode » fictive, un peu meilleure, pour tester légende et comparaison.
    fake = [replace(r, method="fake", objective=r.objective - 500) for r in runs]
    paths = plot_all(runs + fake, tmp_path, "test")
    assert {p.name for p in paths} == {
        "gap_by_case.png",
        "gap_vs_lambda.png",
        "time_by_case.png",
        "size_vs_time.png",
        "size_vs_gap.png",
    }
    assert all(p.stat().st_size > 10_000 for p in paths)
