"""Generated source controls; no real packet, provider, model or scoring run.

Fixtures exercise request/admission refusal paths only. They do not qualify a
provider, a full6400 arm, neural interpretation, or protected actual grading.
"""
from __future__ import annotations

import copy
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
QUERY = "q-" + "1" * 32
MODEL = "generated-control-model-v1"
TOKENS = 128
PREFIX = struct.Struct("!I")
NO_TOOLS = "Do not use tools, code execution, external retrieval, files, or memory from other query trials."


def load(name, filename):
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frame(raw):
    return PREFIX.pack(len(raw)) + raw


def prompt(identifier=QUERY):
    # Complete generated arrays, not acquired EEG or imputed study observations.
    channels = [[0.0] * 1024, [0.125] * 1024]
    demos = [{"trial_id": "generated-demo-" + str(i), "target": i % 2,
              "channels": channels} for i in range(4)]
    query = {"trial_id": identifier, "channels": channels}
    return ("Generated source-control event-label question. " + NO_TOOLS +
            "\nDEMONSTRATIONS\n" + encoded(demos).decode() +
            "\nQUERY\n" + encoded(query).decode())


def response(identifier=QUERY, probability=0.75, response_id="resp_generated_control_1"):
    answer = encoded({"trial_id": identifier, "target_probability": probability}).decode()
    return {"object": "response", "status": "completed", "error": None,
            "incomplete_details": None, "id": response_id, "model": MODEL,
            "max_output_tokens": TOKENS, "tools": [], "tool_choice": "none",
            "parallel_tool_calls": False, "store": False, "truncation": "disabled",
            "previous_response_id": None, "conversation": None,
            "output": [{"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": answer}]}],
            "usage": {"input_tokens": 31, "output_tokens": 9, "total_tokens": 40}}


class ArtifactSpace:
    """Finite generated fixtures, always outside authenticated source trees."""
    CAP = 5 * 1024**2 // 2

    def __init__(self, protected):
        configured = os.environ.get("ARTIFACT_DIR")
        if configured:
            parent = Path(configured)
            if not parent.is_absolute() or ".." in parent.parts:
                raise ValueError("ARTIFACT_DIR must be an absolute ordinary path")
        else:
            parent = Path(tempfile.gettempdir()).resolve() / ("erp-full32-controls-" + secrets.token_hex(8))
        if any(p.is_symlink() for p in (parent, *parent.parents)):
            raise ValueError("Linked ARTIFACT_DIR refused")
        protected = tuple(Path(p).resolve() for p in protected)
        if any(parent.is_relative_to(p) or p.is_relative_to(parent) for p in protected):
            raise ValueError("Artifact/source trees must be disjoint")
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = parent / "erp-full32-provider-pair-controls"
        self.root.mkdir(mode=0o700)  # Fresh run only; never overwrite old evidence.
        self.written = 0
        self.index = 0

    def reserve(self, size):
        if type(size) is not int or size < 0 or self.written + size > self.CAP:
            raise ValueError("Generated fixture write cap")
        self.written += size

    def directory(self, name):
        self.index += 1
        result = self.root / (str(self.index) + "-" + name)
        result.mkdir(mode=0o700)
        return result

    def emit(self, path, body, replace=False):
        if (not path.is_relative_to(self.root) or
                any(p.is_symlink() for p in (path, *path.parents))):
            raise ValueError("Fixture destination escaped artifact tree")
        self.reserve(len(body))
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if replace:
            info = path.stat()
            if info.st_nlink != 1 or not path.is_file():
                raise ValueError("Only owned ordinary fixture replacement")
            path.chmod(0o600)
        with path.open("wb" if replace else "xb") as stream:
            stream.write(body)
        return pin(body)


