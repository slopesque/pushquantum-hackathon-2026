"""H1 : boucle active FMQA (substitut QUBO appris à partir de l'oracle LP).

``h1_fm`` est une *méthode* au format du harnais H0 (``h0.harness.run_method``) :
données initiales aléatoires → FM → QUBO appris → échantillonnage (SA ou PCE) → repair → LP sur les
topologies nouvelles → réentraînement, jusqu'à épuisement du budget du ``Scorer``.
"""

from __future__ import annotations

import json
import math
import time
import warnings
from typing import Any

import numpy as np
from h0.scorer import BudgetExhausted, Scorer

from hackathon.referee import qt
from hackathon.utils import RESULTS_DIR

TESTSET_DIR = RESULTS_DIR / "network" / "testsets"
MIN_NEW_PER_ROUND = 5
MAX_RANDOM_TRIES = 200  # garde anti-boucle : tirages aléatoires consécutifs déjà en cache


def load_testset(instance: str | None) -> tuple[list[list[tuple[int, int]]], list[float]] | None:
    """Jeu de test figé ``results/network/testsets/<instance>.json`` (``None`` s'il est absent)."""
    if instance is None:
        return None
    path = TESTSET_DIR / f"{instance}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    topologies = [[(int(i), int(j)) for i, j in arcs] for arcs in data["arcs"]]
    return topologies, [float(s) for s in data["score"]]


def quantum_round_selected(spec: str, r: int) -> bool:
    """``"none"`` | ``"all"`` | ``"first:k"`` (tours 0..k-1) | ``"every:k"`` (tours 0, k, 2k…)."""
    spec = (spec or "none").strip().lower()
    if spec == "none":
        return False
    if spec == "all":
        return True
    kind, _, arg = spec.partition(":")
    k = int(arg)
    if kind == "first":
        return r < k
    if kind == "every":
        return k > 0 and r % k == 0
    raise ValueError(f"quantum_rounds inconnu : {spec!r}")


