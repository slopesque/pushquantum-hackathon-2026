"""Rend le meilleur run (score minimal) : ``.sol`` vérifié par l'arbitre puis ``save_run``.

``PYTHONPATH=src/network-experiments uv run python -m h0.save_best --hypothesis h0
--instance network12 [--method …] [--seeds …]``
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .harness import save_solution
from .report import filter_records, load_records


def best_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in records if r.get("score") is not None and r.get("best_arcs")]
    if not scored:
        raise SystemExit("aucun record avec score parmi la sélection")
    return min(scored, key=lambda r: r["score"])


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(prog="h0.save_best", description=__doc__)
    parser.add_argument("--hypothesis", nargs="+", default=["h0"])
    parser.add_argument("--instance", required=True)
    parser.add_argument("--method", nargs="+", default=None)
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    args = parser.parse_args(argv)
    records = filter_records(load_records(args.hypothesis), args.instance, args.method, args.seeds)
    rec = best_record(records)
    path = save_solution(rec)
    print(
        f"{rec['instance']} {rec['method']} seed={rec['seed']} score={rec['score']} "
        f"gap={rec['gap'] * 100:+.2f}% → {path}"
    )
    return path


if __name__ == "__main__":
    main()
