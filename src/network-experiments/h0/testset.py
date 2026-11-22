"""Jeu de test figé (F1, F2 ; ``metrics.md`` §3) : topologies aléatoires + B1, avec leur score LP.

``PYTHONPATH=src/network-experiments uv run python -m h0.testset --instance network12``
→ ``results/network/testsets/network12.json``.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from hackathon.referee import qt
from hackathon.utils import RESULTS_DIR, git_hash

from .baselines import _b1_stream
from .instances import load_demand, n_nodes
from .scorer import Arc

TESTSET_DIR = RESULTS_DIR / "network" / "testsets"
MAX_RANDOM_TRIES_FACTOR = 50


def _path(instance: str, out_dir: Path | None) -> Path:
    return (out_dir if out_dir is not None else TESTSET_DIR) / f"{instance}.json"


def build_testset(
    instance: str = "network12",
    seed: int = 12345,
    n_random: int = 500,
    n_b1: int = 500,
    out_dir: Path | None = None,
) -> Path:
    """Construit et sauvegarde le jeu de test, renvoie le chemin du JSON.

    - ``n_random`` topologies ``qt.random_topology`` distinctes (``default_rng(seed)``) ;
    - ``n_b1`` topologies B1 (lots SA de ``b1_topologies``, seed ``seed``) distinctes et absentes
      de la partie aléatoire ;
    - score : ``qt.route_min_congestion(demand, arcs).objective``. Les topologies non routables
      (score ``inf``, graphe non fortement connexe) sont écartées et comptées dans ``meta``.
    """
    n = n_nodes(instance)
    demand = load_demand(instance)
    arcs_out: list[list[Arc]] = []
    scores: list[int] = []
    sources: list[str] = []
    seen: set[frozenset[Arc]] = set()
    skipped = {"random": 0, "b1": 0}

    def add(topo: list[Arc], source: str) -> bool:
        value = qt.route_min_congestion(demand, topo).objective
        if math.isinf(value):
            skipped[source] += 1
            return False
        arcs_out.append(sorted(topo))
        scores.append(int(value))
        sources.append(source)
        return True

    rng = np.random.default_rng(seed)
    got = tries = 0
    while got < n_random and tries < MAX_RANDOM_TRIES_FACTOR * max(n_random, 1):
        tries += 1
        topo = [(int(i), int(j)) for i, j in qt.random_topology(n, rng)]
        key = frozenset(topo)
        if key in seen:
            continue
        seen.add(key)
        got += add(topo, "random")

    got = 0
    if n_b1 > 0:
        for topo in _b1_stream(demand, seed, exclude=seen):
            got += add(topo, "b1")
            if got >= n_b1:
                break

    data = {
        "arcs": [[list(a) for a in topo] for topo in arcs_out],
        "score": scores,
        "source": sources,
        "meta": {
            "instance": instance,
            "seed": seed,
            "n_random": sources.count("random"),
            "n_b1": sources.count("b1"),
            "skipped_unroutable": skipped,
            "b1": {"sa_reads": 100, "penalty": 1.0, "batch_seed": "(seed * 1_000_003 + b) % 2**31"},
            "git": git_hash(),
        },
    }
    path = _path(instance, out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def load_testset(
    instance: str = "network12", out_dir: Path | None = None
) -> tuple[list[list[Arc]], np.ndarray]:
    """``(topologies, scores)`` du jeu de test sauvegardé."""
    data = json.loads(_path(instance, out_dir).read_text())
    topos = [[(int(i), int(j)) for i, j in topo] for topo in data["arcs"]]
    return topos, np.asarray(data["score"], dtype=np.int64)


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(prog="h0.testset", description=__doc__)
    parser.add_argument("--instance", default="network12")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--n-random", type=int, default=500)
    parser.add_argument("--n-b1", type=int, default=500)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    path = build_testset(args.instance, args.seed, args.n_random, args.n_b1, args.out_dir)
    data = json.loads(path.read_text())
    print(f"{path} : {len(data['score'])} topologies, meta={data['meta']}")
    return path


if __name__ == "__main__":
    main()
