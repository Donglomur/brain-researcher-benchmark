"""Generated software controls only; no authentic arrays, fitting or downloads."""
import copy
from contextlib import contextmanager
import hashlib
import json
import sys
import types
from unittest import mock
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("observations", Path(__file__).with_name("observations.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def generated_panel():
    """Entirely invented values; source-shaped counts are not real data parity."""
    planes, fields = [], []
    empty = {("CA3", "f", 23), ("CA3", "f", 25), ("CA3", "n", 23), ("CA3", "n", 36)}
    for region in ("CA1", "CA3"):
        for condition in ("f", "n"):
            key = f"{region}/{condition}"
            nonempty = [i for i in range(1, len(m.ANIMALS[region]) + 1) if (region, condition, i) not in empty]
            remaining_short = m.TOTALS[key] - m.ELIGIBLE[key]
            for ordinal, animal in enumerate(m.ANIMALS[region], 1):
                count = 0 if ordinal not in nonempty else 1
                if ordinal == nonempty[0]:
                    count += m.TOTALS[key] - len(nonempty)
                name = f"generated_plane_{ordinal}"
                planes.append({"region": region, "condition": condition, "plane": name,
                               "plane_ordinal1": ordinal, "animal": animal, "field_count": count})
                for row1 in range(1, count + 1):
                    short = remaining_short > 0
                    remaining_short -= int(short)
                    row = m.support(list(range(14 if short else 15)), 1)
                    row.update({"id": f"{region}/{condition}/{name}/{row1}", "region": region,
                                "condition": condition, "plane": name, "plane_ordinal1": ordinal,
                                "field_row1": row1, "animal": animal})
                    fields.append(row)
    return {"schema": "find013-original-observations/v1", "source_revision": m.REVISION,
            "source_sha256": m.SOURCE_SHA256.copy(), "units": {"response": "cm", "clock": "lap"},
            "planes": planes, "fields": fields}


class ObservationControls(unittest.TestCase):
    def test_gaps_preserve_linear_clock_and_expose_literal_nonlinear_clock(self):
        row = m.support([99, 4, None, 5, float("nan"), 8, None], 2)
        self.assertEqual(row["com_displacement_cm"], [0, 6, 24])
        self.assertEqual(row["observed_laps_since_onset1"], [1, 3, 5])
        self.assertEqual(row["source_laps1"], [2, 4, 6])
        self.assertEqual(row["literal_nonlinear_clock0"], [0, 1, 2])
        self.assertEqual(row["missing_laps_since_onset1"], [2, 4, 6])
        self.assertEqual(row["interior_filled_span"], 5)

    def test_eligibility_uses_span_not_observation_count_or_trailing_length(self):
        eligible = m.support([0] + [None] * 13 + [2] + [None] * 25, 1)
        excluded = m.support([0] + [None] * 12 + [2] + [None] * 25, 1)
        self.assertTrue(eligible["in_original_Tok"])
        self.assertFalse(excluded["in_original_Tok"])
        self.assertEqual(len(eligible["com_displacement_cm"]), 2)
        self.assertEqual(eligible["source_segment_length"], 40)

    def test_fit_response_is_not_truncated_at_fifteen(self):
        row = m.support([0] * 16 + [17], 1)
        self.assertEqual(row["com_displacement_cm"][-1], 102)
        self.assertEqual(len(row["com_displacement_cm"]), 17)

    def test_invalid_onset_or_nonfinite_source_is_not_repaired(self):
        for onset in (0, 4, 1.5, True, float("inf")):
            with self.assertRaises(ValueError):
                m.support([0, 1, 2], onset)
        for values in ([None, 1], [0, math.inf], [0, None]):
            with self.assertRaises(ValueError):
                m.support(values, 1)

    def test_raw_unadjusted_r2_can_be_negative(self):
        metric = m.r_squared([0, 1, 2], [2, 1, 0])
        self.assertEqual(metric, {"n": 3, "sse_cm2": 8, "sst_cm2": 2,
                                  "r2": -3, "status": "defined"})
        self.assertEqual(m.r_squared([0, 1, 2], [1, 1, 1])["r2"], 0)
        self.assertEqual(m.r_squared([0, 1, 2], [0, 1, 2])["r2"], 1)

    def test_constant_response_retained_without_fabricated_r2(self):
        self.assertEqual(m.r_squared([0, 0, 0], [1, 1, 1]),
                         {"n": 3, "sse_cm2": 3, "sst_cm2": 0,
                          "r2": None, "status": "constant_response"})

    def test_prediction_coverage_boolean_nonfinite_and_overflow(self):
        for fitted in ([0], [0, True], [0, math.nan], [0, math.inf], [0, 1e308]):
            with self.assertRaises(ValueError):
                m.r_squared([0, 1], fitted)
        with self.assertRaisesRegex(ValueError, "unsupported derived"):
            m.r_squared([0, 1e-300], [0, 1e-300])

    def test_duplicate_json_arm_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"candidate": {}, "candidate": {}}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                m._read(path)

    def test_source_payload_hash_checked_before_numerical_import(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.mat"
            path.write_bytes(b"not a MAT file")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                m.prepare(path, path)

    def test_complete_panel_scores_all_three_arms_without_superiority_claim(self):
        panel = generated_panel()
        included = [r for r in panel["fields"] if r["in_original_Tok"]]
        truth = {r["id"]: r["com_displacement_cm"] for r in included}
        mean = {r["id"]: [42] * 15 for r in included}
        predictions = {"linear": truth, "plateau": mean, "candidate": truth}
        result = m.score(panel, predictions)
        self.assertEqual(len(result["fields"]), 2649)
        self.assertTrue(all(r["candidate_minus_plateau_r2"] == 1 for r in result["fields"]))
        self.assertIsNone(result["aggregate_superiority_decision"])
        self.assertEqual(result["scientific_qualification"], "not_established")
        del predictions["candidate"][included[0]["id"]]
        with self.assertRaisesRegex(ValueError, "complete 2649"):
            m.score(panel, predictions)

    def test_cohort_or_mapping_mutations_rejected(self):
        panel = generated_panel()
        m.validate_panel(panel)
        for mutate in (
            lambda x: x["fields"].pop(),
            lambda x: x["fields"][0].update(animal="other"),
            lambda x: x["fields"][0].update(in_original_Tok=True),
            lambda x: x["fields"][0].update(literal_nonlinear_clock0=[0]),
            lambda x: x["fields"][0].update(missing_laps_since_onset1=[1]),
            lambda x: x["planes"][0].update(plane_ordinal1=2),
        ):
            changed = copy.deepcopy(panel)
            mutate(changed)
            with self.assertRaises(ValueError):
                m.validate_panel(changed)


@contextmanager
def replace_after_binary_capture(target, replacement):
    """Deterministically model pathname replacement after one complete read."""
    original_open = Path.open
    replaced = False

    @contextmanager
    def opening(path, *args, **kwargs):
        nonlocal replaced
        mode = args[0] if args else kwargs.get("mode", "r")
        with original_open(path, *args, **kwargs) as stream:
            yield stream
        if Path(path) == target and mode == "rb" and not replaced:
            replaced = True
            with original_open(target, "wb") as stream:
                stream.write(replacement)

    with mock.patch.object(Path, "open", opening):
        yield


class SnapshotControls(unittest.TestCase):
    def test_scoring_decodes_exactly_the_authenticated_observation_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation = root / "observations.json"
            predictions = root / "predictions.json"
            output = root / "result.json"
            admitted = b'{"identity": "admitted"}'
            observation.write_bytes(admitted)
            predictions.write_text('{}')
            argv = ["observations.py", "score", "--observations", str(observation),
                    "--expected-observations-sha256", hashlib.sha256(admitted).hexdigest(),
                    "--predictions", str(predictions), "--output", str(output)]
            with replace_after_binary_capture(observation, b'{"identity": "replacement"}'), \
                    mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(m, "score", side_effect=lambda packet, values: {"packet": packet}):
                m.main()
            self.assertEqual(json.loads(output.read_text()), {"packet": {"identity": "admitted"}})
            self.assertEqual(json.loads(observation.read_text()), {"identity": "replacement"})

    def test_mat_adapter_parses_both_admitted_snapshots_after_path_replacement(self):
        # Runtime doubles stop this test from loading numerical libraries or
        # empirical MAT content. Existing controls cover the field arithmetic.
        class Struct(dict):
            def __init__(self, **values):
                super().__init__(values)
                self.dtype = types.SimpleNamespace(names=list(values))

        for replaced_region in ("CA1", "CA3"):
            with self.subTest(region=replaced_region), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = {region: root / (region + ".mat") for region in ("CA1", "CA3")}
                bodies = {"CA1": b"generated CA1 bytes", "CA3": b"generated CA3 bytes"}
                for region in paths:
                    paths[region].write_bytes(bodies[region])
                captured = []
                scipy = types.ModuleType("scipy")
                scipy_io = types.ModuleType("scipy.io")
                scipy.io = scipy_io
                def loadmat(source, *, variable_names):
                    self.assertEqual(variable_names, ["data"])
                    captured.append(source.read() if hasattr(source, "read") else Path(source).read_bytes())
                    return {"data": Struct(f=Struct(), n=Struct())}
                scipy_io.loadmat = loadmat
                modules = {"numpy": types.ModuleType("numpy"), "scipy": scipy, "scipy.io": scipy_io}
                with replace_after_binary_capture(paths[replaced_region], b"different generated bytes"), \
                        mock.patch.dict(sys.modules, modules), \
                        mock.patch.object(m, "SOURCE_SHA256", {k: hashlib.sha256(v).hexdigest() for k, v in bodies.items()}), \
                        mock.patch.object(m, "SOURCE_BYTES", {k: len(v) for k, v in bodies.items()}, create=True), \
                        mock.patch.object(m, "ANIMALS", {"CA1": [], "CA3": []}), \
                        mock.patch.object(m, "_scalar_struct", side_effect=lambda value, name: value), \
                        mock.patch.object(m, "validate_panel"):
                    m.prepare(paths["CA1"], paths["CA3"])
                self.assertEqual(captured, [bodies["CA1"], bodies["CA3"]])

    def test_second_mat_digest_refuses_before_any_numerical_import(self):
        import builtins
        original_import = builtins.__import__
        numerical_imports = []
        def guarded_import(name, *args, **kwargs):
            if name == "numpy" or name.startswith("scipy"):
                numerical_imports.append(name)
                raise AssertionError("numerical import before complete source authentication")
            return original_import(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.mat", root / "second.mat"
            first.write_bytes(b"first")
            second.write_bytes(b"wrong")
            with mock.patch.object(m, "SOURCE_SHA256", {
                    "CA1": hashlib.sha256(b"first").hexdigest(),
                    "CA3": hashlib.sha256(b"right").hexdigest()}), \
                    mock.patch.object(m, "SOURCE_BYTES", {"CA1": 5, "CA3": 5}, create=True), \
                    mock.patch.object(builtins, "__import__", guarded_import):
                with self.assertRaisesRegex(ValueError, "CA3: original source hash mismatch"):
                    m.prepare(first, second)
            self.assertEqual(numerical_imports, [])


if __name__ == "__main__":
    unittest.main()
