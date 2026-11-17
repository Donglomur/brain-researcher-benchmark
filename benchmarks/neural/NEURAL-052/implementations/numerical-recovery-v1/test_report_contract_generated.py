"""Invented report/metadata controls only; no numeric packet, fitting or gold."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from interface import Invalid
import report_contract as C


def design_fixture():
    return {"concept_features": {f"invented_{i:03d}": {} for i in range(100)},
            "feature_names": [f"feature_{i}" for i in range(15)],
            "subjects": [{"subject_id": s} for s in C.SUBJECTS]}


def _construct(spec, defs):
    if "$ref" in spec:
        return _construct(defs[spec["$ref"].split("/")[-1]], defs)
    if "const" in spec:
        return copy.deepcopy(spec["const"])
    if "enum" in spec:
        return copy.deepcopy(spec["enum"][0])
    kind = spec["type"]
    kind = kind[0] if type(kind) is list else kind
    if kind == "object":
        return {k: _construct(v, defs) for k, v in spec["properties"].items()}
    if kind == "array":
        return [_construct(v, defs) for v in spec.get("prefixItems", [])]
    return {"string": "0" * 64, "number": .125, "integer": spec.get("minimum", 0), "boolean": True}[kind]


def summaries(analysis):
    for p in analysis["participants"]:
        for method in C.METHODS:
            for r in C.ROIS:
                yield from p["roi_metrics"][method][r].values()
            yield from p["it_minus_v1"][method].values()
    for method in C.METHODS:
        for r in C.ROIS:
            yield from analysis["group_descriptive"]["roi_metrics"][method][r].values()
        yield from analysis["group_descriptive"]["it_minus_v1"][method].values()


def complete_fixture(design=None):
    design = design or design_fixture()
    schema = C.build_schema(design)
    e = _construct(schema, schema["$defs"])
    a = e["analysis"]
    for s in summaries(a):
        s["conditional_concept_bootstrap"].update(defined_draws=1000, undefined_draws=0, lower=-.5, upper=.5)
        if "participants_defined" in s:
            s["participants_defined"] = 3
    for p in a["participants"]:
        for r in C.ROIS:
            support = p["voxel_support"][r]
            support.update(positive_sst_voxels=support["all_voxels"], zero_sst_voxels=0)
        p["reliability_control_support"].update(all_folds_supported=True, folds_with_common_bins=15)
        for f in p["fold_support"]:
            rel = f["reliability"]
            rel.update(supported=True, common_bins=[C.BINS[1]])
            for r in C.ROIS:
                total = p["voxel_support"][r]["all_voxels"]
                rel["bin_counts"][r] = {b: (total if b == C.BINS[1] else 0) for b in C.BINS}
                rel["weighted_voxels"][r] = total
                rel["zero_weight_voxels"][r] = 0
                rel["undefined_reliability_voxels"][r] = 0
    return e


def null_summary(s, reason):
    s.update(status=reason, value=None)
    s["conditional_concept_bootstrap"].update(status="undefined_point_estimate", lower=None, upper=None,
                                              defined_draws=0, undefined_draws=1000)


def path_set(root, path, value):
    parts = path.split("/")
    x = root
    for p in parts[:-1]:
        x = x[int(p)] if type(x) is list else x[p]
    key = int(parts[-1]) if type(x) is list else parts[-1]
    x[key] = value


PRIMARY = "analysis/participants/0/roi_metrics/macro_primary/V1/joint"
FOLD = "analysis/participants/0/fold_support/0"


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.design = design_fixture()
        self.report = complete_fixture(self.design)

    def check_bad(self, path, value):
        e = copy.deepcopy(self.report)
        path_set(e, path, value)
        with self.assertRaises(Invalid, msg=path):
            C.validate_report(e, self.design)

    def test_complete_and_scientifically_wrong_finite_alternative(self):
        self.assertIsNone(C.validate_report(self.report, self.design))
        for s in summaries(self.report["analysis"]):
            s["value"] = -1e100
            s["conditional_concept_bootstrap"].update(lower=-1e101, upper=1e101)
            if "defined_voxel_mean_diagnostic" in s:
                s["defined_voxel_mean_diagnostic"] = -123.0
        # No sign, [-1,1] bound or equality to a fitted answer is an admission gate.
        self.assertIsNone(C.validate_report(self.report, self.design))

    def test_missing_extra_complete_endpoint_and_participant_keys(self):
        for path in ("analysis", "analysis/participants/0/roi_metrics", "analysis/participants/0/roi_metrics/macro_primary/V1"):
            e = copy.deepcopy(self.report)
            x = e
            for k in path.split("/"):
                x = x[int(k)] if type(x) is list else x[k]
            del x[next(iter(x))]
            with self.assertRaises(Invalid): C.validate_report(e, self.design)
        e = copy.deepcopy(self.report)
        e["analysis"]["participants"][2]["roi_metrics"]["reliability_adjustment"]["IT"]["joint"]["extra"] = 1
        with self.assertRaises(Invalid): C.validate_report(e, self.design)

    def test_nonfinite_bool_and_huge_integer_scalar_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, 10 ** 400, "0.1"):
            self.check_bad(PRIMARY + "/value", value)

    def test_exact_metadata_count_hash_types_and_order(self):
        cases = [("task_id", "NEURAL-051"), ("input_manifest_sha256", "a" * 64 + "\n"),
                 ("input_manifest_sha256", "A" * 64), ("analysis/cohort/concept_count", 99),
                 ("analysis/cohort/concept_count", 100.0), ("analysis/strict_benchmark_panel", 1),
                 ("analysis/bootstrap/draws", 999), ("analysis/bootstrap/refit", 0),
                 ("analysis/bootstrap/multiplicities_sha256", "f" * 64),
                 ("analysis/participants/2/subject_id", "02"),
                 ("analysis/participants/0/roi_overlap_voxels", 1),
                 (FOLD + "/training_rows", 639), (FOLD + "/query_rows", True),
                 (FOLD + "/heldout_sessions", [4, 3, 2, 1]),
                 ("analysis/model/response_transformation", "all-data centering")]
        for p, v in cases:
            with self.subTest(path=p): self.check_bad(p, v)
        self.check_bad("analysis/participants", self.report["analysis"]["participants"][:2])
        self.check_bad("analysis/participants/0/fold_support", self.report["analysis"]["participants"][0]["fold_support"][:14])

    def test_exact_constant_text_and_concept_mapping(self):
        self.check_bad("analysis/limits", [])
        self.check_bad("analysis/estimands/macro_primary", "pooled R2")
        concept = next(iter(self.report["analysis"]["split"]["concept_folds"]))
        value = self.report["analysis"]["split"]["concept_folds"][concept]
        self.check_bad("analysis/split/concept_folds/" + concept, (value + 1) % 5)

    def test_bootstrap_status_and_null_support(self):
        for suffix, value in (("status", "success"), ("status", "undefined_voxel_sst"), ("value", None),
                              ("conditional_concept_bootstrap/defined_draws", 999),
                              ("conditional_concept_bootstrap/defined_draws", True),
                              ("conditional_concept_bootstrap/lower", None),
                              ("conditional_concept_bootstrap/lower", .8)):
            self.check_bad(PRIMARY + "/" + suffix, value)
        # Defined point with even one unsupported requested draw withholds CI.
        s = self.report["analysis"]["participants"][0]["roi_metrics"]["macro_primary"]["V1"]["joint"]
        s["conditional_concept_bootstrap"].update(defined_draws=999, undefined_draws=1,
            status="undefined_resample_support", lower=None, upper=None)
        self.assertIsNone(C.validate_report(self.report, self.design))

    def test_sst_and_reliability_count_partitions(self):
        for path, value in (("analysis/participants/0/voxel_support/V1/all_voxels", 1050),
                            ("analysis/participants/0/voxel_support/V1/zero_sst_voxels", 1),
                            (FOLD + "/reliability/weighted_voxels/V1", 1048),
                            (FOLD + "/reliability/undefined_reliability_voxels/V1", 1),
                            (FOLD + "/reliability/common_bins", []),
                            (FOLD + "/reliability/supported", False),
                            ("analysis/participants/0/reliability_control_support/folds_with_common_bins", 14)):
            self.check_bad(path, value)

    def test_ordered_unique_constant_predictors(self):
        self.check_bad(FOLD + "/constant_training_predictors", ["size", "session"])
        self.check_bad(FOLD + "/constant_training_predictors", ["size", "size"])
        self.check_bad(FOLD + "/constant_training_predictors", ["image_15"])
        self.report["analysis"]["participants"][0]["fold_support"][0]["constant_training_predictors"] = ["session", "size"]
        C.validate_report(self.report, self.design)

    def test_explicit_undefined_primary_does_not_drop_voxel_or_participant(self):
        p = self.report["analysis"]["participants"][0]
        p["voxel_support"]["V1"].update(positive_sst_voxels=1048, zero_sst_voxels=1)
        for f in p["fold_support"]:
            rel = f["reliability"]
            rel["bin_counts"]["V1"][C.BINS[1]] -= 1
            rel["weighted_voxels"]["V1"] -= 1
            rel["zero_weight_voxels"]["V1"] = 1
            rel["undefined_reliability_voxels"]["V1"] = 1
        for m in C.METRICS:
            null_summary(p["roi_metrics"]["macro_primary"]["V1"][m], "undefined_voxel_sst")
            null_summary(p["it_minus_v1"]["macro_primary"][m], "undefined_support")
            for s in (self.report["analysis"]["group_descriptive"]["roi_metrics"]["macro_primary"]["V1"][m],
                      self.report["analysis"]["group_descriptive"]["it_minus_v1"]["macro_primary"][m]):
                null_summary(s, "undefined_participant_support")
                s["participants_defined"] = 2
        C.validate_report(self.report, self.design)
        self.check_bad("analysis/group_descriptive/roi_metrics/macro_primary/V1/joint/participants_defined", 3)

    def test_no_common_bins_is_explicit_unsupported_control(self):
        p = self.report["analysis"]["participants"][0]
        rel = p["fold_support"][0]["reliability"]
        rel["bin_counts"]["IT"] = {b: (4081 if b == C.BINS[2] else 0) for b in C.BINS}
        rel.update(common_bins=[], supported=False)
        for r in C.ROIS:
            rel["weighted_voxels"][r] = 0
            rel["zero_weight_voxels"][r] = p["voxel_support"][r]["all_voxels"]
        p["reliability_control_support"].update(all_folds_supported=False, folds_with_common_bins=14)
        for method, reason in (("reliability_weighted_pooled", "undefined_common_reliability_bins"), ("reliability_adjustment", "undefined_support")):
            for m in C.METRICS:
                for r in C.ROIS:
                    null_summary(p["roi_metrics"][method][r][m], reason)
                    g = self.report["analysis"]["group_descriptive"]["roi_metrics"][method][r][m]
                    null_summary(g, "undefined_participant_support"); g["participants_defined"] = 2
                null_summary(p["it_minus_v1"][method][m], "undefined_support")
                g = self.report["analysis"]["group_descriptive"]["it_minus_v1"][method][m]
                null_summary(g, "undefined_participant_support"); g["participants_defined"] = 2
        C.validate_report(self.report, self.design)

    def test_schema_uses_generated_identity_not_property_values(self):
        # The predecessor checked a real private DESIGN/public schema pair.
        # Source-only recovery deliberately does not provision those files.
        # Check the same metadata-only boundary with invented identities and
        # unreadable/nonfinite scalar payloads instead of authentic inputs.
        design = design_fixture()
        schema = C.build_schema(design)
        for concept in design["concept_features"]:
            design["concept_features"][concept] = {"animacy": float("nan"), "size": object()}
        self.assertEqual(C.build_schema(design), schema)
        C.validate_report(complete_fixture(design), design)
        self.assertEqual(len(schema["properties"]["analysis"]["properties"]["split"]["const"]["concept_folds"]), 100)

    def test_bad_operator_design_is_not_a_candidate_fault(self):
        bad = design_fixture(); bad["subjects"].pop()
        with self.assertRaises(ValueError) as caught:
            C.validate_report(self.report, bad)
        self.assertNotIsInstance(caught.exception, Invalid)


if __name__ == "__main__":
    unittest.main()
