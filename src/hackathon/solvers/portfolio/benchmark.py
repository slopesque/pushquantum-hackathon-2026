"""Banc d'essai des méthodes de résolution (piste P3).

* La **grille** des cas officiels : 32 instances (a010 à a400, 4 seeds de données) × 8 valeurs de λ,
  avec le budget B fixé par le nombre d'actions. Des sous-ensembles nommés (``SETS``) permettent
  d'itérer vite (``dev``) ou de tout lancer (``full``).
* Les **meilleurs connus** publiés par QOBLIB (a010 et a050 uniquement), pour calculer le gap.
* Un **registre de méthodes** : une méthode est une fonction ``(problème, rng, limite de temps) → v``.
* :func:`run_benchmark` lance des méthodes sur des cas, plusieurs seeds chacune, et renvoie un
  :class:`Run` par exécution. Les solutions sont notées par *notre* modèle ; l'arbitre officiel n'est
  utilisé qu'au moment de valider les ``.sol`` gardés (``scripts/bench_portfolio.py --save-sol``).
"""

from __future__ import annotations

import csv
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, fields
from fractions import Fraction
from pathlib import Path

import numpy as np

from hackathon.solvers.portfolio.problem import (
    PortfolioInstance,
    PortfolioProblem,
    fetch,
    load_instance,
)

# ════════════════════════════════════════════════════════════════════════
# La grille des cas
# ════════════════════════════════════════════════════════════════════════

LAMBDAS = ("0", "1e-6", "1e-5", "5e-5", "1e-4", "5e-4", "1e-3", "1e-2")
"""Les 8 poids de risque λ de QOBLIB, du plus faible au plus fort."""

BUDGET_BY_ASSETS = {10: 4, 50: 20, 200: 50, 400: 100}
"""Budget B (unités ouvertes par jour) fixé par QOBLIB selon le nombre d'actions."""

SIZES = (
    "a010_t10",
    "a010_t15",
    "a050_t10",
    "a050_t15",
    "a200_t10",
    "a200_t15",
    "a400_t10",
    "a400_t15",
)
DATA_SEEDS = ("orig", "s00", "s01", "s02")


def _instance_field(instance: str, letter: str) -> int:
    """Lit un champ du nom d'instance : ``a`` (actions) ou ``t`` (jours) dans ``po_a010_t10_orig``."""
    match = re.search(rf"_{letter}(\d+)_", instance)
    if match is None:
        raise ValueError(f"nom d'instance inattendu : {instance}")
    return int(match.group(1))


@dataclass(frozen=True)
class Case:
    """Un cas à résoudre : une instance et un poids de risque λ (le budget en découle)."""

    instance: str
    lam: str

    @property
    def n_assets(self) -> int:
        return _instance_field(self.instance, "a")

    @property
    def n_periods(self) -> int:
        return _instance_field(self.instance, "t")

    @property
    def budget(self) -> int:
        return BUDGET_BY_ASSETS[self.n_assets]

    @property
    def n_vars_qubo(self) -> int:
        """Taille dans le QUBO officiel : 6nT bits de positions + 11T bits de slack."""
        return 6 * self.n_assets * self.n_periods + 11 * self.n_periods

    @property
    def n_vars_int(self) -> int:
        """Taille dans notre encodage entier : une variable v ∈ {-3..3} par action et par jour."""
        return self.n_assets * self.n_periods

    @property
    def label(self) -> str:
        """Nom court pour les tableaux et les graphes, par ex. ``a010_t10_orig λ=1e-4``."""
        return f"{self.instance.removeprefix('po_')} λ={self.lam}"


def grid(sizes: Iterable[str] = SIZES, seeds: Iterable[str] = DATA_SEEDS, lambdas=LAMBDAS):
    return [Case(f"po_{s}_{d}", lam) for s in sizes for d in seeds for lam in lambdas]


