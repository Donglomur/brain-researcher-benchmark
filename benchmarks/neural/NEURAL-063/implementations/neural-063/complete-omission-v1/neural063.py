#!/usr/bin/env python3
"""NEURAL-063 source inspection and explicitly authorized stage interface."""
from pathlib import Path
import sys

# Also works for the isolated trusted-worker Python invocation (-I). The source
# closure is authenticated by its trusted parent before launching this script.
sys.path.insert(0, str(Path(__file__).absolute().parent))
from owner.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
