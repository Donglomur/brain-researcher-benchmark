"""Generated arithmetic controls; no native recordings or reference-model fits."""
import importlib
import importlib.util
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/neural/NEURAL-047/implementations/neural-047/full-conditional-programme-v3"
FEATURES_FILE = PACKAGE / "program/legacy/features.py"


def load_program():
    name = "_neural047_summary_underflow"
    spec = importlib.util.spec_from_file_location(name, PACKAGE / "program/__init__.py")
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    importlib.import_module(name + ".legacy")
    spec = importlib.util.spec_from_file_location(name + ".legacy.features", FEATURES_FILE)
    features = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = features
    spec.loader.exec_module(features)
    development = importlib.import_module(name + ".development")
    transport = importlib.import_module(name + ".legacy.delivery_io")
    return features, development, transport


class SummaryUnderflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.features, cls.development, cls.transport = load_program()

    def view(self, values, arm):
        channels = {"N": ("saav_history",), "B": ("velocity", "dv"),
                    "NB": ("velocity", "dv", "saav_history")}[arm]
        return {"time_offset_seconds": [-1.0, 0.0],
                **{channel: list(values) for channel in channels}}

    def test_representable_tiny_spread_survives_binary64_json_and_active_admission(self):
        self.assertIs(self.development.summaries, self.features.summaries)
        for arm in ("N", "B", "NB"):
            with self.subTest(arm=arm):
                view = self.transport.decode(self.transport.canonical(self.view([1e-200, -1e-200], arm)))
                packet = {"schema": "neural047-fold-v1", "packet_id": "generated",
                          "fold_id": "fold_000", "arm": arm, "test_group": "held",
                          "training": [{"case_key": "a", "group": "train_a", "features": view, "dorsal": 0},
                                       {"case_key": "b", "group": "train_b", "features": view, "dorsal": 1}],
                          "query": [{"case_key": "q", "features": view}]}
                self.assertEqual(self.development.validate(packet), ["train_a", "train_b"])
                result = self.development.summaries(view, arm)
                self.assertEqual(result[2::6], [1e-200] * (len(result) // 6))

    def test_smallest_representable_standard_deviation(self):
        tiny = math.ulp(0.0)
        self.assertEqual(self.features.summaries(self.view([tiny, -tiny], "N"), "N")[2], tiny)

    def test_constant_and_ordinary_features_preserve_declared_values(self):
        self.assertEqual(self.features.summaries(self.view([2.0, 2.0], "N"), "N"),
                         [2.0, 2.0, 0.0, 2.0, 2.0, 0.0])
        self.assertEqual(self.features.summaries(self.view([-2.0, 2.0], "N"), "N"),
                         [2.0, 0.0, 2.0, -2.0, 2.0, 4.0])


if __name__ == "__main__":
    unittest.main()
