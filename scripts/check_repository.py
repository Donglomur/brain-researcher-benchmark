#!/usr/bin/env python3
"""Verify current source ownership; --write explicitly rebuilds its inventory."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("neurobench_repository_checks", ROOT / "src/neurobench/repository_checks.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == "__main__":
    raise SystemExit(module.main())
