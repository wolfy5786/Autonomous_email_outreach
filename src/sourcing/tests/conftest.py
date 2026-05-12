"""Ensure ``discovery`` and ``shared`` packages resolve when running pytest from the repo root."""

from __future__ import annotations

import sys
from pathlib import Path

# Mirrors sourcing Docker layout: ``PYTHONPATH=/app:/app/sourcing`` (``src`` + ``src/sourcing``).
_ROOT = Path(__file__).resolve().parents[3]
_SRC = _ROOT / "src"
for _p in (_SRC, _SRC / "sourcing"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)
