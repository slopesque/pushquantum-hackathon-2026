"""Instances QOBLIB 08 : meilleurs connus et budgets (``docs/network/metrics.md`` §2 et §5)."""

from __future__ import annotations

import numpy as np

from hackathon.referee import qt

BEST_KNOWN: dict[int, int] = {
    5: 65_500, 6: 101_000, 7: 142_400, 8: 170_231, 9: 196_750, 10: 210_800, 11: 238_334,
    12: 276_474, 13: 300_620, 14: 343_091, 15: 370_870, 16: 397_908, 17: 437_000,
    18: 473_375, 19: 492_924, 20: 528_528, 21: 569_273, 22: 618_135, 23: 659_369,
    24: 663_688,
}  # fmt: skip


def n_nodes(instance: str) -> int:
    """``"network12"`` → 12."""
    if not instance.startswith("network"):
        raise ValueError(f"instance network inconnue : {instance}")
    n = int(instance.removeprefix("network"))
    if n not in BEST_KNOWN:
        raise ValueError(f"instance network inconnue : {instance}")
    return n


def instance_name(n: int) -> str:
    return f"network{n:02d}"


def budget(instance: str) -> tuple[int, float]:
    """``(budget LP, plafond de temps en s)`` de la tranche de l'instance (metrics.md §2)."""
    n = n_nodes(instance)
    if n <= 8:
        return 500, 120.0
    if n <= 12:
        return 5_000, 600.0
    if n <= 18:
        return 8_000, 1_200.0
    return 10_000, 1_800.0


def best_known(instance: str) -> int:
    return BEST_KNOWN[n_nodes(instance)]


def load_demand(instance: str) -> np.ndarray:
    return qt.load_network_demand(n_nodes(instance))
