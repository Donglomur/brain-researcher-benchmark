"""Generated protocol controls against the exact existing causal consumer.

No authentic observations, model artifact, API, fit, score or replay is used.
"""
import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


def import_local():
    path = Path(__file__).with_name("direct_dialogue.py")
    spec = importlib.util.spec_from_file_location("hybrid_direct_dialogue", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = import_local()
C = None


def observation(t=0):
    return {"nL": 2, "nR": 60, "nB": 10, "rL": 1, "rR": 0,
            "muL": .5, "muR": .5, "gL": True, "gR": False,
            "first_visit": True, "after_first_visit": False, "t": t}


def fixture():
    # Two invented trials; the second person/session identifiers never appear
    # in messages. These five decisions are NOT the authentic full cohort.
    rows = []
    for trial, length in ((57, 3), (61, 2)):
        for i in range(length):
            rows.append(C.Decision(810001 + len(rows), "19", 4, trial,
                                  C.validate_observation(observation(i)),
                                  3 if i == length - 1 else 1))
    return rows


def adapter(rows=None):
    return A.DirectDialogue(C, C.OnlineSession(fixture() if rows is None else rows, b"invented-private-token-key-0000000"))


def answer(request, probabilities=None):
    query = json.loads(request["messages"][-1]["content"])
    return json.dumps({"token": query["token"], "probabilities": probabilities or [.25] * 4}).encode()


class DialogueControls(unittest.TestCase):
    def test_complete_generated_sequence_commits_real_consumer_and_resets_history(self):
        a = adapter(); lengths = []; markers = []; predictions = []
        while (request := a.next_request()) is not None:
            lengths.append(len(request["messages"])); markers.append(request["new_trial"])
            self.assertEqual(request["condition"], "unassisted_numeric_dialogue")
            self.assertIsNone(a.submit(answer(request)))
        predictions = a.finished_predictions()
        self.assertEqual(lengths, [2, 4, 6, 2, 4])
        self.assertEqual(markers, [True, False, False, True, False])
        self.assertEqual([d.source_row for d, _ in predictions], [d.source_row for d in fixture()])
        self.assertTrue(all(p == (.25,) * 4 for _, p in predictions))

    def test_query_reveal_before_commit_aborts_without_retry(self):
        a = adapter(); q = a.next_request()
        with self.assertRaises(A.DialogueError): a.next_request()
        with self.assertRaises(A.DialogueError): a.submit(answer(q))
        with self.assertRaises(A.DialogueError): a.finished_predictions()

    def test_replayed_token_is_rejected_by_existing_causal_consumer(self):
        a = adapter(); q1 = a.next_request(); old = answer(q1); a.submit(old)
        a.next_request()
        with self.assertRaises(C.ContractError): a.submit(old)
        with self.assertRaises(A.DialogueError): a.next_request()

    def test_duplicate_or_tool_envelope_or_multiple_json_answers_abort(self):
        for kind in ("duplicate", "tool", "array", "two", "prose"):
            with self.subTest(kind=kind):
                a = adapter(); q = a.next_request(); good = answer(q)
                token = json.loads(good)["token"]
                replies = {
                    "duplicate": (b'{"token":"' + token.encode() + b'","token":"' + token.encode() + b'","probabilities":[0.25,0.25,0.25,0.25]}'),
                    "tool": json.dumps({**json.loads(good), "tool_calls": []}).encode(),
                    "array": b"[" + good + b"]", "two": good + good,
                    "prose": b"My answer is " + good,
                }
                with self.assertRaises((ValueError, TypeError)): a.submit(replies[kind])
                with self.assertRaises(A.DialogueError): a.next_request()

    def test_invalid_probabilities_keep_original_rule(self):
        for probabilities in ([0, .2, .3, .5], [True, .2, .3, .5], [.2] * 4, [.25] * 3, [float("nan"), .2, .3, .5]):
            with self.subTest(probabilities=probabilities):
                a = adapter(); q = a.next_request()
                with self.assertRaises(C.ContractError): a.submit(answer(q, probabilities))
                with self.assertRaises(A.DialogueError): a.finished_predictions()

    def test_response_byte_bound_and_type_are_not_relaxed(self):
        for body in (b" " * 4097, "not bytes"):
            a = adapter(); a.next_request()
            with self.assertRaises(C.ContractError): a.submit(body)

    def test_public_request_copy_cannot_mutate_stored_history(self):
        a = adapter(); q = a.next_request(); good = answer(q)
        q["messages"][0]["content"] = "injected"
        q["messages"][-1]["content"] = "injected"
        q["messages"].append({"role": "user", "content": "extra"})
        a.submit(good); following = a.next_request()
        self.assertEqual(following["messages"][0]["content"], A.SYSTEM_PROMPT)
        self.assertEqual(len(following["messages"]), 4)
        self.assertNotIn("injected", json.dumps(following))

    def test_only_current_public_fields_and_own_response_enter_history(self):
        a = adapter(); q = a.next_request()
        current = json.loads(q["messages"][-1]["content"])
        self.assertEqual(set(current), {"schema", "token", "new_trial", "observation"})
        self.assertEqual(set(current["observation"]), set(C.FEATURES))
        self.assertEqual(len(current["token"]), 64)
        self.assertTrue({"source_row", "subject", "session", "trial", "action", "remaining"}.isdisjoint(current))
        raw = answer(q); a.submit(raw); following = a.next_request()
        self.assertEqual(json.loads(following["messages"][2]["content"]), json.loads(raw))

    def test_future_labels_length_and_states_do_not_change_first_request(self):
        original = fixture(); changed = list(original)
        altered = observation(2); altered.update(nL=5, rL=2, muL=3/7)
        changed[-1] = replace(changed[-1], action=4, values=C.validate_observation(altered))
        changed.append(replace(changed[-1], source_row=999999, trial=99))
        self.assertEqual(adapter(original).next_request(), adapter(changed).next_request())

    def test_later_trial_has_no_prior_messages_or_tokens(self):
        a = adapter(); prior = []
        for _ in range(3):
            q = a.next_request(); prior.append(json.loads(q["messages"][-1]["content"])["token"]); a.submit(answer(q))
        q = a.next_request()
        self.assertEqual([m["role"] for m in q["messages"]], ["system", "user"])
        self.assertTrue(all(token not in json.dumps(q) for token in prior))

    def test_roundoff_only_probability_normalization_is_preserved(self):
        a = adapter(fixture()[:1]); q = a.next_request(); a.submit(answer(q, [.25, .25, .25, .2500000001]))
        self.assertIsNone(a.next_request())
        p = a.finished_predictions()[0][1]
        self.assertAlmostEqual(sum(p), 1.0, places=15)
        self.assertNotEqual(p, (.25,) * 4)

    def test_finish_requires_terminal_stream_and_no_new_requests_after_finish(self):
        a = adapter(fixture()[:1]); q = a.next_request()
        with self.assertRaises(A.DialogueError): a.finished_predictions()
        a.submit(answer(q))
        with self.assertRaises(A.DialogueError): a.finished_predictions()
        self.assertIsNone(a.next_request()); self.assertEqual(len(a.finished_predictions()), 1)
        with self.assertRaises(A.DialogueError): a.next_request()
        with self.assertRaises(A.DialogueError): a.finished_predictions()

    def test_changed_consumer_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "consumer.py"
            p.write_bytes(b"raise RuntimeError('must not execute')\n")
            with self.assertRaises(A.DialogueError): A.load_consumer(p)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--consumer-source", type=Path)
    args, rest = parser.parse_known_args()
    C = A.load_consumer(args.consumer_source)
    unittest.main(argv=[sys.argv[0], *rest])
