"""Interface commune des échantillonneurs de la boucle H1 (SA classique, PCE quantique).

Un ``Sampler`` est un callable ``sampler(bqm, seed) -> SampleBatch``. Le BQM a pour variables les
entiers ``0..N-1`` dans l'ordre de ``qt.all_arcs(n)``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import dimod
import numpy as np


@dataclass
class SampleBatch:
    samples: np.ndarray
    """Bits bruts (avant repair), forme ``(r, N)``, dtype ``uint8``, colonnes = variables 0..N-1."""
    probs: np.ndarray | None = None
    """Probabilités des échantillons (PCE, QAOA) ; ``None`` pour SA (poids uniformes)."""
    n_circuits: int = 0
    n_qubits: int = 0
    backend: str = "none"
    """``"none"``, ``"maestro_local"`` ou ``"qoro_cloud"``."""


Sampler = Callable[[dimod.BinaryQuadraticModel, int], SampleBatch]


def sa_sampler(num_reads: int = 100) -> Sampler:
    """SA de dwave-samplers, ``num_reads`` lectures, graine fournie par l'appelant."""
    from dwave.samplers import SimulatedAnnealingSampler

    sa = SimulatedAnnealingSampler()

    def sample(bqm: dimod.BinaryQuadraticModel, seed: int) -> SampleBatch:
        ss = sa.sample(bqm, num_reads=num_reads, seed=int(seed) % (2**32))
        pos = {v: k for k, v in enumerate(ss.variables)}
        idx = [pos[v] for v in range(bqm.num_variables)]
        return SampleBatch(samples=np.asarray(ss.record.sample, dtype=np.uint8)[:, idx])

    return sample
