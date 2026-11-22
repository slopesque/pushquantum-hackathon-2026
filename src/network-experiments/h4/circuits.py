"""H4 : circuits QAOA faisables par construction (Dicke par ligne + mixer XY par ligne).

Variables dans l'ordre ``qt.all_arcs(n)`` : la ligne i (arcs ``(i, j)``, j ≠ i) occupe les qubits
contigus ``i*(n-1) … i*(n-1)+n-2``. Chaque ligne doit contenir exactement 2 uns (degré sortant 2).

- ``DickeRowsState`` : ⊗_blocs |D_k^{(m)}⟩, préparé bloc par bloc avec ``DickeState`` de Divi
  (Bärtschi & Eidenbenz 2019, exact), composé sur les qubits du bloc.
- Mixer XY par ligne : ``build_block_xy_mixer_edges(..., connectivity="ring")`` + ``xy_mixer``.
  **Choix de l'anneau** : O(m) termes par ligne au lieu de O(m²) (11 contre 55 arêtes par ligne sur
  network12), donc des circuits bien moins profonds à simuler ; c'est aussi le mixer du portefeuille
  de Divi et celui du service de caractérisation. L'anneau connecte tout le sous-espace de poids k
  d'une ligne, comme le graphe complet. Chaque arête applique ``exp(-iβ(XX+YY)/2)`` (XX et YY
  commutent sur une même paire), qui conserve le poids : la trotterisation garde la contrainte exacte.
- ``DickeRowsProblem`` : ``BinaryOptimizationProblem`` dont le coût est le BQM fourni (objectif du
  kit + λ·pénalité des degrés entrants), le mixer XY par ligne et l'état initial ``DickeRowsState``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import dimod
from divi.hamiltonians import xy_mixer
from divi.qprog.initial_states import DickeState, InitialState, build_block_xy_mixer_edges
from divi.qprog.problems import BinaryOptimizationProblem
from qiskit.circuit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp

from hackathon.referee import qt

Connectivity = Literal["complete", "path", "ring"]


def row_blocks(n_rows: int, row_len: int) -> list[list[int]]:
    """Blocs de qubits contigus : ``[[0..row_len-1], [row_len..2*row_len-1], …]``."""
    return [list(range(r * row_len, (r + 1) * row_len)) for r in range(n_rows)]


class DickeRowsState(InitialState):
    """Produit de |D_k^{(m)}⟩ sur des blocs de qubits (``blocks``), poids ``k`` par bloc.

    Les qubits hors blocs restent à |0⟩.
    """

    def __init__(self, blocks: Sequence[Sequence[int]], hamming_weight: int = 2):
        self.blocks = [list(map(int, b)) for b in blocks]
        self.hamming_weight = int(hamming_weight)
        flat = [q for b in self.blocks for q in b]
        if len(flat) != len(set(flat)):
            raise ValueError("les blocs se chevauchent")
        for b in self.blocks:
            if not 0 <= self.hamming_weight <= len(b):
                raise ValueError(f"poids {self.hamming_weight} impossible sur un bloc de {len(b)}")

    def build(self, wires: Sequence) -> QuantumCircuit:
        n_wires = len(wires)
        qc = QuantumCircuit(n_wires)
        for b in self.blocks:
            if max(b) >= n_wires:
                raise ValueError(f"bloc {b} hors des {n_wires} fils")
            sub = DickeState(self.hamming_weight, n_qubits=len(b)).build(range(len(b)))
            qc.compose(sub, qubits=b, inplace=True)
        return qc


def row_xy_mixer(
    blocks: Sequence[Sequence[int]], n_qubits: int, connectivity: Connectivity = "ring"
) -> SparsePauliOp:
    """Mixer XY intra-bloc (``0.5 Σ (XX + YY)`` sur les arêtes de chaque bloc)."""
    edges: list[tuple[int, int]] = []
    for b in blocks:
        edges += build_block_xy_mixer_edges(len(b), 1, list(b), connectivity=connectivity)
    return xy_mixer(edges, n_qubits=n_qubits)


def _penalty_side(n: int, side: int) -> dimod.BinaryQuadraticModel:
    arcs = qt.all_arcs(n)
    bqm = dimod.BinaryQuadraticModel({v: 0.0 for v in range(len(arcs))}, {}, 0.0, dimod.BINARY)
    for node in range(n):
        terms = [(v, 1) for v, a in enumerate(arcs) if a[side] == node]
        bqm.add_linear_equality_constraint(terms, 1.0, -2)
    return bqm


def in_degree_penalty(n: int) -> dimod.BinaryQuadraticModel:
    """``Σ_j (indeg_j − 2)²`` sur les variables ``qt.all_arcs(n)``."""
    return _penalty_side(n, 1)


def out_degree_penalty(n: int) -> dimod.BinaryQuadraticModel:
    """``Σ_i (outdeg_i − 2)²`` sur les variables ``qt.all_arcs(n)``."""
    return _penalty_side(n, 0)


def ordered_bqm(bqm: dimod.BinaryQuadraticModel) -> dimod.BinaryQuadraticModel:
    """Copie BINARY, variables 0..N-1 insérées dans l'ordre (qubit i = variable i)."""
    n = bqm.num_variables
    if set(bqm.variables) != set(range(n)):
        raise ValueError("le BQM doit avoir pour variables les entiers 0..N-1")
    src = bqm.change_vartype(dimod.BINARY, inplace=False)
    out = dimod.BinaryQuadraticModel(dimod.BINARY)
    out.add_variables_from((v, src.get_linear(v)) for v in range(n))
    out.add_quadratic_from(src.iter_quadratic())
    out.offset = src.offset
    return out


class DickeRowsProblem(BinaryOptimizationProblem):
    """QAOA sous contrainte de poids par bloc (modèle : ``PortfolioSelectionProblem`` de Divi).

    ``bqm`` : coût complet (variables 0..N-1) ; la contrainte de poids des blocs n'y figure pas (elle
    est imposée par l'état initial et le mixer). ``blocks`` couvre tous les qubits.
    """

    def __init__(
        self,
        bqm: dimod.BinaryQuadraticModel,
        blocks: Sequence[Sequence[int]],
        hamming_weight: int = 2,
        connectivity: Connectivity = "ring",
    ):
        bqm = ordered_bqm(bqm)
        super().__init__(bqm)
        self._blocks = [list(b) for b in blocks]
        self._weight = int(hamming_weight)
        self._connectivity: Connectivity = connectivity
        nq = self._ising.n_qubits
        if nq != bqm.num_variables:
            raise RuntimeError(f"{nq} qubits pour {bqm.num_variables} variables")
        idx = self._canonical_problem.variable_to_idx
        if any(idx[v] != v for v in range(nq)):
            raise RuntimeError("ordre des qubits différent de l'ordre des variables")
        if sorted(q for b in self._blocks for q in b) != list(range(nq)):
            raise ValueError("les blocs doivent couvrir exactement les qubits 0..N-1")

    @property
    def mixer_hamiltonian(self) -> SparsePauliOp:
        if self._mixer_cache is None:
            self._mixer_cache = row_xy_mixer(self._blocks, self._ising.n_qubits, self._connectivity)
        return self._mixer_cache

    @property
    def recommended_initial_state(self) -> InitialState:
        return DickeRowsState(self._blocks, self._weight)
