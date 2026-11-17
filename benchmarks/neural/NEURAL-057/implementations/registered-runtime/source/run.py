"""Only complete qualified source execution, never preparation-time science."""
import time
ORIGINAL_MONOTONIC=time.monotonic();ORIGINAL_CPU=time.process_time()
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from neural057.cli import main
if __name__=='__main__':raise SystemExit(main(ORIGINAL_MONOTONIC,ORIGINAL_CPU))
