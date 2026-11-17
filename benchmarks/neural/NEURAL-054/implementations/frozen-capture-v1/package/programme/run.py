"""Default/named source route; no arguments prints only the metadata plan."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from n054.cli import main
if __name__ == '__main__': main()
