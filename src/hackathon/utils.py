"""Helpers communs : clé API, backend Divi, enregistrement des résultats."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results"

load_dotenv(ROOT / ".env")


def has_api_key() -> bool:
    return bool(os.environ.get("QORO_API_KEY"))


def make_backend(use_cloud: bool = False, shots: int = 10_000, force_sampling: bool = False):
    """Même logique que le notebook 00 : Maestro en local, ou le cloud Qoro (consomme des crédits)."""
    from divi.backends import JobConfig, MaestroSimulator, QoroService

    if use_cloud:
        if not has_api_key():
            raise RuntimeError("use_cloud=True demande QORO_API_KEY (fichier .env)")
        return QoroService(
            job_config=JobConfig(
                shots=shots, simulator_cluster="qoro_maestro", force_sampling=force_sampling
            )
        )
    return MaestroSimulator(shots=shots, force_sampling=force_sampling)


def git_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        dirty = subprocess.run(["git", "diff", "--quiet"], check=False, cwd=ROOT).returncode != 0
        return out.stdout.strip() + ("-dirty" if dirty else "")
    except OSError:
        return "unknown"


def gap(score: float, best_known: float) -> float:
    """Gap officiel : (score - best) / |best|. 0 = égalité, négatif = record battu."""
    return (score - best_known) / abs(best_known)


def save_run(problem: str, sol_name: str, sol_text: str, metadata: dict[str, Any]) -> Path:
    """Écrit ``results/<problem>/<timestamp>_<sol_name>`` (.sol) et son ``.json`` de métadonnées.

    ``metadata`` doit contenir au minimum : instance, n_vars, max_qubits, score, best_known,
    method, params, seed. On y ajoute gap, git hash et date.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = RESULTS_DIR / problem
    out_dir.mkdir(parents=True, exist_ok=True)
    sol_path = out_dir / f"{stamp}_{sol_name}"
    sol_path.write_text(sol_text)
    meta = dict(metadata)
    if "score" in meta and meta.get("best_known") is not None:
        meta["gap"] = gap(meta["score"], meta["best_known"])
    meta.update(git=git_hash(), timestamp=stamp, sol_file=sol_path.name)
    sol_path.with_suffix(".json").write_text(json.dumps(meta, indent=2, default=str))
    return sol_path
