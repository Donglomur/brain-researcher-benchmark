"""Invented protocol tests only. Fake bytes are NOT scientific NPZ evidence."""
import unittest

from adaptive_protocol import Limits, PairedStudy, Reply, Session, Usage, digest

IDS = tuple("invented-trial-%03d" % i for i in range(574))
TOOLS = ("python@sha256:" + "a" * 64, "model@sha256:" + "b" * 64)
CAP = Usage(calls=8, cpu_us=1000, model_input_tokens=100,
            model_output_tokens=100, model_cost_microusd=100)
LIMITS = Limits(CAP, Usage(calls=2, cpu_us=200, model_input_tokens=20,
                         model_output_tokens=20, model_cost_microusd=20),
                wall_us=10000, preparation_wall_us=2000,
                max_memory_bytes=1000000, response_bytes=4096)
RESERVE = Usage(calls=1, cpu_us=100, model_input_tokens=10,
                model_output_tokens=10, model_cost_microusd=10)
OUTPUT = b"INVENTED opaque output; test transport only; NOT a valid predictions.npz"


class Clock:
    def __init__(self):
        self.value = 0
    def __call__(self):
        return self.value


class InventedBackend:
    def __init__(self):
        self.log = []
        self.stop_ok = True
        self.validate_ok = True
        self.commit_ok = True
        self.error = None
        self.actual = RESERVE
        self.memory = 4096
        self.origin_override = None
        self.sha_override = None
        self.output = OUTPUT
        self.during_stop = None
        self.during_validate = None
        self.payload_override = None
        self.observed_request = None
        self.controller_commit_ok = True
        self.finalize_order = []

    def public(self, request, **kwargs):
        self.log.append("public")
        self.observed_request = request
        if self.error:
            raise self.error
        # Invented counts demonstrate a public training-derived estimate, not
        # any genuine dataset or scientific model execution.
        payload = ({"invented_train_counts": [1, 2, 0, 1]} if request["op"] == "view"
                   else {"invented_training_mean": sum([1, 2, 0, 1]) / 4})
        if self.payload_override is not None:
            payload = self.payload_override
        origin = ("preparation" if kwargs["controller_sha256"] is None else
                  "committed_program" if kwargs["mode"] == "frozen_program" else
                  "adaptive_policy")
        return Reply(payload, self.actual, self.memory,
                     self.sha_override or kwargs["controller_sha256"],
                     self.origin_override or origin)

    def freeze_controller(self, source, mode):
        self.log.append("controller_commit")
        self.controller_source = bytes(source)
        return digest(source) if self.controller_commit_ok else "0" * 64

    def stop(self):
        self.log.append("stop")
        if self.during_stop:
            self.during_stop()
        return dict.fromkeys(("controller", "tools", "producer", "holder", "volume"),
                             self.stop_ok)

    def finalize(self):
        # Mirror the existing collector lifecycle: do not destroy tmpfs first.
        self.log.append("finalize")
        self.finalize_order.append("producer_stopped")
        if self.during_stop:
            self.during_stop()
        self.finalize_order.append("captured_with_live_holder")
        captured = self.output
        self.finalize_order.append("holder_volume_removed")
        absence = dict.fromkeys(("controller", "tools", "producer", "holder", "volume"),
                                self.stop_ok)
        return captured, absence

    def commit(self, data, receipt):
        self.log.append("commit")
        self.captured = bytes(data)
        self.commit_receipt = receipt
        return digest(data) if self.commit_ok else "0" * 64

    def validate(self, data):
        self.log.append("validate")
        if self.during_validate:
            self.during_validate()
        assert data == self.captured
        # This is a lifecycle stub, explicitly not NPZ/scientific validation.
        return {"status": "valid_prediction_contract" if self.validate_ok else "rejected_no_score",
                "prediction_contract_valid": self.validate_ok,
                "scientific_score_computed": False, "submission_sha256": digest(data)}

    def grade(self, data):
        self.log.append("grade")
        assert data == self.captured
        return {"status": "scored", "submission_sha256": digest(data),
                "invented_test_only_score": 1.0}


def make(mode="case_adaptive", backend=None, clock=None, limits=LIMITS):
    backend, clock = backend or InventedBackend(), clock or Clock()
    obj = Session(mode=mode, limits=limits, tool_ids=TOOLS, backend=backend,
                  comparison_id="invented-pair", public_packet_sha256="c" * 64,
                  reservation_policy_sha256="d" * 64, trial_ids=IDS, clock_us=clock)
    return obj, backend, clock


def open_case(session):
    session.freeze_controller(b"# invented controller/policy; not scientific model")


