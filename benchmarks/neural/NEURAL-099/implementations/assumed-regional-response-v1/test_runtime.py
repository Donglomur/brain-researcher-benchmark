"""One generated startup boundary check; no fake h5py API or native import."""

import builtins
import os
import sys
import unittest
from unittest.mock import patch

from inspect_clicks import ClickInspectionError, initialize_runtime


class RuntimeOrderingTest(unittest.TestCase):
    def test_refusal_precedes_import_and_selected_environment_reaches_boundary(self):
        class ImportBoundaryReached(Exception):
            pass
        imports = []
        original_import = builtins.__import__
        def stop_at_native(name, *args, **kwargs):
            if name in ("h5py", "numpy"):
                imports.append(name)
                self.assertEqual(os.environ.get("HDF5_PLUGIN_PRELOAD"), "::")
                raise ImportBoundaryReached()
            return original_import(name, *args, **kwargs)
        # A wrong environment and an already initialized stack must each refuse
        # before calling the real import boundary. No fake runtime is returned.
        for environment, preloaded in (({}, {}), ({"HDF5_PLUGIN_PRELOAD": ":"}, {}),
                                        ({"HDF5_PLUGIN_PRELOAD": "::"}, {"h5py.h5pl": object()})):
            with self.subTest(environment=environment, preloaded=bool(preloaded)), \
                 patch.dict(os.environ, environment, clear=True), \
                 patch.dict(sys.modules, preloaded), \
                 patch("builtins.__import__", side_effect=stop_at_native):
                with self.assertRaises(ClickInspectionError):
                    initialize_runtime()
        self.assertEqual(imports, [])
        self.assertFalse(any(name == "h5py" or name.startswith("h5py.") for name in sys.modules))
        with patch.dict(os.environ, {"HDF5_PLUGIN_PRELOAD": "::"}), \
             patch("builtins.__import__", side_effect=stop_at_native):
            with self.assertRaises(ImportBoundaryReached):
                initialize_runtime()
        self.assertEqual(imports, ["h5py"])


if __name__ == "__main__":
    unittest.main()
