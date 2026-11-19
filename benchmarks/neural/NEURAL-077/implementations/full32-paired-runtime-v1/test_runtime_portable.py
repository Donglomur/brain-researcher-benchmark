"""Focused portable binding/driver controls; no actual canary or packet access.

The orchestration callbacks below are generated structural fixtures, not saved
process evidence. Existing profile, capture and canary suites are not replayed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get("ERP_RUNTIME_TEST_SOURCE", str(HERE / "runtime.py")))
spec = importlib.util.spec_from_file_location("erp_full32_portable_runtime_control", SOURCE)
runtime = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runtime
spec.loader.exec_module(runtime)


PIN = {"bytes": 1, "sha256": "0" * 64}
NO_TOOLS = "No tools are permitted."
PROGRAM_TOOLS = "The frozen program may compute."
IDS = ("q-" + "1" * 32, "q-" + "2" * 32)


def config(repository="/generated/repository"):
    return {
        "schema": "erp-full32-two-episode-runtime-v1", "selected": True,
        "repository_root": repository, "public_root": "/generated/operator-packet",
        "public_manifest": dict(PIN), "output_root": "/generated/new-output",
        "interpreter": {"path": "/usr/bin/python3", **PIN},
        "sandbox": {"path": "/usr/bin/sandbox-exec", **PIN},
        "operator_source": dict(PIN), "source_bindings": dict(PIN),
        "positions": [0, 1], "limits": dict(runtime.LIMITS),
    }


def bindings():
    return {"schema": "erp-full32-portable-runtime-sources-v1",
            "members": {role: {"path": path, **PIN}
                        for role, path in runtime.EXPECTED_PATHS.items()}}


def context(identifier, condition):
    permission = NO_TOOLS if condition == runtime.CONDITIONS[0] else PROGRAM_TOOLS
    prompt = "Generated four-demo projection. " + permission + " Query " + identifier + "."
    return {"trial_id": identifier, "condition": condition, "prompt": prompt,
            "context_sha256": runtime.pin(prompt.encode())["sha256"]}


def generated_episode(ordinal, program):
    """Structural return values only; no subprocess is launched by this helper."""
    identifier = program["trial_id"]
    pid = 9000 + ordinal
    envelope = {"trial_id": identifier, "condition": runtime.CONDITIONS[1],
                "context_sha256": program["context_sha256"],
                "status": "ok", "error": None,
                "response": runtime.encode({"trial_id": identifier, "target_probability": 0.5}).decode()}
    end = {"schema": "erp-full6400-owned-episode-v1", "status": "ok", "pid": pid,
           "trial_id": identifier, "condition": runtime.CONDITIONS[1],
           "context_sha256": program["context_sha256"],
           "diagnostic_mode": "concurrent_bounded_stderr_v1",
           "generated_protocol_only": False, "returncode": 0, "normal_exit_observed": True,
           "stdout_EOF_observed": True,
           "owned_cleanup": {"pid": pid, "cleanup_complete": True, "reaped": True,
                             "group_absence_observed": True},
           "stderr_capture": {"reader_joined": True, "closed": True, "eof_observed": True,
                              "overflow": False, "error": None,
                              "observed_bytes": 0, "retained_bytes": 0}}
    return envelope, end


def pinned_public_module(role):
    """Load captured source only after checking the portable adjacent bindings."""
    source_bindings = runtime.decode((SOURCE.parent / "SOURCE_BINDINGS.json").read_bytes())
    runtime.validate_bindings(source_bindings)
    row = source_bindings["members"][role]
    repository = Path(os.environ.get("ERP_RUNTIME_TEST_REPOSITORY", str(SOURCE.parent.parents[4])))
    local_prefix = runtime.RELATIVE + "/"
    path = (SOURCE.parent / row["path"][len(local_prefix):]
            if row["path"].startswith(local_prefix) else repository / row["path"])
    body = path.read_bytes()
    if len(body) != row["bytes"] or hashlib.sha256(body).hexdigest() != row["sha256"]:
        raise AssertionError("Pinned public integration source changed: " + role)
    name = "erp_full32_portable_control_" + role
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


class PortableBindingAndDriverControls(unittest.TestCase):
    def test_relocated_config_preserves_exact_selection_and_path_boundaries(self):
        for repository in ("/generated/repository", "/relocated/repository"):
            value = config(repository)
            self.assertIs(runtime.validate_config(value, here=Path(repository) / runtime.RELATIVE), value)
        initial = config()
        variants = []
        for key, replacement in (("selected", False), ("positions", [0, 2]),
                                 ("positions", [False, 1]),
                                 ("repository_root", "/elsewhere/repository"),
                                 ("public_root", "/usr/private-packet"),
                                 ("output_root", "/generated/operator-packet/child"),
                                 ("output_root", "/generated/repository/" + runtime.RELATIVE + "/child"),
                                 ("output_root", "/generated/../output")):
            value = copy.deepcopy(initial)
            value[key] = replacement
            variants.append((key, replacement, value))
        extra = copy.deepcopy(initial)
        extra["private_targets"] = "/generated/never-open"
        variants.append(("extra", "private_targets", extra))
        changed_limits = copy.deepcopy(initial)
        changed_limits["limits"]["whole_seconds"] += 1
        variants.append(("limits", "changed", changed_limits))
        for key, replacement, value in variants:
            with self.subTest(key=key, value=replacement), self.assertRaises(ValueError):
                runtime.validate_config(value, here=Path(initial["repository_root"]) / runtime.RELATIVE)

    def test_dependency_closure_requires_exact_repository_relative_paths(self):
        initial = bindings()
        self.assertIs(runtime.validate_bindings(initial), initial)
        variants = []
        for role, path in (("consumer", "../private/consumer.py"),
                           ("evaluator", "/private/operator/evaluator.py"),
                           ("episode", runtime.EXPECTED_PATHS["profile"])):
            value = copy.deepcopy(initial)
            value["members"][role]["path"] = path
            variants.append(value)
        missing = copy.deepcopy(initial)
        del missing["members"]["evaluator_bindings"]
        variants.append(missing)
        extra = copy.deepcopy(initial)
        extra["members"]["private_key"] = {"path": "private/key", **PIN}
        variants.append(extra)
        changed_pin = copy.deepcopy(initial)
        changed_pin["members"]["owned"]["sha256"] = "not-a-sha256"
        variants.append(changed_pin)
        for index, value in enumerate(variants):
            with self.subTest(case=index), self.assertRaises(ValueError):
                runtime.validate_bindings(value)

    def test_context_commitment_allows_only_the_declared_permission_change(self):
        direct, program = [context(IDS[0], condition) for condition in runtime.CONDITIONS]
        result = runtime.matched_commitment(direct, program, NO_TOOLS, PROGRAM_TOOLS)
        self.assertEqual(result["direct_context"], runtime.pin(direct["prompt"].encode()))
        self.assertEqual(result["program_context"], runtime.pin(program["prompt"].encode()))
        self.assertEqual(result["permission_normalized_context"], result["direct_context"])
        self.assertIs(result["direct_model_called"], False)
        variants = []
        wrong_identity = copy.deepcopy(program)
        wrong_identity["trial_id"] = IDS[1]
        variants.append(wrong_identity)
        extra_information = copy.deepcopy(program)
        extra_information["prompt"] += " Extra pooled information."
        extra_information["context_sha256"] = runtime.pin(extra_information["prompt"].encode())["sha256"]
        variants.append(extra_information)
        changed_hash = copy.deepcopy(program)
        changed_hash["context_sha256"] = "0" * 64
        variants.append(changed_hash)
        for index, value in enumerate(variants):
            with self.subTest(case=index), self.assertRaises(ValueError):
                runtime.matched_commitment(direct, value, NO_TOOLS, PROGRAM_TOOLS)

    def test_pinned_public_profile_and_framing_adapter_seam(self):
        # This is a source integration check, not a host sandbox availability probe.
        wire, profile, evaluator = [pinned_public_module(role)
                                    for role in ("wire", "profile", "evaluator")]
        client = Path("/generated/frozen-canary.py")
        with patch.object(wire.sys, "platform", "darwin"), \
             patch.object(wire.Path, "is_file", return_value=True):
            predecessor = wire.sandbox_profile(client)
            wrapped = profile.wrap_wire(wire)
            successor = wrapped.sandbox_profile(client)
        quoted_client = json.dumps(str(client))
        scopes = ('(literal "/") (subpath "/System") (subpath "/usr") '
                  '(subpath "/Library/Frameworks") (literal "/dev/null") '
                  '(literal "/dev/urandom") (literal "/dev/random") '
                  '(literal ' + quoted_client + ')')
        metadata = '(allow file-read-metadata ' + scopes + ' (literal "/Library"))'
        self.assertEqual(predecessor.count('(allow file-read-metadata)'), 1)
        self.assertEqual(successor, predecessor.replace('(allow file-read-metadata)', metadata, 1))
        self.assertEqual(successor.replace(metadata, '(allow file-read-metadata)', 1), predecessor)
        self.assertIn('(allow file-read-data ' + scopes + ')', successor)
        self.assertIn('(deny sysctl* process-info* network* process-fork)', successor)
        self.assertNotIn('(subpath "/Library")', successor)
        self.assertIs(wrapped.read_frame, wire.read_frame)
        self.assertIs(wrapped.write_frame, wire.write_frame)
        self.assertIs(wrapped.WireFailure, wire.WireFailure)
        for condition in runtime.CONDITIONS:
            projected = context(IDS[0], condition)
            body = projected["prompt"].encode()
            self.assertEqual(evaluator.context_frame(projected, condition),
                             len(body).to_bytes(4, "big") + body)

    def test_standalone_timer_refuses_existing_owner_and_restores_on_return_or_error(self):
        selected = config(str(SOURCE.parent.parents[4]))
        with patch.object(runtime.signal, "getitimer", return_value=(17.0, 0.0)), \
             patch.object(runtime.signal, "setitimer") as timer, \
             patch.object(runtime.signal, "signal") as handlers, \
             patch.object(runtime, "_run") as actual:
            with self.assertRaisesRegex(ValueError, "Existing caller timer"):
                runtime.run(selected)
            actual.assert_not_called()
            timer.assert_not_called()
            handlers.assert_not_called()
        for fail in (False, True):
            active = [0.0, 0.0]
            signals = (runtime.signal.SIGALRM, runtime.signal.SIGTERM,
                       runtime.signal.SIGHUP, runtime.signal.SIGINT)
            original = {signum: object() for signum in signals}
            installed = dict(original)
            stages, timer_calls = [], []
            def install(signum, handler):
                prior = installed[signum]
                installed[signum] = handler
                return prior
            def set_timer(which, seconds, interval=0.0):
                self.assertEqual(which, runtime.signal.ITIMER_REAL)
                previous = tuple(active)
                active[:] = [float(seconds), float(interval)]
                timer_calls.append(tuple(active))
                return previous
            def generated_operation(value):
                self.assertIs(value, selected)
                self.assertEqual(active, [float(runtime.LIMITS["whole_seconds"]), 0.0])
                stages.append("generated_work")
                # Simulate the existing operation's finalization before run returns.
                self.assertEqual(active[0], runtime.LIMITS["whole_seconds"])
                stages.append("generated_finalization")
                if fail:
                    raise RuntimeError("generated operation failure")
                return {"status": "generated_control_only"}
            with self.subTest(error=fail), \
                 patch.object(runtime.signal, "getitimer", side_effect=lambda _: tuple(active)), \
                 patch.object(runtime.signal, "setitimer", side_effect=set_timer), \
                 patch.object(runtime.signal, "signal", side_effect=install), \
                 patch.object(runtime, "_run", side_effect=generated_operation):
                if fail:
                    with self.assertRaisesRegex(RuntimeError, "generated operation failure"):
                        runtime.run(selected)
                else:
                    self.assertEqual(runtime.run(selected), {"status": "generated_control_only"})
            self.assertEqual(stages, ["generated_work", "generated_finalization"])
            self.assertEqual(active, [0.0, 0.0])
            self.assertEqual(installed, original)
            self.assertEqual(timer_calls, [(float(runtime.LIMITS["whole_seconds"]), 0.0), (0.0, 0.0)])

    def test_two_position_driver_preserves_first_failure_without_retry(self):
        projected, dispatched, requested = [], [], []
        def get_context(identifier, condition):
            requested.append((identifier, condition))
            return context(identifier, condition)
        def project(ordinal, direct, commitment):
            projected.append((ordinal, direct["trial_id"], commitment["trial_id"]))
        def succeed(ordinal, program):
            dispatched.append((ordinal, program["trial_id"]))
            return generated_episode(ordinal, program)
        result = runtime.drive_two(IDS, get_context, succeed, project, NO_TOOLS, PROGRAM_TOOLS)
        self.assertIs(result["complete"], True)
        self.assertIsNone(result["error"])
        self.assertEqual(result["direct_projection_count"], 2)
        self.assertEqual(result["program_episode_count"], 2)
        self.assertEqual([row["status"] for row in result["episodes"]], ["passed", "passed"])
        self.assertEqual(projected, [(0, IDS[0], IDS[0]), (1, IDS[1], IDS[1])])
        self.assertEqual(dispatched, [(0, IDS[0]), (1, IDS[1])])
        self.assertEqual(len(requested), 4)
        for failure in ("response", "generated_scope", "nonfixed_probability"):
            projected.clear(); dispatched.clear(); requested.clear()
            def fail_first(ordinal, program):
                dispatched.append((ordinal, program["trial_id"]))
                envelope, end = generated_episode(ordinal, program)
                if failure == "response":
                    envelope.update(status="error", error="generated first failure")
                elif failure == "generated_scope":
                    end["generated_protocol_only"] = True
                else:
                    envelope["response"] = runtime.encode({"trial_id": program["trial_id"],
                                                           "target_probability": 0.6}).decode()
                return envelope, end
            result = runtime.drive_two(IDS, get_context, fail_first, project, NO_TOOLS, PROGRAM_TOOLS)
            with self.subTest(failure=failure):
                self.assertIs(result["complete"], False)
                self.assertIsNotNone(result["error"])
                self.assertEqual(result["direct_projection_count"], 1)
                self.assertEqual(result["program_episode_count"], 1)
                self.assertEqual([row["status"] for row in result["episodes"]],
                                 ["closed_failure", "not_attempted"])
                self.assertIsNone(result["episodes"][1]["pid"])
                self.assertIsNone(result["episodes"][1]["end"])
                self.assertEqual(dispatched, [(0, IDS[0])])
                self.assertEqual(projected, [(0, IDS[0], IDS[0])])
                self.assertEqual(len(requested), 2)


if __name__ == "__main__":
    unittest.main()
