"""Graphes des benchmarks (piste P3), en PNG pour les rapports Typst.

Trois graphes, tous construits à partir des exécutions (:class:`~.benchmark.Run`) :

* ``gap_by_case.png`` : pour chaque cas, le gap du meilleur score de chaque méthode ;
* ``gap_vs_lambda.png`` : le gap en fonction de λ, un panneau par instance ;
* ``time_by_case.png`` : le temps moyen par cas et par méthode (échelle log) ;
* ``size_vs_time.png`` / ``size_vs_gap.png`` : la taille de l'instance en ordonnée, le temps ou le gap en
  abscisse, une série (couleur + symbole) par méthode. Le plus parlant pour comparer des variantes.

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
import matplotlib.ticker
import numpy as np

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
    "<",
    ">",
    "*",
    "p",
    "d",
    "8",
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


def _methods(runs: Sequence[Run], limit: int = len(SERIES)) -> list[str]:
    """Méthodes dans l'ordre d'apparition. ``limit`` : couleurs (8) ou symboles disponibles."""
    seen: list[str] = []
    for r in runs:
        if r.method not in seen:
            seen.append(r.method)
    if len(seen) > limit:
        raise ValueError(f"au plus {limit} méthodes par graphe (ici {len(seen)})")
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


# Métriques disponibles pour l'axe horizontal de plot_size_vs_metric : (libellé, échelle).
METRICS = {
    "time": ("temps par exécution (s, échelle log)", "log"),
    "gap": ("gap au meilleur connu (%, échelle symlog) — plus petit = mieux", "symlog"),
}


# Rampe séquentielle (bleu, du clair au foncé) pour λ : une grandeur ordonnée, donc une seule teinte.
LAMBDA_RAMP = (
    "#b7d3f6",
    "#86b6ef",
    "#5598e7",
    "#3987e5",
    "#256abf",
    "#1c5cab",
    "#104281",
    "#0d366b",
)


def _lambda_colors(lams: Iterable[str]) -> dict[str, str]:
    """Une couleur par λ présent, du plus clair (λ faible) au plus foncé (λ fort)."""
    ordered = sorted(set(lams), key=lambda x: float(x))
    if len(ordered) > len(LAMBDA_RAMP):
        raise ValueError(f"au plus {len(LAMBDA_RAMP)} valeurs de λ par graphe")
    # On étale les λ présents sur toute la rampe pour garder le contraste.
    if len(ordered) == 1:
        return {ordered[0]: LAMBDA_RAMP[-3]}
    idx = np.linspace(0, len(LAMBDA_RAMP) - 1, len(ordered)).round().astype(int)
    return {lam: LAMBDA_RAMP[k] for lam, k in zip(ordered, idx, strict=True)}


def plot_size_vs_metric(
    runs: Sequence[Run], path: Path, metric: str = "time", label: str = ""
) -> Path:
    """Un point par exécution : taille de l'instance (ordonnée) en fonction d'une métrique (abscisse).

    * **Symbole** : la méthode de résolution (configuration d'optimisations).
    * **Couleur** : la valeur de λ, du bleu clair (λ faible) au bleu foncé (λ fort).

    Tous les runs passés en entrée sont sur le même graphe. La taille est le nombre de variables du QUBO
    officiel, en échelle log ; les points d'une même taille sont légèrement décalés verticalement pour ne pas
    se recouvrir. Pour le gap, un cas sans meilleur connu (a200, a400) se rapporte au meilleur score des
    méthodes présentes, et n'est tracé que si au moins deux méthodes y ont tourné.
    """
    if metric not in METRICS:
        raise ValueError(f"métrique inconnue : {metric} (disponibles : {sorted(METRICS)})")
    xlabel, scale = METRICS[metric]
    methods = _methods(runs, limit=len(MARKERS))  # la couleur sert à λ : seul le symbole compte
    colors = _lambda_colors(r.lam for r in runs)
    refs = _references(summarize(runs)) if metric == "gap" else {}
    if metric == "gap":
        # Sans meilleur connu, la référence est le meilleur des méthodes présentes : elle n'a de sens que
        # si au moins deux méthodes ont tourné sur le cas (sinon la méthode serait sa propre référence).
        methods_per_case: dict[Case, set[str]] = {}
        for r in runs:
            methods_per_case.setdefault(r.case, set()).add(r.method)
        refs = {
            c: ref for c, ref in refs.items() if ref[1] or len(methods_per_case.get(c, ())) >= 2
        }
    rng = np.random.default_rng(0)  # décalage vertical reproductible

    with plt.rc_context(cast(Any, STYLE)):
        fig, ax = plt.subplots(figsize=(8.5, 5.5))
        xs_all: list[float] = []
        for k, method in enumerate(methods):
            xs, ys, cs = [], [], []
            for r in runs:
                if r.method != method or not r.feasible:
                    continue
                if metric == "time":
                    x = max(r.time_s, 1e-4)
                elif r.case in refs:
                    x = _gap_pct(r.objective, refs[r.case][0])
                else:
                    continue
                xs.append(x)
                ys.append(r.n_vars_qubo * 10 ** rng.uniform(-0.04, 0.04))
                cs.append(colors[r.lam])
            xs_all += xs
            ax.scatter(
                xs,
                ys,
                s=26,
                c=cs,
                marker=MARKERS[k],
                alpha=0.85,
                edgecolors=SURFACE,
                linewidths=0.5,
                zorder=3,
            )
        sizes = sorted({(r.n_vars_qubo, _size(r.case)) for r in runs})
        ax.set_yscale("log")
        ax.set_yticks(
            [n for n, _ in sizes],
            [f"{name}  ({n:,} var.)".replace(",", " ") for n, name in sizes],
        )
        ax.minorticks_off()
        if scale == "symlog":
            ax.set_xscale("symlog", linthresh=1.0)
            ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, zorder=1)
            low = min(xs_all, default=0.0)
            ax.set_xlim(left=low * 1.3 if low < 0 else -0.05)
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:g}"))
        else:
            ax.set_xscale(scale)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("taille de l'instance (variables du QUBO officiel, échelle log)")
        title = {"time": "Temps de calcul selon la taille", "gap": "Qualité selon la taille"}[
            metric
        ]
        ax.set_title(_title(title, label), loc="left")

        # Deux légendes : les symboles (méthodes, en gris) et les couleurs (λ).
        method_handles = [
            Line2D(
                [], [], color=TEXT_SECONDARY, marker=MARKERS[k], linestyle="", markersize=6, label=m
            )
            for k, m in enumerate(methods)
        ]
        lam_handles = [
            Line2D([], [], color=c, marker="s", linestyle="", markersize=7, label=f"λ = {lam}")
            for lam, c in colors.items()
        ]
        first = ax.legend(
            handles=method_handles,
            title="méthode (symbole)",
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            title_fontsize=8,
        )
        ax.add_artist(first)
        second = ax.legend(
            handles=lam_handles,
            title="λ (couleur)",
            loc="lower left",
            bbox_to_anchor=(1.01, 0.0),
            title_fontsize=8,
        )
        note = fig.text(
            0.01,
            0.005,
            "un point = une exécution (un cas, une seed)",
            fontsize=7,
            color=TEXT_SECONDARY,
        )
        fig.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight", bbox_extra_artists=[first, second, note])
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
    paths += [
        plot_size_vs_metric(runs, out_dir / f"size_vs_{metric}.png", metric, label)
        for metric in METRICS
    ]
    return [p for p in paths if p is not None]
