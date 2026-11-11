"""Fixed independent prospective reference producer using the public participant ABI."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from neural057.reference_cli import main
if __name__=='__main__':main()
