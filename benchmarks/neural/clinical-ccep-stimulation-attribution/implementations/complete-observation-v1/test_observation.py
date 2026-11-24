"""Generated controls only; no clinical packet or physiological inference."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


O = load(HERE / "observation.py", "ccep_observation")
sys.modules["pairing"] = O.C
F = load(HERE.parent / "clinical-ccep-pairing/test_pairing.py", "ccep_generated_fixture")


class ObservationControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.f = F.Fixture(self.root).freeze()

    def tearDown(self):
        self.tmp.cleanup()

    def export(self, name=None, **kwargs):
        name = name or self.f.policy["cases"][0]["case_id"]
        return O.export(self.f.pp, self.f.ph, self.f.cp, self.f.ch, name, self.f.paths[name],
                        "observation-001", kwargs.pop("max_bytes", 100000), **kwargs)

    def write(self, name, value):
        return self.f.write(name, value)

    def response(self, public):
        return {"schema": "ccep-observation-response-v1", "observation_id": public["observation_id"],
                "response_token": public["response_token"], "probabilities": [.25] * 4}

    def test_all_original_cases_export_when_entire_null_unavailable(self):
        for row in self.f.control["rows"]:
            row["stimulated_site"] = "same-site"
        self.f.freeze()
        self.assertFalse(self.f.mapping["transforms"])
        exported = []
        for case in self.f.policy["cases"]:
            name = case["case_id"]
            public, binding = self.export(name)
            expected = json.loads(base64.b64decode(self.f.blocks[name]["response_b64"]))
            self.assertEqual(public["response"], expected)
            self.assertEqual(len(public["response"]), case["repetitions"])
            self.assertEqual(public["relative_times_seconds"], ["0.011", "0.125", "0.500"])
            self.assertEqual(binding["condition"], "original_full_scope")
            exported.append(binding["case_id"])
        self.assertEqual(exported, [c["case_id"] for c in self.f.policy["cases"]])

    def test_paired_same_schema_keeps_complete_donor_and_recipient_components(self):
        transform = self.f.mapping["transforms"][0]
        pair = transform["donors"][0]
        r, d = pair["recipient"], pair["donor"]
        original, _ = self.export(r)
        paired, binding = self.export(r, map_path=self.f.mp, map_sha256=self.f.mh,
                                      transform_id=transform["id"], donor_packet_path=self.f.paths[d])
        self.assertEqual(set(original), set(paired))
        self.assertEqual(paired["response"], json.loads(base64.b64decode(self.f.blocks[d]["response_b64"])))
        for key in ("relative_times_seconds", "units", "missing", "artifact", "recording_location"):
            self.assertEqual(paired[key], original[key])
        self.assertEqual(binding["condition"], "paired_support_only")
        self.assertEqual(binding["transform_id"], transform["id"])
        self.assertNotEqual(paired["response_token"], original["response_token"])
        self.assertFalse({"case_id", "patient", "session", "site_block", "VTC_contact", "donor",
                          "transform_id", "policy_sha256", "targets_sha256"} & set(paired))
        self.assertEqual(paired["class_order"], list(O.P.CLASSES))

    def test_generated_capacity_boundary_refuses_whole_packet(self):
        public, _ = self.export()
        size = len(O.encoded(public))
        self.assertEqual(self.export(max_bytes=size)[0], public)
        with self.assertRaisesRegex(O.P.Invalid, "capacity"):
            self.export(max_bytes=size - 1)
        with self.assertRaises(O.P.Invalid):
            self.export(max_bytes=True)

    def test_malformed_complete_matrix_and_hash_are_rejected(self):
        name = self.f.policy["cases"][0]["case_id"]
        original = copy.deepcopy(self.f.blocks[name])
        for which, mutate in [("response", lambda a: a.pop()),
                              ("response", lambda a: a[0].__setitem__(1, 0)),
                              ("layout", lambda a: a["missing"][0].__setitem__(0, 1)),
                              ("layout", lambda a: a["relative_times_seconds"].__setitem__(0, "0.010"))]:
            self.f.blocks[name] = copy.deepcopy(original)
            value = json.loads(base64.b64decode(original[which + "_b64"]))
            mutate(value)
            body, digest = F.blob(value)
            self.f.blocks[name][which + "_b64"] = body
            next(row for row in self.f.control["rows"] if row["case_id"] == name)[which + "_sha256"] = digest
            self.f.freeze()
            with self.assertRaises(O.P.Invalid):
                self.export(name)
        self.f.blocks[name] = original
        self.f.freeze()
        self.f.paths[name].write_bytes(b'{}')
        with self.assertRaises(O.P.Invalid):
            self.export(name)

    def test_unresolved_case_and_incomplete_paired_arguments_rejected(self):
        name = self.f.policy["cases"][0]["case_id"]
        with self.assertRaises(O.P.Invalid):
            self.export(name, map_path=self.f.mp)
        self.f.policy["cases"][0].update(coverage="invalid_signal", coverage_reason="invented missing signal")
        self.f.freeze()
        with self.assertRaises(O.P.Invalid):
            self.export(name)

    def test_response_collection_yields_existing_scorer_row_and_no_target_open(self):
        public, binding = self.export()
        bp, bh = self.write("binding", binding)
        rp, _ = self.write("response", self.response(public))
        self.f.tp.unlink()
        result = O.collect(self.f.pp, self.f.ph, bp, bh, rp)
        self.assertEqual(result["row"], {"case_id": binding["case_id"], "probabilities": [.25] * 4})
        self.assertEqual(result["condition"], "original_full_scope")
        self.assertEqual(binding["public_sha256"], hashlib.sha256(O.encoded(public)).hexdigest())
        payload = dict(public); payload.pop("response_token")
        self.assertEqual(public["response_token"], hashlib.sha256(O.encoded(payload)).hexdigest())

    def test_response_identity_vector_and_external_binding_digest_are_required(self):
        public, binding = self.export()
        bp, bh = self.write("binding", binding)
        good = self.response(public)
        for field, value in [("observation_id", "wrong"), ("response_token", "0" * 64),
                             ("probabilities", [.5] * 4), ("probabilities", [True, 0, 0, 0]),
                             ("probabilities", [.25] * 3)]:
            response = copy.deepcopy(good); response[field] = value
            rp, _ = self.write("response", response)
            with self.assertRaises(O.P.Invalid):
                O.collect(self.f.pp, self.f.ph, bp, bh, rp)
        with patch.object(O.P, "read_document", side_effect=AssertionError("unexpected read")):
            for policy_hash, binding_hash in [(None, bh), (self.f.ph, None)]:
                with self.assertRaises(O.P.Invalid):
                    O.collect(self.f.pp, policy_hash, bp, binding_hash, "unused")

    def test_cli_roundtrip_and_no_clobber_from_unrelated_directory(self):
        import subprocess
        name = self.f.policy["cases"][0]["case_id"]
        binding_path = self.root / "cli-binding.json"
        command = [sys.executable, "-I", "-S", "-B", str(HERE / "observation.py")]
        args = ["export", "--policy", str(self.f.pp), "--policy-sha256", self.f.ph,
                "--control", str(self.f.cp), "--control-sha256", self.f.ch,
                "--case-id", name, "--packet", str(self.f.paths[name]),
                "--observation-id", "observation-001", "--max-public-bytes", "100000",
                "--binding-output", str(binding_path)]
        first = subprocess.run(command + args, cwd=self.root, capture_output=True, timeout=10)
        self.assertEqual(first.returncode, 0, first.stderr)
        public = json.loads(first.stdout)
        frozen = binding_path.read_bytes()
        binding = json.loads(frozen)
        self.assertEqual(binding["public_sha256"], hashlib.sha256(first.stdout).hexdigest())
        self.assertEqual(binding_path.stat().st_mode & 0o777, 0o600)
        rp, _ = self.write("cli-response", self.response(public))
        second = subprocess.run(command + ["collect", "--policy", str(self.f.pp),
                     "--policy-sha256", self.f.ph, "--binding", str(binding_path),
                     "--binding-sha256", hashlib.sha256(frozen).hexdigest(),
                     "--response", str(rp)], cwd=self.root, capture_output=True, timeout=10)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)["row"], {"case_id": name, "probabilities": [.25] * 4})
        repeated = subprocess.run(command + args, cwd=self.root, capture_output=True, timeout=10)
        self.assertEqual(repeated.returncode, 2)
        self.assertEqual(binding_path.read_bytes(), frozen)
        self.assertEqual(json.loads(repeated.stdout)["status"], "invalid_or_incomplete")

    def test_export_cli_capacity_failure_leaves_no_binding(self):
        name = self.f.policy["cases"][0]["case_id"]
        args = ["export", "--policy", str(self.f.pp), "--policy-sha256", self.f.ph,
                "--control", str(self.f.cp), "--control-sha256", self.f.ch,
                "--case-id", name, "--packet", str(self.f.paths[name]),
                "--observation-id", "observation-001", "--max-public-bytes", "1",
                "--binding-output", str(self.root / "not-created.json")]
        import contextlib
        import io
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(O.main(args), 2)
        self.assertFalse((self.root / "not-created.json").exists())
        self.assertEqual(json.loads(output.getvalue())["status"], "invalid_or_incomplete")


if __name__ == "__main__":
    unittest.main(verbosity=2)
