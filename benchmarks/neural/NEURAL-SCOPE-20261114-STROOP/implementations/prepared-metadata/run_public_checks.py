"""Generated controls for the unprovisioned, authenticated public source package."""
from pathlib import Path
import sys
import unittest


def main():
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    import test_metadata_contract_v2
    import test_public_interface
    original = unittest.defaultTestLoader.loadTestsFromTestCase(test_metadata_contract_v2.MetadataContractTests)
    boundary = unittest.defaultTestLoader.loadTestsFromTestCase(test_public_interface.PublicInterface)
    if original.countTestCases() != 15 or boundary.countTestCases() != 3:
        raise SystemExit('Reviewed public control roster differs.')
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([original, boundary]))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
