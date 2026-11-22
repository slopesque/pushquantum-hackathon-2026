"""H2 : substitut analytique enrichi (chemins à 2 sauts) et règles de λ.

Variables ``0..N-1`` dans l'ordre de ``qt.all_arcs(n)`` (comme ``qt.build_network_qubo``), BINARY.
``t = demand / demand.max()``.

Objectif (avant normalisation) ::

    - α Σ_{i≠j} t_ij x_ij                                   (direct, = kit)
    - β₂ Σ_{i,j,k distincts} t_ik x_ij x_jk                 (la demande i→k peut passer par j)
    + γ Σ_j Σ_{i<i'} t_ij t_i'j x_ij x_i'j                  (équilibrage, arcs entrants de j)
    + γ Σ_i Σ_{j<j'} t_ij t_ij' x_ij x_ij'                  (équilibrage, arcs sortants de i)

Terme γ (choix H2, 0 par défaut) : pénalise deux arcs **lourds** (forte demande directe) qui entrent
dans (ou sortent d') un même nœud, car leurs flux se concentrent sur les 2 seuls liens du nœud.
Puis normalisation à max|coeff| = 1 (linéaires et quadratiques), offset 0.
"""

from __future__ import annotations

from collections import defaultdict

import dimod
import numpy as np

from hackathon.referee import qt

LAMBDA_RULES = ("unit", "ayodele", "broesamle", "vlm", "momc")


def physics_objective(
    demand: np.ndarray, alpha: float = 1.0, beta2: float = 0.5, gamma: float = 0.0
) -> dimod.BinaryQuadraticModel:
    """Objectif H2 (sans pénalité), normalisé à max|coeff| = 1, offset 0 (voir le module)."""
    n = len(demand)
    arcs = qt.all_arcs(n)
    idx = {a: v for v, a in enumerate(arcs)}
    t = np.asarray(demand, dtype=float)
    t = t / (t.max() or 1.0)
    linear = np.array([-alpha * t[i, j] for i, j in arcs], dtype=float)
    quad: dict[tuple[int, int], float] = defaultdict(float)
    if beta2:
        for i in range(n):
            for j in range(n):
                if j == i:
                    continue
                u = idx[i, j]
                for k in range(n):
                    if k in (i, j) or t[i, k] == 0:
                        continue
                    v = idx[j, k]
                    quad[(u, v) if u < v else (v, u)] -= beta2 * t[i, k]
    if gamma:
        for node in range(n):
            ins = [(idx[i, node], t[i, node]) for i in range(n) if i != node]
            outs = [(idx[node, j], t[node, j]) for j in range(n) if j != node]
            for group in (ins, outs):
                for a in range(len(group)):
                    for b in range(a + 1, len(group)):
                        (u, tu), (v, tv) = group[a], group[b]
                        quad[(u, v) if u < v else (v, u)] += gamma * tu * tv
    bqm = dimod.BinaryQuadraticModel(dict(enumerate(linear)), dict(quad), 0.0, dimod.BINARY)
    for v in range(len(arcs)):  # garantit toutes les variables, même sans biais
        bqm.add_variable(v, 0.0)
    scale = _max_abs(bqm)
    if scale > 0:
        bqm.scale(1.0 / scale)
    bqm.offset = 0.0
    return bqm


def physics_qubo(
    demand: np.ndarray,
    alpha: float = 1.0,
    beta2: float = 0.5,
    gamma: float = 0.0,
    lam: float = 1.0,
) -> tuple[dimod.BinaryQuadraticModel, dimod.BinaryQuadraticModel]:
    """``(full, objective)`` : objectif H2 + ``lam`` · pénalité de degré du kit."""
    objective = physics_objective(demand, alpha, beta2, gamma)
    _, penalty, _ = qt.build_network_qubo(demand)
    full = objective.copy()
    full.update(penalty * lam)
    return full, objective


def degree_penalty(n: int) -> dimod.BinaryQuadraticModel:
    """Pénalité de degré du kit (2ᵉ sortie de ``qt.build_network_qubo``) pour ``n`` nœuds."""
    return qt.build_network_qubo(np.ones((n, n)))[1]


