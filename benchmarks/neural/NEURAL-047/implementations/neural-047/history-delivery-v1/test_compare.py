"""Generated paired-grading controls; no authentic observations or model calls."""
import copy
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Test-only override lets an isolated new source file reuse installed dependencies.
dependency = Path(os.environ.get("NEURAL047_PAIR_TEST_DEPENDENCY", HERE))
fixture = load("neural047_pair_fixture", dependency / "test_delivery.py")
d = fixture.d
a = load("neural047_pair_audit", dependency / "audit_collection.py")
c = load("neural047_pair_subject", HERE / "compare.py")
score = importlib.import_module(d.public_contract.__module__).score


def records(abstain=None, single_class=False):
    panel, folds = fixture.fixture()
    targets = {key: (0 if single_class and fold_index == 0 else event_index)
               for fold_index, fold in enumerate(panel["folds"])
               for event_index, key in enumerate(fold["case_keys"])}
    private = {"schema": "neural047-targets-v1", "packet_id": panel["packet_id"],
               "targets": [{"case_key": key, "dorsal": value} for key, value in targets.items()]}
    contexts, responses, audits = {}, {}, {}
    for mode in d.MODES:
        contexts[mode], responses[mode], audits[mode] = [], [], []
        for packet in folds:
            session = fixture.session(panel, packet, mode)
            session.open()
            if mode == "typed_viewer":
                session.dispatch(fixture.full_history(packet))
            request = fixture.request(packet)
            if mode == "typed_viewer" and packet["fold_id"] == "fold_000":
                request["predictions"] = [{"case_key": row["case_key"],
                                            "p_dorsal": .9 if targets[row["case_key"]] else .1}
                                           for row in packet["query"]]
            if (mode, packet["fold_id"], packet["arm"]) == abstain:
                request = {"action": "abstain", "reason": "generated deliberate abstention"}
            responses[mode].append(session.dispatch(request))
            contexts[mode].append(copy.deepcopy(session.receipt))
            audits[mode].append({"schema": "neural047-observation-transcript-v1",
                                 "context": copy.deepcopy(session.receipt), "closed": session.closed,
                                 "response_persisted": session.closed, "failure_type": None,
                                 "actions": copy.deepcopy(session.transcript),
                                 "head_sha256": session.transcript_hash,
                                 "accepted_response_payload_bytes": session.transcript_bytes})
    return panel, contexts, responses, audits, private


class PairedGradeControls(unittest.TestCase):
    def compare(self, data, loader=None):
        panel, contexts, responses, audits, private = data
        return c.compare_paired(d, a, score, panel, contexts, responses, audits,
                                loader or (lambda: private))

    def test_complete_pair_reuses_one_target_load_and_original_metrics(self):
        data = records()
        loads = []
        result = self.compare(data, lambda: loads.append(True) or data[-1])
        self.assertEqual(loads, [True])
        self.assertEqual(result["private_target_loads"], 1)
        self.assertEqual(result["scorer_cached_target_callbacks"], 2)
        self.assertEqual(result["paired_differences"]["animals"], 3)
        direct_loss = -(math.log(.75) + math.log(.25)) / 2
        for arm in d.CHANNELS:
            values = result["paired_differences"]["animal_macro"][arm]
            self.assertAlmostEqual(values["balanced_accuracy_difference"], 1 / 6)
            self.assertAlmostEqual(values["log_loss_difference"], (-math.log(.9) - direct_loss) / 3)
        for mode in d.MODES:
            collection = d.collect(data[0], mode, data[1][mode], data[2][mode])
            original = score(data[0], collection["submission"], lambda: data[-1])
            self.assertEqual(result["grades"][mode], original)
        self.assertIsNone(result["scientific_success"])
        self.assertIsNone(result["paired_differences"]["uncertainty"])

    def test_one_condition_abstention_blocks_all_target_access(self):
        for mode in d.MODES:
            with self.subTest(mode=mode):
                result = self.compare(records(abstain=(mode, "fold_001", "NB")),
                                      lambda: self.fail("Abstention must avoid private targets"))
                self.assertEqual(result["status"], "abstained")
                self.assertEqual(result["private_target_loads"], 0)
                self.assertIsNone(result["grades"])
                self.assertIsNone(result["paired_differences"])

    def test_incomplete_or_modified_second_mode_is_rejected_before_targets(self):
        for failure in ("missing", "changed_audit", "changed_prediction"):
            data = records()
            if failure == "missing":
                data[2]["typed_viewer"].pop()
            elif failure == "changed_audit":
                data[3]["typed_viewer"][0]["head_sha256"] = "0" * 64
            else:
                data[2]["typed_viewer"][0]["outcome"]["predictions"][0]["p_dorsal"] = .2
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                self.compare(data, lambda: self.fail("Both conditions must be accepted first"))

    def test_single_class_worm_preserves_all_rows_and_undefined_panel_ba(self):
        result = self.compare(records(single_class=True))
        paired = result["paired_differences"]
        self.assertEqual(len(paired["groups"]), 3)
        for arm in d.CHANNELS:
            self.assertIsNone(paired["groups"][0]["arms"][arm]["balanced_accuracy_difference"])
            self.assertIsNone(paired["animal_macro"][arm]["balanced_accuracy_difference"])
            self.assertIsNotNone(paired["animal_macro"][arm]["log_loss_difference"])

    def test_animal_differences_are_not_weighted_by_event_count(self):
        result = self.compare(records())
        grades = copy.deepcopy(result["grades"])
        for index, event_count in enumerate((2, 20, 200)):
            for mode in d.MODES:
                grades[mode]["groups"][index]["events"] = event_count
                grades[mode]["groups"][index]["class_counts"] = [event_count // 2] * 2
        paired = c._paired_differences(d, grades)
        for arm in d.CHANNELS:
            self.assertAlmostEqual(paired["animal_macro"][arm]["balanced_accuracy_difference"], 1 / 6)
        grades["typed_viewer"]["groups"].reverse()
        with self.assertRaises(ValueError):
            c._paired_differences(d, grades)

    def test_target_loader_cannot_change_admitted_public_submission(self):
        data = records()
        expected = self.compare(data)

        def loader():
            data[0]["folds"].clear()
            data[2]["direct_observation"].clear()
            return data[-1]

        self.assertEqual(self.compare(data, loader), expected)

    def test_operator_cli_writes_one_private_grade_and_refuses_overwrite(self):
        data = records()
        with tempfile.TemporaryDirectory(prefix="n047-pair-") as temporary:
            root = Path(temporary).resolve()
            names = ("panel", "contexts", "responses", "audits", "private-targets")
            args = []
            for name, value in zip(names, data):
                path = root / (name + ".json")
                path.write_bytes(d.io.canonical(value))
                args += ["--" + name, str(path)]
            output = root / "grade.json"
            args += ["--output", str(output)]
            with patch.object(c, "_load_sources", return_value=(d, a, score)):
                c.main(args)
                self.assertEqual(json.loads(output.read_text())["status"], "scored")
                original = output.read_bytes()
                with self.assertRaises(ValueError):
                    c.main(args)
                self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=1)
