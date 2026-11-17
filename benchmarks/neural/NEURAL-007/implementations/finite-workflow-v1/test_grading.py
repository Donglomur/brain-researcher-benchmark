"""Generated-only controls; no recordings, authentic targets or native runtime.

Three ordinary files carry invented full 5,450-epoch predictions. Corruptions
are injected into the original locked-byte reader in memory, leaving its exact
NPZ/header/probability validation intact. File custody is separately exercised.
"""
from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grading as G
import common as C
import provenance


class GradingControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter, cls.helper, _, _ = C.load_sources()
        cls.np = cls.adapter.np
        cls.spec = cls.adapter.Specification(tuple(cls.adapter.Case(*c) for c in C.SPEC_CASES), ("YASA", "RF"))
        cls.temp = tempfile.TemporaryDirectory(prefix="sleep007-generated-grading-")
        cls.root = Path(cls.temp.name).resolve()
        cls.disk_created = 0
        cls.serialized_bytes = 0
        cls.viewer_arrays = {"class_order": cls.np.asarray(cls.adapter.CLASS_ORDER)}
        cls.part_arrays, cls.targets = {}, {}
        for index, case in enumerate(cls.spec.cases):
            ids = cls.adapter.expected_ids(case)
            viewer = cls.np.full((case.epochs, 5), .2, dtype=cls.np.float32)
            programme = cls.np.zeros((case.epochs, 5), dtype=cls.np.float32)
            programme[:, 4] = 1
            truth = [0, 0, 1, 1] if index == 0 else [1, 1, 1]
            for row, label in enumerate(truth):
                programme[row] = 0
                programme[row, label] = 1
            cls.viewer_arrays[case.case_id + "__epoch_id"] = ids
            cls.viewer_arrays[case.case_id + "__probabilities"] = viewer
            cls.part_arrays[case.case_id] = {"class_order": cls.np.asarray(cls.adapter.CLASS_ORDER),
                                           case.case_id + "__epoch_id": ids,
                                           case.case_id + "__probabilities": programme}
            stages = cls.np.full(case.epochs, -1, dtype=cls.np.int8)
            stages[:len(truth)] = truth
            cls.targets[case.case_id] = {"epoch_id": ids.copy(), "stage": stages, "score_mask": stages >= 0}
        cls.viewer_raw = cls.encode(cls.viewer_arrays)
        cls.viewer = cls.save("viewer.npz", cls.viewer_raw)
        cls.parts = {case: cls.save(case + ".npz", cls.encode(arrays)) for case, arrays in cls.part_arrays.items()}
        cls.refs = {"YASA": cls.viewer, "RF": cls.viewer}
        # Reuse one malformed aggregate across viewer/reference-boundary controls.
        bad = dict(cls.viewer_arrays)
        key = cls.spec.cases[1].case_id + "__probabilities"
        bad[key] = bad[key].copy()
        bad[key][-1, 0] = cls.np.nan  # Invalid even though this invented target is masked.
        cls.bad_aggregate = cls.encode(bad)
        assert cls.disk_created < 2 * 2**20

    @classmethod
    def tearDownClass(cls):
        retained = sum(p.stat().st_size for p in cls.root.iterdir())
        assert retained == cls.disk_created
        cls.temp.cleanup()
        assert not cls.root.exists()
        assert cls.serialized_bytes <= 6 * 2**20
        print("GENERATED_FIXTURE_ACCOUNTING=" + json.dumps({
            "ordinary_files_created": 3, "cumulative_file_bytes": cls.disk_created,
            "peak_retained_fixture_file_bytes": retained,
            "npz_serialization_bytes_including_in_memory_corruptions": cls.serialized_bytes,
            "owned_temporary_directory_removed": True, "filesystem_overhead_bytes": None,
            "authentic_data": False}, sort_keys=True))

    @classmethod
    def encode(cls, arrays):
        stream = io.BytesIO()
        cls.np.savez(stream, **arrays)
        raw = stream.getvalue()
        cls.serialized_bytes += len(raw)
        return raw

    @classmethod
    def save(cls, name, raw):
        descriptor = C.write(cls.root / name, raw)
        cls.disk_created += len(raw)
        return descriptor

    def targets_copy(self):
        return {case: {key: value.copy() for key, value in arrays.items()} for case, arrays in self.targets.items()}

    def validated(self):
        return G.validate_public(self.viewer, self.parts, self.refs, self.adapter)

    def reject_before_targets(self, viewer=None, parts=None, refs=None):
        loader = mock.Mock(side_effect=AssertionError("private loader forbidden"))
        with self.assertRaises((ValueError, OSError)):
            validated = G.validate_public(self.viewer if viewer is None else viewer,
                                          self.parts if parts is None else parts,
                                          self.refs if refs is None else refs, self.adapter)
            G.compare(validated, loader, self.adapter)
        loader.assert_not_called()

    def memory_descriptor(self, raw, suffix="invented.npz"):
        return {"path": str(self.root / suffix), **C.pin(raw)}

    def injected(self, descriptor, raw):
        original = self.adapter._locked_bytes

        def read(path, expected):
            if str(path) == descriptor["path"]:
                self.assertEqual(expected, C.pin(raw))
                return raw
            return original(path, expected)
        return mock.patch.object(self.adapter, "_locked_bytes", side_effect=read)

    def test_complete_pair_one_target_load_original_metrics_and_all_deltas(self):
        validated = self.validated()
        loader = mock.Mock(return_value=self.targets_copy())
        result = G.compare(validated, loader, self.adapter)
        loader.assert_called_once_with()
        self.assertEqual(result["full_epochs"], 5450)
        self.assertEqual([p["full_epochs"] for p in result["arms"]["viewer"]["per_person"]], [2780, 2670])
        self.assertEqual([p["scored_epochs"] for p in result["arms"]["viewer"]["per_person"]], [4, 3])
        self.assertEqual(set(result["signed_differences"]), {
            "programme_minus_viewer", "programme_minus_YASA", "programme_minus_RF", "viewer_minus_YASA", "viewer_minus_RF"})
        self.assertAlmostEqual(result["arms"]["viewer"]["person_mean_macro_f1"], 1 / 15)
        self.assertAlmostEqual(result["arms"]["programme"]["person_mean_macro_f1"], .3)
        self.assertAlmostEqual(result["signed_differences"]["programme_minus_viewer"]["person_mean_macro_f1_delta"], 7 / 30)
        self.assertEqual(result["signed_differences"]["viewer_minus_YASA"]["person_mean_macro_f1_delta"], 0)
        self.assertIsNone(result["binary_scientific_success_threshold"])
        self.assertFalse(result["population_inference"])
        self.assertIn("different allowed information", result["interpretation"])

    def test_default_adapter_identity_survives_load_sources_reimport(self):
        validated = G.validate_public(self.viewer, self.parts, self.refs)
        C.load_sources()  # A later caller imports new Case/Specification identities.
        self.assertEqual(G.compare(validated, lambda: self.targets_copy())["full_epochs"], 5450)

    def test_result_structure_and_original_arrays_read_only_without_conversion(self):
        validated = self.validated()
        with self.assertRaises(FrozenInstanceError):
            validated.viewer = None
        with self.assertRaises(TypeError):
            validated.programme["people"]["development-002"] = None
        for case, _ in C.SPEC_CASES:
            array = validated.programme["people"][case]["probabilities"]
            self.assertEqual(array.dtype, self.np.dtype("float32"))
            self.assertFalse(array.flags.writeable)
            self.np.testing.assert_array_equal(array, self.part_arrays[case][case + "__probabilities"])
            with self.assertRaises(ValueError):
                array[0, 0] = .5

    def test_missing_extra_or_misidentified_parts_refs_and_descriptors_before_targets(self):
        for parts in ({"development-001": self.parts["development-001"]},
                      {**self.parts, "development-003": self.parts["development-001"]},
                      {"development-001": self.parts["development-002"], "development-002": self.parts["development-001"]}):
            with self.subTest(parts=tuple(parts)):
                self.reject_before_targets(parts=parts)
        for refs in ({"YASA": self.viewer}, {**self.refs, "third": self.viewer}):
            with self.subTest(refs=tuple(refs)):
                self.reject_before_targets(refs=refs)
        for viewer in ({**self.viewer, "extra": True}, {**self.viewer, "bytes": True},
                       {**self.viewer, "path": "relative.npz"}, {**self.viewer, "bytes": 4_000_001}):
            with self.subTest(viewer_keys=tuple(viewer)):
                self.reject_before_targets(viewer=viewer)

    def test_real_frozen_file_digest_mismatch_before_targets(self):
        self.reject_before_targets(viewer={**self.viewer, "sha256": "0" * 64})

    def test_malformed_second_person_ids_nan_sum_and_out_of_range_before_targets(self):
        case = "development-002"
        for kind in ("ids", "nan", "row_sum", "out_of_range"):
            arrays = {key: value.copy() for key, value in self.part_arrays[case].items()}
            if kind == "ids":
                arrays[case + "__epoch_id"][-1] = arrays[case + "__epoch_id"][-2]
            elif kind == "nan":
                arrays[case + "__probabilities"][-1, 0] = self.np.nan
            elif kind == "row_sum":
                arrays[case + "__probabilities"][-1] *= .5
            else:
                arrays[case + "__probabilities"][-1, :2] = [-.25, .25]
            raw = self.encode(arrays)
            descriptor = self.memory_descriptor(raw)
            with self.subTest(kind=kind), self.injected(descriptor, raw):
                self.reject_before_targets(parts={**self.parts, case: descriptor})

    def test_bad_viewer_and_either_reference_before_targets(self):
        descriptor = self.memory_descriptor(self.bad_aggregate)
        with self.injected(descriptor, self.bad_aggregate):
            self.reject_before_targets(viewer=descriptor)
            for name in ("YASA", "RF"):
                with self.subTest(reference=name):
                    self.reject_before_targets(refs={**self.refs, name: descriptor})

    def test_mask_is_private_applied_after_full_validation_and_empty_person_rejected(self):
        validated = self.validated()
        for kind in ("inconsistent_mask", "illegal_stage", "empty_person", "wrong_ids", "missing_person"):
            targets = self.targets_copy()
            target = targets["development-002"]
            if kind == "inconsistent_mask":
                target["score_mask"][-1] = True
            elif kind == "illegal_stage":
                target["stage"][0] = 5
            elif kind == "empty_person":
                target["stage"][:] = -1
                target["score_mask"][:] = False
            elif kind == "wrong_ids":
                target["epoch_id"][-1] = target["epoch_id"][-2]
            else:
                targets.pop("development-002")
            loader = mock.Mock(return_value=targets)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                G.compare(validated, loader, self.adapter)
            loader.assert_called_once_with()

    def test_ties_choose_W_and_absent_classes_count_zero_with_undefined_recall(self):
        result = G.compare(self.validated(), lambda: self.targets_copy(), self.adapter)
        first, second = result["arms"]["viewer"]["per_person"]
        self.assertEqual(first["confusion"], [[2, 0, 0, 0, 0], [2, 0, 0, 0, 0], [0] * 5, [0] * 5, [0] * 5])
        self.assertEqual(first["recall_by_stage"], [1., 0., None, None, None])
        self.assertEqual(second["recall_by_stage"], [None, 0., None, None, None])
        self.assertEqual(second["supported_class_count"], 1)
        self.assertEqual(first["f1_by_stage"][2:], [0., 0., 0.])

    def test_role_reversal_preserves_negative_gains_and_equal_person_weight(self):
        validated = self.validated()
        # Swap already validated values without rescoring or loading targets twice.
        reverse = G.Validated(validated.specification,
                              G._freeze({"people": dict(validated.programme["people"]), "file": dict(validated.viewer["file"])}),
                              G._freeze({"people": dict(validated.viewer["people"]), "parts": dict(validated.programme["parts"])}),
                              validated.references, self.adapter)
        result = G.compare(reverse, lambda: self.targets_copy(), self.adapter)
        delta = result["signed_differences"]["programme_minus_viewer"]
        self.assertAlmostEqual(delta["person_mean_macro_f1_delta"], -7 / 30)
        self.assertAlmostEqual(delta["person_mean_macro_f1_delta"], sum(r["macro_f1_delta"] for r in delta["per_person"]) / 2)
        self.assertTrue(all(r["macro_f1_delta"] < 0 for r in delta["per_person"]))

    def private_fixture(self):
        expected = {"invented_manifest": True, "cases": [c for c, _ in C.SPEC_CASES]}
        raw_files = {"manifest.json": C.json_bytes(expected)}
        for case, arrays in self.targets.items():
            raw_files[case + "_labels.npz"] = self.encode(arrays)
        assets = {"private_files": {name: C.pin(raw) for name, raw in raw_files.items()},
                  "private_manifest_expected": expected}
        locations = {"schema": "sleep007_private_locations_v1", "files": {name: str(self.root / name) for name in raw_files}}
        return assets, locations, raw_files

    def test_private_loader_exact_manifest_and_original_target_headers(self):
        assets, locations, raw_files = self.private_fixture()
        calls = []
        def read(path, expected):
            name = Path(path).name
            calls.append(name)
            self.assertEqual(expected, C.pin(raw_files[name]))
            return raw_files[name]
        with mock.patch.object(C, "descriptor_read", return_value=C.json_bytes(locations)), \
             mock.patch.object(self.adapter, "_locked_bytes", side_effect=read), \
             mock.patch.object(self.helper, "target_headers", wraps=self.helper.target_headers) as headers:
            result = G.private_targets({"invented_descriptor": True}, assets, self.adapter, self.helper)
        self.assertEqual(calls, ["manifest.json", "development-001_labels.npz", "development-002_labels.npz"])
        self.assertEqual(headers.call_count, 2)
        for case in result:
            self.np.testing.assert_array_equal(result[case]["stage"], self.targets[case]["stage"])

    def test_private_manifest_mismatch_stops_before_label_reads(self):
        # No extra target buffers are created for this metadata-only rejection.
        assets = {"private_files": {name: C.pin(b"{}") for name in
                  ("manifest.json", "development-001_labels.npz", "development-002_labels.npz")},
                  "private_manifest_expected": {"expected": True}}
        locations = {"schema": "sleep007_private_locations_v1", "files": {name: str(self.root / name) for name in assets["private_files"]}}
        with mock.patch.object(C, "descriptor_read", return_value=C.json_bytes(locations)), \
             mock.patch.object(self.adapter, "_locked_bytes", return_value=b"{}") as read:
            with self.assertRaises(ValueError):
                G.private_targets({}, assets, self.adapter, self.helper)
        read.assert_called_once_with(locations["files"]["manifest.json"], C.pin(b"{}"))

    def request(self):
        return {"schema": "sleep007_finite_grade_v1", "source_freeze": {"invented": "source"},
                "viewer_proof": {"invented": "proof"}, "programme_commit": {"invented": "commit"},
                "viewer": self.viewer, "parts": self.parts, "references": self.refs,
                "private_locations": {"invented": "private-never-read-publicly"}}

    def run_main(self, request, private_loader, authentication=None, admission=None):
        raw = C.json_bytes(request)
        stdout = io.StringIO()
        with mock.patch.object(C, "read", return_value=raw), \
             mock.patch.object(C, "authenticate_sources", authentication or mock.Mock()), \
             mock.patch.object(provenance, "admit_grade", admission or mock.Mock()), \
             mock.patch.object(C, "load_sources", return_value=(self.adapter, self.helper, {}, {})), \
             mock.patch.object(G, "private_targets", private_loader), redirect_stdout(stdout):
            code = G.main(["--request", str(self.root / "generated-request.json"), "--bytes", str(len(raw)), "--sha256", C.pin(raw)["sha256"]])
        return code, json.loads(stdout.getvalue())

    def test_worker_public_failure_never_opens_private_locations(self):
        request = self.request()
        request["parts"] = {"development-001": self.parts["development-001"]}
        private = mock.Mock(side_effect=AssertionError("PRIVATE_SECRET_MUST_NOT_APPEAR"))
        code, report = self.run_main(request, private)
        self.assertEqual(code, 2)
        self.assertEqual(report, {"status": "failed", "failure_stage": "public_validation", "private_loader_calls": 0})
        private.assert_not_called()

    def test_worker_source_or_provenance_rejection_is_before_public_and_private(self):
        for stage in ("source_authentication", "public_provenance"):
            fail = mock.Mock(side_effect=RuntimeError("SECRET_OPERATOR_PATH"))
            private = mock.Mock()
            with self.subTest(stage=stage), mock.patch.object(G, "validate_public") as public:
                code, report = self.run_main(self.request(), private,
                    authentication=fail if stage == "source_authentication" else None,
                    admission=fail if stage == "public_provenance" else None)
            self.assertEqual(code, 2)
            self.assertEqual(report, {"status": "failed", "failure_stage": stage, "private_loader_calls": 0})
            private.assert_not_called()
            public.assert_not_called()

    def test_worker_private_failure_has_one_attempt_and_no_exception_text(self):
        private = mock.Mock(side_effect=OSError("SECRET_TARGET_PATH_AND_LABELS"))
        code, report = self.run_main(self.request(), private)
        self.assertEqual(code, 2)
        self.assertEqual(report, {"status": "failed", "failure_stage": "private_validation", "private_loader_calls": 1})
        private.assert_called_once()

    def test_worker_success_is_bounded_and_calls_protected_loader_once(self):
        private = mock.Mock(return_value=self.targets_copy())
        code, report = self.run_main(self.request(), private)
        self.assertEqual(code, 0)
        self.assertEqual(report["private_loader_calls"], 1)
        self.assertLess(len(C.json_bytes(report)), 200_000)
        private.assert_called_once()


if __name__ == "__main__":
    unittest.main()
