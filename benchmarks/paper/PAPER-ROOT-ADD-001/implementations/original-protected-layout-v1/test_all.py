"""Combined generated component controls; no original data or native runtime."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_layout import LayoutControls
from test_packed import PackedControls

if __name__ == '__main__':
    unittest.main()
