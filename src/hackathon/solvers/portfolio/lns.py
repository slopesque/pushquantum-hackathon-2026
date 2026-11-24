"""Recherche à grand voisinage (LNS) avec sous-problèmes en QUBO (piste P7).

Principe (formalisé dans ``formalisations/portfolio/lns.typ``) :

1. partir d'une bonne solution (recherche locale P4) ;
2. choisir une **fenêtre** : quelques actions × quelques jours consécutifs ;
3. **fixer le signe** σ de chaque case de la fenêtre et écrire la **quantité** ``m ∈ {0..3}`` sur 2 bits
   (``m = b0 + 2·b1``), le reste de la solution étant figé : le sous-problème devient un QUBO de
   ``2 × (nombre de cases)`` variables ;
4. le résoudre avec un **sous-solveur** : énumération exacte, recuit simulé, QAOA ou PCE (Divi) ;
5. décoder les meilleurs candidats, les **réparer** s'ils violent une contrainte, et **accepter** le meilleur
   seulement s'il améliore l'objectif exact (évaluateur P2) ;
6. recommencer avec une autre fenêtre.

Le QUBO est une approximation (frais entre deux jours de même signe, contraintes en pénalité) ; la décision
d'accepter repose toujours sur l'objectif exact, donc la solution courante reste exacte et faisable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import dimod
import numpy as np

from hackathon.solvers.portfolio.evaluator import Change, PortfolioState
from hackathon.solvers.portfolio.local_search import _terms, hedge_partners

# ════════════════════════════════════════════════════════════════════════
# Fenêtres
# ════════════════════════════════════════════════════════════════════════


@dataclass
class Window:
    """Les cases libérées ``(t, i)`` et le signe σ imposé à chacune (+1 long, -1 court)."""

    cells: list[tuple[int, int]]
    signs: np.ndarray

    @property
    def size(self) -> int:
        return len(self.cells)

    @property
    def n_bits(self) -> int:
        return 2 * self.size


def choose_signs(
    state: PortfolioState, cells: list[tuple[int, int]], rng, flip: float
) -> np.ndarray:
    """Signe de chaque case : celui de la position actuelle si elle est non nulle ; sinon le sens dans
    lequel ajouter une unité coûte le moins (variation exacte d'un mouvement simple). Avec une probabilité
    ``flip``, le signe est inversé, pour explorer."""
    terms = _terms(state)
    signs = np.empty(len(cells), dtype=np.int64)
    for k, (t, i) in enumerate(cells):
        v = state.v[t, i]
        if v != 0:
            s = int(np.sign(v))
        else:
            up = terms.base[0][t, i] + terms.fee_in[0][t, i] + terms.fee_out[0][t, i]
            down = terms.base[1][t, i] + terms.fee_in[1][t, i] + terms.fee_out[1][t, i]
            s = 1 if up <= down else -1
        if rng.random() < flip:
            s = -s
        signs[k] = s
    return signs


class WindowSampler:
    """Tire des fenêtres ``n_assets`` actions × ``n_days`` jours consécutifs.

    Stratégies :

    * ``"wide"`` (défaut) : jusqu'à ``n_assets`` actions sur ``n_days`` jours — d'abord celles détenues ces
      jours-là, puis celles qu'il serait le plus intéressant d'ajouter (meilleure variation d'un mouvement
      simple), puis des actions au hasard. Avec ``n_assets >= n``, la fenêtre couvre *tout le portefeuille*
      sur ces jours : c'est la forme qui marche (voir ``lns.typ``) ;
    * ``"random"`` : actions au hasard ;
    * ``"hedge"`` : une action « graine » (de préférence déjà détenue) et des partenaires de couverture
      tirés dans ses listes corrélées / anti-corrélées (P4) ;
    * ``"mixed"`` : alterne ``"hedge"`` et ``"random"``.
    """

    def __init__(
        self,
        state: PortfolioState,
        n_assets: int,
        n_days: int | tuple[int, ...],
        strategy: str = "wide",
    ):
        p = state.problem
        self.n_assets = min(n_assets, p.n)
        choices = (n_days,) if isinstance(n_days, int) else tuple(n_days)
        self.day_choices = tuple(
            min(d, p.T) for d in choices
        )  # une longueur tirée à chaque fenêtre
        self.strategy = strategy
        self.partners = hedge_partners(p, 15) if p.n > 1 else None
        self._count = 0

    def sample(self, state: PortfolioState, rng: np.random.Generator) -> list[tuple[int, int]]:
        p = state.problem
        n_days = int(rng.choice(self.day_choices))
        t0 = int(rng.integers(0, p.T - n_days + 1))
        days = range(t0, t0 + n_days)
        strategy = self.strategy
        if strategy == "wide":
            return [(t, i) for i in self._wide_assets(state, days, rng) for t in days]
        if strategy == "mixed":
            strategy = ("hedge", "random")[self._count % 2]
        self._count += 1
        if strategy == "hedge" and self.partners is not None and self.n_assets > 1:
            held = np.flatnonzero(np.abs(state.v[t0 : t0 + n_days]).sum(axis=0))
            seed = (
                int(rng.choice(held))
                if len(held) and rng.random() < 0.7
                else int(rng.integers(p.n))
            )
            pool = np.unique(np.concatenate([self.partners[0][seed], self.partners[1][seed]]))
            pool = pool[pool != seed]
            others = rng.choice(pool, size=min(self.n_assets - 1, len(pool)), replace=False)
            assets = [seed, *map(int, others)]
        else:
            assets = list(map(int, rng.choice(p.n, size=self.n_assets, replace=False)))
        return [(t, i) for i in sorted(assets) for t in days]

    def _wide_assets(
        self, state: PortfolioState, days: range, rng: np.random.Generator
    ) -> list[int]:
        p = state.problem
        if self.n_assets >= p.n:
            return list(range(p.n))
        block = state.v[days.start : days.stop]
        held = list(np.flatnonzero(np.abs(block).sum(axis=0)))
        rng.shuffle(held)
        chosen = held[: self.n_assets]
        if len(chosen) < self.n_assets:
            terms = _terms(state)
            gain = (
                np.minimum(
                    terms.base[0] + terms.fee_in[0] + terms.fee_out[0],
                    terms.base[1] + terms.fee_in[1] + terms.fee_out[1],
                )[days.start : days.stop]
                .min(axis=0)
                .astype(float)
            )
            gain[chosen] = np.inf
            n_best = (
                self.n_assets - len(chosen) + 1
            ) // 2  # moitié par attractivité, moitié au hasard
            best = list(np.argsort(gain)[:n_best])
            chosen += best
            rest = np.setdiff1d(np.arange(p.n), chosen)
            chosen += list(rng.choice(rest, size=self.n_assets - len(chosen), replace=False))
        return sorted(int(i) for i in chosen)


# ════════════════════════════════════════════════════════════════════════
# Le QUBO d'une fenêtre
# ════════════════════════════════════════════════════════════════════════


@dataclass
class WindowQUBO:
    """Sous-problème d'une fenêtre, en quantités ``m`` puis en bits.

    En quantités : ``E(m) = offset + h·m + mᵀ J m`` (``J`` symétrique, diagonale comprise), qui vaut la
    variation de l'objectif quand les cases de la fenêtre prennent les valeurs ``v = σ·m`` — exactement,
    sauf deux approximations documentées (frais entre cases de même signe, pénalités). ``h_pen`` et
    ``J_pen`` portent les pénalités des contraintes, séparées pour pouvoir les mesurer.
    """

    window: Window
    offset: float
    h: np.ndarray
    J: np.ndarray
    h_pen: np.ndarray
    J_pen: np.ndarray

    def objective_energy(self, m: np.ndarray) -> float:
        """Variation approchée de l'objectif (sans pénalité) pour des quantités ``m``."""
        return float(self.offset + self.h @ m + m @ self.J @ m)

    def energy(self, m: np.ndarray) -> float:
        """Énergie du QUBO (objectif approché + pénalités)."""
        return self.objective_energy(m) + float(self.h_pen @ m + m @ self.J_pen @ m)

    # ── passage aux bits : m_c = b_{2c} + 2·b_{2c+1} ─────────────────────

    def _expansion(self) -> np.ndarray:
        K = self.window.size
        P = np.zeros((K, 2 * K))
        P[np.arange(K), 2 * np.arange(K)] = 1.0
        P[np.arange(K), 2 * np.arange(K) + 1] = 2.0
        return P

    def bits_matrices(self) -> tuple[np.ndarray, np.ndarray]:
        """``(linéaire, quadratique triangulaire supérieure)`` du QUBO en bits (``b_j² = b_j``)."""
        P = self._expansion()
        h = P.T @ (self.h + self.h_pen)
        M = P.T @ (self.J + self.J_pen) @ P
        linear = h + np.diag(M)
        quad = np.triu(2 * M, k=1)
        return linear, quad

    def to_bqm(self) -> dimod.BinaryQuadraticModel:
        """BQM dimod, variables ``0 … 2K-1`` dans cet ordre (indispensable pour lire les sorties de Divi)."""
        linear, quad = self.bits_matrices()
        rows, cols = np.nonzero(quad)
        return dimod.BinaryQuadraticModel.from_numpy_vectors(
            linear, (rows, cols, quad[rows, cols]), self.offset, dimod.BINARY
        )

    def bits_to_m(self, bits: np.ndarray) -> np.ndarray:
        b = np.asarray(bits, dtype=np.int64).reshape(-1, 2)
        return b[:, 0] + 2 * b[:, 1]

    def changes(self, state: PortfolioState, m: np.ndarray) -> list[Change]:
        """Changements ``(t, i, d)`` qui donnent ``v = σ·m`` sur la fenêtre."""
        out = []
        for (t, i), s, mc in zip(self.window.cells, self.window.signs, m, strict=True):
            d = int(s * mc - state.v[t, i])
            if d:
                out.append((t, i, d))
        return out


def build_window_qubo(
    state: PortfolioState, window: Window, penalty_scale: float = 1.0
) -> WindowQUBO:
    """Construit le QUBO d'une fenêtre (voir ``lns.typ`` pour le détail de chaque terme)."""
    p, v = state.problem, state.v
    T = p.T
    K = window.size
    cells, sig = window.cells, window.signs
    index = {cell: k for k, cell in enumerate(cells)}
    h = np.zeros(K)
    J = np.zeros((K, K))

    slope = p.interest[0]  # intérêts : I(c) = slope·c tant que 0 <= c <= 15 (poids 10·2^k)
    if any(w != slope * 2**k for k, w in enumerate(p.interest)):
        raise ValueError("intérêts non linéaires : cas non prévu")

    by_day: dict[int, list[int]] = {}
    for k, (t, _) in enumerate(cells):
        by_day.setdefault(t, []).append(k)

    for t, ks in by_day.items():
        assets = np.array([cells[k][1] for k in ks])
        s = sig[ks].astype(float)
        # Risque : risk(u + σm) - risk(u) = Σ σ_c m_c (G u)_c + mᵀ (σσᵀ ∘ R_sym) m, u = v_t hors fenêtre.
        Gu = state.Gv[t].astype(float).copy()
        for i in assets:
            Gu -= p.G[t, :, i] * v[t, i]
        h[ks] += s * Gu[assets]
        R_sym = (p.R[t][np.ix_(assets, assets)] + p.R[t][np.ix_(assets, assets)].T) / 2
        J[np.ix_(ks, ks)] += np.outer(s, s) * R_sym
        for k, i, sc in zip(ks, assets, s, strict=True):
            h[k] += -sc * p.ret[t, i]  # rendement
            h[k] += slope * sc  # intérêts : +10 par unité de position nette
            if sc < 0:
                h[k] += p.sc[t, i]  # coût du court
            if t == 0:
                h[k] += p.tc[0, i]  # achat initial
            if t == T - 1:
                h[k] += p.tc[T - 1, i]  # liquidation

    # Frais de transition t-1 → t, facturés pour 1 <= t <= T-2.
    for k, (t, i) in enumerate(cells):
        for a, b in ((t - 1, t), (t, t + 1)):  # transition (a → b) touchant la case
            if not (1 <= b <= T - 2) or a < 0:
                continue
            tc = p.tc[b, i]
            ka, kb = index.get((a, i)), index.get((b, i))
            if ka is not None and kb is not None:
                if k != kb:
                    continue  # transition interne : traitée une seule fois, depuis la case b
                if sig[ka] != sig[kb]:  # |m_a + m_b| exact
                    h[ka] += tc
                    h[kb] += tc
                else:  # |m_b - m_a| ≈ (m_b - m_a)², exact si l'écart est <= 1
                    J[ka, ka] += tc
                    J[kb, kb] += tc
                    J[ka, kb] -= tc
                    J[kb, ka] -= tc
            else:  # transition de bord : l'autre jour est figé à w
                w = v[b, i] if ka is not None else v[a, i]
                if w == 0 or np.sign(w) != sig[k]:  # |σm - w| = m + |w| : exact
                    h[k] += tc
                else:  # |m - |w|| ≈ (m - |w|)², exact si l'écart est <= 1
                    J[k, k] += tc
                    h[k] += -2 * abs(w) * tc

    # Pénalités des contraintes de chaque jour, seulement si elles peuvent être violées.
    mu = penalty_scale * max(1.0, float(np.abs(h).mean()))
    h_pen = np.zeros(K)
    J_pen = np.zeros((K, K))

    def add_penalty(ks: list[int], coef: np.ndarray, bound: float) -> None:
        """Pénalité μ·x(x+1) pour la contrainte ``x = coef·m - bound <= 0`` : nulle en x = 0 et x = -1."""
        J_pen[np.ix_(ks, ks)] += mu * np.outer(coef, coef)
        h_pen[ks] += mu * coef * (1 - 2 * bound)

    for t, ks in by_day.items():
        assets = [cells[k][1] for k in ks]
        s = sig[ks].astype(float)
        cur = v[t, assets]
        free_budget = p.budget - (state.total[t] - np.abs(cur).sum())
        if p.ub * len(ks) > free_budget:
            add_penalty(ks, np.ones(len(ks)), free_budget)
        net_out = state.net[t] - cur.sum()
        w_max = p.ub * (s > 0).sum()
        w_min = -p.ub * (s < 0).sum()
        if net_out + w_max > p.net_max:
            add_penalty(ks, s, p.net_max - net_out)
        if net_out + w_min < p.net_min:
            add_penalty(ks, -s, net_out - p.net_min)

    # Décalage : variation quand toute la fenêtre est mise à zéro (m = 0), avec des intérêts *linéaires*.
    # L'état m = 0 peut être infaisable (position nette hors bornes) : là, les intérêts exacts ne sont plus
    # linéaires (le slack déborde des 4 bits). On corrige pour rester cohérent avec les termes linéaires,
    # ce qui rend le QUBO exact pour toute affectation finale faisable.
    zero = [(t, i, -int(v[t, i])) for (t, i) in cells if v[t, i]]
    offset = float(state.delta(zero)[0]) if zero else 0.0
    for t, ks in by_day.items():
        slack0 = p.capital - (state.net[t] - sum(v[t, cells[k][1]] for k in ks))
        offset += float(p.interest_of_slack(slack0)) - slope * slack0
    return WindowQUBO(window, offset, h, J, h_pen, J_pen)


# ════════════════════════════════════════════════════════════════════════
# Sous-solveurs : QUBO → liste de candidats (tableaux de bits)
# ════════════════════════════════════════════════════════════════════════


@dataclass
class SubSolverInfo:
    """Ce qu'un sous-solveur rapporte : qubits utilisés et circuits exécutés (0 pour le classique)."""

    qubits: int = 0
    circuits: int = 0


class SubSolver:
    """Un sous-solveur : ``solver(qubo, rng)`` renvoie des candidats (tableaux de bits), du meilleur au pire."""

    def __init__(self) -> None:
        self.info = SubSolverInfo()

    def __call__(self, q: WindowQUBO, rng: np.random.Generator) -> list[np.ndarray]:
        raise NotImplementedError


class EnumSolver(SubSolver):
    """Énumère les ``2^(2K)`` affectations et renvoie les ``n_candidates`` d'énergie minimale."""

    def __init__(self, n_candidates: int = 20, max_bits: int = 22) -> None:
        super().__init__()
        self.n_candidates, self.max_bits = n_candidates, max_bits

    def __call__(self, q: WindowQUBO, rng: np.random.Generator) -> list[np.ndarray]:
        n = q.window.n_bits
        if n > self.max_bits:
            raise ValueError(f"énumération limitée à {self.max_bits} bits (ici {n})")
        linear, quad = q.bits_matrices()
        best_e = np.full(0, np.inf)
        best_x = np.zeros((0, n), dtype=np.int8)
        chunk = 1 << min(n, 16)
        for start in range(0, 1 << n, chunk):
            idx = np.arange(start, min(start + chunk, 1 << n))
            x = ((idx[:, None] >> np.arange(n)) & 1).astype(np.float64)
            e = x @ linear + np.einsum("bi,ij,bj->b", x, quad, x)
            keep = np.argsort(e)[: self.n_candidates]
            best_e = np.concatenate([best_e, e[keep]])
            best_x = np.concatenate([best_x, x[keep].astype(np.int8)])
            order = np.argsort(best_e)[: self.n_candidates]
            best_e, best_x = best_e[order], best_x[order]
        return list(best_x)


class SASolver(SubSolver):
    """Recuit simulé (dwave-samplers) sur le même QUBO : la référence classique du quantique."""

    def __init__(self, num_reads: int = 64, num_sweeps: int = 500, n_candidates: int = 20) -> None:
        super().__init__()
        from dwave.samplers import SimulatedAnnealingSampler

        self.sampler = SimulatedAnnealingSampler()
        self.num_reads, self.num_sweeps, self.n_candidates = num_reads, num_sweeps, n_candidates

    def __call__(self, q: WindowQUBO, rng: np.random.Generator) -> list[np.ndarray]:
        res = self.sampler.sample(
            q.to_bqm(),
            num_reads=self.num_reads,
            num_sweeps=self.num_sweeps,
            seed=int(rng.integers(2**31)),
        )
        rec = res.aggregate().record
        order = np.argsort(rec.energy)[: self.n_candidates]
        return [np.asarray(rec.sample[k], dtype=np.int8) for k in order]


class DiviSolver(SubSolver):
    """QAOA ou PCE (Divi) sur le QUBO de la fenêtre, sur le simulateur local ou le cloud Qoro.

    Les variables du BQM sont ``0 … 2K-1`` dans l'ordre ; pour PCE, on lit la solution décodée
    (``decoded``), pas la mesure brute des qubits (``bitstring``). Les candidats sont reclassés avec
    notre propre calcul d'énergie.
    """

    def __init__(
        self,
        routine: str = "qaoa",
        n_layers: int = 2,
        population: int = 20,
        iterations: int = 5,
        shots: int = 2000,
        n_candidates: int = 20,
        use_cloud: bool = False,
    ) -> None:
        super().__init__()
        if routine not in ("qaoa", "pce"):
            raise ValueError(f"routine inconnue : {routine}")
        self.routine, self.n_layers, self.population = routine, n_layers, population
        self.iterations, self.shots, self.n_candidates = iterations, shots, n_candidates
        self.use_cloud = use_cloud

    def __call__(self, q: WindowQUBO, rng: np.random.Generator) -> list[np.ndarray]:
        from divi.qprog.algorithms import PCE, QAOA, PolyEncoding, SoftObjective
        from divi.qprog.optimizers import MonteCarloOptimizer
        from divi.qprog.problems import BinaryOptimizationProblem

        from hackathon.utils import make_backend

        problem = BinaryOptimizationProblem(q.to_bqm())
        optimizer = MonteCarloOptimizer(population_size=self.population)
        backend = make_backend(use_cloud=self.use_cloud, shots=self.shots)
        seed = int(rng.integers(2**31))
        n = 4 * self.n_candidates
        if self.routine == "qaoa":
            prog = QAOA(
                problem,
                n_layers=self.n_layers,
                optimizer=optimizer,
                max_iterations=self.iterations,
                backend=backend,
                seed=seed,
            )
            prog.run()
            cands = [
                np.array([int(c) for c in s.bitstring], dtype=np.int8)
                for s in prog.get_top_solutions(n=n)
            ]
        else:
            prog = PCE(
                problem,
                encoding=PolyEncoding(),
                objective=SoftObjective(alpha=2.0),
                n_layers=self.n_layers,
                optimizer=optimizer,
                max_iterations=self.iterations,
                backend=backend,
                seed=seed,
            )
            prog.run()
            sols = prog.get_top_solutions(n=n, sort_by="energy", include_decoded=True)
            cands = [np.asarray(s.decoded, dtype=np.int8) for s in sols]
        self.info.qubits = max(self.info.qubits, int(getattr(prog, "n_qubits", q.window.n_bits)))
        self.info.circuits += int(prog.total_circuit_count)
        linear, quad = q.bits_matrices()
        energies = [float(x @ linear + x @ quad @ x) for x in (c.astype(float) for c in cands)]
        order = np.argsort(energies)[: self.n_candidates]
        return [cands[k] for k in order]


def enum_solver(n_candidates: int = 20, max_bits: int = 22) -> EnumSolver:
    return EnumSolver(n_candidates, max_bits)


def sa_solver(num_reads: int = 64, num_sweeps: int = 500, n_candidates: int = 20) -> SASolver:
    return SASolver(num_reads, num_sweeps, n_candidates)


def divi_solver(routine: str = "qaoa", **kwargs) -> DiviSolver:
    return DiviSolver(routine, **kwargs)


# ════════════════════════════════════════════════════════════════════════
# Réparation et boucle
# ════════════════════════════════════════════════════════════════════════


def repair(state: PortfolioState, q: WindowQUBO, m: np.ndarray) -> tuple[np.ndarray, int, bool]:
    """Rend faisable une affectation ``m`` en retirant des unités dans la fenêtre, une à la fois,
    en choisissant à chaque fois le retrait qui donne le meilleur objectif exact.
    Renvoie ``(m, variation exacte, faisable)``."""
    m = m.copy()
    delta, ok = state.delta(q.changes(state, m))
    while not ok and m.any():
        best = None
        for k in np.flatnonzero(m):
            m[k] -= 1
            d, f = state.delta(q.changes(state, m))
            m[k] += 1
            key = (not f, d)
            if best is None or key < best[0]:
                best = (key, k, d, f)
        assert best is not None
        _, k, delta, ok = best
        m[k] -= 1
    return m, delta, ok


@dataclass
class LNSStats:
    iterations: int = 0
    accepted: int = 0
    repaired: int = 0
    max_qubits: int = 0
    circuits: int = 0
    trace: list[tuple[float, int]] = field(default_factory=list)
    """Historique ``(temps écoulé en s, objectif)`` à chaque amélioration."""


def lns(
    state: PortfolioState,
    sub_solver: SubSolver,
    rng: np.random.Generator,
    time_limit: float = 60.0,
    n_assets: int = 50,
    n_days: int | tuple[int, ...] = (1, 2),
    strategy: str = "wide",
    flip: float = 0.1,
    penalty_scale: float = 1.0,
    max_iterations: int | None = None,
) -> LNSStats:
    """Boucle LNS (modifie ``state`` en place, qui reste exact et faisable)."""
    if not state.feasible:
        raise ValueError("le LNS doit partir d'une solution faisable")
    sampler = WindowSampler(state, n_assets, n_days, strategy)
    stats = LNSStats()
    start = time.perf_counter()
    stats.trace.append((0.0, state.objective))
    while time.perf_counter() - start < time_limit:
        if max_iterations is not None and stats.iterations >= max_iterations:
            break
        stats.iterations += 1
        cells = sampler.sample(state, rng)
        window = Window(cells, choose_signs(state, cells, rng, flip))
        q = build_window_qubo(state, window, penalty_scale)
        best: tuple[int, np.ndarray] | None = None
        for bits in sub_solver(q, rng):
            m, delta, ok = repair(state, q, q.bits_to_m(bits))
            if ok and (best is None or delta < best[0]):
                best = (delta, m)
        if best is not None and best[0] < 0:
            m = best[1]
            state.apply(q.changes(state, m))
            stats.accepted += 1
            stats.trace.append((time.perf_counter() - start, state.objective))
    stats.max_qubits, stats.circuits = sub_solver.info.qubits, sub_solver.info.circuits
    return stats
