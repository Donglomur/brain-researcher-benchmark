"""Protected whole-campaign assembly; --submission is the programme descriptor."""
import sys
sys.dont_write_bytecode = True
from adapter import main

if __name__ == "__main__":
    raise SystemExit(main("score"))
