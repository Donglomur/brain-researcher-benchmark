"""Wrong archive plus lingering child: malformed outputs must not open targets."""
import argparse
from pathlib import Path
import subprocess
import sys
parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
(args.out / 'predictions.npz').write_bytes(b'not-an-npz')
subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
