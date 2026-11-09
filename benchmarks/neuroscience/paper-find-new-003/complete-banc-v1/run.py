"""Portable complete BANC central entrypoint."""
import time
_WRAPPER_ORIGIN=(time.monotonic_ns(),time.time_ns())
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'runtime'))
from central.entry import main
if __name__=='__main__':raise SystemExit(main(origin=_WRAPPER_ORIGIN))
