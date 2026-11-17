"""Run recovered numerical controls and new portable-operator controls together."""
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().discover(str(HERE / "recovered"), pattern="test*.py"))
    suite.addTests(unittest.TestLoader().discover(str(HERE), pattern="test_operator.py"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
