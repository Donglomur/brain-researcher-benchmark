"""Generated CLI controls for input hard-link preservation; no study data."""
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "evaluator.py"
e = types.ModuleType("voice_output_identity_evaluator")
exec(compile(SOURCE.read_bytes(), str(SOURCE), "exec"), e.__dict__)


def write_inputs(root):
    plan = {"schema_version": 1, "task_id": e.TASK_ID,
            "trial_ids": ["first", "second"], "condition_ids": ["brain"],
            "cohort_label": "prospective", "tokenization_policy_id": "generated-words",
            "phonemization_policy_id": "generated-phonemes", "pairing_policy_id": "generated-pair",
            "pairs": [{"pair_id": "pair", "trial_ids": ["first", "second"],
                       "listener_ids": [str(i) for i in range(7)]}]}
    references = [{"trial_id": trial, "words": [trial], "phonemes": [trial]}
                  for trial in plan["trial_ids"]]
    predictions = [{**row, "condition_id": "brain", "listener_id": str(listener)}
                   for row in references for listener in range(7)]
    for name, value in zip(("plan", "reference", "prediction"), (plan, references, predictions)):
        (root / name).write_text(json.dumps(value))
    return [item for name in ("plan", "reference", "prediction", "output")
            for item in ("--" + name, str(root / name))]


class OutputIdentityTests(unittest.TestCase):
    def test_input_hard_links_are_rejected_without_modifying_any_input(self):
        for aliased_name in ("plan", "reference", "prediction"):
            with self.subTest(aliased_name=aliased_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                command = write_inputs(root)
                before = {name: (root / name).read_bytes() for name in ("plan", "reference", "prediction")}
                (root / "output").hardlink_to(root / aliased_name)
                with self.assertRaises(SystemExit) as caught:
                    e.main(["transcriptions", *command])
                self.assertEqual(caught.exception.code, 2)
                self.assertEqual((root / "output").read_bytes(), before[aliased_name])
                for name, raw in before.items():
                    self.assertEqual((root / name).read_bytes(), raw)

    def test_distinct_output_retains_exact_scores_and_input_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = write_inputs(root)
            raw = {name: (root / name).read_bytes() for name in ("plan", "reference", "prediction")}
            expected = e.evaluate_transcriptions(*(e.parse_json(raw[name]) for name in raw))
            expected["input_sha256"] = {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
            e.main(["transcriptions", *command])
            self.assertEqual(json.loads((root / "output").read_text()), expected)
            for name, value in raw.items():
                self.assertEqual((root / name).read_bytes(), value)


if __name__ == "__main__":
    unittest.main()
