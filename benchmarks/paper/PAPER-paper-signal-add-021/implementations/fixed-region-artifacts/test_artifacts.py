"""Generated complete artifacts and byte fixtures; never authentic data/gold."""
import argparse
import contextlib
import copy
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("artifact_route", HERE / "artifacts.py")
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
PROFILE_ROOT = None


def fixture(s):
    def paired(n):
        return {"n": n, "df": n - 1, "mean": 0.0, "sample_sd": 1.0,
                "standard_error": 1 / math.sqrt(n), "t": 0.0, "cohens_dz": 0.0, "degenerate": None}
    regions = []
    for rid in s.REGIONS:
        effects = {}
        for eid in s.EFFECTS:
            effects[eid] = {"differences_by_source_position": [0.0] * 15, "paired": paired(15),
                "sign_flip": {"enumerated": 32768, "extreme": 32768, "p_two_sided": 1.0},
                "bootstrap": {"draws": 2000, "seed": 20261114, "lower": -1.0, "upper": 1.0},
                "holm_all36_region_sensitivity_p": 1.0,
                "leave_one_position_out": [{"excluded_position": i, "paired": paired(14)} for i in range(15)]}
        regions.append({"id": rid, "condition_means_by_source_position": [[0.0] * 15 for _ in range(4)], "effects": effects})
    return {"schema": "tms-paired-eeg-region-reference-v1", "source_positions": list(range(15)),
            "region_definitions": 12, "paired_effects": 36, "leave_one_out_summaries": 540, "regions": regions}


class ArtifactRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = a.source(PROFILE_ROOT)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.ref = a.encode(fixture(self.s)); self.refpin = a.pin(self.ref)
        self.candidate = self.s.submission_from_reference(json.loads(self.ref))
        self.ap = self.root / "participant-A.json"; self.bp = self.root / "participant-B.json"
        self.ap.write_bytes(a.encode(self.candidate)); self.bp.write_bytes(a.encode(self.candidate))
        self.gold = self.root / "generated-gold.json"; self.gold.write_bytes(self.ref)
        self.pair = self.root / "pair"; self.out = self.root / "score.json"; self.reads = []

    def tearDown(self):
        # Only owned generated temporary files are made removable.
        for root, dirs, files in os.walk(self.root):
            Path(root).chmod(0o700)
            for name in files:
                p = Path(root) / name
                if not p.is_symlink(): p.chmod(0o600)
        self.temp.cleanup()

    def reader(self, path, cap, expected):
        self.reads.append(str(path)); return a.read_file(path, cap, expected)

    def freeze(self):
        return a.freeze_pair(self.ap, self.bp, self.pair, self.s)

    def score(self):
        return a.score_pair(self.pair, self.gold, self.out, self.s,
                            reference_pin=self.refpin, reference_reader=self.reader)

    def replace_frozen(self, name, body):
        self.pair.chmod(0o700); p = self.pair / name; p.chmod(0o600)
        p.write_bytes(body); p.chmod(0o400); self.pair.chmod(0o500)

    def test_physical_alias_refused_before_public_validation(self):
        class NoValidation:
            def decode(self, raw):
                raise AssertionError("physical alias reached public decoder")
        linked = self.root / "hardlink.json"
        os.link(self.ap, linked)
        with self.assertRaisesRegex(a.Refusal, "distinct physical"):
            a.freeze_pair(self.ap, linked, self.pair, NoValidation())
        linked.unlink()
        case_alias = self.root / self.ap.name.upper()
        if case_alias.exists() and case_alias.samefile(self.ap):
            with self.assertRaisesRegex(a.Refusal, "distinct physical"):
                a.freeze_pair(self.ap, case_alias, self.pair, NoValidation())
        self.assertFalse(self.pair.exists())
        self.assertEqual(self.reads, [])

    def test_complete_pair_scores_unchanged_and_reference_read_once(self):
        wrong = copy.deepcopy(self.candidate)
        wrong["regions"][0]["effects"][0]["differences"] = [1.0] * 15
        self.bp.write_bytes(a.encode(wrong)); self.freeze(); result = self.score()
        report = json.loads(self.out.read_bytes())
        self.assertEqual(result["status"], "scored_trusted_external_artifacts")
        self.assertEqual(report["scores"]["A"]["score"], 1.0)
        self.assertAlmostEqual(report["scores"]["B"]["score"], 1 - 0.5 / (36 * 7))
        self.assertEqual(self.reads, [str(self.gold)])
        self.assertFalse(report["protected_execution_attested"])
        self.assertIsNone(report["combined_arm_metric"])
        for score in report["scores"].values():
            self.assertEqual((score["all_regions"], score["all_effects"], score["all_leave_one_out"]), (12, 36, 540))
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o600)

    def test_malformed_second_arm_prevents_pair_creation(self):
        self.bp.write_bytes(b'{}')
        with self.assertRaises(self.s.InvalidSubmission): self.freeze()
        self.assertFalse(self.pair.exists()); self.assertEqual(self.reads, [])

    def test_public_revalidation_precedes_private_load(self):
        self.freeze(); malformed = b'{"schema":"wrong"}'
        receipt = json.loads((self.pair / "PAIR.json").read_bytes())
        receipt["submissions"]["B"].update(a.pin(malformed))
        self.replace_frozen("B.json", malformed)
        self.replace_frozen("PAIR.json", a.encode(receipt))
        with self.assertRaises(self.s.InvalidSubmission): self.score()
        self.assertEqual(self.reads, []); self.assertFalse(self.out.exists())

    def test_tampered_snapshot_pin_refused_before_reference(self):
        self.freeze(); self.replace_frozen("A.json", (self.pair / "A.json").read_bytes() + b' ')
        with self.assertRaises(a.Refusal): self.score()
        self.assertEqual(self.reads, [])

    def test_wrong_reference_is_infrastructure_not_score(self):
        self.freeze(); self.gold.write_bytes(b'{}')
        with self.assertRaises(self.s.InvalidReference): self.score()
        self.assertEqual(self.reads, [str(self.gold)]); self.assertFalse(self.out.exists())

    def test_reference_support_error_keeps_output_absent(self):
        ref = json.loads(self.ref); ref["region_definitions"] = 11
        self.ref = a.encode(ref); self.refpin = a.pin(self.ref); self.gold.write_bytes(self.ref)
        self.freeze()
        with self.assertRaises(self.s.InvalidReference): self.score()
        self.assertFalse(self.out.exists())

    def test_existing_output_is_never_overwritten_or_gold_read(self):
        self.freeze(); self.out.write_bytes(b'preserve')
        with self.assertRaises(a.Refusal): self.score()
        self.assertEqual(self.out.read_bytes(), b'preserve'); self.assertEqual(self.reads, [])

    def test_receipt_escape_or_protection_claim_refused(self):
        self.freeze(); original = (self.pair / "PAIR.json").read_bytes()
        for edit in ("escape", "protection"):
            receipt = json.loads(original)
            if edit == "escape": receipt["submissions"]["A"]["file"] = "../participant-A.json"
            else: receipt["protected_execution_attested"] = True
            self.replace_frozen("PAIR.json", a.encode(receipt))
            with self.subTest(edit=edit), self.assertRaises(a.Refusal): self.score()
        self.assertEqual(self.reads, [])

    def test_file_aliases_and_duplicate_locator_refused(self):
        with self.assertRaises(a.Refusal): a.freeze_pair(self.ap, self.ap, self.pair, self.s)
        alias = self.root / "alias.json"; alias.symlink_to(self.ap)
        with self.assertRaises(a.Refusal): a.freeze_pair(alias, self.bp, self.pair, self.s)
        alias.unlink(); os.link(self.ap, alias)
        with self.assertRaises(a.Refusal): a.freeze_pair(alias, self.bp, self.pair, self.s)
        self.assertFalse(self.pair.exists())

    def make_inputs(self):
        root = self.root / "generated-inputs"; root.mkdir(); expected = {}
        for i, name in enumerate(a.INPUTS):
            body = ("generated-only-" + str(i)).encode(); (root / name).write_bytes(body)
            expected[name] = a.pin(body)
        return root, expected

    def test_input_import_preserves_complete_fixture_bytes_and_modes(self):
        root, expected = self.make_inputs(); target = self.root / "imported"
        result = a.check_inputs(root, expected=expected, destination=target)
        self.assertEqual(result["input_files"], expected)
        self.assertEqual(set(x.name for x in target.iterdir()), set(a.INPUTS))
        self.assertEqual(target.stat().st_mode & 0o777, 0o500)
        for name in expected:
            self.assertEqual((target / name).read_bytes(), (root / name).read_bytes())
            self.assertEqual((target / name).stat().st_mode & 0o777, 0o400)
        self.assertFalse(result["array_decode"]); self.assertEqual(result["reference_reads"], 0)

    def test_failed_import_is_retained_and_not_retried(self):
        root, expected = self.make_inputs(); target = self.root / "failed-import"
        expected["pair_counts.u8"]["sha256"] = "0" * 64
        with self.assertRaises(a.Refusal): a.check_inputs(root, expected=expected, destination=target)
        self.assertTrue(target.exists()); self.assertFalse((target / "missingness.json").exists())
        before = {x.name: x.read_bytes() for x in target.iterdir()}
        with self.assertRaises(a.Refusal): a.check_inputs(root, expected=expected, destination=target)
        self.assertEqual(before, {x.name: x.read_bytes() for x in target.iterdir()})

    def test_input_population_and_namespace_overlap_refused(self):
        root, expected = self.make_inputs(); (root / "unexpected").write_bytes(b'x')
        with self.assertRaises(a.Refusal): a.check_inputs(root, expected=expected)
        (root / "unexpected").unlink()
        with self.assertRaises(a.Refusal): a.check_inputs(root, expected=expected, destination=root / "nested")

    def test_real_CLI_parse_validate_and_freeze_route(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(a.main(["--profile-root", str(PROFILE_ROOT), "validate", "--submission", str(self.ap)]), 0)
        self.assertEqual(json.loads(out.getvalue())["omissions"], 540)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(a.main(["--profile-root", str(PROFILE_ROOT), "freeze-pair", "--submission-a", str(self.ap),
                                    "--submission-b", str(self.bp), "--output-root", str(self.pair)]), 0)
        self.assertEqual(set(a.load_pair(self.pair, self.s)[0]), {"A", "B"})
        self.assertEqual(self.reads, [])

    def test_changed_scorer_refused_before_execution(self):
        root = self.root / "changed-profile"; root.mkdir()
        for name in a.SHARED:
            (root / name).write_bytes((PROFILE_ROOT / name).read_bytes())
        (root / "scorer.py").write_bytes(b"raise AssertionError('changed source executed')\n")
        with self.assertRaises(a.Refusal): a.source(root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-root", type=Path, required=True)
    args, remaining = parser.parse_known_args(); PROFILE_ROOT = args.profile_root.resolve(strict=True)
    unittest.main(argv=[__file__, *remaining])