def lambda_rule(
    objective_bqm: dimod.BinaryQuadraticModel,
    rule: str = "unit",
    penalty_bqm: dimod.BinaryQuadraticModel | None = None,
) -> float:
    """Poids λ de la pénalité de degré selon une règle statique.

    Notation : ``C`` = objectif, ``G`` = pénalité (``penalty_bqm``, par défaut celle du kit pour
    ``n`` déduit de ``N = n(n-1)``). Pour une variable i, ``W_i(M) = max(−M_ii − Σ_{j≠i} min(M_ij, 0),
    M_ii + Σ_{j≠i} max(M_ij, 0))`` est la plus grande variation de M obtenue en basculant x_i.

    * ``"unit"`` : 1,0 (kit, B1).
    * ``"ayodele"`` = **MOC** d'Ayodele 2022 (arXiv 2206.11040, éq. 19), la règle qui donne les
      plus petits poids valides sur les problèmes de permutation (QAP) :
      ``λ = max(1, max_{i : W_i(G) > 0} W_i(C) / W_i(G))``.
    * ``"momc"`` : MOMC (éq. 18) ``max(1, max_i W_i(C) / min_{W_i(G) > 0} W_i(G))``.
    * ``"vlm"`` : Verma & Lewis 2020 (éq. 15 d'Ayodele), ``max_i W_i(C)``.
    * ``"broesamle"`` : Broesamle et al. 2026 (arXiv 2602.10951, Théorème 2) : pour un objectif
      linéaire ``cᵀx`` et des pénalités entières ≥ 1 sur toute violation, ``P > Σ_i |c_i|``
      garantit que tout minimum global du QUBO est faisable et optimal. Notre objectif est
      quadratique : on l'étend par ``P > Σ|linéaires| + Σ|quadratiques|`` (borne de l'amplitude de
      l'objectif ; la pénalité de degré du kit est entière, ≥ 1 sur toute violation). On renvoie
      cette somme × (1 + 1e-9).
    """
    rule = rule.lower()
    if rule == "unit":
        return 1.0
    lin, (_, _, qv), _ = objective_bqm.to_numpy_vectors(variable_order=_order(objective_bqm))
    if rule == "broesamle":
        return float((np.abs(lin).sum() + np.abs(qv).sum()) * (1.0 + 1e-9))
    wc = _flip_weights(objective_bqm)
    if rule == "vlm":
        return float(wc.max())
    if penalty_bqm is None:
        n_vars = objective_bqm.num_variables
        n = round((1 + np.sqrt(1 + 4 * n_vars)) / 2)
        assert n * (n - 1) == n_vars, f"N={n_vars} n'est pas de la forme n(n-1)"
        penalty_bqm = degree_penalty(n)
    wg = _flip_weights(penalty_bqm)
    pos = wg > 0
    if rule == "ayodele":
        return float(max(1.0, (wc[pos] / wg[pos]).max()))
    if rule == "momc":
        return float(max(1.0, wc.max() / wg[pos].min()))
    raise ValueError(f"règle λ inconnue : {rule!r} ({', '.join(LAMBDA_RULES)})")


def _order(bqm: dimod.BinaryQuadraticModel) -> list:
    return sorted(bqm.variables)


def _flip_weights(bqm: dimod.BinaryQuadraticModel) -> np.ndarray:
    """``W_i`` d'Ayodele (éq. 14/16) pour chaque variable (ordre trié)."""
    order = _order(bqm)
    pos = {v: k for k, v in enumerate(order)}
    lin = np.array([bqm.get_linear(v) for v in order], dtype=float)
    neg = np.zeros(len(order))
    plus = np.zeros(len(order))
    for (u, v), b in bqm.quadratic.items():
        for w in (u, v):
            if b < 0:
                neg[pos[w]] += b
            else:
                plus[pos[w]] += b
    return np.maximum(-lin - neg, lin + plus)


def _max_abs(bqm: dimod.BinaryQuadraticModel) -> float:
    lin = np.abs(np.fromiter(bqm.linear.values(), float, bqm.num_variables)).max(initial=0.0)
    quad = np.abs(np.fromiter(bqm.quadratic.values(), float, bqm.num_interactions)).max(initial=0.0)
    return float(max(lin, quad))