class ProtocolTests(unittest.TestCase):
    def test_public_training_then_adaptive_observed_queries_have_one_budget(self):
        session, backend, _ = make()
        got = session.request({"op": "view", "scope": "training"}, RESERVE)
        self.assertEqual(got["invented_train_counts"], [1, 2, 0, 1])
        self.assertNotIn("eval_counts_heldin", backend.observed_request["allowed_fields"])
        open_case(session)
        for index in (0, 573):
            session.request({"op": "view", "scope": "trial", "trial_id": IDS[index]}, RESERVE)
        got = session.request({"op": "tool", "tool_id": TOOLS[0], "arguments": {}}, RESERVE)
        self.assertEqual(got["invented_training_mean"], 1.0)
        self.assertEqual(session.used.calls, 4)
        self.assertEqual(session.preparation_used.calls, 1)
        self.assertIn("eval_counts_heldin", backend.observed_request["allowed_fields"])
        self.assertNotIn("eval_counts_heldout", backend.observed_request["allowed_fields"])

    def test_no_query_before_controller_freeze_or_unknown_public_id(self):
        session, backend, _ = make()
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "panel"}, RESERVE)
        self.assertNotIn("public", backend.log)
        open_case(session)
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "trial", "trial_id": "private"}, RESERVE)
        self.assertNotIn("public", backend.log)

    def test_private_path_score_or_unknown_tool_never_dispatched(self):
        for request in ({"op": "grade"}, {"op": "view", "scope": "targets"},
                        {"op": "view", "scope": "panel", "path": "/operator/gold.npz"},
                        {"op": "tool", "tool_id": "unfrozen", "arguments": {}}):
            session, backend, _ = make()
            open_case(session)
            with self.assertRaises(ValueError):
                session.request(request, RESERVE)
            self.assertNotIn("public", backend.log)

    def test_failed_tool_preserves_full_cpu_token_money_reservation(self):
        session, backend, _ = make()
        open_case(session)
        backend.error = TimeoutError("invented worker timeout")
        with self.assertRaises(TimeoutError):
            session.request({"op": "view", "scope": "panel"}, RESERVE)
        self.assertEqual(session.used, RESERVE)
        self.assertEqual(session.state, "failed")
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "panel"}, RESERVE)
        session.close()
        self.assertNotIn("grade", backend.log)

    def test_overrun_retains_actual_excess_and_fails(self):
        session, backend, _ = make()
        open_case(session)
        backend.actual = Usage(calls=1, cpu_us=1001, model_input_tokens=200,
                               model_output_tokens=10, model_cost_microusd=101)
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "panel"}, RESERVE)
        self.assertEqual(session.used, backend.actual)
        self.assertEqual(session.state, "failed")

    def test_total_budget_cannot_reset_for_second_trial(self):
        tight = Limits(RESERVE, RESERVE, 10000, 2000, 1000000)
        session, backend, _ = make(limits=tight)
        open_case(session)
        session.request({"op": "view", "scope": "trial", "trial_id": IDS[0]}, RESERVE)
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "trial", "trial_id": IDS[1]}, RESERVE)
        self.assertEqual(backend.log.count("public"), 1)

    def test_preparation_budget_is_nested_not_added_to_total(self):
        session, backend, _ = make()
        for _ in range(2):
            session.request({"op": "view", "scope": "training"}, RESERVE)
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "training"}, RESERVE)
        open_case(session)
        self.assertEqual(session.used.calls, 2)
        self.assertEqual(session.preparation_used.calls, 2)
        self.assertEqual(backend.log.count("public"), 2)

    def test_wall_clock_includes_unmetered_reasoning_and_no_per_case_reset(self):
        session, backend, clock = make()
        open_case(session)
        clock.value = LIMITS.wall_us
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "panel"}, RESERVE)
        self.assertNotIn("public", backend.log)
        self.assertEqual(session.state, "failed")

    def test_fixed_transport_rejects_post_query_adaptive_decision(self):
        session, backend, _ = make("frozen_program")
        open_case(session)
        backend.origin_override = "adaptive_policy"
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "panel"}, RESERVE)
        self.assertEqual(session.used, RESERVE)
        self.assertEqual(session.state, "failed")

    def test_wrong_actual_controller_hash_rejected(self):
        session, backend, _ = make("frozen_program")
        open_case(session)
        backend.sha_override = "f" * 64
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "panel"}, RESERVE)
        self.assertEqual(session.state, "failed")

    def test_memory_and_oversize_public_response_fail_without_grade(self):
        for kind in ("memory", "response"):
            session, backend, _ = make()
            open_case(session)
            if kind == "memory":
                backend.memory = LIMITS.max_memory_bytes + 1
            else:
                backend.payload_override = "x" * LIMITS.response_bytes
            with self.assertRaises(ValueError):
                session.request({"op": "view", "scope": "panel"}, RESERVE)
            self.assertNotIn("grade", backend.log)
            self.assertEqual(session.used, RESERVE)

    def test_complete_teardown_commit_validate_order_and_mutation_resistance(self):
        session, backend, _ = make()
        open_case(session)
        def no_more_public_requests():
            with self.assertRaises(ValueError):
                session.request({"op": "view", "scope": "panel"}, RESERVE)
        backend.during_stop = no_more_public_requests
        receipt = session.finish()
        self.assertEqual(backend.log, ["controller_commit", "finalize", "commit", "validate"])
        self.assertEqual(receipt["full_shape_required"], [574, 140, 45])
        self.assertEqual(backend.finalize_order, ["producer_stopped",
                         "captured_with_live_holder", "holder_volume_removed"])
        receipt["submission_sha256"] = "0" * 64
        backend.output = b"changed after capture"
        self.assertEqual(session.submission, OUTPUT)
        self.assertEqual(session.commit_receipt["submission_sha256"], digest(OUTPUT))
        with self.assertRaises(ValueError):
            session.private_grade()
        self.assertNotIn("grade", backend.log)

    def test_unstopped_incomplete_or_uncommitted_output_never_reaches_private_grade(self):
        for kind in ("stop", "empty", "commit", "invalid"):
            session, backend, _ = make()
            open_case(session)
            if kind == "stop":
                backend.stop_ok = False
            elif kind == "empty":
                backend.output = b""
            elif kind == "commit":
                backend.commit_ok = False
            else:
                backend.validate_ok = False
            with self.assertRaises(ValueError):
                session.finish()
            self.assertNotIn("grade", backend.log)
            if kind in ("stop", "empty", "commit"):
                self.assertNotIn("validate", backend.log)

    def test_pair_withholds_both_grades_until_both_full_commits(self):
        fixed, fb, _ = make("frozen_program")
        adaptive, ab, _ = make()
        paired = PairedStudy(fixed, adaptive)
        open_case(fixed)
        open_case(adaptive)
        fixed.finish()
        with self.assertRaises(ValueError):
            paired.grade()
        self.assertNotIn("grade", fb.log)
        self.assertNotIn("grade", ab.log)
        adaptive.finish()
        result = paired.grade()
        self.assertTrue(result["same_panel_tools_and_caps"])
        self.assertEqual(result["biological_cases"], 1)
        self.assertEqual(fb.log, ["controller_commit", "finalize", "commit", "validate", "grade"])
        self.assertEqual(ab.log, ["controller_commit", "finalize", "commit", "validate", "grade"])
        with self.assertRaises(ValueError):
            paired.grade()

    def test_mismatched_budget_or_shared_backend_cannot_form_pair(self):
        for kind in ("budget", "backend"):
            fixed, fb, _ = make("frozen_program")
            different = Limits(CAP, LIMITS.preparation, 10001, 2000, 1000000)
            adaptive, _, _ = make(backend=fb if kind == "backend" else None,
                                  limits=different if kind == "budget" else LIMITS)
            with self.assertRaises(ValueError):
                PairedStudy(fixed, adaptive)

    def test_full_574_trial_scope_is_not_configurable_subset(self):
        kwargs = dict(mode="case_adaptive", limits=LIMITS, tool_ids=TOOLS,
                      backend=InventedBackend(), comparison_id="invented-pair",
                      public_packet_sha256="c" * 64,
                      reservation_policy_sha256="d" * 64, clock_us=Clock())
        for ids in (IDS[:-1], IDS[:-1] + (IDS[0],)):
            with self.assertRaises(ValueError):
                Session(trial_ids=ids, **kwargs)


    def test_controller_is_durably_committed_before_query_and_bad_commit_is_terminal(self):
        session, backend, _ = make()
        backend.controller_commit_ok = False
        with self.assertRaises(ValueError):
            open_case(session)
        self.assertEqual(session.state, "failed")
        self.assertEqual(backend.log, ["controller_commit"])
        with self.assertRaises(ValueError):
            session.request({"op": "view", "scope": "panel"}, RESERVE)
        good, gb, _ = make()
        open_case(good)
        self.assertEqual(good.controller_sha, digest(gb.controller_source))

    def test_close_is_terminal_even_when_stop_fails(self):
        for stop_ok in (True, False):
            session, backend, _ = make()
            open_case(session)
            backend.stop_ok = stop_ok
            if stop_ok:
                session.close()
            else:
                with self.assertRaises(ValueError):
                    session.close()
            self.assertEqual(session.state, "closed")
            self.assertEqual(session.terminal_outcome, "case")
            for action in (
                lambda: session.request({"op": "view", "scope": "panel"}, RESERVE),
                lambda: session.request({"op": "tool", "tool_id": TOOLS[0],
                                         "arguments": {}}, RESERVE),
                lambda: session.freeze_controller(b"new"),
                session.finish,
            ):
                with self.assertRaises(ValueError):
                    action()
            self.assertNotIn("public", backend.log)
            self.assertNotIn("finalize", backend.log)

    def test_distinct_reservation_policy_cannot_form_equal_budget_pair(self):
        fixed, _, _ = make("frozen_program")
        adaptive, _, _ = make()
        adaptive.reservation_policy_sha = "e" * 64
        with self.assertRaises(ValueError):
            PairedStudy(fixed, adaptive)

    def test_report_never_creates_authority_or_adoption(self):
        session, _, _ = make()
        report = session.report()
        self.assertIsNone(report["root_external_witness"])
        self.assertIsNone(report["root_current_tip_adoption"])
        self.assertFalse(report["execution_authority"])
        self.assertFalse(report["operational_backend_qualified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
