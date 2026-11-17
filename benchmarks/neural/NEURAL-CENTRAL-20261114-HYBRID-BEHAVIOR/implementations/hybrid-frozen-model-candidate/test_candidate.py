"""Invented candidate-interface controls. No authentic data, fits or native run."""
import ast
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest


def run(prepare, root, manifest_sha, *, captured):
    # Reuse the accepted source-only80-fold fixture and its native/fit/import guards.
    with tempfile.TemporaryDirectory(prefix="hybrid-candidate-invented-") as temp:
        base = Path(temp).resolve()
        fixture = types.ModuleType("hybrid_candidate_prepare_fixture")
        fixture.__file__ = str(root / "test_prepare.py")
        exec(compile(captured["test_prepare.py"], fixture.__file__, "exec"), fixture.__dict__)
        operator = fixture.invented_binding(base)
        raw = prepare.encode(operator); binding_path = base / "binding.json"; binding_path.write_bytes(raw)
        destination = base / "source"
        preparation = prepare.materialize(root, manifest_sha, binding_path, prepare.pin(raw), destination)
        helper = prepare.bootstrap(destination)
        if "source_binding" in sys.modules:
            raise ValueError("fresh generated fixture namespace")
        sys.modules["source_binding"] = helper
        inherited = types.ModuleType("hybrid_candidate_inherited_fixture")
        inherited.__file__ = str(destination / "test_operation.py")
        lock = prepare.strict(helper.exact(destination / "SOURCE_LOCK.json", preparation["source_lock"], 262144))
        test_pin = next(x for x in lock["files"] if x["path"] == inherited.__file__)
        exec(compile(helper.exact(inherited.__file__, test_pin), inherited.__file__, "exec"), inherited.__dict__)
        inherited.SourceControls.setUpClass()
        bank = inherited.SourceControls

        class CandidateControls(unittest.TestCase):
            def setUp(self):
                self.temp = tempfile.TemporaryDirectory(prefix="candidate-source-invented-")
                self.folder = Path(self.temp.name).resolve()
                self.program = self.folder / "program"; self.program.mkdir()
                self.manifest = self.folder / "candidate.json"
                self.marker = self.folder / "never-executed"
                self.bodies = {name: ("from pathlib import Path\nPath(" + repr(str(self.marker)) +
                    ").write_text('host execution forbidden')\n").encode() for name in bank.reuse.PROGRAMME}
                self.descriptor = self.write_programme(self.bodies)

            def tearDown(self):
                for directory, _, _ in os.walk(self.folder):
                    Path(directory).chmod(0o700)
                self.temp.cleanup()

            def write_programme(self, bodies):
                rows = []
                for name, body in sorted(bodies.items()):
                    (self.program / name).write_bytes(body)
                    rows.append(dict(name=name, **prepare.pin(body)))
                raw = prepare.encode({"schema": "hybrid-frozen-model-candidate-program-v1", "files": rows})
                self.manifest.write_bytes(raw)
                return {"directory": str(self.program), "manifest": dict(path=str(self.manifest), **prepare.pin(raw))}

            def plan(self):
                return {"evaluation_arm": "candidate_frozen_models", "candidate_program": self.descriptor}

            def candidate(self):
                return bank.reuse.admit_candidate(bank.sources, self.plan())

            def score(self, nll):
                # A mathematically realizable invented aggregate, not observed cases.
                # Correct-class probability exp(-NLL) is maximal for tested NLL<=1.
                nll = float(nll); counts = [40784, 40784, 40784, 40783]
                matrix = [[counts[i] if i == j else 0 for j in range(4)] for i in range(4)]
                return {"schema": "hybrid-protected-main-score-v1",
                    "primary_subject_session_mean_nll": nll,
                    "subject_mean_nll": {str(s): nll for s in range(1, 21)},
                    "session_mean_nll": {str(s) + ":" + str(k): nll for s in range(1, 21) for k in range(1, 5)},
                    "trial_balanced_nll": nll, "decision_weighted_nll": nll, "accuracy": 1.0,
                    "per_action_recall": [1.0] * 4, "macro_action_recall": 1.0,
                    "stop_brier": (2 * (1 - math.exp(-nll)) / 3) ** 2, "confusion": matrix,
                    "participants": 20, "sessions": 80, "trials": 4884, "decisions": 163135,
                    "scoring_unit_for_uncertainty": "participant, not row/fold/coding",
                    "claim": "conditional next-action prediction on selected completed two-option trials",
                    "benchmark_ready": False, "scientific_count_delta": 0}

            def outcome(self, candidate, score):
                return {"status": bank.contract.CANDIDATE_STATUS, "error": None, "source_lock_sha256": bank.lock_sha,
                    "new_fits": 0, "reused_folds": 80, "signals_received": [], "episodes_registered": 4884,
                    "all_registered_episodes_closed": True, "participant_campaign_run": True, "scientific_count_delta": 0,
                    "reuse_receipt": {"invented": True}, "participant_result": {"invented": True},
                    "participant_summary": score, "outer_recovery_still_required": True,
                    "evaluation_arm": "candidate_frozen_models", "candidate_program": candidate.identity}

            def test_candidate_source_is_data_and_freeze_tampering_is_rejected(self):
                candidate = self.candidate()
                self.assertEqual(candidate.programme, self.bodies)
                self.assertFalse(self.marker.exists())
                (self.program / "participant_entry.py").write_bytes(b"# changed\n")
                with self.assertRaises(Exception): candidate.check()
                with self.assertRaises(Exception): self.candidate()
                self.assertFalse(self.marker.exists())

            def test_external_directory_scan_stops_at_fifth_entry_and_closes(self):
                candidate = self.candidate()
                class Entries:
                    def __init__(self, extra):
                        self.names = iter(list(bank.reuse.PROGRAMME) + (["unexpected"] if extra else []))
                        self.count, self.closed = 0, False
                    def __enter__(self): return self
                    def __exit__(self, *args): self.closed = True
                    def __iter__(self): return self
                    def __next__(self):
                        self.count += 1
                        if self.count > 5: raise AssertionError("sixth external entry was requested")
                        return types.SimpleNamespace(name=next(self.names))
                original = bank.reuse.os.scandir
                try:
                    for operation in (self.candidate, candidate.check):
                        entries = Entries(True)
                        bank.reuse.os.scandir = lambda root: entries
                        with self.assertRaisesRegex(Exception, "exceeds four"):
                            operation()
                        self.assertEqual(entries.count, 5)
                        self.assertTrue(entries.closed)
                    entries = Entries(False)
                    bank.reuse.os.scandir = lambda root: entries
                    bank.reuse._candidate_roster(self.program)
                    self.assertEqual(entries.count, 5)  # four names then EOF
                    self.assertTrue(entries.closed)
                finally:
                    bank.reuse.os.scandir = original

            def test_closed_roster_unknown_arms_and_overbudget_refused(self):
                self.assertIsNone(bank.reuse.admit_candidate(bank.sources, {}))
                for plan in ({"evaluation_arm": "anything"}, {"candidate_program": self.descriptor},
                             {"evaluation_arm": "candidate_frozen_models"}):
                    with self.assertRaisesRegex(Exception, "arm|candidate|reference"):
                        bank.reuse.admit_candidate(bank.sources, plan)
                value = json.loads(self.manifest.read_bytes())
                value["files"][0]["bytes"] = 196606
                for row in value["files"][1:]: row["bytes"] = 1
                raw = prepare.encode(value); self.manifest.write_bytes(raw)
                self.descriptor["manifest"] = dict(path=str(self.manifest), **prepare.pin(raw))
                with self.assertRaisesRegex(Exception, "fits192KiB"): self.candidate()
                value["files"][0]["name"] = "../escape.py"
                raw = prepare.encode(value); self.manifest.write_bytes(raw)
                self.descriptor["manifest"] = dict(path=str(self.manifest), **prepare.pin(raw))
                with self.assertRaisesRegex(Exception, "candidate source pin"): self.candidate()

            def test_candidate_binding_cannot_override_data_runtime_or_reference_arm(self):
                value = fixture.invented_binding(self.folder)
                value["schema"] = "hybrid-frozen-model-candidate-binding-v1"
                value["candidate_program"] = self.descriptor
                prepare.validate_binding(value, self.folder / "new-source", root)
                for key in ("image", "case_sha256", "scope", "candidate_read_policy"):
                    bad = deepcopy(value); bad[key] = "override"
                    with self.assertRaises(ValueError): prepare.validate_binding(bad, self.folder / "new-source", root)
                bad = deepcopy(value); bad["schema"] = "hybrid-operator-local-binding-v1"
                with self.assertRaises(ValueError): prepare.validate_binding(bad, self.folder / "new-source", root)
                body = prepare.encode(value); path = self.folder / "operator.json"; path.write_bytes(body)
                receipt = prepare.materialize(root, manifest_sha, path, prepare.pin(body), self.folder / "new-source")
                plan = json.loads((self.folder / "new-source/PLAN.json").read_bytes())
                self.assertEqual(plan["evaluation_arm"], "candidate_frozen_models")
                self.assertEqual(plan["candidate_program"], self.descriptor)
                self.assertFalse(receipt["candidate_source_captured"])
                self.assertFalse(receipt["candidate_runtime_whole_read_qualified"])
                for key in ("cases", "references", "base_entry", "venv_entry", "runtime_receipt"):
                    for field in ("bytes", "sha256"):
                        self.assertEqual(plan[key][field], bank.plan[key][field])

            def test_all80_signed_reused_models_bind_candidate_bytes_without_execution(self):
                candidate = self.candidate()
                target = self.folder / "delivery"; receipt = self.folder / "reuse.json"
                prepared = bank.reuse._stage_reused(bank.sources, bank.rows, bank.accepted, candidate.programme,
                    target, receipt, bank.secret, bank.fixture_pin, fixture_counts=(160, 80))
                payload = bank.sources.export._unsign((target / "DELIVERY.private.json").read_bytes(), bank.secret)
                self.assertEqual(payload["programme"], candidate.identity["programme"])
                self.assertEqual(len(payload["bundles"]), 80)
                self.assertEqual(prepared["new_fits"], 0)
                self.assertEqual(payload["evidence_kind"], "invented_engineering_fixture")
                self.assertFalse(self.marker.exists())
                candidate.check()
                for record, bundle in zip(bank.records, payload["bundles"]):
                    self.assertEqual(bundle["artifact"]["sha256"], record["artifacts"]["family_train_selected"]["sha256"])
                malformed = deepcopy(bank.accepted); malformed["artifact_manifest_private"] = malformed["artifact_manifest_private"][:-1]
                with self.assertRaisesRegex(Exception, "all80"):
                    bank.reuse._stage_reused(bank.sources, bank.rows, malformed, candidate.programme,
                        self.folder / "partial", self.folder / "partial.json", bank.secret,
                        bank.fixture_pin, fixture_counts=(160, 80))

            def test_better_and_worse_scores_allowed_only_in_candidate_arm(self):
                candidate = self.candidate(); historical = self.score(.5); scoring = bank.sources.modules["scoring"]
                bank.contract.reconcile_score(historical, historical)
                for nll in (.25, 1.0):
                    score = self.score(nll)
                    paired = scoring.paired_comparison(score, historical)
                    bank.contract.validate_candidate(self.outcome(candidate, score), bank.lock_sha, candidate.identity)
                    got = bank.contract.reconcile_candidate(score, historical, paired, scoring)
                    self.assertEqual(got, paired)
                    with self.assertRaises(Exception): bank.contract.reconcile_score(score, historical)
                    with self.assertRaises(Exception): bank.contract.validate(self.outcome(candidate, score), bank.lock_sha)

            def test_partial_or_forged_candidate_outcomes_rejected(self):
                candidate = self.candidate(); score = self.score(.25); outcome = self.outcome(candidate, score)
                for key, value in (("episodes_registered", 4883), ("reused_folds", 79),
                                   ("all_registered_episodes_closed", False), ("new_fits", 1),
                                   ("evaluation_arm", "reference_replay"), ("candidate_program", {})):
                    bad = deepcopy(outcome); bad[key] = value
                    with self.assertRaises(Exception): bank.contract.validate_candidate(bad, bank.lock_sha, candidate.identity)
                bad = deepcopy(outcome); del bad["participant_summary"]["subject_mean_nll"]["20"]
                with self.assertRaises(Exception): bank.contract.validate_candidate(bad, bank.lock_sha, candidate.identity)
                history = self.score(.5); scoring = bank.sources.modules["scoring"]
                paired = scoring.paired_comparison(score, history)
                forged = deepcopy(paired); forged["candidate_minus_reference_nll"] += .1
                with self.assertRaises(Exception): bank.contract.reconcile_candidate(score, history, forged, scoring)
                bad = deepcopy(score); bad["session_mean_nll"]["20:4"] = float("nan")
                with self.assertRaises(Exception): bank.contract.reconcile_candidate(bad, history, paired, scoring)

            def test_admission_precedes_dispatch_and_reference_calls_remain(self):
                for name, dispatch in (("operation_outer.py", "subprocess.Popen"), ("operation_worker.py", "owner.call")):
                    tree = ast.parse((root / name).read_bytes())
                    main = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "main")
                    calls = [(ast.unparse(x.func), x.lineno) for x in ast.walk(main) if isinstance(x, ast.Call)]
                    admission = min(line for call, line in calls if call == "reuse.admit_candidate")
                    first = min(line for call, line in calls if call == dispatch)
                    self.assertLess(admission, first)
                    self.assertIn("contract.validate_candidate", [call for call, _ in calls])
                    self.assertIn("contract.validate", [call for call, _ in calls])
                outer = (root / "operation_outer.py").read_text()
                self.assertIn("contract.reconcile_score(worker[", outer)
                self.assertIn("contract.reconcile_candidate(worker[", outer)

            def test_separate_host_read_bound_keeps_old_reference_policy(self):
                bound = json.loads((root / "READ_BOUNDS.json").read_bytes())
                candidate = bound["candidate_arm"]
                old = sum(x["maximum_bytes"] for x in bound["components"])
                self.assertEqual(old, 15084075045)
                calculated = old - 2 * 4884 * (27417 + 65536) + 2 * 4884 * (196608 + 65536) + 2 * (196608 + 8192)
                self.assertEqual(candidate["conservative_host_managed_total_bytes"], calculated)
                self.assertLess(calculated, 16 * 1024**3)
                self.assertFalse(candidate["candidate_internal_reads_metered"])
                self.assertFalse(candidate["candidate_runtime_whole_read_qualified"])

        try:
            result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CandidateControls))
            print(json.dumps({"candidate_interface_controls": result.testsRun, "invented_only": True,
                              "authentic_runs": 0, "fits": 0, "native_dispatch": False}, sort_keys=True))
            return result.wasSuccessful()
        finally:
            inherited.SourceControls.tearDownClass()
