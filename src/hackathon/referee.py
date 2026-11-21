"""Accès à l'arbitre officiel ``references/qoblib_tools.py``, sans le copier ni le modifier.

Usage::

    from hackathon.referee import qt
    model = qt.PortfolioModel(qt.load_portfolio_instance("po_a010_t10_orig"), budget=4, lam=1e-4)
"""

import sys
from pathlib import Path

REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"

if str(REFERENCES_DIR) not in sys.path:
    sys.path.insert(0, str(REFERENCES_DIR))

import qoblib_tools as qt

__all__ = ["REFERENCES_DIR", "qt"]