def h1_fm(
    demand: np.ndarray,
    seed: int,
    scorer: Scorer,
    *,
    rank: int = 8,
    lam: float = 1.0,
    target: str = "rank",
    n0_frac: float = 0.2,
    sa_reads: int = 100,
    epochs_init: int = 300,
    epochs_round: int = 50,
    lr: float = 0.01,
    l2: float = 1e-4,
    quantum: dict[str, Any] | None = None,
    quantum_rounds: str = "none",
    diag_instance: str | None = None,
) -> dict[str, Any]:
    """Boucle FMQA. Toutes les notations LP passent par ``scorer`` (budget commun)."""
    from h1.diagnostics import kit_objective, surrogate_metrics
    from h1.fm import FactorizationMachine, learned_qubo, make_target, topologies_to_X
    from h1.samplers import sa_sampler

    n = len(demand)
    arcs_list = qt.all_arcs(n)
    n_vars = len(arcs_list)
    rng = np.random.default_rng(seed)

    data_topos: list[list[tuple[int, int]]] = []
    data_scores: list[float] = []
    trajectory: list[list[float]] = []
    out: dict[str, Any] = {
        "feasible_mass": None,
        "n_circuits": 0,
        "max_qubits": 0,
        "backend": "none",
        "spearman_rho": None,
        "top10_precision": None,
        "spearman_rho_init": None,
        "top10_precision_init": None,
        "spearman_rho_kit": None,
        "top10_precision_kit": None,
        "n_rounds": 0,
        "n_quantum_rounds": 0,
        "n_explore": 0,
        "score_after_n0": None,
        "trajectory": trajectory,
        "fit_time_s": 0.0,
        "sample_time_s": 0.0,
    }
    feasible: list[float] = []
    testset = load_testset(diag_instance)
    fm = None

    def score(arcs: list[tuple[int, int]]) -> float:
        before = scorer.best_score
        value = scorer.score(arcs)
        data_topos.append(sorted(arcs))
        data_scores.append(value)
        if scorer.best_score < before:
            trajectory.append([scorer.lp_calls, float(scorer.best_score)])
        return value

    def explore(k: int) -> int:
        """Note jusqu'à ``k`` topologies aléatoires nouvelles ; renvoie le nombre notées."""
        done = misses = 0
        while done < k and not scorer.exhausted and misses < MAX_RANDOM_TRIES:
            arcs = qt.random_topology(n, rng)
            if scorer.is_cached(arcs):
                misses += 1
                continue
            score(arcs)
            done += 1
            misses = 0
        return done

    def fit(epochs: int) -> None:
        t0 = time.perf_counter()
        X = topologies_to_X(data_topos, n)
        y = make_target(np.asarray(data_scores, dtype=float), mode=target)
        fm.fit(X, y, epochs=epochs, warm_start=True)
        out["fit_time_s"] += time.perf_counter() - t0

    def diagnose(suffix: str) -> None:
        if testset is None or fm is None:
            return
        _, obj = learned_qubo(fm, demand, lam)
        m = surrogate_metrics(obj, testset[0], testset[1], n)
        out[f"spearman_rho{suffix}"] = _f(m.get("spearman_rho"))
        out[f"top10_precision{suffix}"] = _f(m.get("top10_precision"))

    try:
        # Diagnostics du QUBO du kit (sans appel LP, jeu de test seulement).
        if testset is not None:
            m = surrogate_metrics(kit_objective(demand), testset[0], testset[1], n)
            out["spearman_rho_kit"] = _f(m.get("spearman_rho"))
            out["top10_precision_kit"] = _f(m.get("top10_precision"))

        # 1. Données initiales (comptent dans le budget).
        budget_lp = scorer.max_lp_calls if scorer.max_lp_calls is not None else 1000
        n0 = max(int(n0_frac * budget_lp), 2)
        explore(n0)
        out["score_after_n0"] = _f(scorer.best_score)

        # 2. FM initiale.
        fm = FactorizationMachine(n_vars, rank=rank, seed=seed, l2=l2, lr=lr)
        fit(epochs_init)
        diagnose("_init")

        # 3. Boucle active.
        sa = sa_sampler(sa_reads)
        qsampler = None
        r = 0
        while not scorer.exhausted:
            use_q = quantum is not None and quantum_round_selected(quantum_rounds, r)
            if use_q and qsampler is None:
                from h1 import pce

                qsampler = pce.make_pce_sampler(**quantum)
            full, _ = learned_qubo(fm, demand, lam)
            t0 = time.perf_counter()
            batch = (qsampler if use_q else sa)(full, seed * 1_000_003 + r)
            out["sample_time_s"] += time.perf_counter() - t0
            out["n_rounds"] += 1
            if use_q:
                out["n_quantum_rounds"] += 1
                out["n_circuits"] += int(batch.n_circuits)
                out["max_qubits"] = max(out["max_qubits"], int(batch.n_qubits))
                out["backend"] = batch.backend

            samples = np.asarray(batch.samples, dtype=np.uint8)
            valid = np.array(
                [qt.is_valid_topology(n, qt.decode_topology(row, arcs_list)) for row in samples]
            )
            if batch.probs is not None and len(samples):
                p = np.asarray(batch.probs, dtype=float)
                feasible.append(float(p[valid].sum() / p.sum()) if p.sum() > 0 else 0.0)
            elif len(samples):
                feasible.append(float(valid.mean()))

            # Repair, dédoublonnage, tri par énergie apprise, LP sur les nouvelles.
            seen: set[frozenset[tuple[int, int]]] = set()
            cands: list[list[tuple[int, int]]] = []
            for row in samples:
                fixed = qt.repair_topology(n, qt.decode_topology(row, arcs_list), demand)
                key = frozenset(fixed)
                if key in seen or scorer.is_cached(fixed):
                    continue
                seen.add(key)
                cands.append(sorted(fixed))
            if cands:
                pred = np.asarray(fm.predict(topologies_to_X(cands, n)), dtype=float)
                cands = [cands[i] for i in np.argsort(pred, kind="stable")]
            for arcs in cands:
                if scorer.exhausted:
                    break
                score(arcs)
            if len(cands) < MIN_NEW_PER_ROUND:
                got = explore(MIN_NEW_PER_ROUND - len(cands))
                out["n_explore"] += got
                if not cands and got == 0:
                    break  # plus rien de nouveau à proposer
            if scorer.exhausted:
                break
            fit(epochs_round)
            r += 1
    except BudgetExhausted:
        pass

    try:
        diagnose("")
    except Exception as exc:  # noqa: BLE001 — un diagnostic raté ne doit pas faire perdre le run
        warnings.warn(f"diagnostic final du substitut impossible : {exc}", stacklevel=2)
    out["feasible_mass"] = float(np.mean(feasible)) if feasible else None
    out["fit_time_s"] = round(out["fit_time_s"], 3)
    out["sample_time_s"] = round(out["sample_time_s"], 3)
    return out


def _f(x: Any) -> float | None:
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else x
