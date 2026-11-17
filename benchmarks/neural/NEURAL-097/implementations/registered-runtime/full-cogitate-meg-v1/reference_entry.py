#!/usr/bin/env python3
"""Private future reference worker entry, never candidate-visible."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from n097.reference_worker import main
if __name__=="__main__":raise SystemExit(main())
