"""Generated source-integration controls; no native or scientific qualification.

Run only in an explicitly selected fresh external NEURAL010_PAIRED_TEST_ROOT.
All evidence remains there. The public filename roster is authentic metadata;
every duration, event, signal identity, prediction and service response is a
generated control. No signal window, detector, renderer or model is executed.
"""
import contextlib
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from fixture_builder import (
    DURATION, LIMITS, PACKAGE, GeneratedFixture, digest, encoded, load_source,
    pin, read_json, write,
)


class PairedConditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected = os.environ.get("NEURAL010_PAIRED_TEST_ROOT")
        if not selected:
            raise RuntimeError("select a fresh external NEURAL010_PAIRED_TEST_ROOT")
        cls.root = Path(selected)
        if (not cls.root.is_absolute() or ".." in cls.root.parts
                or cls.root.exists() or cls.root.is_relative_to(PACKAGE)
                or len(str(cls.root).encode()) > 512
                or any(p.is_symlink() for p in cls.root.parents)):
            raise RuntimeError("fresh ordinary external absolute test root, at most512 path bytes")
        cls.root.mkdir(mode=0o700)
        (cls.root / "cases").mkdir(mode=0o700)
        cls.runtime = load_source()
        cls.fixture = GeneratedFixture(cls.root / "fixture", cls.runtime)
        cls.viewer_empty = cls.fixture.campaign("viewer-empty", "typed_viewer", [])
        cls.viewer_perfect = cls.fixture.campaign("viewer-perfect", "typed_viewer", [[0, 1]])
        cls.program_perfect = cls.fixture.campaign("program-perfect", "frozen_program", [[0, 1]])
        cls.program_far = cls.fixture.campaign("program-far", "frozen_program", [[100, 101]])

    @classmethod
    def tearDownClass(cls):
        # Metadata inventory only: keep generated failures and successes rather
        # than cleaning them up or inferring any qualification from their count.
        count, size = 0, 0
        for folder, dirs, files in os.walk(cls.root):
            if any((Path(folder) / name).is_symlink() for name in dirs + files):
                raise AssertionError("unexpected generated fixture symlink")
            for name in files:
                count += 1
                size += (Path(folder) / name).stat().st_size
        write(cls.root / "GENERATED_CONTROL_INVENTORY.json", encoded({
            "schema": "neural010-paired-generated-inventory-v1",
            "files_before_inventory": count, "bytes_before_inventory": size,
            "source_run_campaigns": {name: c["run_costs"] for name, c in cls.fixture.campaigns.items()},
            "records_per_campaign": 686, "people_per_campaign": 23,
            "generated_duration_seconds": DURATION, "scientific_qualification": False,
            "native_understanding_established": False,
        }))
        if count > 12000 or size > 128 * 1048576:
            raise AssertionError("generated artifact estimate exceeded: inspect retained evidence")

    def setUp(self):
        self.case = self.root / "cases" / self._testMethodName
        self.case.mkdir(mode=0o700)
        self.target_opens = 0

    def selection(self, left=None, right=None, **kwargs):
        return self.fixture.pair_selection(self.case / "selection", left or self.viewer_empty,
                                           right or self.program_perfect, **kwargs)

    def invoke(self, selection, *, before_open=None, authority_pin=None, read_roots=None):
        raw, auth, selected_pin = selection
        roots = [str(self.root)] if read_roots is None else read_roots
        actual_open = os.open
        def observed_open(path, *args, **kwargs):
            is_target = not isinstance(path, int) and Path(os.fsdecode(path)).name == "assessment.json"
            if is_target:
                self.target_opens += 1
            if before_open is not None:
                before_open(path, is_target)
            return actual_open(path, *args, **kwargs)
        with mock.patch("os.open", observed_open):
            result_pin = self.runtime["pair"].compare(
                raw, auth, selected_pin if authority_pin is None else authority_pin,
                source_pin=self.runtime["source"], source_root=self.runtime["root"],
                output_root=str(self.case / "comparison"), read_roots=roots,
                initial_source_reads=self.runtime["reads"])
        body = Path(result_pin["path"]).read_bytes()
        self.assertEqual(pin(body), {k: result_pin[k] for k in ("bytes", "sha256")})
        return json.loads(body)

    def original(self, result, side):
        desc = result["original_result_pins"][side]
        raw = Path(desc["path"]).read_bytes()
        self.assertEqual(pin(raw), {k: desc[k] for k in ("bytes", "sha256")})
        return json.loads(raw)

    def refused(self, selection, *, expected_hits=None):
        with self.assertRaises(ValueError):
            self.invoke(selection)
        self.assertEqual(self.target_opens, 0, "rejected pair must never open protected targets")
        self.assertFalse((self.case / "comparison/COMPARISON.json").exists())
        self.assertFalse((self.case / "comparison/left/RESULT.json").exists())
        self.assertFalse((self.case / "comparison/right/RESULT.json").exists())
        failure = read_json(self.case / "comparison/FAILURE.json")
        self.assertFalse(failure["comparison_complete"])
        self.assertTrue(failure["charges_retained_on_failure"])
        self.assertGreater(failure["costs"]["read_bytes"], 0)
        self.assertTrue(all(n == 0 for n in failure["replay_target_uses"].values()))
        if expected_hits is not None:
            self.assertEqual(failure["admission_boundary_hits"], expected_hits)
        return failure

    def test_complete_pair_preserves_original_results_and_one_target_capture(self):
        selection = self.selection()
        result = self.invoke(selection)
        self.assertNotIn("original_outcomes", result, "preserve pinned originals without duplicating their full bodies")
        self.assertEqual(self.target_opens, 1)
        self.assertEqual((result["recordings"], result["people"], result["observed_seconds"]),
                         (686, 23, 686 * DURATION))
        self.assertEqual(result["joint_admission"]["physical_protected_assessment_captures"], 1)
        self.assertTrue(result["joint_admission"]["both_complete_before_target"])
        self.assertTrue(result["joint_admission"]["captured_operand_replay_only"])
        for key in ("scientific_qualification", "native_understanding_established",
                    "real_world_isolation_established", "rendering_fidelity_established",
                    "statistical_superiority_established"):
            self.assertIs(result[key], False)
        self.assertIsNone(result["ranking"])
        self.assertEqual(result["evidence_class"], "generated_control")
        selected = json.loads(selection[0])
        for side, expected in (("left", 0.0), ("right", 1.0)):
            original = self.original(result, side)
            self.assertEqual(set(original["patients"]), set(self.fixture.people))
            self.assertEqual(original["biological_patients"], 23)
            for patient in original["patients"].values():
                self.assertEqual(patient["candidate"]["event_f1"], expected)
                self.assertEqual(patient["candidate"]["event_sensitivity"], expected)
            # Independent direct source route, outside the paired target-open
            # counter. Its full original JSON must equal the retained arm JSON.
            arm = selected[side]
            raw, auth = (Path(arm[k]["path"]).read_bytes() for k in ("request", "authority"))
            legacy = self.runtime["legacy"]
            io = legacy["u"].IO([str(self.root), str(legacy["root"])], legacy["u"].Budget(LIMITS))
            desc = legacy["campaign"].score(raw, auth, pin(auth), source_pin=legacy["source"],
                source_root=legacy["root"], output_root=self.case / ("direct-" + side), io=io)
            self.assertEqual(original, read_json(desc["path"]))
        self.assertEqual(len(result["paired_montages"]), 1)
        montage = next(iter(result["paired_montages"].values()))
        self.assertEqual(montage["expected_people"], 23)
        self.assertEqual(montage["metrics"], result["paired_metrics"])
        self.assertEqual(result["paired_metrics"]["event_f1"]["complete_support_mean"], -1.0)

    def test_identical_decisions_have_zero_paired_differences(self):
        result = self.invoke(self.selection(left=self.viewer_perfect))
        self.assertEqual(self.target_opens, 1)
        for metric in result["paired_metrics"].values():
            self.assertEqual(metric["defined_people"], 23)
            self.assertEqual(metric["complete_support_mean"], 0)
            self.assertTrue(all(r["left_minus_right"] == 0 for r in metric["people"].values()))

    def test_reversing_conditions_reverses_signed_differences(self):
        result = self.invoke(self.selection(left=self.program_perfect, right=self.viewer_empty))
        for name in ("event_f1", "event_sensitivity"):
            metric = result["paired_metrics"][name]
            self.assertEqual(metric["complete_support_mean"], 1.0)
            self.assertTrue(all(r["left_minus_right"] == 1 for r in metric["people"].values()))
        self.assertEqual(result["conditions"]["left"]["mode"], "frozen_program")
        self.assertEqual(result["conditions"]["right"]["mode"], "typed_viewer")

    def test_false_alarm_direction_uses_all_observed_seconds(self):
        result = self.invoke(self.selection(right=self.program_far))
        metric = result["paired_metrics"]["false_alarms_per_24_observed_hours"]
        self.assertEqual(metric["better_direction"], "lower")
        self.assertEqual(metric["complete_support_mean"], -86400 / DURATION)
        self.assertTrue(all(r["left"] == 0 and r["right"] == 86400 / DURATION
                            for r in metric["people"].values()))
        self.assertEqual(result["paired_metrics"]["event_f1"]["better_direction"], "higher")
        self.assertEqual(result["paired_metrics"]["event_f1"]["complete_support_mean"], 0)

    def test_missing_second_campaign_record_refuses_before_target(self):
        bad = self.fixture.missing_second_record(self.program_perfect, self.case / "bad-campaign")
        self.refused(self.selection(right=bad), expected_hits={"left": 1, "right": 0})

    def test_changed_frozen_support_refuses_before_target(self):
        bad = self.fixture.clone_campaign(self.program_perfect, self.case / "bad-campaign")
        path = bad["root"] / "SUPPORT.json"
        raw = path.read_bytes() + b" "
        path.write_bytes(raw)
        complete = read_json(bad["root"] / "CAMPAIGN.json")
        complete["support"] = pin(raw)
        body = encoded(complete)
        (bad["root"] / "CAMPAIGN.json").write_bytes(body)
        bad["complete"] = {"path": str(bad["root"] / "CAMPAIGN.json"), **pin(body)}
        self.refused(self.selection(right=bad), expected_hits={"left": 1, "right": 0})

    def test_changed_references_refuse_before_target(self):
        refs = self.fixture.references(self.case / "changed-references", changed=True)
        changed = self.fixture.campaign("program-changed-references", "frozen_program", [[0, 1]], refs=refs)
        self.refused(self.selection(right=changed), expected_hits={"left": 1, "right": 1})

    def test_changed_assessment_selection_refuses_before_target(self):
        changed = dict(self.fixture.assessment, sha256=digest("WRONG ASSESSMENT IDENTITY"))
        self.refused(self.selection(assessment=changed))

    def test_changed_learning_policy_refuses_before_target(self):
        changed = self.fixture.campaign("program-changed-learning", "frozen_program", [[0, 1]],
                                       learning=digest("DIFFERENT LEARNING POLICY"))
        self.refused(self.selection(right=changed), expected_hits={"left": 1, "right": 1})

    def test_reused_context_ids_refuse_before_target(self):
        changed = self.fixture.campaign("program-reused-context", "frozen_program", [[0, 1]],
                                       context_alias="viewer-empty")
        self.refused(self.selection(right=changed), expected_hits={"left": 1, "right": 1})

    def test_cross_condition_exchange_overlap_is_rejected(self):
        pair, u = self.runtime["pair"], self.runtime["legacy"]["u"]
        left = copy.deepcopy(self.viewer_empty["request"])
        right = copy.deepcopy(self.program_perfect["request"])
        person = self.fixture.people[0]
        path = left["contexts"][person]["participant_exchange"]
        for collision in (path, path + "/nested", path.upper()):
            with self.subTest(collision=collision):
                right["contexts"][person]["custody_exchange"] = collision
                with self.assertRaisesRegex(ValueError, "namespaces must be disjoint"):
                    pair._disjoint_contexts(left, right, u)

    def test_other22_training_refuses_zero_training_pair_before_target(self):
        trained = self.fixture.campaign("program-other22", "frozen_program", [[0, 1]], training="other22")
        self.refused(self.selection(right=trained), expected_hits={"left": 1, "right": 1})

    def test_reference_dictionary_order_does_not_change_scoring(self):
        reordered = self.fixture.campaign("program-reordered", "frozen_program", [[0, 1]],
                                         reverse_reference_order=True)
        normal = read_json(self.program_perfect["request"]["evaluation"]["path"])
        changed = read_json(reordered["request"]["evaluation"]["path"])
        self.assertNotEqual(list(normal["references"]), list(changed["references"]))
        normal_proof = read_json(normal["reference_provenance"]["path"])
        changed_proof = read_json(changed["reference_provenance"]["path"])
        self.assertNotEqual(list(normal_proof["reference_runs"]), list(changed_proof["reference_runs"]))
        self.assertEqual(normal["references"], changed["references"])
        self.assertEqual(normal_proof["reference_runs"], changed_proof["reference_runs"])
        result = self.invoke(self.selection(right=reordered))
        self.assertEqual(self.target_opens, 1)
        self.assertEqual(result["paired_metrics"]["event_f1"]["complete_support_mean"], -1)

    def test_post_admission_operand_mutation_replays_captured_bytes(self):
        selection = self.selection()
        operand = self.program_perfect["root"] / "SELECTED_REQUEST.json"
        original = operand.read_bytes()
        mutated = []
        def mutate(_path, is_target):
            if is_target and not mutated:
                operand.chmod(0o600)
                operand.write_bytes(b"CHANGED AFTER BOTH ADMISSIONS\n")
                operand.chmod(0o400)
                mutated.append(True)
        try:
            result = self.invoke(selection, before_open=mutate)
        finally:
            operand.chmod(0o600)
            operand.write_bytes(original)
            operand.chmod(0o400)
        self.assertEqual(mutated, [True])
        self.assertEqual(self.target_opens, 1)
        self.assertEqual(result["paired_metrics"]["event_f1"]["complete_support_mean"], -1)
        write(self.case / "MUTATION_CONTROL.json", encoded({"generated_only": True,
              "operand": str(operand), "mutation_at_first_physical_assessment_open": True,
              "restored_pin": pin(original)}))

    def test_caller_container_mutation_cannot_redirect_snapshotted_selection(self):
        selection = self.selection()
        selected_pin, roots, changed = dict(selection[2]), [str(self.root)], []
        def mutate(_path, _is_target):
            if not changed:
                selected_pin["sha256"] = digest("MUTATED CALLER AUTHORITY")
                roots.clear()
                changed.append(True)
        result = self.invoke(selection, before_open=mutate, authority_pin=selected_pin, read_roots=roots)
        self.assertEqual(changed, [True])
        self.assertEqual(roots, [])
        self.assertEqual(self.target_opens, 1)
        self.assertEqual(result["paired_metrics"]["event_f1"]["complete_support_mean"], -1)

    def test_capture_budget_exhaustion_refuses_without_target_read(self):
        failure = self.refused(self.selection(capture_bytes=1), expected_hits={"left": 0, "right": 0})
        self.assertEqual(failure["capture_accounted_bytes"], 0)
        self.assertGreater(failure["costs"]["write_bytes"], 0)

    def adapter(self):
        u, replay = self.runtime["legacy"]["u"], self.runtime["replay"]
        actual = u.IO([str(self.root)], u.Budget(LIMITS))
        return actual, replay.CapturedIO(actual, replay.Retention(128 * 1048576), u)

    def defer(self, adapter):
        with self.assertRaises(self.runtime["replay"].DeferredAssessment) as caught:
            adapter.capture_assessment(self.fixture.assessment)
        self.assertIs(caught.exception, adapter.boundary)
        self.assertEqual(adapter.admission_hits, 1)
        adapter.enable_replay(self.fixture.assessment_raw)

    def test_names_journal_stat_and_capture_replay_have_no_filesystem_fallback(self):
        folder = self.case / "operands"
        body = write(folder / "metadata.json", encoded({"generated": "body"}))
        journal = write(folder / "journal.json", encoded({"generated": "journal"}))
        stat_only = write(folder / "opaque.json", b"GENERATED OPAQUE EXTENT")
        actual, adapter = self.adapter()
        expected_names = adapter.names(folder)
        expected_journal = adapter.journal_body(journal["path"], "control_journal")
        self.assertIsNone(adapter.stat_only(stat_only, "control_stat"))
        expected_body = adapter.capture(body, "control_body")
        self.defer(adapter)
        for item in folder.iterdir():
            item.unlink()
        write(folder / "changed.json", b"new namespace")
        with contextlib.ExitStack() as stack:
            for method in ("names", "journal_body", "stat_only", "capture", "capture_assessment"):
                stack.enter_context(mock.patch.object(actual, method,
                    side_effect=AssertionError("replay must not fall back to physical " + method)))
            self.assertEqual(adapter.names(folder), expected_names)
            self.assertEqual(adapter.journal_body(journal["path"], "control_journal"), expected_journal)
            self.assertIsNone(adapter.stat_only(stat_only, "control_stat"))
            self.assertEqual(adapter.capture(body, "control_body"), expected_body)
            self.assertEqual(adapter.capture_assessment(self.fixture.assessment), self.fixture.assessment_raw)
        self.assertEqual(adapter.cursor, len(adapter.events))
        self.assertEqual(adapter.replay_hits, 1)

    def test_uncaptured_or_reordered_replay_access_is_refused(self):
        desc = write(self.case / "metadata.json", b"generated replay body")
        actual, adapter = self.adapter()
        adapter.capture(desc, "selected_role")
        self.defer(adapter)
        with mock.patch.object(actual, "capture", side_effect=AssertionError("unexpected disk fallback")):
            with self.assertRaisesRegex(ValueError, "identity/order"):
                adapter.capture(desc, "different_role")
            self.assertEqual(adapter.cursor, 0)
            self.assertEqual(adapter.capture(desc, "selected_role"), b"generated replay body")
            with self.assertRaisesRegex(ValueError, "unexpected replay access"):
                adapter.capture(desc, "selected_role")
        self.assertEqual(adapter.replay_hits, 0)

    def test_undefined_metrics_retain_all_people_and_withhold_partial_mean(self):
        metrics = self.runtime["pair"].METRICS
        left = {p: {"candidate": {m: 0.5 for m in metrics}} for p in self.fixture.people}
        right = copy.deepcopy(left)
        p, q, r = self.fixture.people[:3]
        left[p]["candidate"]["event_f1"] = None
        right[q]["candidate"]["event_sensitivity"] = None
        left[r]["candidate"]["false_alarms_per_24_observed_hours"] = None
        right[r]["candidate"]["false_alarms_per_24_observed_hours"] = None
        result = self.runtime["pair"]._differences(left, right, self.fixture.people)
        for metric in result.values():
            self.assertEqual(metric["expected_people"], 23)
            self.assertEqual(metric["defined_people"], 22)
            self.assertEqual(set(metric["people"]), set(self.fixture.people))
            self.assertIsNone(metric["complete_support_mean"])
        self.assertEqual(result["event_f1"]["people"][p]["undefined_reason"], "left_undefined")
        self.assertEqual(result["event_sensitivity"]["people"][q]["undefined_reason"], "right_undefined")
        self.assertEqual(result["false_alarms_per_24_observed_hours"]["people"][r]["undefined_reason"], "both_undefined")

    def test_isolated_entry_cli_uses_exact_pins_and_retains_reservation(self):
        selection = self.selection()
        ledger = self.case / "invocation-ledger"
        ledger.mkdir(mode=0o700)
        source = self.runtime["source"]
        args = [sys.executable, "-I", "-S", "-B", str(PACKAGE / "entry.py"),
                "--source-bytes", str(source["bytes"]), "--source-sha256", source["sha256"],
                "--read-root", str(self.root), "--output", str(self.case / "cli-comparison"),
                "--reservation-root", str(ledger)]
        for name, raw in (("request", selection[0]), ("authority", selection[1])):
            args += ["--" + name, str(self.case / "selection" / ("paired-" + name + ".json")),
                     "--" + name + "-bytes", str(len(raw)), "--" + name + "-sha256", pin(raw)["sha256"]]
        completed = subprocess.run(args, cwd=self.case, env={"PATH": "/usr/bin:/bin", "LANG": "C"},
                                   stdin=subprocess.DEVNULL, capture_output=True, timeout=180, check=False)
        # Fixed entry emits a single bounded JSON status, never model output.
        write(self.case / "CLI_STDOUT.json", completed.stdout or b"\n")
        write(self.case / "CLI_STDERR.txt", completed.stderr or b"\n")
        self.assertLessEqual(len(completed.stdout) + len(completed.stderr), 16384)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        status = json.loads(completed.stdout)
        self.assertFalse(status["scientific_qualification"])
        raw = Path(status["result"]["path"]).read_bytes()
        self.assertEqual(pin(raw), {k: status["result"][k] for k in ("bytes", "sha256")})
        result = json.loads(raw)
        self.assertEqual(result["paired_metrics"]["event_f1"]["complete_support_mean"], -1)
        reservations = list(ledger.iterdir())
        self.assertEqual([p.name for p in reservations], [pin(selection[0])["sha256"] + ".json"])
        self.assertTrue(read_json(reservations[0])["charge_retained_on_failure"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
