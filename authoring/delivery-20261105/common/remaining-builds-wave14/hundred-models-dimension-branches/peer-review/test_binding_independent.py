"""Lifecycle and metadata linkage controls; numerical consumer is stubbed."""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tracemalloc
from types import SimpleNamespace
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from hundred_models_dimensions import program as p, consumers as c, linkage as link, operations as ops
g = p.catalog
spec = importlib.util.spec_from_file_location("peer_author_invented_builder", BASE / "test_program.py")
f = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = f
spec.loader.exec_module(f)
REAL_DUMPS = json.dumps
REAL_ENCODED = g.encoded
CANONICAL_BYTES = 0
CANONICAL_CALLS = 0
CATALOG_NEWLINES = 0
CAP = 5_000_000


def counted_dumps(value, *args, **kwargs):
    global CANONICAL_BYTES, CANONICAL_CALLS
    reserved = f.json_size(value)
    if reserved > CAP - CANONICAL_BYTES - CATALOG_NEWLINES:
        raise AssertionError("peer prospective serialization cap")
    text = REAL_DUMPS(value, *args, **kwargs)
    assert len(text.encode("ascii")) == reserved
    CANONICAL_BYTES += reserved
    CANONICAL_CALLS += 1
    return text


def counted_encoded(value):
    global CATALOG_NEWLINES
    if CANONICAL_BYTES + CATALOG_NEWLINES >= CAP:
        raise AssertionError("peer prospective newline cap")
    CATALOG_NEWLINES += 1
    return REAL_ENCODED(value)


def partial(branch, folders, layers, roi, frame, **kwargs):
    return c.ROIResult(roi, (), (), (), (), roi in c.DISPLAY_DEPTH_ROIS)


def frames(count=17, fail_at_eof=False):
    for _ in range(count):
        yield SimpleNamespace(records=())
    if fail_at_eof:
        raise RuntimeError("invented late iterator failure")


class Never:
    def __iter__(self):
        raise AssertionError("invalid metadata touched stream")


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bound, cls.layers, cls.folders = f.binding("figure17")

    def test_01_real_eof_then_single_completion(self):
        with patch.object(c, "consume_roi", partial):
            stream = p.run_branch(self.bound, frames())
            for roi in p.ROIS:
                row = next(stream)
                self.assertEqual(row.roi, roi)
                self.assertFalse(row.whole_branch_complete)
            done = next(stream)
            self.assertIs(type(done), p.BranchComplete)
            self.assertEqual((len(done.models), done.n_stimuli, done.repetitions), (51, 1000, 3))
            self.assertFalse(done.catalog_global99_complete)
            self.assertTrue(done.input_test102_catalog_prerequisite)
            self.assertFalse(done.scientific_qualified)
            with self.assertRaises(StopIteration):
                next(stream)

    def test_02_missing_extra_and_late_failure_keep_only_partials(self):
        for source, count, error in ((frames(16), 16, ValueError), (frames(18), 17, ValueError), (frames(17, True), 17, RuntimeError)):
            with self.subTest(count=count, error=error), patch.object(c, "consume_roi", partial):
                stream = p.run_branch(self.bound, source)
                saved = [next(stream) for _ in range(count)]
                with self.assertRaises(error):
                    next(stream)
                self.assertTrue(all(not event.whole_branch_complete for event in saved))
                with self.assertRaises(StopIteration):
                    next(stream)

    def test_03_pin_parameter_and_geometry_fail_before_iterator(self):
        bad_run = g.strict(self.bound.run_raw)
        bad_run["conditions"][0]["reduction"]["n_samples_estim"] = 1000
        raw = g.encoded(bad_run)
        candidates = [replace(self.bound, run_raw=self.bound.run_raw + b" "),
                      replace(self.bound, run_raw=raw, run_pin=(len(raw), hashlib.sha256(raw).hexdigest())),
                      replace(self.bound, limits=replace(self.bound.limits, max_input_rows=1))]
        for candidate in candidates:
            with self.assertRaises(ValueError):
                next(p.run_branch(candidate, Never()))

    def test_04_modal_one_refuses_before_iterator(self):
        # Isolate preflight geometry using an invented compiled catalog seam.
        # No claim this is authentic graph metadata or a complete compiler test.
        original = g.compile_catalog
        def one_layer(*args, **kwargs):
            out = original(*args, **kwargs)
            for model, _ in c.membership("figure17"):
                out["models"][model]["layers"] = ["invented_one_layer"]
            return out
        with patch.object(g, "compile_catalog", one_layer), patch.object(p, "_run_contract", return_value=(self.folders, 1000, 3)):
            with self.assertRaisesRegex(ValueError, "modal depth one"):
                next(p.run_branch(self.bound, Never()))

    def test_05_leaf_link_keeps_full_producer_axis_and_exact_serializers(self):
        budget = ops.SerializationBudget(500_000)
        ids = ops.TEST_STIMULI
        stimuli = ops.StimulusSupport(ids, ops.canonical_digest(ids, budget), "c" * 64)
        shapes = tuple(ops.LayerShape(name, (200,)) for name in ("early", "skip", "late"))
        support = ops.FeatureSupport("invented_model", stimuli, ("early", "skip", "late"),
            tuple(ops.FeatureFile(name + ".npz", name, shapes) for name in ids), "c" * 64)
        contract = ops.compile_model_contract(ops.TEST_SPLIT, support, ops.literal_script_pca(), budget=budget)
        record = link.model_condition_link(contract, "models_pca_rerun", ("early", "late"), f.DUMMY, f.DUMMY, budget=budget)
        self.assertEqual(record["layer_order"], g.pin(g.encoded(("early", "late"))))
        self.assertEqual(record["producer_layer_order"], g.pin(g.encoded(("early", "skip", "late"))))
        raw = ops.canonical_bytes(contract, budget)
        self.assertEqual(record["operation_contract"], {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        self.assertNotEqual(record["operation_contract"]["sha256"], hashlib.sha256(raw + b"\n").hexdigest())
        with self.assertRaises(ValueError):
            link.model_condition_link(contract, "models", ("early", "late"), f.DUMMY, f.DUMMY, budget=budget)
        with self.assertRaises(ValueError):
            link.model_condition_link(contract, "models_pca_rerun", ("foreign",), f.DUMMY, f.DUMMY, budget=budget)


if __name__ == "__main__":
    filenames = ("program.py", "consumers.py", "linkage.py", "operations.py", "_scope.py")
    source_bytes = {name: (BASE / "hundred_models_dimensions" / name).read_bytes() for name in filenames}
    tracemalloc.start()
    with patch.object(g, "encoded", counted_encoded), patch.object(json, "dumps", counted_dumps):
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    live, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    for name, body in source_bytes.items():
        assert (BASE / "hundred_models_dimensions" / name).read_bytes() == body
    print(REAL_DUMPS({"groups": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "runtime_pins": {name: {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()} for name, body in source_bytes.items()}, "canonical_fixture_bytes_including_newlines": CANONICAL_BYTES + CATALOG_NEWLINES, "json_calls": CANONICAL_CALLS, "catalog_newlines": CATALOG_NEWLINES, "traced_live_after_runtime_and_builder_imports": live, "traced_peak_after_runtime_and_builder_imports": peak, "physical_fixture_file_bytes": 0, "limitation": "Lifecycle consume_roi and modal preflight seams are explicit; no full numerical branch replay."}, sort_keys=True))
    sys.exit(not result.wasSuccessful())
