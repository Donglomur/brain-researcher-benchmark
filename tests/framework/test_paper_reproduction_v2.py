"""Generated metadata controls only: no scientific arrays, models or comparators."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from neurobench import paper_reproduction as v1
V1_SCHEMAS_BEFORE = copy.deepcopy((v1.CONTRACT_SCHEMA, v1.RESULT_SCHEMA, v1.RECEIPT_SCHEMA))
from neurobench import paper_reproduction_v2 as paper

SPEC = importlib.util.spec_from_file_location("reproduction_v1_generated_fixtures", ROOT / "tests/framework/test_paper_reproduction.py")
legacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(legacy)


def member(identifier, collection=False):
    """Invented 2x3 support; these hashes do not identify real artifacts."""
    return {
        "id": identifier, "manifest_key": "generated." + identifier,
        "source_quantity": "Generated full-support test quantity", "membership": "data_dependent" if collection else "fixed",
        "shape": [2, 3], "axes": [
            {"name": name, "units": "index", "identity_sha256": char * 64,
             "coordinates": {"kind": "arithmetic", "start": 0, "step": 1, "count": count}}
            for name, char, count in (("train_time", "1", 2), ("test_time", "2", 3))],
        "allowed_dtypes": ["float32", "float64"], "units": "dimensionless",
        "semantic_identity_sha256": "3" * 64, "support_manifest_sha256": "4" * 64,
        "domain_policy_sha256": "5" * 64, "source_aggregation": "Generated source reduction preserves every grid cell.",
        "derivation_policy_sha256": "6" * 64,
        "collection": {"record_key_fields": ["cluster_id"], "zero_records_allowed": True,
                       "correspondence": {"status": "specified", "policy_sha256": "8" * 64,
                                          "rationale": "Generated independently frozen mask correspondence, not ID/count equality.",
                                          "evidence_ids": ["paper"]}} if collection else None,
        "evidence_ids": ["paper"],
    }


def fixture():
    reproduction, improvement, outcomes, result, improvement_result = legacy.fixture()
    reproduction["schema_version"] = paper.CONTRACT_VERSION
    structured = {
        "id": "maps", "kind": "indexed_array_family", "description": "Generated complete maps and cluster collection",
        "status": "verified",
        "expected": {"manifest_sha256": "a" * 64, "provenance_role": "operator_reconstruction",
                     "source_revision": "generated-source-only", "provenance": "Invented reference for metadata controls, not science.",
                     "publication_equivalence": "verified", "equivalence_rationale": "Generated source-equivalence declaration only.",
                     "evidence_ids": ["paper"]},
        "representation": {"status": "specified", "family_id": "generated-family", "family_identity_sha256": "9" * 64,
                           "members": [member("map"), member("clusters", True)], "evidence_ids": ["paper"]},
        "required_granular_output_ids": ["maps-output"],
        "comparison": {"status": "specified", "comparison_class": paper.COMPARISON_CLASS,
                       "reference_manifest_sha256": "a" * 64, "comparison_program_sha256": "b" * 64,
                       "criterion_policy_sha256": "c" * 64, "uncertainty_policy_sha256": "d" * 64,
                       "coverage": "complete_declared_source_support", "method": "Generated whole-family criterion",
                       "independent_unit": "participant", "dependence": "All temporal cells remain dependent within participant.",
                       "multiplicity": "Generated policy jointly covers the complete map family.",
                       "rationale": "No scientific threshold is established by this fixture.", "evidence_ids": ["paper"]},
        "evidence_ids": ["paper"],
    }
    reproduction["findings"].append(structured)
    computation = reproduction["admission_policy"]["computation"]
    computation["required_outputs"].append({"id": "maps-output", "kind": "source_grounded_derived",
                                           "description": "Generated full maps and all cluster records",
                                           "identity_sha256": "7" * 64, "finding_ids": ["maps"], "evidence_ids": ["paper"]})
    for pairing in outcomes["pairing"].values():
        pairing["protocol"]["computation"] = copy.deepcopy(computation)
    result["schema_version"] = paper.RESULT_VERSION
    observed = {"id": "maps", "kind": "indexed_array_family", "output_manifest_sha256": "b" * 64,
                "family_spec_digest": paper.contract_digest(structured["representation"]), "members": []}
    for spec in structured["representation"]["members"]:
        observed["members"].append({
            key: copy.deepcopy(spec[key]) for key in ("id", "manifest_key", "semantic_identity_sha256", "shape", "units",
                                                       "support_manifest_sha256", "domain_policy_sha256", "derivation_policy_sha256")})
        observed["members"][-1].update(dtype="float64", axis_identity_sha256=[a["identity_sha256"] for a in spec["axes"]],
                                       content_sha256="f" * 64, complete=True, records=[])
    result["findings"].append(observed)
    outcomes["contracts"] = {"reproduction": paper.contract_digest(reproduction), "improvement": paper.contract_digest(improvement)}
    result["contract_digest"] = outcomes["contracts"]["reproduction"]
    receipt = legacy.receipt_for(outcomes, result)
    receipt["schema_version"] = paper.RECEIPT_VERSION
    receipt["output_verification"]["finished_at"] = "2026-11-16T10:45:00Z"
    comparison = {
        "finding_id": "maps", "actor_role": "independent_operator", "candidate_sha256": receipt["candidate_sha256"],
        "contract_digest": paper.contract_digest(reproduction), "outcomes_digest": paper.contract_digest(outcomes),
        "execution_id": receipt["analysis_execution"]["execution_id"], "output_manifest_sha256": "b" * 64,
        "result_digest": paper.contract_digest(result), "finding_result_digest": paper.contract_digest(observed),
        "family_spec_digest": paper.contract_digest(structured["representation"]),
        "reference_manifest_sha256": "a" * 64, "reference_descriptor_digest": paper.contract_digest(structured["expected"]),
        "comparison_class": paper.COMPARISON_CLASS, "comparison_program_sha256": "b" * 64,
        "criterion_policy_sha256": "c" * 64, "uncertainty_policy_sha256": "d" * 64,
        "coverage": "complete_declared_source_support", "started_at": "2026-11-16T10:45:00Z",
        "finished_at": "2026-11-16T10:50:00Z", "decision_manifest_sha256": "e" * 64,
        "evidence_ids": ["scientific"], "member_assessments": [], "criterion_satisfied": True,
    }
    for spec, actual in zip(structured["representation"]["members"], observed["members"]):
        comparison["member_assessments"].append({
            "member_id": spec["id"], "reference_member_key": spec["manifest_key"],
            "submitted_member_digest": paper.contract_digest(actual), "status": "assessed", "comparison_record_sha256": "f" * 64,
            "correspondence_policy_sha256": spec["collection"]["correspondence"]["policy_sha256"] if spec["collection"] else None})
    receipt["scientific_comparisons"] = [comparison]
    receipt["evidence"].append({"id": "scientific", "kind": "scientific_comparison", "sha256": "e" * 64, "locator": "urn:fixture:scientific"})
    return reproduction, improvement, outcomes, receipt


def reseal(reproduction, improvement, outcomes, receipt):
    """Recompute bindings after intentional semantic changes in generated controls."""
    outcomes["contracts"] = {"reproduction": paper.contract_digest(reproduction), "improvement": paper.contract_digest(improvement)}
    receipt["outcomes_digest"] = paper.contract_digest(outcomes)
    receipt["freeze"]["outcomes_digest"] = receipt["outcomes_digest"]
    result = receipt["result"]
    result["contract_digest"] = outcomes["contracts"]["reproduction"]
    receipt["evaluation"]["result_digest"] = paper.contract_digest(result)
    receipt["output_verification"]["result_digest"] = paper.contract_digest(result)
    by_id = {finding["id"]: finding for finding in result["findings"]}
    for comparison in receipt["scientific_comparisons"]:
        comparison.update(contract_digest=outcomes["contracts"]["reproduction"], outcomes_digest=receipt["outcomes_digest"],
                          result_digest=paper.contract_digest(result))
        observed = by_id.get(comparison["finding_id"])
        if observed is not None:
            comparison["finding_result_digest"] = paper.contract_digest(observed)
            members = {member["id"]: member for member in observed.get("members", [])}
            for assessment in comparison["member_assessments"]:
                if assessment["member_id"] in members:
                    assessment["submitted_member_digest"] = paper.contract_digest(members[assessment["member_id"]])


class VersionAndDesignTests(unittest.TestCase):
    def test_v1_files_and_schema_dictionaries_remain_unchanged(self):
        self.assertEqual((v1.CONTRACT_SCHEMA, v1.RESULT_SCHEMA, v1.RECEIPT_SCHEMA), V1_SCHEMAS_BEFORE)
        frozen = {"src/neurobench/paper_reproduction.py": "f819b4477ded1db9c2395866c75a06c40a797ff05a6d076c8592540b6657f754",
                  "tests/framework/test_paper_reproduction.py": "0facf9f2ac93420a64f3a3f8b3824c26f065f4f6e61751720ac715cf20415833"}
        for name, digest in frozen.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(v1.CONTRACT_SCHEMA["properties"]["schema_version"], {"const": "paper-reproduction/v1"})
        self.assertNotIn("scientific_comparisons", v1.RECEIPT_SCHEMA["properties"])
        self.assertEqual(v1.CONTRACT_SCHEMA["properties"]["findings"]["items"]["properties"]["kind"]["enum"], ["scalar", "categorical"])

    def test_v1_dispatch_is_exact_and_v1_rejects_v2_receipts(self):
        r, i, o, result, _ = legacy.fixture()
        receipt = legacy.receipt_for(o, result)
        self.assertEqual(paper.contract_validate(r), v1.contract_validate(r))
        self.assertEqual(paper.outcomes_validate(o, r, i), v1.outcomes_validate(o, r, i))
        self.assertEqual(paper.admit_outcome(o, r, i, receipt), v1.admit_outcome(o, r, i, receipt))
        self.assertEqual(paper.summary(o, r, i, [receipt]), v1.summary(o, r, i, [receipt]))
        receipt["schema_version"] = paper.RECEIPT_VERSION
        self.assertFalse(paper.admit_outcome(o, r, i, receipt)["metadata_admitted"])

    def test_known_support_without_reference_or_identities_is_an_honest_design(self):
        r, i, o, receipt = fixture()
        r.update(eligibility="source_unresolved", blocking_issues=["Authentic realization/reference and criteria not recovered."])
        r.pop("admission_policy")
        finding = r["findings"][-1]
        finding.update(status="unresolved", expected=None)
        representation = finding["representation"]
        representation.update(status="unresolved", family_identity_sha256=None)
        for member in representation["members"]:
            for key in ("semantic_identity_sha256", "support_manifest_sha256", "domain_policy_sha256", "derivation_policy_sha256", "allowed_dtypes"):
                member[key] = None
            for axis in member["axes"]:
                axis["identity_sha256"] = None
        comparison = finding["comparison"]
        comparison["status"] = "unresolved"
        for key in ("reference_manifest_sha256", "comparison_program_sha256", "criterion_policy_sha256", "uncertainty_policy_sha256"):
            comparison[key] = None
        self.assertEqual(paper.contract_validate(r), [])
        r["eligibility"] = "eligible"
        self.assertTrue(paper.contract_validate(r))

    def test_source_shaped_examples_preserve_unknown_identities_and_partial_scope(self):
        # Source-shape examples, not task contracts or recovered numerical data.
        # RNN notebook SHA31b0c0068f3835e3c10db3f839b0bcbc5b67183baf56521bff1132ceda2f276e;
        # FIND032 qmd SHAdf704b3008a0b421ed85af56ab734917fd3cca9587878905898a044a18b7a001.
        cases = (
            [("rnn.fit.input", [32, 1000, 18], ["sequence_row", "integration_index", "source_pattern_index"]),
             ("rnn.fit.output", [32, 1000, 500], ["sequence_row", "integration_index", "source_readout_unit"]),
             ("rnn.fit.target", [32, 1000, 500], ["sequence_row", "integration_index", "source_readout_unit"]),
             ("rnn.fit.mask", [32, 1000, 500], ["sequence_row", "integration_index", "source_readout_unit"]),
             ("rnn.panel_L.curves", [2, 1000], ["panel_L_condition", "integration_index"]),
             ("rnn.panel_M.curves", [2, 1000], ["panel_M_condition", "integration_index"]),
             ("rnn.panel_L.readout_ids.trained", [None], ["selected_unit_position"])],
            [("sound.participant.accuracy", [33, 135], ["train_time", "test_time"]),
             ("omission.participant.full", [141, 141], ["train_time", "test_time"]),
             ("omission.participant.inference_view", [34, 135], ["train_time", "test_time"]),
             ("random.confusion.raw", [None, None, None, 4, 4],
              ["fold", "train_time", "test_time", "true_class", "predicted_class"])],
        )
        for case in cases:
            r, _, _, _ = fixture()
            r.update(eligibility="source_unresolved", blocking_issues=[
                "Partial source-shape example; full original finding scope, authentic identities, references and criteria remain unresolved."])
            r.pop("admission_policy")
            f = r["findings"][-1]
            f.update(status="unresolved", expected=None)
            f["representation"].update(status="unresolved", family_identity_sha256=None, members=[])
            for key, shape, axis_names in case:
                spec = member(key)
                spec.update(manifest_key=key, shape=shape, allowed_dtypes=None,
                            semantic_identity_sha256=None, support_manifest_sha256=None,
                            domain_policy_sha256=None, derivation_policy_sha256=None,
                            source_aggregation="Source quantity retained; complete source derivation remains unresolved.",
                            axes=[{"name": name, "units": "source coordinate units unresolved", "identity_sha256": None,
                                   "coordinates": {"kind": "unresolved", "description": "Actual ordered source coordinates unavailable."}}
                                  for name in axis_names])
                f["representation"]["members"].append(spec)
            f["comparison"]["status"] = "unresolved"
            for key in ("reference_manifest_sha256", "comparison_program_sha256", "criterion_policy_sha256", "uncertainty_policy_sha256"):
                f["comparison"][key] = None
            self.assertEqual(paper.contract_validate(r), [])
            r["eligibility"] = "eligible"
            self.assertTrue(paper.contract_validate(r))

    def test_other_scientific_comparison_class_is_schema_blocked_not_ineligible(self):
        r, _, _, _ = fixture()
        r.update(eligibility="schema_blocked", blocking_issues=["Relational criterion is outside the implemented comparison class."])
        comparison = r["findings"][-1]["comparison"]
        comparison.update(status="schema_limited", comparison_class="source_relational_distributional_effect")
        self.assertEqual(paper.contract_validate(r), [])
        r["eligibility"] = "eligible"
        self.assertTrue(paper.contract_validate(r))

    def test_verified_target_and_comparison_status_are_not_readiness_shortcuts(self):
        for expected in (None, {**fixture()[0]["findings"][-1]["expected"], "publication_equivalence": "unresolved"}):
            r, _, _, _ = fixture()
            r.update(eligibility="source_unresolved", blocking_issues=["Original source target remains unresolved."])
            f = r["findings"][-1]
            f["expected"] = expected
            f["comparison"]["status"] = "unresolved"
            self.assertTrue(paper.contract_validate(r))
            f["status"] = "unresolved"
            self.assertEqual(paper.contract_validate(r), [])
        for supported in (True, False):
            for status in ("specified", "unresolved", "schema_limited"):
                r, _, _, _ = fixture()
                r.update(eligibility="source_unresolved", blocking_issues=["Comparison eligibility not claimed."])
                comparison = r["findings"][-1]["comparison"]
                comparison.update(comparison_class=paper.COMPARISON_CLASS if supported else "source_distributional",
                                  status=status)
                errors = paper.contract_validate(r)
                self.assertEqual(bool(errors), supported == (status == "schema_limited"), (supported, status, errors))

    def test_incomplete_or_malformed_representations_fail_without_exceptions(self):
        for mutate in (
            lambda m: m.update(shape=None), lambda m: m.update(axes=None),
            lambda m: m.update(shape=[None, 3]), lambda m: m.update(shape=[]),
            lambda m: m.update(axes={}), lambda m: m.update(shape=[True, 3]),
            lambda m: m.pop("shape"), lambda m: m.update(allowed_dtypes=None),
        ):
            r, _, _, _ = fixture()
            mutate(r["findings"][-1]["representation"]["members"][0])
            self.assertTrue(paper.contract_validate(r))

    def test_eligible_source_requires_reference_policy_and_coordinate_bindings(self):
        mutations = [
            lambda f: f.update(expected=None),
            lambda f: f["expected"].update(publication_equivalence="unresolved"),
            lambda f: f["comparison"].update(uncertainty_policy_sha256=None),
            lambda f: f["comparison"].update(reference_manifest_sha256="0" * 64),
            lambda f: f["representation"]["members"][0]["axes"][0].update(identity_sha256=None),
            lambda f: f["representation"]["members"][0]["axes"][0]["coordinates"].update(count=3),
            lambda f: f["representation"]["members"][0].update(domain_policy_sha256=None),
            lambda f: f["representation"]["members"][1].update(manifest_key=f["representation"]["members"][0]["manifest_key"]),
        ]
        for change in mutations:
            r, _, _, _ = fixture()
            change(r["findings"][-1])
            self.assertTrue(paper.contract_validate(r))

    def test_semantically_duplicate_numeric_coordinates_and_unknown_versions_refused(self):
        r, _, _, _ = fixture()
        axis = r["findings"][-1]["representation"]["members"][0]["axes"][0]
        axis["coordinates"] = {"kind": "labels", "values": [1, 1.0]}
        self.assertTrue(paper.contract_validate(r))
        for version in ("paper-reproduction/v3", "paper-reproduction/v02", None):
            r, _, _, _ = fixture()
            r["schema_version"] = version
            self.assertTrue(paper.contract_validate(r))


class AdmissionTests(unittest.TestCase):
    def decision(self, mutation=None, *, seal=True):
        r, i, o, receipt = fixture()
        if mutation is not None:
            mutation(r, receipt)
        if seal:
            reseal(r, i, o, receipt)
        return paper.admit_outcome(o, r, i, receipt)

    def test_full_metadata_is_admitted_but_science_unknown(self):
        r, i, o, receipt = fixture()
        self.assertEqual(paper.contract_validate(r), [])
        self.assertEqual(paper.outcomes_validate(o, r, i), [])
        decision = paper.admit_outcome(o, r, i, receipt)
        self.assertTrue(decision["metadata_admitted"], decision)
        self.assertTrue(decision["criterion_satisfied"], decision)
        self.assertEqual(decision["scientific_outcome"], "unknown")
        summary = paper.summary(o, r, i, [receipt])
        self.assertEqual(summary["task_count"], 1)
        self.assertEqual(len(summary["cells"]), 4)
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in summary["cells"]))

    def test_genuine_declared_mismatch_is_retained(self):
        decision = self.decision(lambda r, x: x["scientific_comparisons"][0].update(criterion_satisfied=False))
        self.assertTrue(decision["metadata_admitted"], decision)
        self.assertIs(decision["criterion_satisfied"], False)
        self.assertIs(decision["finding_matches"]["maps"], False)

    def test_derivation_alone_cannot_be_scientific_comparison(self):
        decision = self.decision(lambda r, x: x.update(scientific_comparisons=[]))
        self.assertFalse(decision["metadata_admitted"])
        self.assertIsNone(decision["criterion_satisfied"])

    def test_member_axis_support_and_output_substitution_refused(self):
        mutations = [
            lambda x: x["members"].pop(),
            lambda x: x["members"].append(copy.deepcopy(x["members"][0])),
            lambda x: x["members"][0].update(manifest_key="generated.other_panel"),
            lambda x: x["members"][0].update(axis_identity_sha256=["2" * 64, "1" * 64]),
            lambda x: x["members"][0].update(support_manifest_sha256="0" * 64),
            lambda x: x["members"][0].update(shape=[3, 2]),
            lambda x: x["members"][0].update(units="percent"),
            lambda x: x["members"][0].update(domain_policy_sha256="0" * 64),
            lambda x: x.update(output_manifest_sha256="0" * 64),
        ]
        for mutate in mutations:
            decision = self.decision(lambda r, receipt: mutate(receipt["result"]["findings"][-1]))
            self.assertFalse(decision["metadata_admitted"], decision)
            self.assertIsNone(decision["criterion_satisfied"])

    def test_comparison_binding_and_full_coverage_refusals(self):
        for key in ("reference_manifest_sha256", "reference_descriptor_digest", "comparison_program_sha256",
                    "criterion_policy_sha256", "uncertainty_policy_sha256", "family_spec_digest", "candidate_sha256"):
            decision = self.decision(lambda r, x: x["scientific_comparisons"][0].update({key: "0" * 64}))
            self.assertFalse(decision["metadata_admitted"], (key, decision))
        # Do not reseal these fields: each is itself the immutable binding under test.
        for key in ("contract_digest", "outcomes_digest", "execution_id", "result_digest", "finding_result_digest"):
            decision = self.decision(lambda r, x: x["scientific_comparisons"][0].update({key: "0" * 64}), seal=False)
            self.assertFalse(decision["metadata_admitted"], (key, decision))
        for mutate in (
            lambda c: c.update(actor_role="ai_solver"),
            lambda c: c["member_assessments"].pop(),
            lambda c: c["member_assessments"][0].update(status="not_assessed"),
            lambda c: c["member_assessments"][0].update(reference_member_key="wrong.panel"),
            lambda c: c["member_assessments"][1].update(correspondence_policy_sha256="0" * 64),
            lambda c: c.update(started_at="2026-11-16T10:00:00Z"),
        ):
            decision = self.decision(lambda r, x: mutate(x["scientific_comparisons"][0]))
            self.assertFalse(decision["metadata_admitted"], decision)

    def test_zero_clusters_distinct_from_missing_family(self):
        self.assertTrue(self.decision()["metadata_admitted"])
        decision = self.decision(lambda r, x: x["result"]["findings"][-1]["members"].pop())
        self.assertFalse(decision["metadata_admitted"])
        r, i, o, receipt = fixture()
        spec = r["findings"][-1]["representation"]
        spec["members"][1]["collection"]["zero_records_allowed"] = False
        receipt["result"]["findings"][-1]["family_spec_digest"] = paper.contract_digest(spec)
        receipt["scientific_comparisons"][0]["family_spec_digest"] = paper.contract_digest(spec)
        reseal(r, i, o, receipt)
        decision = paper.admit_outcome(o, r, i, receipt)
        self.assertTrue(any("empty collection" in e for e in decision["errors"]), decision)

    def test_data_dependent_records_do_not_require_reference_id_or_count_equality(self):
        def add(r, x):
            member = x["result"]["findings"][-1]["members"][1]
            member["records"] = [{"key": ["new-local-cluster"], "content_sha256": "a" * 64,
                                  "shape": [2, 3], "dtype": "float32", "axis_identity_sha256": ["1" * 64, "2" * 64],
                                  "support_manifest_sha256": "4" * 64}]
        self.assertTrue(self.decision(add)["metadata_admitted"])
        def duplicate(r, x):
            add(r, x)
            records = x["result"]["findings"][-1]["members"][1]["records"]
            records.append(copy.deepcopy(records[0]))
        self.assertFalse(self.decision(duplicate)["metadata_admitted"])

    def test_stale_member_report_cannot_certify_changed_contents(self):
        r, i, o, receipt = fixture()
        observation = receipt["result"]["findings"][-1]
        observation["members"][1]["content_sha256"] = "0" * 64
        receipt["evaluation"]["result_digest"] = paper.contract_digest(receipt["result"])
        receipt["output_verification"]["result_digest"] = paper.contract_digest(receipt["result"])
        comparison = receipt["scientific_comparisons"][0]
        comparison.update(result_digest=paper.contract_digest(receipt["result"]),
                          finding_result_digest=paper.contract_digest(observation))
        decision = paper.admit_outcome(o, r, i, receipt)
        self.assertTrue(any("assessment changes member/output identity" in e for e in decision["errors"]), decision)
        self.assertFalse(decision["metadata_admitted"])

    def test_wrong_result_kind_is_rejected_without_exception(self):
        r, i, o, receipt = fixture()
        _, _, _, _, improvement_result = legacy.fixture()
        receipt["result"] = improvement_result
        decision = paper.admit_outcome(o, r, i, receipt)
        self.assertFalse(decision["metadata_admitted"])
        self.assertIsNone(decision["criterion_satisfied"])
        r, i, o, receipt = fixture()
        replacement = copy.deepcopy(receipt["result"]["findings"][0])
        replacement["id"] = "maps"
        receipt["result"]["findings"][-1] = replacement
        decision = paper.admit_outcome(o, r, i, receipt)
        self.assertFalse(decision["metadata_admitted"])
        self.assertTrue(any("structured result cannot be replaced" in e for e in decision["errors"]), decision)

    def test_improvement_keeps_its_existing_comparison_semantics(self):
        r, i, o, _ = fixture()
        _, _, _, _, result = legacy.fixture()
        receipt = legacy.receipt_for(o, result, outcome="improvement")
        receipt.update(schema_version=paper.RECEIPT_VERSION, scientific_comparisons=[])
        decision = paper.admit_outcome(o, r, i, receipt)
        self.assertTrue(decision["metadata_admitted"], decision)
        self.assertEqual(decision["scientific_outcome"], "unknown")

    def test_scientific_comparison_receipts_cannot_be_reused_between_conditions(self):
        r, i, o, original = fixture()
        code = legacy.receipt_for(o, original["result"], condition="paper_data_author_code")
        code.update(schema_version=paper.RECEIPT_VERSION,
                    scientific_comparisons=copy.deepcopy(original["scientific_comparisons"]))
        code["output_verification"]["finished_at"] = "2026-11-16T10:45:00Z"
        code["scientific_comparisons"][0]["execution_id"] = code["analysis_execution"]["execution_id"]
        code["evidence"].append(copy.deepcopy(original["evidence"][-1]))
        report = paper.summary(o, r, i, [original, code])
        self.assertTrue(report["errors"])
        self.assertFalse(report["paired_metadata_admitted"]["reproduction"])
        code["scientific_comparisons"][0]["decision_manifest_sha256"] = "0" * 64
        code["evidence"][-1]["sha256"] = "0" * 64
        report = paper.summary(o, r, i, [original, code])
        self.assertEqual(report["errors"], [], report)
        self.assertTrue(report["paired_metadata_admitted"]["reproduction"], report)

    def test_cross_role_lifecycle_receipt_reuse_is_rejected(self):
        r, i, o, original = fixture()
        code = legacy.receipt_for(o, original["result"], condition="paper_data_author_code")
        code.update(schema_version=paper.RECEIPT_VERSION,
                    scientific_comparisons=copy.deepcopy(original["scientific_comparisons"]))
        code["output_verification"]["finished_at"] = "2026-11-16T10:45:00Z"
        code["scientific_comparisons"][0]["execution_id"] = code["analysis_execution"]["execution_id"]
        code["scientific_comparisons"][0]["decision_manifest_sha256"] = "0" * 64
        code["evidence"].append({**original["evidence"][-1], "sha256": "0" * 64})
        # Multiple lifecycle roles may share a wrapper within one condition.
        report = paper.summary(o, r, i, [original, code])
        self.assertEqual(report["errors"], [], report)
        self.assertTrue(report["paired_metadata_admitted"]["reproduction"], report)
        for item in code["evidence"]:
            if item["kind"] in ("evaluation", "analysis_execution"):
                item["sha256"] = "f" * 64
            elif item["kind"] in ("freeze", "output_verification"):
                item["sha256"] = "d" * 64
        for receipt in (original, code):
            admission = paper.admit_outcome(o, r, i, receipt)
            self.assertTrue(admission["metadata_admitted"], admission)
            self.assertIs(admission["criterion_satisfied"], True)
        report = paper.summary(o, r, i, [original, code])
        self.assertTrue(report["errors"], report)
        self.assertFalse(report["paired_metadata_admitted"]["reproduction"])
        for cell in report["cells"]:
            self.assertEqual(cell["scientific_outcome"], "unknown")
            if cell["receipt"] is not None:
                self.assertFalse(cell["receipt"]["metadata_admitted"])
                self.assertIsNone(cell["receipt"]["criterion_satisfied"])
                self.assertEqual(cell["receipt"]["finding_matches"], {})

    def test_metadata_admission_never_opens_artifacts_or_executes_programs(self):
        r, i, o, receipt = fixture()
        receipt["analysis_execution"]["entrypoint"] = "not-executed --even-with-shell-syntax $(false)"
        with mock.patch("builtins.open", side_effect=AssertionError("metadata admission opened a file")), \
                mock.patch("subprocess.Popen", side_effect=AssertionError("metadata admission launched a process")):
            self.assertTrue(paper.admit_outcome(o, r, i, receipt)["metadata_admitted"])

    def test_raw_arrays_unknown_fields_and_nonfinite_metadata_are_rejected(self):
        for mutate in (
            lambda r, x: x["result"]["findings"][-1].update(raw_array=[[1, 2, 3], [4, 5, 6]]),
            lambda r, x: x["scientific_comparisons"][0].update(criterion_satisfied=1),
            lambda r, x: x["result"]["findings"][-1]["members"][0].update(shape=[float("nan"), 3]),
        ):
            decision = self.decision(mutate, seal=False)
            self.assertFalse(decision["metadata_admitted"])


if __name__ == "__main__":
    unittest.main()
