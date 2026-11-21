"""Graphes des benchmarks (piste P3), en PNG pour les rapports Typst.

Trois graphes, tous construits à partir des exécutions (:class:`~.benchmark.Run`) :

* ``gap_by_case.png`` : pour chaque cas, le gap du meilleur score de chaque méthode ;
* ``gap_vs_lambda.png`` : le gap en fonction de λ, un panneau par instance ;
* ``time_by_case.png`` : le temps moyen par cas et par méthode (échelle log).

**Référence du gap.** Quand QOBLIB publie un meilleur connu (a010, a050), le gap s'y rapporte. Sinon
(a200, a400), il se rapporte au meilleur score trouvé par l'ensemble des méthodes du graphe ; ces cas sont
marqués d'un ``†``. Un gap négatif signifie qu'on bat le meilleur connu.

Couleurs : palette catégorielle validée (daltonisme compris), attribuée dans un ordre fixe aux méthodes,
par ordre d'apparition. Une méthode garde donc sa couleur tant que la liste des méthodes ne change pas.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from hackathon.solvers.portfolio.benchmark import (
    LAMBDAS,
    SIZES,
    Case,
    Run,
    Summary,
    summarize,
)

# Palette catégorielle de référence (mode clair), dans son ordre validé. Ne pas réordonner.
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
MARKERS = (
    "o",
    "s",
    "D",
    "^",
    "v",
    "P",
    "X",
    "h",
)  # codage secondaire : l'identité ne repose pas que sur la couleur

STYLE: dict[str, Any] = {
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": TEXT_SECONDARY,
    "axes.titlecolor": TEXT,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_SECONDARY,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "legend.frameon": False,
    "font.size": 9,
    "text.color": TEXT,
}


def _case_order(case: Case) -> tuple:
    size = case.instance.removeprefix("po_").rsplit("_", 1)[0]
    s = SIZES.index(size) if size in SIZES else len(SIZES)
    lam = LAMBDAS.index(case.lam) if case.lam in LAMBDAS else len(LAMBDAS)
    return (s, case.instance, lam)


def _methods(runs: Sequence[Run]) -> list[str]:
    seen: list[str] = []
    for r in runs:
        if r.method not in seen:
            seen.append(r.method)
    if len(seen) > len(SERIES):
        raise ValueError(f"au plus {len(SERIES)} méthodes par graphe (ici {len(seen)})")
    return seen


def _references(summaries: Iterable[Summary]) -> dict[Case, tuple[float, bool]]:
    """Référence du gap par cas : ``(valeur, publiée ?)``."""
    refs: dict[Case, tuple[float, bool]] = {}
    for s in summaries:
        if s.best_known is not None:
            refs[s.case] = (s.best_known, True)
        elif s.best is not None:
            current = refs.get(s.case)
            if current is None or (not current[1] and s.best < current[0]):
                refs[s.case] = (s.best, False)
    return refs


def _title(base: str, label: str) -> str:
    return f"{base} — {label}" if label else base


def _gap_pct(value: float, ref: float) -> float:
    return 100 * (value - ref) / abs(ref)


def _legend(ax, methods: list[str]) -> None:
    if len(methods) < 2:
        return  # une seule série : le titre la nomme
    handles = [
        Line2D([], [], color=SERIES[k], marker=MARKERS[k], linestyle="", markersize=6, label=m)
        for k, m in enumerate(methods)
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0))


def plot_gap_by_case(runs: Sequence[Run], path: Path, label: str = "") -> Path:
    """Dot plot horizontal : un cas par ligne, un point par méthode (meilleur score sur les seeds)."""
    methods = _methods(runs)
    summaries = summarize(runs)
    refs = _references(summaries)
    cases = sorted(refs, key=_case_order)
    by_key = {(s.case, s.method): s for s in summaries}

    with plt.rc_context(cast(Any, STYLE)):
        fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(cases) + 1.4))
        ax.grid(axis="y", visible=False)
        ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, zorder=1)
        offsets = (
            [0.0]
            if len(methods) == 1
            else [
                0.24 * (k - (len(methods) - 1) / 2) / max(1, len(methods) - 1) * 2
                for k in range(len(methods))
            ]
        )
        for k, method in enumerate(methods):
            xs, ys = [], []
            for row, case in enumerate(cases):
                s = by_key.get((case, method))
                if s is None or s.best is None:
                    continue
                xs.append(_gap_pct(s.best, refs[case][0]))
                ys.append(row + offsets[k])
            ax.scatter(
                xs,
                ys,
                s=36,
                color=SERIES[k],
                marker=MARKERS[k],
                zorder=3,
                edgecolors=SURFACE,
                linewidths=1.0,
                label=method,
            )
        labels = [c.label + ("" if refs[c][1] else "  †") for c in cases]
        ax.set_yticks(range(len(cases)), labels)
        ax.invert_yaxis()
        ax.set_xlabel("gap au meilleur connu (%) — plus petit = mieux, < 0 = record battu")
        ax.set_title(_title("Gap par cas (meilleure seed)", label), loc="left")
        if not all(published for _, published in refs.values()):
            fig.text(
                0.01,
                0.005,
                "† pas de meilleur connu publié : gap au meilleur score trouvé ici",
                fontsize=7,
                color=TEXT_SECONDARY,
            )
        _legend(ax, methods)
        fig.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(fig)
    return path


def plot_gap_vs_lambda(runs: Sequence[Run], path: Path, label: str = "") -> Path | None:
    """Petits multiples : un panneau par instance (avec ≥ 3 valeurs de λ), gap en fonction de λ."""
    methods = _methods(runs)
    summaries = summarize(runs)
    refs = _references(summaries)
    by_key = {(s.case, s.method): s for s in summaries}
    instances: dict[str, list[Case]] = {}
    for case in sorted(refs, key=_case_order):
        instances.setdefault(case.instance, []).append(case)
    instances = {k: v for k, v in instances.items() if len(v) >= 3}
    if not instances:
        return None

    n = len(instances)
    ncols = min(n, 2)
    nrows = (n + ncols - 1) // ncols
    with plt.rc_context(cast(Any, STYLE)):
        fig, axes = plt.subplots(
            nrows, ncols, figsize=(4.2 * ncols, 2.8 * nrows), squeeze=False, sharey=False
        )
        for ax, (instance, cases) in zip(axes.flat, instances.items(), strict=False):
            ax.axhline(0, color=TEXT_SECONDARY, linewidth=1, zorder=1)
            x = range(len(cases))
            for k, method in enumerate(methods):
                pts = [
                    (i, _gap_pct(s.best, refs[c][0]))
                    for i, c in enumerate(cases)
                    if (s := by_key.get((c, method))) is not None and s.best is not None
                ]
                if pts:
                    xs, ys = zip(*pts, strict=True)
                    ax.plot(
                        xs,
                        ys,
                        color=SERIES[k],
                        linewidth=2,
                        marker=MARKERS[k],
                        markersize=6,
                        markeredgecolor=SURFACE,
                        markeredgewidth=1.0,
                        zorder=3,
                    )
            ax.set_xticks(list(x), [c.lam for c in cases])
            ax.set_xlabel("λ (poids du risque)")
            ax.set_ylabel("gap (%)")
            dagger = "" if refs[cases[0]][1] else " †"
            ax.set_title(instance.removeprefix("po_") + dagger, loc="left", fontsize=9)
            ax.grid(axis="x", visible=False)
        for ax in list(axes.flat)[n:]:
            ax.set_visible(False)
        fig.suptitle(_title("Gap en fonction de λ", label), x=0.01, ha="left", fontweight="bold")
        if len(methods) >= 2:
            handles = [
                Line2D([], [], color=SERIES[k], marker=MARKERS[k], linewidth=2, label=m)
                for k, m in enumerate(methods)
            ]
            fig.legend(handles=handles, loc="upper right", ncols=min(len(methods), 4))
        fig.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(fig)
    return path


def plot_time_by_case(runs: Sequence[Run], path: Path, label: str = "") -> Path:
    """Dot plot horizontal du temps moyen par exécution, échelle logarithmique."""
    methods = _methods(runs)
    summaries = summarize(runs)
    cases = sorted({s.case for s in summaries}, key=_case_order)
    by_key = {(s.case, s.method): s for s in summaries}
    with plt.rc_context(cast(Any, STYLE)):
        fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(cases) + 1.2))
        ax.grid(axis="y", visible=False)
        for k, method in enumerate(methods):
            pts = [
                (max(s.time_mean, 1e-4), row)
                for row, c in enumerate(cases)
                if (s := by_key.get((c, method))) is not None
            ]
            if pts:
                xs, ys = zip(*pts, strict=True)
                ax.scatter(
                    xs,
                    ys,
                    s=36,
                    color=SERIES[k],
                    marker=MARKERS[k],
                    zorder=3,
                    edgecolors=SURFACE,
                    linewidths=1.0,
                )
        ax.set_xscale("log")
        ax.set_yticks(range(len(cases)), [c.label for c in cases])
        ax.invert_yaxis()
        ax.set_xlabel("temps moyen par exécution (s, échelle log)")
        ax.set_title(_title("Temps de calcul", label), loc="left")
        _legend(ax, methods)
        fig.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(fig)
    return path


MAX_CASES_PER_FIGURE = 48


def _size(case: Case) -> str:
    """Taille d'une instance, par ex. ``a010_t10`` pour ``po_a010_t10_orig``."""
    return case.instance.removeprefix("po_").rsplit("_", 1)[0]


