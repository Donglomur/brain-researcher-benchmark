"""Validate curation payloads with the actual Draft 2020-12 schema.

Run separately from the standard-library framework suite, in the CI-pinned
jsonschema environment. These generated examples do not authenticate artifacts
or establish scientific execution.
"""

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "src/neurobench/curation/contracts/curation-contracts-v1.schema.json"


def artifact_ref():
    return {
        "artifact_id": "fixture-source",
        "uri": "artifact://fixture/source",
        "sha256": "a" * 64,
        "media_type": "application/json",
        "visibility": "public",
    }


def definition_validator(document, definition):
    # Retain the complete document so local $defs references resolve normally.
    return Draft202012Validator({**document, "$ref": "#/$defs/" + definition})


class EvidenceReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = definition_validator(cls.schema, "EvidenceItem")

    def test_source_backed_statuses_reject_empty_references(self):
        for status in ("reported", "verified", "measured"):
            item = {"field": "dataset_identity", "status": status, "evidence_refs": []}
            with self.subTest(status=status):
                errors = list(self.validator.iter_errors(item))
                self.assertTrue(errors)
                self.assertTrue(any(error.validator == "minItems"
                                    and list(error.path) == ["evidence_refs"]
                                    for error in errors))

    def test_source_backed_statuses_accept_complete_references(self):
        for status in ("reported", "verified", "measured"):
            item = {"field": "dataset_identity", "status": status,
                    "evidence_refs": [artifact_ref()]}
            with self.subTest(status=status):
                self.validator.validate(item)

    def test_planned_and_missing_allow_empty_references(self):
        for status in ("planned", "missing"):
            with self.subTest(status=status):
                self.validator.validate({"field": "ceiling", "status": status,
                                         "evidence_refs": []})

    def test_reference_array_remains_required_for_every_status(self):
        for status in ("reported", "verified", "measured", "planned", "missing"):
            for refs in (None, {}, "source"):
                with self.subTest(status=status, refs=refs):
                    self.assertFalse(self.validator.is_valid(
                        {"field": "dataset_identity", "status": status,
                         "evidence_refs": refs}))
            with self.subTest(status=status, absent=True):
                self.assertFalse(self.validator.is_valid(
                    {"field": "dataset_identity", "status": status}))

    def test_supplied_references_must_be_complete_and_well_formed(self):
        for status in ("reported", "verified", "measured", "planned", "missing"):
            for field in artifact_ref():
                incomplete = artifact_ref()
                del incomplete[field]
                with self.subTest(status=status, missing=field):
                    self.assertFalse(self.validator.is_valid(
                        {"field": "dataset_identity", "status": status,
                         "evidence_refs": [incomplete]}))
            for bad_reference in ({}, {**artifact_ref(), "sha256": "invalid"},
                                  {**artifact_ref(), "visibility": "unknown"}):
                with self.subTest(status=status, reference=bad_reference):
                    self.assertFalse(self.validator.is_valid(
                        {"field": "dataset_identity", "status": status,
                         "evidence_refs": [bad_reference]}))

    def test_optional_fields_and_extension_properties_remain_allowed(self):
        item = {"field": "ceiling", "status": "planned", "evidence_refs": []}
        self.validator.validate(item)
        for probe in (None, {"question": "Which ceiling is supported?"}):
            self.validator.validate({**item, "value": None, "probe": probe,
                                     "curator_note": "Unexecuted plan"})


def transition(outcome="released", stage="ADJUDICATE",
               from_state="benchmark_calibrated", to_state=None):
    result = {
        "schema_version": "CurationTransitionV1",
        "transition_id": "fixture-transition",
        "job_id": "fixture-job",
        "opportunity_id": "fixture-opportunity",
        "candidate_id": "fixture-candidate",
        "stage": stage,
        "from_state": from_state,
        "to_state": outcome if to_state is None else to_state,
        "outcome": outcome,
        "actor": {
            "human_owner": "fixture-owner",
            "executed_by": {
                "agent": "fixture-worker", "model_snapshot": "fixture-snapshot",
                "skill_sha": "b" * 64, "tool_manifest_ref": artifact_ref(),
            },
            "human_reviewed_by": "fixture-reviewer" if outcome == "released" else None,
        },
        "artifact_refs": [artifact_ref()],
    }
    if outcome == "released":
        result["maximum_defensible_claim"] = "Generated schema fixture only."
    return result


class AdjudicationTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = definition_validator(cls.schema, "CurationTransition")

    def test_terminal_outcomes_accept_both_calibrated_source_states(self):
        for outcome in ("released", "retired"):
            for state in ("benchmark_calibrated", "family_calibrated"):
                with self.subTest(outcome=outcome, from_state=state):
                    self.validator.validate(transition(outcome, from_state=state))

    def test_terminal_outcomes_reject_wrong_stage_or_uncalibrated_state(self):
        for outcome in ("released", "retired"):
            for stage, state in (("SCOUT", "unstarted"),
                                 ("SCOUT", "benchmark_calibrated"),
                                 ("ADJUDICATE", "data_acquired")):
                with self.subTest(outcome=outcome, stage=stage, from_state=state):
                    self.assertFalse(self.validator.is_valid(
                        transition(outcome, stage, state)))

    def test_terminal_outcomes_require_the_matching_target_state(self):
        for outcome, other in (("released", "retired"), ("retired", "released")):
            for target in (other, "blocked"):
                with self.subTest(outcome=outcome, to_state=target):
                    self.assertFalse(self.validator.is_valid(
                        transition(outcome, to_state=target)))

    def test_existing_release_review_and_claim_requirements_remain(self):
        missing_claim = transition()
        del missing_claim["maximum_defensible_claim"]
        self.assertFalse(self.validator.is_valid(missing_claim))
        empty_claim = transition()
        empty_claim["maximum_defensible_claim"] = ""
        self.assertFalse(self.validator.is_valid(empty_claim))
        for reviewer in (None, ""):
            invalid = transition()
            invalid["actor"]["human_reviewed_by"] = reviewer
            with self.subTest(reviewer=reviewer):
                self.assertFalse(self.validator.is_valid(invalid))
        # Retirement retains its existing nullable reviewer and optional claim.
        retired = transition("retired")
        self.assertNotIn("maximum_defensible_claim", retired)
        self.assertIsNone(retired["actor"]["human_reviewed_by"])
        self.validator.validate(retired)

    def test_ordinary_outcomes_keep_the_declared_stage_transitions(self):
        for stage, rule in self.schema["x-stage-transition-contract"].items():
            for start in rule["inputs"]:
                for outcome in ("passed", "killed"):
                    if outcome in rule:
                        with self.subTest(stage=stage, start=start, outcome=outcome):
                            self.validator.validate(
                                transition(outcome, stage, start, rule[outcome]))
                with self.subTest(stage=stage, start=start, outcome="blocked"):
                    self.validator.validate(transition("blocked", stage, start, "blocked"))
                with self.subTest(stage=stage, target=start, outcome="retry"):
                    self.validator.validate(transition("retry", stage, "blocked", start))

    def test_worker_results_still_cannot_release_or_retire(self):
        validator = definition_validator(self.schema, "StageResult")
        result = {
            "schema_version": "curation-stage-result-v1",
            "job_id": "fixture-job", "opportunity_id": "fixture-opportunity",
            "stage": "ADJUDICATE", "outcome": "passed",
            "artifact_refs": [artifact_ref()], "evidence": [], "deviations": [],
            "next_stage_candidate": None, "next_job_inputs": [],
            "maximum_defensible_claim": "Generated schema fixture only.",
            "public_summary": "Recommendation only.",
        }
        validator.validate(result)
        for outcome in ("released", "retired"):
            with self.subTest(outcome=outcome):
                self.assertFalse(validator.is_valid({**result, "outcome": outcome}))


if __name__ == "__main__":
    unittest.main()
