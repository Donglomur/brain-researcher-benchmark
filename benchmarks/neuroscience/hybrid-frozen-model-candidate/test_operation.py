"""Source controls only. No authentic cases/artifacts, fit, Docker or subprocess.

The existing TrialOwner.run_trial is exercised through synthetic CLI/inspection
seams; this tests actual engine argument and mount/cwd validation code, and is
explicitly not native containment evidence. Existing actual 17-episode evidence
remains distinct. All historical fold records below are invented test records.
"""
import ast
import builtins
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import source_binding as binding


HERE = Path(__file__).absolute().parent
SCALE_OBSERVATIONS = {}


class SourceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        original_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.split(".")[0] in {"numpy", "scipy", "torch", "jax", "tensorflow"}:
                raise AssertionError("scientific import prohibited in source controls")
            return original_import(name, *args, **kwargs)
        cls.stack.enter_context(patch("builtins.__import__", guarded))
        cls.stack.enter_context(patch.object(subprocess, "Popen", side_effect=AssertionError("native dispatch prohibited")))
        cls.stack.enter_context(patch.object(os, "system", side_effect=AssertionError("native shell prohibited")))
        cls.lock_sha = hashlib.sha256((HERE / "SOURCE_LOCK.json").read_bytes()).hexdigest()
        cls.plan, cls.lock, _, cls.delivery, cls.sources, _, modules = binding.load(cls.lock_sha)
        cls.reuse, cls.contract = modules["reuse_delivery"], modules["result_contract"]
        for name in ("train_anonymous", "train_and_seal"):
            cls.stack.enter_context(patch.object(cls.sources.export.base, name,
                side_effect=AssertionError("new fitting is prohibited")))
        for name in ("fit_ridge", "select_reference"):
            cls.stack.enter_context(patch.object(cls.sources.reference, name,
                side_effect=AssertionError("reference fitting is prohibited")))
        cls.stack.enter_context(patch.object(cls.sources.consumer, "load_accepted_private_cases",
            side_effect=AssertionError("authentic case reads prohibited")))
        cls.temp = tempfile.TemporaryDirectory(prefix="hybrid-no-refit-invented-")
        cls.root = Path(cls.temp.name).resolve()
        cls.rows = []
        for person in range(1, 21):
            for session in range(1, 5):
                for clock, action in ((0, 1), (1, 3)):
                    values = (0, 0, session, 0, 0, .5, .5, True, False, True, False, clock)
                    cls.rows.append(cls.sources.consumer.Decision(len(cls.rows) + 1, str(person), session, 1, values, action))
        cls.rows = tuple(cls.rows)
        cls.programme = {name: b"# Invented inert programme.\n" for name in cls.reuse.PROGRAMME}
        cls.secret = b"invented-private-key-for-source-controls-0001"
        artifact = cls.sources.artifact.encode_artifact(cls.sources.artifact.from_model(cls.sources.reference.Uniform()))
        cls.records = []
        for index, (person, held) in enumerate(sorted(cls.sources.consumer.GROUPS)):
            train, test = cls.sources.consumer.outer_fold(cls.rows, person, held)
            artifact_path = cls.root / ("original-%02d.json" % index)
            artifact_path.write_bytes(artifact)
            candidates = []
            for family, penalty in cls.sources.export.SPECS:
                losses = [math.log(4)] * 3
                candidates.append({"family": family, "penalty": penalty, "inner_session_losses": losses,
                                   "mean": math.fsum(losses) / 3})
            trace = {"selection": "train-only inner held-session NLL", "ledger": candidates,
                     "winner": candidates[0], "all_outer_test_inputs_unavailable_to_selector": True}
            cls.records.append({"subject_private": person, "held_session_private": held,
                "training_decisions": len(train), "held_decisions_private": len(test),
                "training_projection_sha256": cls.sources.export.sha256(cls.sources.export.canonical(cls.sources.consumer.training_view(train))),
                "selection": trace, "artifacts": {"family_train_selected": {"path": str(artifact_path),
                    "bytes": len(artifact), "sha256": hashlib.sha256(artifact).hexdigest()}},
                "training_only": True, "outer_test_available_to_selector": False})
        cls.accepted = {"schema": "hybrid-complete-train-only-reference-v1", "complete_outer_folds": 80,
            "inner_ridge_fits": 720, "final_ridge_fits": 80, "authentic_counts": {"decisions": 160, "trials": 80},
            "artifact_manifest_private": cls.records}
        cls.fixture_pin = (1, "0" * 64)
        cls.prepared = cls.reuse._stage_reused(cls.sources, cls.rows, cls.accepted, cls.programme,
            cls.root / "delivery", cls.root / "REUSE.json", cls.secret, cls.fixture_pin, fixture_counts=(160, 80))
        cls.payload = cls.sources.export._unsign((cls.root / "delivery/DELIVERY.private.json").read_bytes(), cls.secret)

    @classmethod
    def tearDownClass(cls):
        try:
            for directory, _, _ in os.walk(cls.root):
                Path(directory).chmod(0o700)
            cls.temp.cleanup()
        finally:
            cls.stack.close()

    def test_all80_reused_bytes_and_original_selection_are_explicit(self):
        receipt = self.sources.export._unsign((self.root / "REUSE.json").read_bytes(), self.secret)
        self.assertEqual((receipt["complete_folds"], receipt["new_fits"]), (80, 0))
        self.assertFalse(receipt["new_train_anonymous_or_train_and_seal_called"])
        self.assertEqual(receipt["origin"], "previously_accepted_complete_reference_workflow")
        self.assertEqual(receipt["evidence_kind"], "invented_engineering_fixture")
        for row, record, bundle in zip(receipt["folds"], self.records, self.payload["bundles"]):
            original = Path(record["artifacts"]["family_train_selected"]["path"]).read_bytes()
            copied = (self.root / "delivery" / bundle["artifact"]["relative_path"]).read_bytes()
            self.assertEqual(original, copied)
            provenance = self.sources.export._unsign((self.root / "delivery" / bundle["provenance"]["relative_path"]).read_bytes(), self.secret)
            self.assertEqual(provenance["schema"], "hybrid-private-historical-export-v1")
            self.assertEqual(provenance["historical_record_sha256"], row["historical_record_sha256"])
            self.assertNotIn("producer_closure", provenance)

    def test_existing_bound_family_accepts_explicit_historical_variant(self):
        fake = object()  # Never dispatched; only unchanged complete bundle validation runs.
        bound = self.delivery.BoundFamily(self.sources, self.rows, self.root / "delivery",
            (self.prepared["manifest"]["bytes"], self.prepared["manifest"]["sha256"]), self.secret, fake,
            _fixture_counts=(160, 80))
        self.assertEqual(set(bound.folds), self.sources.consumer.GROUPS)
        self.assertFalse(bound.poisoned)

    def test_wrong_projection_or_declared_held_extent_is_rejected(self):
        for field, value in (("training_projection_sha256", "0" * 64), ("training_decisions", 5),
                             ("held_decisions_private", 1), ("training_only", False),
                             ("outer_test_available_to_selector", True)):
            bad = deepcopy(self.records[0])
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.reuse.check_record(self.sources, bad, self.rows, self.programme, self.secret, (160, 80), False)

    def test_new_producer_receipt_is_not_accepted_as_historical(self):
        bundle = self.payload["bundles"][0]
        body = {key: (self.root / "delivery" / pin["relative_path"]).read_bytes() for key, pin in bundle.items()}
        provenance = self.sources.export._unsign(body["provenance"], self.secret)
        provenance["schema"] = "hybrid-private-training-export-v1"
        with self.assertRaises(ValueError):
            self.sources.export.verify_export(body["artifact"], self.sources.export._sign(provenance, self.secret),
                body["request"], body["preparation"], self.programme, self.secret, require_authentic=False)

    def test_fixture_origin_cannot_be_promoted_to_authentic_reuse(self):
        with self.assertRaises(ValueError):
            self.reuse.require_reuse(self.sources, self.root / "REUSE.json", self.prepared["reuse"],
                                     self.prepared["manifest"], self.secret)

    def test_wrong_artifact_digest_fails_before_any_candidate_dispatch(self):
        bad = deepcopy(self.accepted)
        bad["artifact_manifest_private"][0]["artifacts"]["family_train_selected"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.reuse._stage_reused(self.sources, self.rows, bad, self.programme, self.root / "bad-digest",
                self.root / "bad-reuse.json", self.secret, self.fixture_pin, fixture_counts=(160, 80))
        self.assertFalse((self.root / "bad-digest/DELIVERY.private.json").exists())

    def test_missing_fold_cannot_make_a_complete_delivery(self):
        bad = deepcopy(self.accepted)
        bad["artifact_manifest_private"].pop()
        with self.assertRaises(ValueError):
            self.reuse._stage_reused(self.sources, self.rows, bad, self.programme, self.root / "missing-fold",
                self.root / "missing-reuse.json", self.secret, self.fixture_pin, fixture_counts=(160, 80))
        self.assertFalse((self.root / "missing-fold").exists())

    def test_duplicate_fold_cannot_replace_another(self):
        bad = deepcopy(self.accepted)
        bad["artifact_manifest_private"][1] = deepcopy(bad["artifact_manifest_private"][0])
        with self.assertRaises(ValueError):
            self.reuse._stage_reused(self.sources, self.rows, bad, self.programme, self.root / "duplicate-fold",
                self.root / "duplicate-reuse.json", self.secret, self.fixture_pin, fixture_counts=(160, 80))
        self.assertFalse((self.root / "duplicate-fold/DELIVERY.private.json").exists())

    def test_complete_result_contract_rejects_partial_or_wrong_scope(self):
        value = {"status": self.contract.STATUS, "error": None, "source_lock_sha256": self.lock_sha,
            "new_fits": 0, "reused_folds": 80, "signals_received": [], "episodes_registered": 4884,
            "all_registered_episodes_closed": True, "participant_campaign_run": True,
            "scientific_count_delta": 0, "reuse_receipt": {"invented": True}, "participant_result": {"invented": True},
            "participant_summary": {"participants": 20, "sessions": 80, "trials": 4884, "decisions": 163135},
            "outer_recovery_still_required": True}
        self.assertTrue(self.contract.validate(value, self.lock_sha))
        for key, wrong in (("episodes_registered", 4883), ("reused_folds", 79), ("new_fits", 1),
                           ("all_registered_episodes_closed", False), ("outer_recovery_still_required", False),
                           ("status", "COMPLETE_PREFIX_AND_TRAIN_ONLY_STATISTICAL_REFERENCES")):
            bad = deepcopy(value)
            bad[key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.contract.validate(bad, self.lock_sha)

    def test_whole_reference_score_reconciliation_is_not_a_gain_test(self):
        old = {"primary": .2, "count": 163135, "nested": {"person": .4}, "matrix": [[1, 2], [3, 4]]}
        same = deepcopy(old)
        same["primary"] += 1e-13
        self.assertTrue(self.contract.reconcile_score(same, old))
        for bad in ({**old, "primary": .1}, {**old, "count": 163134}, {**old, "primary": float("nan")}):
            with self.assertRaises(ValueError):
                self.contract.reconcile_score(bad, old)

    def test_successor_dispatch_never_names_old_fit_worker(self):
        spec = importlib.util.spec_from_file_location("operation_outer_for_controls", HERE / "operation_outer.py")
        outer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(outer)
        argv = outer.worker_argv(self.plan, HERE, self.lock_sha, 12345.5)
        self.assertEqual(argv[3], str(HERE / "operation_worker.py"))
        self.assertNotIn("endpoint_worker.py", " ".join(argv))
        self.assertEqual(argv[-2:], ["--work-deadline", "12345.5"])
        for name in ("operation_worker.py", "reuse_delivery.py"):
            tree = ast.parse((HERE / name).read_text())
            forbidden = {"fit_all_references", "train_anonymous", "train_and_seal", "prepare_authentic", "fit_ridge", "select_reference"}
            calls = {n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id if isinstance(n.func, ast.Name) else ""
                     for n in ast.walk(tree) if isinstance(n, ast.Call)}
            self.assertFalse(calls & forbidden)

    def test_final_decision_requires_original_deadline_after_durable_writes_and_stdout(self):
        for stage in ("none", "initial", "outcome", "decision", "stdout", "signal_after_decision"):
            now, signals, written = [10.], [], {}
            if stage == "initial":
                now[0] = 20.
            def emit(path, value):
                written[path.name] = deepcopy(value)
                if (stage == "outcome" and path.name == "OUTCOME.json") or (stage == "decision" and path.name == "FINAL_DECISION.json"):
                    now[0] = 20.
                if stage == "signal_after_decision" and path.name == "FINAL_DECISION.json":
                    signals.append(15)
                return {"path": str(path), "bytes": 1, "sha256": "0" * 64}
            def announce(text):
                if stage == "stdout":
                    now[0] = 20.
            code = self.contract.finish({"invented": True}, True, 20., signals, self.root,
                emit, clock=lambda: now[0], announce=announce)
            with self.subTest(stage=stage):
                self.assertEqual(code, 0 if stage == "none" else 1)
                self.assertNotEqual(written["OUTCOME.json"]["status"], "COMPLETE")
                if stage in ("decision", "stdout", "signal_after_decision"):
                    self.assertIn("TERMINAL_INVALIDATION.json", written)
                if stage in ("initial", "outcome"):
                    self.assertEqual(written["FINAL_DECISION.json"]["status"], "FAILED_PRESERVED")

    def test_complete4884_recovery_journal_receipts_fit_existing16mib_cap(self):
        good, bad = [], []
        for i in range(4884):
            name = self.plan["operation_token"] + ("-e%05d-00" % i)
            record = {"name": name, "state": "acknowledged", "dispatch_may_have_occurred": True,
                "cid": "a" * 64, "resolution_basis": "natural_complete_create_cli_success",
                "journal_base": "member-00", "call_sequence": 16,
                "call_result": {"name": "call-016.result.json", "bytes": 8192, "sha256": "f" * 64},
                "stdout": {"name": "call-016.stdout", "bytes": 1024, "sha256": "f" * 64,
                           "received_bytes": 65536, "complete": True}}
            good.append({"episode": i, "all_dispatch_completions_known": True, "errors": [], "rows": [record]})
            bad.append({"episode": i, "all_dispatch_completions_known": False,
                "errors": [{"name": name, "type": "ContractError", "reason": "x" * 512}],
                "rows": [{"name": name, "state": "journal_or_dispatch_unknown", "dispatch_may_have_occurred": True}]})
        base = {"schema": "hybrid-participant-independent-outer-recovery-v1",
            "namespace_absent_at_final_probe": True, "all_create_completions_known": True,
            "all_recovery_cli_groups_closed": True, "errors": [], "controller_group_closed": True,
            "complete": True, "quarantine_required": False}
        for label, rows in (("all4884_success", good), ("all4884_bounded_journal_errors", bad)):
            body = (json.dumps(dict(base, episode_journals=rows), indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
            SCALE_OBSERVATIONS[label + "_receipt_bytes"] = len(body)
            self.assertLess(len(body) + 65536, 16 * 1048576)

    def engine_case(self, corrupt_workdir=False):
        """Real TrialOwner logic; only external CLI/inspection/exchange are seams."""
        folder = self.root / ("engine-bad-cwd" if corrupt_workdir else "engine-good")
        folder.mkdir()
        trial = self.rows[:2]
        programme = self.root / "delivery/program"
        artifact_pin = self.records[0]["artifacts"]["family_train_selected"]
        pins = {x["name"]: {"bytes": x["bytes"], "sha256": x["sha256"]} for x in self.payload["programme"]["members"]}
        cust = self.sources.modules["donor_checked_source"]
        life = self.sources.modules["donor_create_lifecycle"]
        closer = self.sources.modules["donor_process_closure"]
        TrialOwner = self.sources.modules["trial_transport"].TrialOwner
        owner = TrialOwner(cust, closer, folder, self.sources.runner_root, self.plan, self.lock_sha,
            time.monotonic() + 300, [], "invented-engine", lifecycle=life, cli_group_mode="controller")
        calls, exchanges = [], []
        cid = "a" * 64
        def fake_call(args, **kwargs):
            self.assertEqual(args[0], "create")
            calls.append(args)
            life.mark_dispatch(kwargs["creation"], 1)
            owner.last_call_receipt = {"invented": True}
            return 0, (cid + "\n").encode(), b"", {"invented": True}
        def fake_inspect(ident, absent=False, **kwargs):
            if absent:
                return None
            argv = calls[0]
            idx = argv.index("--entrypoint")
            args = argv[idx + 3:]
            return {"id": cid, "name": "/invented-engine-00", "image": self.plan["image"], "owner": "invented-engine",
                "mounts": [{"Source": str(programme), "Destination": "/program", "RW": False, "Type": "bind"},
                           {"Source": artifact_pin["path"], "Destination": "/model/model.json", "RW": False, "Type": "bind"}],
                "network": "none", "readonly": True, "memory": 1024**3, "swap": 1024**3, "cpus": 10**9,
                "pids": 32, "user": "501:20", "entrypoint": ["/usr/bin/env"], "args": args,
                "caps": ["ALL"], "security": ["no-new-privileges"], "tmpfs": {"/tmp": "rw,noexec,nosuid,nodev,size=64m"},
                "privileged": False, "pid_mode": "", "ipc_mode": "private", "cgroupns_mode": "private", "devices": [],
                "restart": {"Name": "no", "MaximumRetryCount": 0}, "log_driver": "none",
                "workdir": "/program" if corrupt_workdir else "/tmp",
                "state": {"Status": "exited", "ExitCode": 0, "OOMKilled": False}}
        def fake_exchange(cid, protocol, count, *args):
            exchanges.append(count)
            while True:
                query = protocol.next_query()
                if query is None:
                    break
                protocol.commit({"token": query["token"], "probabilities": [.25] * 4})
            return {"complete": True, "invented_external_exchange": True}
        def fake_cleanup(name, cid, creation):
            return {"absent": True, "errors": [], "invented_cleanup": True}
        with patch.object(owner, "call", fake_call), patch.object(owner, "inspect", fake_inspect), \
             patch.object(owner, "exchange", fake_exchange), patch.object(owner, "cleanup", fake_cleanup):
            result, values = owner.run_trial(trial, programme, Path(artifact_pin["path"]), "participant_entry.py", pins, artifact_pin)
        self.assertIn("--workdir=/tmp", calls[0])
        self.assertIn("--network=none", calls[0])
        self.assertEqual(sum(x == "--mount" for x in calls[0]), 2)
        self.assertNotIn(str(self.root / "delivery/private"), " ".join(calls[0]))
        return result, values, exchanges

    def test_existing_engine_accepts_exact_two_mounts_and_tmp_cwd(self):
        result, values, exchanges = self.engine_case()
        self.assertTrue(result["complete"])
        self.assertEqual((len(values), exchanges), (2, [2]))

    def test_existing_engine_rejects_wrong_effective_cwd_before_exchange(self):
        result, values, exchanges = self.engine_case(True)
        self.assertFalse(result["complete"])
        self.assertIn("effective participant isolation", result["error"]["reason"])
        self.assertIsNone(values)
        self.assertEqual(exchanges, [])


if __name__ == "__main__":
    unittest.main()
