"""Generated MAT-v5 structural round trips; no authentic observations or fits."""
import copy
import importlib.util
import io
import math
import os
from pathlib import Path
import sys
import unittest

import numpy as np
from scipy.io import loadmat, savemat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tca_decoded_projection as p


def fixture():
    units = np.empty((1, 5), dtype=[("cluster_id", object), ("xvec", object), ("hmat", object)])
    for i in range(5):
        units[0, i] = (np.array([[i + 10]], dtype=np.uint64),
                       {"COFF": np.array([[-2., -1., 0., .8, 1., 2.]])},
                       {event: np.arange(36, dtype=float).reshape(6, 6) + i * 100
                        for event in p.EVENTS})
    stream = io.BytesIO()
    savemat(stream, {"S": {"Block": np.array([[3, 1, 2, 3, 1, 2]]),
                           "vios": np.zeros((1, 6), dtype=np.uint8)}, "SU": units})
    stream.seek(0)
    return loadmat(stream, struct_as_record=True, squeeze_me=False, mat_dtype=True)


def project(data, limit=10000):
    return p.project_decoded(data,
        identity={"session_id": "generated-session", "animal_id": "generated-rat", "cohort": "Expert"},
        source_binding={"source_sha256": "a" * 64, "decoder_id": "generated-scipy-loadmat-v5"},
        max_projected_elements=limit)


def tca_module():
    path = os.environ.get("OFC_TCA_INPUTS_PATH")
    if path is None:
        path = str(Path(__file__).resolve().parent.parent / "tensor-source-analysis" / "ofc_tca_inputs.py")
    spec = importlib.util.spec_from_file_location("existing_tca_component", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProjectionControls(unittest.TestCase):
    def test_mat_roundtrip_preserves_five_complete_matrices_and_reaches_existing_transform(self):
        decoded = fixture(); result = project(decoded); session = result["session"]
        self.assertEqual(result["projection"]["event_order"], list(p.EVENTS))
        self.assertEqual(session["SU"][4]["hmat"]["Opt"][5][5], 435.)
        transformed = tca_module().prepare_session(session)
        self.assertEqual(transformed["report"]["status"], "transformed")
        self.assertEqual(len(transformed["data"][0]), 18)
        self.assertAlmostEqual(transformed["data"][0][15][0], (10 - 17.5) / math.sqrt(111.))
        self.assertFalse(result["whole_task_complete"])

    def test_opt_is_required_in_every_eligible_unit(self):
        d = fixture(); unit = d["SU"][0, 4]; h = unit["hmat"]
        unit["hmat"] = h[list(e for e in p.EVENTS if e != "Opt")]
        with self.assertRaisesRegex(p.ProjectionError, "missing Opt"):
            project(d)

    def test_violation_and_outside_crop_samples_are_not_removed(self):
        d = fixture(); d["S"][0, 0]["vios"][0, 0] = 1
        d["SU"][0, 0]["hmat"][0, 0]["COFF"][0, 0] = 12345.
        session = project(d)["session"]
        self.assertEqual(session["S"]["vios"], [1, 0, 0, 0, 0, 0])
        self.assertEqual(session["SU"][0]["hmat"]["COFF"][0][0], 12345.)
        self.assertEqual(len(session["SU"][0]["hmat"]["COFF"]), 6)

    def test_row_and_column_source_vectors_preserve_order(self):
        a = fixture(); b = copy.deepcopy(a)
        b["SU"] = b["SU"].T
        for field in ("Block", "vios"):
            b["S"][0, 0][field] = b["S"][0, 0][field].T
        self.assertEqual(project(a)["session"], project(b)["session"])

    def test_integer_cluster_identity_does_not_round_through_float(self):
        d = fixture(); x = 2 ** 53 + 7
        d["SU"][0, 0]["cluster_id"] = np.array([[x]], dtype=np.uint64)
        self.assertEqual(project(d)["session"]["SU"][0]["cluster_id"], x)

    def test_duplicate_cluster_is_not_a_source_exclusion(self):
        d = fixture(); d["SU"][0, 1]["cluster_id"] = d["SU"][0, 0]["cluster_id"].copy()
        with self.assertRaisesRegex(p.ProjectionError, "duplicate"):
            project(d)

    def test_source_excluded_session_keeps_all_identities_without_demanding_unused_events(self):
        d = fixture(); d["SU"] = d["SU"][:, :4]
        for unit in d["SU"].ravel():
            unit["hmat"] = None
        result = project(d)
        self.assertTrue(result["projection"]["source_excluded"])
        self.assertEqual([u["cluster_id"] for u in result["session"]["SU"]], [10, 11, 12, 13])
        self.assertEqual(tca_module().prepare_session(result["session"])["report"]["status"], "excluded_by_source")

    def test_nonvector_struct_and_ragged_trial_axis_refused(self):
        d = fixture(); d["SU"] = np.tile(d["SU"][:, :3], (2, 1))
        with self.assertRaisesRegex(p.ProjectionError, "nonvector"):
            project(d)
        d = fixture(); d["SU"][0, 0]["hmat"][0, 0]["Opt"] = np.zeros((5, 6))
        with self.assertRaisesRegex(p.ProjectionError, "trial axis"):
            project(d)

    def test_missingness_and_nonfinite_values_are_not_imputed(self):
        d = fixture(); a = d["SU"][0, 0]["hmat"][0, 0]["Opt"]
        a[0, :4] = [np.nan, np.inf, -np.inf, -0.0]
        result = project(d)["session"]["SU"][0]["hmat"]["Opt"][0]
        self.assertTrue(math.isnan(result[0])); self.assertEqual(result[1:3], [math.inf, -math.inf])
        self.assertEqual(math.copysign(1, result[3]), -1.)

    def test_copy_budget_refuses_complete_session_instead_of_truncating(self):
        d = fixture(); needed = project(d)["projection"]["copied_elements"]
        self.assertEqual(project(d, needed)["projection"]["copied_elements"], needed)
        with self.assertRaisesRegex(p.ProjectionError, "budget"):
            project(d, needed - 1)

    def test_no_input_mutation_and_first_unit_only_axis(self):
        d = fixture(); before = d["SU"][0, 0]["hmat"][0, 0]["COFF"].copy()
        d["SU"][0, 1]["xvec"] = None
        result = project(d); result["session"]["SU"][0]["hmat"]["COFF"][0][0] = 999
        np.testing.assert_array_equal(d["SU"][0, 0]["hmat"][0, 0]["COFF"], before)
        self.assertNotIn("xvec", result["session"]["SU"][1])

    def test_complex_or_squeezed_representation_is_not_silently_coerced(self):
        d = fixture(); d["SU"][0, 0]["hmat"][0, 0]["Opt"] = np.ones((6, 6), dtype=complex)
        with self.assertRaisesRegex(p.ProjectionError, "primitive real"):
            project(d)
        d = fixture(); d["S"] = d["S"].squeeze()
        with self.assertRaisesRegex(p.ProjectionError, "shape"):
            project(d)

    def test_extended_precision_is_not_silently_narrowed(self):
        d = fixture()
        dtype = np.dtype(np.longdouble)
        d["SU"][0, 0]["hmat"][0, 0]["Opt"] = np.ones((6, 6), dtype=dtype)
        if dtype.itemsize > 8:
            with self.assertRaisesRegex(p.ProjectionError, "extended precision"):
                project(d)
        else:
            self.assertEqual(project(d)["session"]["SU"][0]["hmat"]["Opt"][0][0], 1.)


if __name__ == "__main__":
    unittest.main(verbosity=1)
