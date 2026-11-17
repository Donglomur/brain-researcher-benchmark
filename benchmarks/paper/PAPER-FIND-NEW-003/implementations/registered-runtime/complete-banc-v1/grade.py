"""Canonical score alias: one closed method and its retained stage receipts."""
import time
_WRAPPER_ORIGIN=(time.monotonic_ns(),time.time_ns())
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'runtime'))
from central.entry import main
if __name__=='__main__':
    args=sys.argv[1:]
    if '--submission' in args:args[args.index('--submission')]='--program'
    raise SystemExit(main(['grade']+args,origin=_WRAPPER_ORIGIN))