SETS: dict[str, list[Case]] = {
    # Quelques minutes : un petit cas complet, un moyen, un grand.
    "dev": grid(["a010_t10"], ["orig"])
    + grid(["a050_t10"], ["orig"], ["1e-4", "1e-3", "1e-2"])
    + grid(["a200_t10"], ["orig"], ["1e-4"]),
    "a010": grid(["a010_t10", "a010_t15"]),
    "a050": grid(["a050_t10", "a050_t15"]),
    "known": grid(["a010_t10", "a010_t15", "a050_t10", "a050_t15"]),  # avec meilleur connu
    "large": grid(["a200_t10", "a200_t15", "a400_t10", "a400_t15"]),  # sans meilleur connu
    "a400": grid(["a400_t15"], ["orig"]),
    "full": grid(),
}


# ════════════════════════════════════════════════════════════════════════
# Meilleurs connus (QOBLIB)
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class BestKnown:
    value: int
    status: str
    """``optimal`` (prouvé) ou ``best known``."""


_BKV_ROW = re.compile(
    r"^\|\s*(a\d+_t\d+_\w+?)_b(\d+)_l(\S+)\s*\|\s*(-?\d+)\s*\|\s*([^|]+?)\s*\|", re.MULTILINE
)


def best_known_table(refresh: bool = False) -> dict[tuple[str, int, Fraction], BestKnown]:
    """Table des meilleurs connus, clé ``(instance, budget, λ)``. Téléchargée une fois puis en cache."""
    rel = "06-portfolio/solutions/README.md"
    path = fetch(rel)
    if refresh:
        path.unlink()
        path = fetch(rel)
    table = {}
    for inst, budget, lam, value, status in _BKV_ROW.findall(path.read_text()):
        table["po_" + inst, int(budget), Fraction(lam)] = BestKnown(int(value), status)
    return table


def best_known(case: Case, table: dict | None = None) -> BestKnown | None:
    table = best_known_table() if table is None else table
    return table.get((case.instance, case.budget, Fraction(case.lam)))


def gap(objective: float, reference: float) -> float:
    """Gap relatif : ``(score - référence) / |référence|``. 0 = égalité, négatif = mieux."""
    return (objective - reference) / abs(reference)


# ════════════════════════════════════════════════════════════════════════
# Méthodes
# ════════════════════════════════════════════════════════════════════════

Method = Callable[[PortfolioProblem, np.random.Generator, float], np.ndarray]
"""``(problème, générateur aléatoire, limite de temps en s) → solution v`` (doit être faisable)."""

METHODS: dict[str, Method] = {}


def register(name: str) -> Callable[[Method], Method]:
    """Décorateur : ajoute une méthode au registre sous ``name``."""

    def deco(fn: Method) -> Method:
        if name in METHODS:
            raise ValueError(f"méthode déjà enregistrée : {name}")
        METHODS[name] = fn
        return fn

    return deco


@register("empty")
def empty_portfolio(problem: PortfolioProblem, rng: np.random.Generator, time_limit: float):
    """Repère trivial : ne rien détenir. Score = intérêts sur le cash seuls (-100 par jour)."""
    return np.zeros((problem.T, problem.n), dtype=np.int64)


# ════════════════════════════════════════════════════════════════════════
# Exécution
# ════════════════════════════════════════════════════════════════════════


@dataclass
class Run:
    """Le résultat d'une exécution : une méthode, un cas, une seed."""

    instance: str
    lam: str
    budget: int
    n_vars_int: int
    n_vars_qubo: int
    method: str
    seed: int
    objective: int
    feasible: bool
    best_known: int | None
    bkv_status: str
    gap: float | None
    """Gap au meilleur connu, ``None`` s'il n'y en a pas (a200, a400)."""
    time_s: float

    @property
    def case(self) -> Case:
        return Case(self.instance, self.lam)


class ProblemCache:
    """Charge chaque instance une seule fois, même si elle sert pour plusieurs λ."""

    def __init__(self) -> None:
        self._instances: dict[str, PortfolioInstance] = {}

    def problem(self, case: Case) -> PortfolioProblem:
        if case.instance not in self._instances:
            self._instances[case.instance] = load_instance(case.instance)
        return PortfolioProblem(self._instances[case.instance], case.budget, case.lam)


