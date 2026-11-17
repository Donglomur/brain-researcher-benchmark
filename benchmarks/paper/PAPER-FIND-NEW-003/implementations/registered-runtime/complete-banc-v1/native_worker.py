"""Entrypoint for the separately qualified scientific worker enclosure."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'runtime'))
from central.worker import main
if __name__=='__main__':main()
