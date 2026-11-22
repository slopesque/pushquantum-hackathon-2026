"""Diagnostics F1/F2 d'un substitut QUBO (`docs/network/metrics.md`) : énergie vs score LP.

Les énergies se calculent sur l'**objectif seul** (pénalités de degré exclues). Plus bas = meilleur
des deux côtés (énergie et score LP).
"""

from __future__ import annotations

import dimod
import numpy as np
from scipy.stats import spearmanr

from hackathon.referee import qt

from .fm import topologies_to_X


def qubo_energies(bqm: dimod.BinaryQuadraticModel, X: np.ndarray) -> np.ndarray:
    """Énergies des lignes de ``X`` (colonnes = variables ``0..N-1``), vectorisé."""
    X = np.atleast_2d(np.asarray(X, dtype=np.int8))
    return np.asarray(bqm.energies((X, list(range(X.shape[1])))), dtype=float)


def spearman_rho(energies: np.ndarray, scores: np.ndarray) -> float:
    """F1 : corrélation de rang entre énergie et score LP."""
    return float(spearmanr(energies, scores).statistic)


def top10_precision(energies: np.ndarray, scores: np.ndarray) -> float:
    """F2 : |top10 %(énergie) ∩ top10 %(score)| / k, avec k = max(1, round(0,1·m)) (hasard ≈ 0,10)."""
    energies, scores = np.asarray(energies), np.asarray(scores)
    k = max(1, round(0.1 * len(scores)))
    top_e = set(np.argsort(energies, kind="stable")[:k].tolist())
    top_s = set(np.argsort(scores, kind="stable")[:k].tolist())
    return len(top_e & top_s) / k


def surrogate_metrics(
    objective_bqm: dimod.BinaryQuadraticModel, topologies, scores: np.ndarray, n: int
) -> dict:
    """``{"spearman_rho", "top10_precision"}`` de l'objectif (sans pénalité) sur un jeu de topologies."""
    energies = qubo_energies(objective_bqm, topologies_to_X(topologies, n))
    return {
        "spearman_rho": spearman_rho(energies, scores),
        "top10_precision": top10_precision(energies, scores),
    }


def kit_objective(demand: np.ndarray) -> dimod.BinaryQuadraticModel:
    """Substitut du kit ``-Σ t_ij x_ij`` (objectif seul de ``qt.build_network_qubo``)."""
    return qt.build_network_qubo(demand)[0]
