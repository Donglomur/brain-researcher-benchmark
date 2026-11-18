"""Generated transcript-integrity controls; no authentic data or model runs."""
import copy
import importlib.util
import os
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# These test-only overrides allow new source to be exercised against the existing
# installed dependency without copying or modifying the registered programme.
dependency = Path(os.environ.get("NEURAL047_DELIVERY_TEST_SOURCE", HERE / "test_delivery.py"))
fixture_module = load("neural047_audit_generated_fixture", dependency)
d = fixture_module.d
a = load("neural047_audit_subject", HERE / "audit_collection.py")


def transcript(session):
    return {"schema": "neural047-observation-transcript-v1", "context": copy.deepcopy(session.receipt),
            "closed": session.closed, "response_persisted": session.closed, "failure_type": None,
            "actions": copy.deepcopy(session.transcript), "head_sha256": session.transcript_hash,
            "accepted_response_payload_bytes": session.transcript_bytes}


def panel_records(abstain=False, history=True):
    panel, folds = fixture_module.fixture()
    contexts, responses, audits = {}, {}, {}
    for mode in d.MODES:
        contexts[mode], responses[mode], audits[mode] = [], [], []
        for index, packet in enumerate(folds):
            session = fixture_module.session(panel, packet, mode)
            session.open()
            if mode == "typed_viewer" and history:
                session.dispatch(fixture_module.full_history(packet))
            request = ({"action": "abstain", "reason": "generated inability to interpret"}
                       if abstain and index == 0 else fixture_module.request(packet))
            response = session.dispatch(request)
            contexts[mode].append(copy.deepcopy(session.receipt))
            responses[mode].append(response)
            audits[mode].append(transcript(session))
    return panel, contexts, responses, audits


class AuditCollectionControls(unittest.TestCase):
    def setUp(self):
        self.panel, self.contexts, self.responses, self.audits = panel_records()

    def collect(self, audits=None, responses=None, contexts=None):
        return a.collect_paired_audited(d, self.panel,
                                       self.contexts if contexts is None else contexts,
                                       self.responses if responses is None else responses,
                                       self.audits if audits is None else audits)

    def test_all_modes_folds_and_arms_preserve_existing_scorer_submission(self):
        result = self.collect()
        legacy = d.collect_paired(self.panel, self.contexts, self.responses)
        for mode in d.MODES:
            self.assertEqual(result["collections"][mode]["collection"], legacy["collections"][mode])
            self.assertEqual(len(result["collections"][mode]["operator_audits"]), 9)
            self.assertEqual(result["collections"][mode]["qualification"],
                             "saved_operator_artifact_integrity_only")
        self.assertNotEqual(self.contexts[d.MODES[0]][0]["delivery_id"],
                            self.contexts[d.MODES[1]][0]["delivery_id"])

    def test_missing_duplicate_foreign_or_crossmode_audits_fail(self):
        missing = copy.deepcopy(self.audits)
        missing[d.MODES[0]].pop()
        duplicate = copy.deepcopy(self.audits)
        duplicate[d.MODES[0]][-1] = duplicate[d.MODES[0]][0]
        crossmode = copy.deepcopy(self.audits)
        crossmode[d.MODES[0]][0] = crossmode[d.MODES[1]][0]
        foreign = copy.deepcopy(self.audits)
        foreign[d.MODES[0]][0]["context"]["fold_id"] = "fold_999"
        for damaged in (missing, duplicate, crossmode, foreign):
            with self.subTest(damaged=damaged is missing), self.assertRaises(ValueError):
                self.collect(damaged)

    def test_failed_unpersisted_and_nonboolean_closure_are_not_results(self):
        mutations = [("closed", False), ("closed", 1), ("response_persisted", False),
                     ("response_persisted", 1), ("failure_type", "BrokenPipeError")]
        for key, value in mutations:
            damaged = copy.deepcopy(self.audits)
            damaged[d.MODES[0]][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.collect(damaged)

    def test_deleted_reordered_or_modified_chain_fails(self):
        for mutation in ("deleted", "reordered", "hash", "index", "previous", "head"):
            damaged = copy.deepcopy(self.audits)
            audit = damaged["typed_viewer"][0]
            if mutation == "deleted":
                audit["actions"].pop(1)
            elif mutation == "reordered":
                audit["actions"][0], audit["actions"][1] = audit["actions"][1], audit["actions"][0]
            elif mutation == "head":
                audit["head_sha256"] = "0" * 64
            else:
                audit["actions"][1][{"hash": "sha256", "index": "index", "previous": "previous"}[mutation]] = (
                    True if mutation == "index" else "0" * 64)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.collect(damaged)

    def test_valid_probabilities_cannot_be_substituted_after_audit(self):
        changed = copy.deepcopy(self.responses)
        changed["direct_observation"][0]["outcome"]["predictions"][0]["p_dorsal"] = .8
        # This is admissible under the original result-only collector.
        d.collect_paired(self.panel, self.contexts, changed)
        with self.assertRaises(ValueError):
            self.collect(responses=changed)

    def test_rehashed_tail_with_different_request_or_opening_is_rejected(self):
        for position in (0, -1):
            damaged = copy.deepcopy(self.audits)
            audit = damaged["direct_observation"][0]
            audit["actions"][position]["request_pin"] = d.digest({"action": "catalog"})
            previous = "0" * 64
            for row in audit["actions"]:
                row["previous"] = previous
                row["sha256"] = d.digest({k: v for k, v in row.items() if k != "sha256"})["sha256"]
                previous = row["sha256"]
            audit["head_sha256"] = previous
            with self.subTest(position=position), self.assertRaises(ValueError):
                self.collect(damaged)

    def test_inconsistent_bytes_and_extra_fields_fail(self):
        for value in (True, 1, d.CAP + 1):
            damaged = copy.deepcopy(self.audits)
            damaged["typed_viewer"][0]["accepted_response_payload_bytes"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.collect(damaged)
        damaged = copy.deepcopy(self.audits)
        damaged["typed_viewer"][0]["private_target"] = 1
        with self.assertRaises(ValueError):
            self.collect(damaged)

    def test_explicit_abstention_preserves_target_last_no_private_access(self):
        panel, contexts, responses, audits = panel_records(abstain=True)
        result = a.collect_paired_audited(d, panel, contexts, responses, audits)
        from neural047_delivery_source.legacy.scorer_core import score
        def forbidden():
            raise AssertionError("No private target should be opened after abstention")
        for mode in d.MODES:
            grade = score(panel, result["collections"][mode]["collection"]["submission"], forbidden)
            self.assertEqual(grade["status"], "abstained")
            self.assertEqual(grade["private_target_callbacks"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
