"""Fixed trusted host entry, not a participant single-program dispatcher."""
import time
ORIGINAL_MONOTONIC=time.monotonic()
ORIGINAL_CPU=time.process_time()
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).absolute().parent))
from neural057.operator import launch
if __name__=='__main__':
    ORIGINAL_OWNER=launch(ORIGINAL_MONOTONIC,ORIGINAL_CPU,tuple(sys.argv[1:]))
    raise SystemExit(ORIGINAL_OWNER.exit_status)
