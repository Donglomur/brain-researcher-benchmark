"""Run portable source checks from a trusted, unprovisioned checkout."""
from pathlib import Path
import sys
import unittest


def main():
    root = Path(__file__).resolve().parent
    if (root / 'BINDING.json').exists() or (root / 'BINDING.json').is_symlink():
        raise SystemExit('Public checks require an unprovisioned source checkout.')
    sys.path.insert(0, str(root))
    import test_prepare_pid
    import test_public_interface
    original = unittest.defaultTestLoader.loadTestsFromTestCase(test_prepare_pid.Preparation)
    excluded = 'test_production_cli_never_admits_generated_alternative'
    if original.countTestCases() != 12 or sum(t._testMethodName == excluded for t in original) != 1:
        raise SystemExit('Original test roster differs from the reviewed twelve methods.')
    portable = unittest.TestSuite(t for t in original if t._testMethodName != excluded)
    boundary = unittest.defaultTestLoader.loadTestsFromTestCase(test_public_interface.PublicInterface)
    if boundary.countTestCases() != 3:
        raise SystemExit('Public boundary test roster differs.')
    suite = unittest.TestSuite([portable, boundary])
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
