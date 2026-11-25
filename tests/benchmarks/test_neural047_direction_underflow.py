"""Generated complete-cohort target controls; no authentic-data preparation."""
import importlib
import importlib.util
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/neural/NEURAL-047/implementations/neural-047/full-conditional-programme-v3"
HISTORY_FILE = PACKAGE / "program/legacy/history.py"


def load_program():
    name = "_neural047_direction_underflow"
    spec = importlib.util.spec_from_file_location(name, PACKAGE / "program/__init__.py")
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    importlib.import_module(name + ".legacy")
    spec = importlib.util.spec_from_file_location(name + ".legacy.history", HISTORY_FILE)
    history = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = history
    spec.loader.exec_module(history)
    packets = importlib.import_module(name + ".packets")
    transport = importlib.import_module(name + ".legacy.delivery_io")
    return history, packets, transport


def record(name="generated", positive=0.25):
    state = [0] * 30
    for start, end in ((5, 9), (18, 22)):
        state[start:end + 1] = [1] * (end - start + 1)
    dv = [0.25] * 30
    dv[10:12] = [positive, positive]
    dv[23:25] = [-0.25, -0.25]
    return {
        "recording_id": name, "split_group": name, "split_unit": "animal",
        "source_pin": {"bytes": 236931813, "sha256": "4fcf5906d95d144ed1d6741cc86f4ef4fd332dec0f52e00ee5f34e8b75fe6d45"},
        "evidence": {"time_mapping": "generated, unqualified", "dv_orientation": "dorsal_positive: generated",
                     "saav_identity": "SAAV: generated", "group_identity": "generated", "processed_signal_support": "generated"},
        "time_seconds": list(range(30)), "native_frame0": list(range(30)),
        "velocity": [i / 32 for i in range(30)], "dv": dv, "saav": [i / 64 for i in range(30)],
        "reversal_state": state,
        "events": [{"event_id": "first", "onset_index0": 5, "end_index0": 9},
                   {"event_id": "second", "onset_index0": 18, "end_index0": 22}],
    }


class DirectionUnderflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history, cls.packets, cls.transport = load_program()

    def test_nonzero_tiny_direction_survives_complete_three_animal_construction(self):
        records = [record(name, math.ulp(0.0)) for name in ("a", "b", "c")]
        normalized = {"schema": "neural047-normalized-native-v1", "source_pin": records[0]["source_pin"],
                      "complete_WT_recording_roster": [r["recording_id"] for r in records],
                      "excluded_recordings": [], "records": records,
                      "mapping_status": "generated controls; no native qualification"}
        normalized = self.transport.decode(self.transport.canonical(normalized))
        result = self.packets.construct(normalized, b"g" * 32)
        self.assertEqual(len(result["panel"]["folds"]), 3)
        self.assertEqual(len(result["folds"]), 9)
        self.assertEqual(sorted(row["dorsal"] for row in result["targets"]["targets"]), [0, 0, 0, 1, 1, 1])
        self.assertTrue(all(row["eligible_events"] == 2 and row["excluded"] == []
                            for row in result["audit"]["exclusions"]))

    def test_exact_zero_remains_excluded(self):
        row = record()
        row["dv"][10:12] = [math.ulp(0.0), -math.ulp(0.0)]
        cases, excluded = self.history.extract(row)
        self.assertEqual([c["event_id"] for c in cases], ["second"])
        self.assertEqual(excluded, [{"event_id": "first", "reason": "zero_direction_endpoint"}])

    def test_ordinary_large_and_tiny_nonzero_signs(self):
        for value in (0.25, -0.25, 1e308, -1e308, math.ulp(0.0), -math.ulp(0.0)):
            with self.subTest(value=value):
                cases, excluded = self.history.extract(record(positive=value))
                self.assertEqual(excluded, [])
                self.assertEqual(cases[0]["label"], int(value > 0))


    def test_opposed_mixed_and_boundary_inputs_retain_exact_mean_sign(self):
        # Expected signs are mathematical, including exact Python int/float order.
        tiny = math.ulp(0.0)
        cases = ((tiny, -2 * tiny, 0), (2 * tiny, -tiny, 1),
                 (2 ** 53 + 1, -float(2 ** 53), 1),
                 (-float(2 ** 53), 2 ** 53 + 1, 1),
                 (-(2 ** 53 + 1), float(2 ** 53), 0),
                 (float(2 ** 53), -(2 ** 53 + 1), 0),
                 (1e308, -math.nextafter(1e308, 0.0), 1),
                 (-1e308, math.nextafter(1e308, 0.0), 0))
        for first, second, expected in cases:
            with self.subTest(first=first, second=second):
                row = record()
                row["dv"][10:12] = [first, second]
                row = self.transport.decode(self.transport.canonical(row))
                selected, excluded = self.history.extract(row)
                self.assertEqual(excluded, [])
                self.assertEqual(selected[0]["label"], expected)
        for first, second in ((0.0, -0.0), (2 ** 53, -float(2 ** 53))):
            with self.subTest(zero=(first, second)):
                row = record()
                row["dv"][10:12] = [first, second]
                selected, excluded = self.history.extract(row)
                self.assertEqual([v["event_id"] for v in selected], ["second"])
                self.assertEqual(excluded, [{"event_id": "first", "reason": "zero_direction_endpoint"}])


if __name__ == "__main__":
    unittest.main()
