"""Adaptateur PCE (Divi 0.16.2) vers l'interface ``Sampler`` de la boucle H1.

Même recette que le notebook ``references/02_network_design.ipynb`` (§1.3) : BQM normalisé,
``PCE(BinaryOptimizationProblem(bqm_n), PolyEncoding(), SoftObjective(alpha), MonteCarloOptimizer)``,
puis ``get_top_solutions(sort_by="energy")``.

Ordre des bits : ``SolutionEntry.bitstring`` est la solution QUBO *décodée* (une lettre par variable,
pas l'état des qubits), dans l'ordre des variables du BQM passé à ``BinaryOptimizationProblem``. On
construit donc ``bqm_n`` avec les variables insérées dans l'ordre 0..N-1 ; le test
``test_bitstring_order_matches_bqm_energy`` le vérifie en recalculant l'énergie avec ``bqm.energy``.
"""

from __future__ import annotations

import dimod
import numpy as np

from h1.samplers import SampleBatch, Sampler

_ENCODINGS = ("poly", "dense")


def pce_n_qubits(n_vars: int, encoding: str) -> int:
    """Qubits du circuit PCE pour ``n_vars`` variables (formule de Divi, sans rien exécuter).

    ``poly`` : plus petit q tel que q(q+1)/2 ≥ N ; ``dense`` : ⌈log2(N+1)⌉.
    """
    return _make_encoding(encoding).min_qubits(int(n_vars))


def _make_encoding(encoding: str):
    from divi.qprog.algorithms import DenseEncoding, PolyEncoding

    if encoding == "poly":
        return PolyEncoding()
    if encoding == "dense":
        return DenseEncoding()
    raise ValueError(f"encoding doit être l'un de {_ENCODINGS}, reçu {encoding!r}")


def _make_backend(use_cloud: bool, shots: int, simulator_cluster: str | None):
    from hackathon.utils import make_backend

    if not use_cloud or simulator_cluster is None:
        return make_backend(use_cloud=use_cloud, shots=shots)
    # Cluster explicite (``qoro_maestro``, ``qoro_cpu``, ``qoro_gpu``) : make_backend fixe qoro_maestro.
    from divi.backends import JobConfig, QoroService

    from hackathon.utils import has_api_key

    if not has_api_key():
        raise RuntimeError("use_cloud=True demande QORO_API_KEY (fichier .env)")
    return QoroService(job_config=JobConfig(shots=shots, simulator_cluster=simulator_cluster))


def _ordered_copy(bqm: dimod.BinaryQuadraticModel) -> dimod.BinaryQuadraticModel:
    """Copie BINARY du BQM, variables insérées dans l'ordre 0..N-1 (contrat de ``Sampler``)."""
    n = bqm.num_variables
    if set(bqm.variables) != set(range(n)):
        raise ValueError("le BQM doit avoir pour variables les entiers 0..N-1")
    src = bqm.change_vartype(dimod.BINARY, inplace=False)
    out = dimod.BinaryQuadraticModel(dimod.BINARY)
    out.add_variables_from((v, src.get_linear(v)) for v in range(n))
    out.add_quadratic_from(src.iter_quadratic())
    out.offset = src.offset
    return out


def make_pce_sampler(
    *,
    use_cloud: bool = False,
    encoding: str = "poly",
    n_layers: int = 2,
    population: int = 20,
    iterations: int = 5,
    alpha: float = 2.0,
    shots: int = 10_000,
    top_n: int = 100,
    max_local_qubits: int = 24,
    simulator_cluster: str | None = None,
) -> Sampler:
    """Sampler PCE : ``sample(bqm, seed) -> SampleBatch`` (top ``top_n`` par énergie).

    En local (``use_cloud=False``), lève ``ValueError`` *avant* toute exécution si le circuit
    dépasse ``max_local_qubits`` qubits. ``simulator_cluster`` n'est utilisé qu'en cloud (sinon le
    cluster par défaut de ``make_backend`` : ``qoro_maestro``).
    """
    _make_encoding(encoding)  # valide le nom tout de suite

    def sample(bqm: dimod.BinaryQuadraticModel, seed: int) -> SampleBatch:
        from divi.qprog.algorithms import PCE, SoftObjective
        from divi.qprog.optimizers import MonteCarloOptimizer
        from divi.qprog.problems import BinaryOptimizationProblem

        n = bqm.num_variables
        n_qubits = pce_n_qubits(n, encoding)
        if not use_cloud and n_qubits > max_local_qubits:
            raise ValueError(
                f"PCE {encoding} sur {n} variables = {n_qubits} qubits > {max_local_qubits} "
                "(aucun circuit > 24 qubits en local) : passer en 'dense' ou au cloud"
            )
        bqm_n = _ordered_copy(bqm)
        bqm_n.normalize()
        pce = PCE(
            BinaryOptimizationProblem(bqm_n),
            encoding=_make_encoding(encoding),
            objective=SoftObjective(alpha=alpha),
            n_layers=n_layers,
            optimizer=MonteCarloOptimizer(population_size=population),
            max_iterations=iterations,
            backend=_make_backend(use_cloud, shots, simulator_cluster),
            seed=int(seed),
        )
        if pce.n_qubits != n_qubits:  # garde-fou : la formule doit suivre Divi
            raise RuntimeError(f"n_qubits Divi {pce.n_qubits} != calculé {n_qubits}")
        pce.run()
        tops = pce.get_top_solutions(n=top_n, min_prob=0.0, sort_by="energy")
        if tops:
            samples = np.array([[c == "1" for c in s.bitstring] for s in tops], dtype=np.uint8)
        else:
            samples = np.zeros((0, n), dtype=np.uint8)
        probs = np.array([s.prob for s in tops], dtype=float)
        return SampleBatch(
            samples=samples,
            probs=probs,
            n_circuits=int(pce.total_circuit_count),
            n_qubits=int(pce.n_qubits),
            backend="qoro_cloud" if use_cloud else "maestro_local",
        )

    return sample
