#!/usr/bin/env python3
"""Score arbitrary submitted artifacts; candidate source is never executed."""
import hashlib
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SHARED=ROOT/'authoring/delivery-integration-native-v1'
PINS={'runner.py': '93fb99e2558e0a27832344d866778adcb0a8716507a908d20818a1a4021cdc04', 'runtime_helpers.py': '7aa4b34865a4ed70063df6ea6af51dd8242af880c7fd77f9aedf4b994db8a6c0', 'worker.py': 'd6b1348cf0db6a4a3967cca086ab29a62b152c97d96d2526e408ed47e4a931d1'}
for name,expected in PINS.items():
    if hashlib.sha256((SHARED/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Changed trusted scoring implementation')
sys.path.insert(0,str(SHARED))
from runner import main
if __name__=='__main__':raise SystemExit(main(HERE))