def run_benchmark(
    cases: Iterable[Case],
    methods: Iterable[str],
    seeds: Iterable[int],
    time_limit: float,
    on_run: Callable[[Run, PortfolioProblem, np.ndarray], None] | None = None,
) -> list[Run]:
    """Lance chaque méthode sur chaque cas avec chaque seed.

    ``on_run(run, problem, v)`` est appelé après chaque exécution (affichage, sauvegarde des ``.sol``).
    """
    methods, seeds = list(methods), list(seeds)
    unknown = [m for m in methods if m not in METHODS]
    if unknown:
        raise KeyError(f"méthodes inconnues : {unknown} (disponibles : {sorted(METHODS)})")
    table = best_known_table()
    cache = ProblemCache()
    runs = []
    for case in cases:
        problem = cache.problem(case)
        bkv = best_known(case, table)
        for method in methods:
            for seed in seeds:
                start = time.perf_counter()
                v = METHODS[method](problem, np.random.default_rng(seed), time_limit)
                elapsed = time.perf_counter() - start
                objective = problem.objective(v)
                run = Run(
                    instance=case.instance,
                    lam=case.lam,
                    budget=case.budget,
                    n_vars_int=case.n_vars_int,
                    n_vars_qubo=case.n_vars_qubo,
                    method=method,
                    seed=seed,
                    objective=objective,
                    feasible=problem.is_feasible(v),
                    best_known=bkv.value if bkv else None,
                    bkv_status=bkv.status if bkv else "",
                    gap=gap(objective, bkv.value) if bkv else None,
                    time_s=elapsed,
                )
                runs.append(run)
                if on_run is not None:
                    on_run(run, problem, v)
    return runs


# ════════════════════════════════════════════════════════════════════════
# Agrégation et CSV
# ════════════════════════════════════════════════════════════════════════


@dataclass
class Summary:
    """Une méthode sur un cas, toutes seeds confondues."""

    case: Case
    method: str
    best: int | None
    """Meilleur score faisable sur toutes les seeds (``None`` si aucune exécution faisable)."""
    median: float | None
    n_runs: int
    n_feasible: int
    best_known: int | None
    gap_best: float | None
    gap_median: float | None
    time_mean: float


def summarize(runs: Iterable[Run]) -> list[Summary]:
    """Meilleur score et médiane par (cas, méthode), sur les exécutions faisables."""
    groups: dict[tuple[Case, str], list[Run]] = {}
    for r in runs:
        groups.setdefault((r.case, r.method), []).append(r)
    out = []
    for (case, method), rs in groups.items():
        ok = [r.objective for r in rs if r.feasible]
        best = min(ok) if ok else None
        median = float(np.median(ok)) if ok else None
        bkv = rs[0].best_known
        out.append(
            Summary(
                case=case,
                method=method,
                best=best,
                median=median,
                n_runs=len(rs),
                n_feasible=len(ok),
                best_known=bkv,
                gap_best=gap(best, bkv) if bkv is not None and best is not None else None,
                gap_median=gap(median, bkv) if bkv is not None and median is not None else None,
                time_mean=float(np.mean([r.time_s for r in rs])),
            )
        )
    return out


def write_csv(runs: Iterable[Run], path: Path) -> None:
    names = [f.name for f in fields(Run)]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=names)
        writer.writeheader()
        for r in runs:
            writer.writerow(asdict(r))


def read_csv(path: Path) -> list[Run]:
    def parse(row: dict[str, str]) -> Run:
        return Run(
            instance=row["instance"],
            lam=row["lam"],
            budget=int(row["budget"]),
            n_vars_int=int(row["n_vars_int"]),
            n_vars_qubo=int(row["n_vars_qubo"]),
            method=row["method"],
            seed=int(row["seed"]),
            objective=int(row["objective"]),
            feasible=row["feasible"] == "True",
            best_known=int(row["best_known"]) if row["best_known"] else None,
            bkv_status=row["bkv_status"],
            gap=float(row["gap"]) if row["gap"] else None,
            time_s=float(row["time_s"]),
        )

    with path.open() as f:
        return [parse(row) for row in csv.DictReader(f)]
