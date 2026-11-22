"""CLI des runs H0.

``PYTHONPATH=src/network-experiments uv run python -m h0.run --instance network12 --seed 0 1 2
--method b1_sa_kit [--max-lp-calls N] [--time-limit S] [--no-write] [--save-sol]``
"""

from __future__ import annotations

import argparse
from typing import Any

from .baselines import METHODS
from .harness import run_method, save_solution


def format_summary(record: dict[str, Any]) -> str:
    score = record["score"]
    gap = record["gap"]
    fm = record.get("feasible_mass")
    return (
        f"{record['instance']} {record['method']} seed={record['seed']} "
        f"score={score if score is not None else '-'} "
        f"gap={f'{gap * 100:+.2f}%' if gap is not None else '-'} "
        f"lp_calls={record['lp_calls']} wall_time_s={record['wall_time_s']} "
        f"feasible_mass={f'{fm:.4f}' if fm is not None else '-'}"
    )


def main(argv: list[str] | None = None) -> list[dict[str, Any]]:
    parser = argparse.ArgumentParser(prog="h0.run", description=__doc__)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--seed", type=int, nargs="+", default=[0])
    parser.add_argument("--method", required=True, choices=sorted(METHODS))
    parser.add_argument("--max-lp-calls", type=int, default=None)
    parser.add_argument("--time-limit", type=float, default=None)
    parser.add_argument("--no-write", action="store_true", help="ne pas écrire la ligne JSONL")
    parser.add_argument("--save-sol", action="store_true", help="save_run du meilleur .sol")
    args = parser.parse_args(argv)

    records = []
    for seed in args.seed:
        record = run_method(
            "h0",
            args.method,
            METHODS[args.method],
            args.instance,
            seed,
            max_lp_calls=args.max_lp_calls,
            time_limit_s=args.time_limit,
            write=not args.no_write,
        )
        print(format_summary(record), flush=True)
        if args.save_sol and record["score"] is not None:
            print(f"  .sol : {save_solution(record)}", flush=True)
        records.append(record)
    return records


if __name__ == "__main__":
    main()