def plot_all(runs: Sequence[Run], out_dir: Path, label: str = "") -> list[Path]:
    """Produit les graphes dans ``out_dir`` et renvoie leurs chemins.

    Au-delà de ``MAX_CASES_PER_FIGURE`` cas, les graphes sont découpés par taille d'instance
    (``gap_by_case_a010_t10.png``, …) pour rester lisibles.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    n_cases = len({r.case for r in runs})
    if n_cases <= MAX_CASES_PER_FIGURE:
        groups = {"": list(runs)}
    else:
        groups: dict[str, list[Run]] = {}
        for r in runs:
            groups.setdefault(_size(r.case), []).append(r)
    paths: list[Path | None] = []
    for size, rs in sorted(
        groups.items(), key=lambda kv: SIZES.index(kv[0]) if kv[0] in SIZES else -1
    ):
        suffix = f"_{size}" if size else ""
        sub = f"{label} — {size}" if size and label else (size or label)
        paths += [
            plot_gap_by_case(rs, out_dir / f"gap_by_case{suffix}.png", sub),
            plot_gap_vs_lambda(rs, out_dir / f"gap_vs_lambda{suffix}.png", sub),
            plot_time_by_case(rs, out_dir / f"time_by_case{suffix}.png", sub),
        ]
    return [p for p in paths if p is not None]
