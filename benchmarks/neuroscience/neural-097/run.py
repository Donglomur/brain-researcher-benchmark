"""NEURAL-097 central candidate runner; complete or one named contribution."""
import sys
sys.dont_write_bytecode = True
from adapter import main

if __name__ == "__main__":
    raise SystemExit(main("run"))