class ProviderPairControls(unittest.TestCase):
    maxDiff = 1200
    @classmethod
    def setUpClass(cls):
        cls.bridge = load("full32_provider_bridge_control", "bridge.py")
        cls.pair = load("full32_provider_pair_control", "pair.py")
        cls.modules = cls.pair.dependencies()
        # Protect the whole selected repository, component and test directory.
        cls.artifacts = ArtifactSpace((HERE, cls.modules["root"]))

    @classmethod
    def tearDownClass(cls):
        cls.artifacts.emit(cls.artifacts.root / "FIXTURE_SCOPE.json", encoded({
            "schema": "erp-full32-generated-control-scope-v1",
            "generated_fixture_only": True, "provider_calls": 0, "original_payload_reads": 0,
            "private_labels_opened": 0, "fixture_write_cap": cls.artifacts.CAP,
            "fixture_write_charge_before_receipt": cls.artifacts.written,
            "new_benchmark_or_provider_qualification": False}))

    def study(self):
        area = self.artifacts.directory("study")
        author = area / "authoring"; author.mkdir()
        documents = area / "declarations"; documents.mkdir()
        packet_parent = area / "packet-input"; packet_parent.mkdir()
        self.artifacts.emit(author / "candidate.py", b"def main():\n    return 0\n")
        self.artifacts.emit(author / "config.json", encoded({"generated_fixture_only": True}))
        manifest_path = documents / "manifest.json"
        manifest = self.artifacts.emit(manifest_path, encoded({
            "schema": "neural077_python_bundle_v1", "entry_module": "candidate",
            "modules": ["candidate.py"], "config": "config.json"}))
        exposure_path = documents / "exposure.json"
        exposure = self.artifacts.emit(exposure_path, encoded({
            "schema": "erp-full32-authoring-exposure-v1",
            "declared_authoring_inputs": ["Generated source-control fixture; no study data."],
            "remaining32_query_or_answer_tuning_declared": False,
            "six_person_feature_training_declared": False, "pretraining_exposure": "unknown",
            "notes": "Declaration fixture only; no provider or hidden-exposure qualification."}))
        spec = {"schema": "erp-full32-provider-pair-freeze-spec-v1",
            "public_root": str(packet_parent / "public"), "public_manifest": pin(b"unopened-fixture"),
            "provider": {"model": MODEL, "max_output_tokens": TOKENS},
            "programme_root": str(author), "programme_manifest": {"path": str(manifest_path), **manifest},
            "authoring_exposure": {"path": str(exposure_path), **exposure},
            "interpreter": {"path": str(area / "unexecuted-interpreter"), **pin(b"fixture")},
            "sandbox": {"path": "/usr/bin/sandbox-exec", **pin(b"unexecuted-fixture")},
            "limits": {"episode_work_seconds": 30, "episode_cleanup_seconds": 5,
                "campaign_seconds": 180, "read_bytes": 32 * 1024**3, "write_bytes": 1024**2}}
        output = area / "frozen"
        self.artifacts.reserve(32768)
        with mock.patch.object(self.modules["consumer"], "PacketSession",
                               side_effect=AssertionError("Freeze opened a query")) as opened:
            frozen = self.pair.freeze(spec, output, modules=self.modules)
            opened.assert_not_called()
        self.assertLessEqual(sum(p.stat().st_size for p in output.iterdir()), 32768)
        self.assertEqual(frozen["query_records_opened"], 0)
        contract = json.loads((output / "CONTRACT.json").read_bytes())
        return area, contract, frozen["contract"]

    def capture(self, contract, identifier=QUERY, response_id="resp_generated_control_1"):
        text = prompt(identifier)
        context = {"trial_id": identifier, "condition": self.pair.CONDITIONS[0],
                   "prompt": text, "context_sha256": pin(text.encode())["sha256"]}
        config = self.pair.provider_configuration(context, contract, self.modules["bridge"], 1030.0)
        captured = {"CONFIG.json": encoded(config), "INPUT.bin": frame(text.encode()), "STDERR.bin": b""}
        requests = []; receipts = []
        raw_response = encoded(response(identifier, response_id=response_id))
        def sender(request):
            requests.append(request)
            return raw_response
        answer = self.modules["bridge"].exchange(text, model=MODEL, max_output_tokens=TOKENS,
                                                send_json=sender, record=receipts.append)
        self.assertEqual(len(requests), 1); self.assertEqual(len(receipts), 1)
        captured.update({"OUTPUT.bin": frame(answer), "REQUEST.bin": requests[0], "RESPONSE.bin": raw_response})
        end = {"schema": "erp_full32_provider_owned_episode_v1", "status": "closed_first_answer",
            "error_type": None, "pid": 12345, "returncode": 0,
            "trial_id": identifier, "condition": context["condition"],
            "context_sha256": context["context_sha256"],
            "first_response_immutable": True, "automatic_retry": False,
            "trailing_byte": pin(b""), "trailing_byte_hex": "",
            "provider_context_qualified": False, "provider_tool_policy_qualified": False,
            "private_target_reads": 0, "scoring_performed": False,
            "owned_cleanup": {"pid": 12345, "cleanup_complete": True, "reaped": True,
                              "group_absence_observed": True, "returncode": 0},
            "normal_exit_observed": True, "stdout_EOF_observed": True,
            "stderr_capture": {"eof_observed": True, "reader_joined": True, "closed": True,
                "overflow": False, "error": None, "observed_bytes": 0, "retained_bytes": 0},
            "started_monotonic": 1000.0, "finished_monotonic": 1001.0, "elapsed_seconds": 1.0}
        for field, name in (("config", "CONFIG.json"), ("input", "INPUT.bin"),
                            ("output", "OUTPUT.bin"), ("stderr", "STDERR.bin")):
            end[field] = pin(captured[name])
        captured["END.json"] = encoded(end)
        captured["BRIDGE.json"] = encoded({"schema": "erp_full32_provider_binding_bridge_v1",
            "config_pin": pin(captured["CONFIG.json"]), "status": "recorded", "receipt": receipts[0], "failure": None})
        captured["HTTP.json"] = encoded({"schema": "neural077_https_binding_v1",
            "config_pin": pin(captured["CONFIG.json"]), "endpoint": "https://api.openai.com/v1/responses",
            "request": pin(requests[0]), "response": pin(raw_response), "status_code": 200,
            "request_complete": True, "response_complete": True, "body_overflow": False,
            "requests_attempted": 1, "redirects_followed": 0, "retries": 0, "connection_closed": True,
            "credential_retained": False, "failure": None, "started_monotonic": 1000.25,
            "finished_monotonic": 1000.75, "deadline": 1030.0})
        return context, captured

    def header(self, contract, commitment, condition):
        return {"schema": "erp-full32-provider-arm-v1" if condition == self.pair.CONDITIONS[0]
                else "erp-full6400-numeric-arm-v1", "status": "closed_unscored_arm", "condition": condition,
            "contract": commitment, "public_manifest": contract["public_manifest"],
            "study_source_bindings": contract["source_bindings"],
            "programme_identity": contract["programme"]["bundle_identity"],
            "authoring_exposure": contract["authoring_exposure"]["file"],
            "query_count": 6400, "attempt_inventory_count": 6400,
            "private_target_reads": 0, "scoring_performed": False, "episodes": [{} for _ in range(6400)]}

    def test_complete_request_has_only_one_matched_query_and_fixed_policy(self):
        text = prompt()
        raw = self.bridge.request_body(text, MODEL, TOKENS)
        request = json.loads(raw)
        self.assertEqual(request["model"], MODEL)
        self.assertEqual(request["input"], [{"role": "user", "content": [{"type": "input_text", "text": text}]}])
        self.assertEqual(request["tools"], [])
        self.assertEqual(request["tool_choice"], "none")
        self.assertIs(request["parallel_tool_calls"], False)
        self.assertIs(request["store"], False)
        self.assertIs(request["stream"], False)
        self.assertIs(request["background"], False)
        self.assertEqual(request["truncation"], "disabled")
        self.assertNotIn("previous_response_id", request)
        self.assertNotIn("conversation", request)
        self.assertEqual(request["text"]["format"]["schema"]["properties"]["trial_id"]["enum"], [QUERY])
        self.assertEqual(self.bridge.query_identity(text), QUERY)
        for malformed in (text.replace(QUERY, "development-001-" + "a" * 24),
                          text + " q-" + "2" * 32, text.replace(NO_TOOLS, "Tools allowed.")):
            with self.subTest(kind="identity_or_permission"), self.assertRaises(ValueError):
                self.bridge.request_body(malformed, MODEL, TOKENS)

    def test_provider_response_rejects_truncation_policy_model_and_second_answers(self):
        valid = response()
        answer, metadata = self.bridge.completed_text(encoded(valid), QUERY, MODEL, TOKENS)
        self.assertEqual(json.loads(answer), {"trial_id": QUERY, "target_probability": 0.75})
        self.assertEqual(metadata["provider_response_id"], "resp_generated_control_1")
        variants = []
        for field, value in (("status", "incomplete"), ("model", "another-model"),
                             ("tools", [{"type": "function", "name": "hidden_tool"}]),
                             ("previous_response_id", "resp_other"),
                             ("truncation", "auto"), ("max_output_tokens", TOKENS + 1)):
            item = copy.deepcopy(valid); item[field] = value; variants.append(encoded(item))
        item = copy.deepcopy(valid); item["output"].append(copy.deepcopy(item["output"][0])); variants.append(encoded(item))
        item = copy.deepcopy(valid); item["output"][0]["content"][0]["text"] = encoded({"trial_id": QUERY, "target_probability": True}).decode(); variants.append(encoded(item))
        variants.append(encoded(valid)[:-1])
        for index, raw in enumerate(variants):
            with self.subTest(case=index), self.assertRaises(ValueError):
                self.bridge.completed_text(raw, QUERY, MODEL, TOKENS)

    def test_exchange_preserves_first_answer_and_never_retries(self):
        text = prompt(); sent = []; receipts = []
        raw = encoded(response())
        def sender(request):
            sent.append(request)
            return raw
        answer = self.bridge.exchange(text, model=MODEL, max_output_tokens=TOKENS,
                                      send_json=sender, record=receipts.append)
        self.assertEqual(len(sent), 1)
        self.assertEqual(pin(sent[0]), pin(self.bridge.request_body(text, MODEL, TOKENS)))
        self.assertEqual(json.loads(answer)["target_probability"], 0.75)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["sender_calls_attempted"], 1)
        self.assertEqual(receipts[0]["retry_count"], 0)
        for field in ("provider_execution_qualified", "provider_capacity_qualified",
                      "provider_context_qualified", "provider_tool_policy_qualified",
                      "scientific_qualification"):
            self.assertIs(receipts[0][field], False)
        for broken in (b"{", encoded(response())[:-4]):
            sent = []; receipts = []
            def bad_sender(request):
                sent.append(request)
                return broken
            with self.assertRaises(ValueError):
                self.bridge.exchange(text, model=MODEL, max_output_tokens=TOKENS,
                                     send_json=bad_sender, record=receipts.append)
            self.assertEqual(len(sent), 1)
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0]["sender_calls_attempted"], 1)
            self.assertEqual(receipts[0]["retry_count"], 0)

    def test_generated_capture_binds_request_first_response_and_owned_clock(self):
        _, contract, _ = self.study()
        context, capture = self.capture(contract)
        valid = self.pair.validate_provider_capture(context, contract, capture, self.modules["bridge"])
        self.assertEqual(json.loads(valid["answer"])["target_probability"], 0.75)
        self.assertIs(valid["captured_request_policy_verified"], True)
        self.assertIs(valid["provider_context_qualified"], False)
        self.assertIs(valid["provider_tool_policy_qualified"], False)
        variants = []
        altered = copy.deepcopy(capture); request = json.loads(altered["REQUEST.bin"])
        request["input"][0]["content"][0]["text"] += " Altered signal instruction."
        altered["REQUEST.bin"] = encoded(request)
        variants.append((altered, "Raw request changed"))
        altered = copy.deepcopy(capture); altered["INPUT.bin"] = altered["INPUT.bin"][:-1]
        variants.append((altered, "Complete first input frame"))
        altered = copy.deepcopy(capture)
        altered["OUTPUT.bin"] = frame(encoded({"trial_id": QUERY, "target_probability": 0.25}))
        variants.append((altered, "First emitted response differs"))
        altered = copy.deepcopy(capture); altered["RESPONSE.bin"] = encoded(response(probability=0.25))
        variants.append((altered, "First emitted response differs"))
        altered = copy.deepcopy(capture); config = json.loads(altered["CONFIG.json"])
        config["model"] = "changed-after-freeze"; altered["CONFIG.json"] = encoded(config)
        variants.append((altered, "Frozen provider configuration changed"))
        altered = copy.deepcopy(capture); http = json.loads(altered["HTTP.json"])
        http["finished_monotonic"] = 1002.0; altered["HTTP.json"] = encoded(http)
        variants.append((altered, "HTTP custody outside"))
        altered = copy.deepcopy(capture); altered["STDERR.bin"] = b"lost diagnostic"
        variants.append((altered, "Complete bounded stderr custody"))
        for mutated, expected in variants:
            with self.subTest(refusal=expected), self.assertRaisesRegex(ValueError, expected):
                self.pair.validate_provider_capture(context, contract, mutated, self.modules["bridge"])

    def test_generic_closure_missing_custody_retry_and_qualification_claims_refused(self):
        _, contract, _ = self.study()
        context, capture = self.capture(contract)
        missing = dict(capture); missing.pop("REQUEST.bin")
        with self.assertRaisesRegex(ValueError, "Complete provider capture file set"):
            self.pair.validate_provider_capture(context, contract, missing, self.modules["bridge"])
        for field, value in (("requests_attempted", 2), ("retries", 1),
                             ("response_complete", False), ("redirects_followed", 1)):
            altered = dict(capture); http = json.loads(altered["HTTP.json"])
            http[field] = value; altered["HTTP.json"] = encoded(http)
            with self.subTest(http=field), self.assertRaisesRegex(ValueError, "One complete nonretried HTTP exchange"):
                self.pair.validate_provider_capture(context, contract, altered, self.modules["bridge"])
        for field, value in (("retry_count", 1), ("sender_calls_attempted", 2),
                             ("provider_context_qualified", True), ("provider_tool_policy_qualified", True),
                             ("scientific_qualification", True)):
            altered = dict(capture); wrapped = json.loads(altered["BRIDGE.json"])
            wrapped["receipt"][field] = value; altered["BRIDGE.json"] = encoded(wrapped)
            with self.subTest(bridge=field), self.assertRaisesRegex(ValueError, "Captured bridge first response/retry/policy mismatch"):
                self.pair.validate_provider_capture(context, contract, altered, self.modules["bridge"])
        altered = dict(capture); end = json.loads(altered["END.json"])
        end["owned_cleanup"]["group_absence_observed"] = False; altered["END.json"] = encoded(end)
        with self.assertRaisesRegex(ValueError, "Genuine owned broker closure records required"):
            self.pair.validate_provider_capture(context, contract, altered, self.modules["bridge"])
        for field, value in (("trailing_byte", pin(b"x")), ("trailing_byte_hex", "78"),
                             ("automatic_retry", True), ("first_response_immutable", False)):
            altered = dict(capture); end = json.loads(altered["END.json"])
            end[field] = value; altered["END.json"] = encoded(end)
            with self.subTest(end=field), self.assertRaises(ValueError):
                self.pair.validate_provider_capture(context, contract, altered, self.modules["bridge"])

    def test_freeze_precedes_queries_and_rejects_changed_programme_config_exposure(self):
        _, contract, commitment = self.study()
        self.assertEqual(pin(self.pair.encode(contract)), commitment)
        verified = self.pair.verify_frozen(contract, self.modules)
        self.assertIn(b"candidate", verified["client"])
        programme_path = Path(contract["programme"]["path"])
        original = programme_path.read_bytes()
        for member, changed in (("candidate.py", b"def main():\n    return 7\n"),
                                ("config.json", b'{"changed_after_freeze":true}')):
            frozen = json.loads(original)
            frozen["members"][member]["base64"] = base64.b64encode(changed).decode()
            self.artifacts.emit(programme_path, encoded(frozen), replace=True)
            with self.subTest(member=member), self.assertRaisesRegex(ValueError, "Committed input changed"):
                self.pair.verify_frozen(contract, self.modules)
            self.artifacts.emit(programme_path, original, replace=True)
        exposure_path = Path(contract["authoring_exposure"]["path"])
        original_exposure = exposure_path.read_bytes(); altered = json.loads(original_exposure)
        altered["remaining32_query_or_answer_tuning_declared"] = True
        self.artifacts.emit(exposure_path, encoded(altered), replace=True)
        with self.assertRaisesRegex(ValueError, "Committed input changed"):
            self.pair.verify_frozen(contract, self.modules)
        self.artifacts.emit(exposure_path, original_exposure, replace=True)
        with self.assertRaisesRegex(ValueError, "No local held-out tuning declared"):
            self.pair.validate_exposure(altered)
        changed_contract = copy.deepcopy(contract)
        changed_contract["adapter_sources"]["bridge"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Adapter changed since pre-query freeze"):
            self.pair.verify_frozen(changed_contract, self.modules)
        self.pair.verify_frozen(contract, self.modules)

    def test_private_descriptor_stays_sealed_until_both_full_arms_admit(self):
        area, contract, commitment = self.study()
        arms = {}; originals = {}
        for condition in self.pair.CONDITIONS:
            arm = area / condition; arm.mkdir()
            header = self.header(contract, commitment, condition)
            body = self.pair.encode(header); originals[condition] = body
            arms[condition] = {"root": str(arm), "receipt": self.artifacts.emit(arm / "ARM.json", body)}
            self.pair.verify_arm_header(header, condition, commitment, contract)
        private = mock.Mock(side_effect=AssertionError("Private descriptor was opened"))
        factory = mock.Mock(side_effect=AssertionError("Packet was opened before headers"))
        mutations = (("query_count", 6399), ("attempt_inventory_count", 6399),
                     ("episodes", []), ("condition", "numeric_direct_four_demo"),
                     ("study_source_bindings", pin(b"changed source")),
                     ("authoring_exposure", pin(b"changed exposure")),
                     ("programme_identity", pin(b"changed programme")),
                     ("public_manifest", pin(b"changed packet")))
        program = self.pair.CONDITIONS[1]
        with mock.patch.object(self.modules["core"], "load_private_people",
                               side_effect=AssertionError("Private labels were opened")) as labels:
            for field, value in mutations:
                altered = json.loads(originals[program]); altered[field] = value
                arms[program]["receipt"] = self.artifacts.emit(
                    Path(arms[program]["root"]) / "ARM.json", self.pair.encode(altered), replace=True)
                with self.subTest(header=field), self.assertRaisesRegex(ValueError, "aligned arm|Incomplete attempt"):
                    self.pair.evaluate_pair(contract, commitment, arms, private, area / "unwritten-result",
                                            modules=self.modules, session_factory=factory)
                private.assert_not_called(); labels.assert_not_called(); factory.assert_not_called()
            arms[program]["receipt"] = self.artifacts.emit(
                Path(arms[program]["root"]) / "ARM.json", originals[program], replace=True)
            changed_contract = copy.deepcopy(contract); changed_contract["provider"]["model"] = "changed-after-freeze"
            with self.assertRaisesRegex(ValueError, "contract|commitment|Contract"):
                self.pair.evaluate_pair(changed_contract, commitment, arms, private, area / "unwritten-result",
                                        modules=self.modules, session_factory=factory)
            private.assert_not_called(); labels.assert_not_called(); factory.assert_not_called()
            # Inject only detailed arm refusal at the admission seam: this is
            # a control of private-access ordering, never a full-arm positive.
            roster = tuple("q-" + format(i, "032x") for i in range(6400))
            session = mock.MagicMock(); session.__enter__.return_value = types.SimpleNamespace(trial_ids=roster)
            for failed in ("admit_direct_arm", "admit_program_arm"):
                with mock.patch.object(self.pair, "admit_direct_arm", return_value={}) as direct, \
                     mock.patch.object(self.pair, "admit_program_arm", return_value={}) as programme:
                    (direct if failed == "admit_direct_arm" else programme).side_effect = ValueError("Generated detailed arm refusal")
                    with self.subTest(detailed=failed), self.assertRaisesRegex(ValueError, "Generated detailed arm refusal"):
                        self.pair.evaluate_pair(contract, commitment, arms, private, area / "unwritten-result",
                                                modules=self.modules, session_factory=lambda *a: session)
                    if failed == "admit_direct_arm":
                        programme.assert_not_called()
                    private.assert_not_called(); labels.assert_not_called()
            # Exercise the additive retained ATTEMPT authentication itself.
            # The old grader and Darwin profile lookup are stubbed only to reach
            # this new refusal portably, without claiming sandbox qualification
            # or synthesizing a successful6400 programme arm or opening data.
            first = Path(arms[program]["root"]) / "0000"
            original_attempt = {"trial_id": roster[0], "condition": program,
                "context_sha256": "0" * 64, "status": "ok", "error": None,
                "response": encoded({"trial_id": roster[0], "target_probability": 0.75}).decode()}
            changed_attempt = copy.deepcopy(original_attempt)
            changed_attempt["response"] = encoded({"trial_id": roster[0], "target_probability": 0.25}).decode()
            self.artifacts.emit(first / "ATTEMPT.json", self.pair.encode(changed_attempt))
            end = self.artifacts.emit(first / "END.json", self.pair.encode({
                "attempt": pin(self.pair.encode(original_attempt))}))
            changed_header = json.loads(originals[program]); changed_header["episodes"][0] = {"end": end}
            arms[program]["receipt"] = self.artifacts.emit(
                Path(arms[program]["root"]) / "ARM.json", self.pair.encode(changed_header), replace=True)
            with mock.patch.object(self.pair, "admit_direct_arm", return_value={}), \
                 mock.patch.object(self.modules["core"], "_admit_public_arm", return_value={}), \
                 mock.patch.object(self.modules["wire"], "sandbox_profile", return_value="generated-fixture-profile"):
                with self.assertRaisesRegex(ValueError, "Committed input changed"):
                    self.pair.evaluate_pair(contract, commitment, arms, private, area / "unwritten-result",
                                            modules=self.modules, session_factory=lambda *a: session)
            private.assert_not_called(); labels.assert_not_called()

    def test_duplicate_provider_identity_refused_on_second_real_admission(self):
        area, contract, commitment = self.study()
        roster = tuple("q-" + format(i, "032x") for i in range(6400))
        root = area / "generated-direct-arm"; root.mkdir()
        header = self.header(contract, commitment, self.pair.CONDITIONS[0])
        header.update({"provider": contract["provider"], "captured_request_policy_verified": True,
                       "provider_context_qualified": False, "provider_tool_policy_qualified": False})
        contexts = {}
        header["episodes"] = [{"trial_id": identifier, "status": "ok", "end": pin(b"unopened-fixture")}
                              for identifier in roster]
        for ordinal, identifier in enumerate(roster[:2]):
            context, capture = self.capture(contract, identifier, response_id="resp_reused_generated_identity")
            contexts[identifier] = context
            for name, path in self.pair.capture_paths(root / format(ordinal, "04d")).items():
                self.artifacts.emit(path, capture[name])
            header["episodes"][ordinal]["end"] = pin(capture["END.json"])
        predictions = b"".join(encoded({"trial_id": identifier, "target_probability": 0.75}) + b"\n"
                               for identifier in roster)
        header["predictions"] = self.artifacts.emit(root / "collection/predictions.jsonl", predictions)
        header["collection"] = self.artifacts.emit(root / "collection/COMPLETE.json", encoded({
            "status": "complete_unscored_submission", "condition": self.pair.CONDITIONS[0],
            "responses": 6400, "predictions": header["predictions"], "manifest_pin": contract["public_manifest"]}))
        descriptor = {"root": str(root), "receipt": self.artifacts.emit(root / "ARM.json", self.pair.encode(header))}
        visited = []
        def context(identifier, condition):
            visited.append(identifier)
            self.assertEqual(condition, self.pair.CONDITIONS[0])
            self.assertIn(identifier, contexts, "Duplicate should refuse before third query")
            return contexts[identifier]
        session = types.SimpleNamespace(trial_ids=roster, context=context)
        deadline = time.monotonic() + 30
        budget = self.pair.Budget(32 * 1024**3, 1024**2, deadline)
        with self.assertRaisesRegex(ValueError, "Reused provider response identity"):
            self.pair.admit_direct_arm(descriptor, contract, commitment, session, self.modules, budget, deadline)
        self.assertEqual(visited, list(roster[:2]))


if __name__ == "__main__":
    unittest.main()
