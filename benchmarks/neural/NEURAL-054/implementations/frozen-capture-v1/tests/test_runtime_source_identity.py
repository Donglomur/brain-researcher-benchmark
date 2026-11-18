"""Generated metadata tests of the authenticated preparation/issuer call paths.

No authentic rows, category targets, arrays, native imports, model or Docker run.
--base-package is only for testing a private postimage overlay before integration.
"""
import argparse
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PARSER = argparse.ArgumentParser(add_help=False)
PARSER.add_argument("--base-package", type=Path)
OPTIONS, REMAINING = PARSER.parse_known_args()
sys.argv = [sys.argv[0], *REMAINING]
PACKAGE = Path(__file__).resolve().parents[1] / "package"
BASE = OPTIONS.base_package or PACKAGE


def body(name):
    changed = PACKAGE / name
    return (changed if changed.is_file() else BASE / name).read_bytes()


def generated_roster():
    rows = []
    for person in ("BIGMEG1", "BIGMEG2", "BIGMEG3", "BIGMEG4"):
        epoch = 0
        for session in range(1, 13):
            for concept in range(1, 1855):
                image = (session - 1) * 1854 + concept
                rows.append({"person": person, "epoch_index": epoch,
                             "session": session, "run": (concept - 1) % 10 + 1,
                             "trial_type": "exp", "image": image,
                             "concept": concept,
                             "image_path": f"generated-only/{image}.jpg"})
                epoch += 1
        for disposition in ("repeat", "catch"):
            for index in range(2400):
                rows.append({"person": person, "epoch_index": epoch,
                             "session": index % 12 + 1, "run": index % 10 + 1,
                             "trial_type": disposition})
                epoch += 1
    return rows


class ReachedBoundary(RuntimeError):
    """Stop before a target read or native dependency import."""


class RuntimeSourceIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the production source authenticator and captured-module importer.
        spec = importlib.util.spec_from_loader("n054_identity_test_entry", loader=None)
        cls.entry = importlib.util.module_from_spec(spec)
        exec(compile(body("entry.py"), str(PACKAGE / "entry.py"), "exec"), cls.entry.__dict__)
        raw = body("RUNTIME_SOURCE_LOCK.json")

        class Prefix:
            def read(self, path, size, expected):
                value = body(str(path.relative_to(PACKAGE)))
                if len(value) != size or hashlib.sha256(value).hexdigest() != expected["sha256"]:
                    raise ValueError("source identity mismatch")
                return value

        cls.prefix = Prefix()
        cls.lock = json.loads(raw)
        cls.captured = cls.entry.authenticate(PACKAGE, len(raw), hashlib.sha256(raw).hexdigest(), cls.prefix)
        if any(name == "n054" or name.startswith("n054.") for name in sys.modules):
            raise RuntimeError("fresh n054 import domain required")
        cls.finder = cls.entry.CapturedRuntime(PACKAGE, cls.captured)
        sys.meta_path.insert(0, cls.finder)
        cls.preparation = importlib.import_module("n054.preparation")
        cls.views = importlib.import_module("n054.views")
        cls.identity = importlib.import_module("n054.source_identity")
        cls.rows = generated_roster()
        cls.order = list(range(1, 22249))
        cls.images = [{"image": i, "image_path": f"generated-only/{i}.jpg"} for i in cls.order]

    @classmethod
    def tearDownClass(cls):
        sys.meta_path.remove(cls.finder)
        for name in list(sys.modules):
            if name == "n054" or name.startswith("n054."):
                del sys.modules[name]

    def admission(self):
        pin = {"path": "generated-only-roster.json", "bytes": 1, "sha256": "0" * 64}
        result = {"domain": self.preparation.DOMAIN, "execution_selection": "generated-selection",
                  "generation": "generated-only", "roster": pin,
                  "labels": {**pin, "path": "never-read-targets.json"},
                  "images": self.images, "image_order": self.order,
                  "derivatives": [{"kind": "FIF" if i < 16 else "EYE_CSV", "path": f"generated-only/{i}"}
                                  for i in range(64)]}
        for key in ("release_bridge", "clock_geometry", "preprocessing", "native_environment", "rights", "immutable_mount"):
            result[key] = {"status": "QUALIFIED", "evidence": "generated control only"}
        return result

    def test_validator_is_inside_authenticated_runtime_closure(self):
        self.assertIn("programme/n054/source_identity.py", self.captured)
        self.assertEqual(self.preparation.validate_roster, self.identity.validate_roster)
        self.assertEqual(self.views.validate_roster, self.identity.validate_roster)

    def test_source_authenticator_rejects_changed_validator(self):
        original = body
        def corrupt(name):
            value = original(name)
            return value + b"# changed\n" if name == "programme/n054/source_identity.py" else value
        raw = original("RUNTIME_SOURCE_LOCK.json")
        with patch(__name__ + ".body", side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, "source identity mismatch"):
                self.entry.authenticate(PACKAGE, len(raw), hashlib.sha256(raw).hexdigest(), self.prefix)

    def test_wrong_execution_authority_precedes_all_roster_access(self):
        admission = self.admission()
        with patch.object(self.preparation, "load") as prep_read, patch.object(self.views, "load") as view_read:
            for call in (lambda: self.preparation.extract(admission, "unused", "unused", "unused", "wrong"),
                         lambda: self.views.FeatureIssuer(admission, "unused", b"x" * 32, "wrong")):
                with self.assertRaisesRegex(ValueError, "execution selection"):
                    call()
            prep_read.assert_not_called()
            view_read.assert_not_called()

    def test_unqualified_preparation_gate_precedes_roster_access(self):
        admission = self.admission()
        admission["clock_geometry"]["status"] = "UNQUALIFIED"
        with patch.object(self.preparation, "load") as read:
            with self.assertRaisesRegex(ValueError, "clock_geometry"):
                self.preparation.extract(admission, "unused", "unused", "unused", "generated-selection")
            read.assert_not_called()

    def test_cross_person_concept_swap_rejected_before_preparation_side_effects(self):
        admission = self.admission()
        with patch.dict(self.rows[27048], concept=2), patch.dict(self.rows[27049], concept=1), \
             patch.object(self.preparation, "load", return_value=self.rows), patch.object(Path, "mkdir") as mkdir:
            with self.assertRaisesRegex(self.identity.IdentityError, "inconsistent concept"):
                self.preparation.extract(admission, "unused", "unused", "unused", "generated-selection")
            mkdir.assert_not_called()
        self.assertNotIn("numpy", sys.modules)

    def test_cross_person_concept_swap_rejected_before_issuer_targets(self):
        with patch.dict(self.rows[27048], concept=2), patch.dict(self.rows[27049], concept=1), \
             patch.object(self.views, "load", side_effect=[self.rows, ReachedBoundary("targets")]) as read:
            with self.assertRaisesRegex(self.identity.IdentityError, "inconsistent concept"):
                self.views.FeatureIssuer(self.admission(), "unused", b"x" * 32, "generated-selection")
            self.assertEqual(read.call_count, 1)

    def test_extra_visual_row_rejected_before_issuer_targets(self):
        admission = self.admission()
        admission["image_order"] = self.order + [1]
        with patch.object(self.views, "load", side_effect=[self.rows, ReachedBoundary("targets")]) as read:
            with self.assertRaisesRegex(ValueError, "Complete shared visual row order"):
                self.views.FeatureIssuer(admission, "unused", b"x" * 32, "generated-selection")
            read.assert_not_called()

    def test_null_missing_or_nonlist_visual_order_cannot_skip_validation(self):
        for value in (None, False, tuple(self.order), [], {"image": 1}, "missing"):
            with self.subTest(value_type=type(value).__name__):
                admission = self.admission()
                if value == "missing":
                    del admission["image_order"]
                else:
                    admission["image_order"] = value
                with patch.object(self.views, "load") as read:
                    with self.assertRaisesRegex(ValueError, "Complete shared visual row order"):
                        self.views.FeatureIssuer(admission, "unused", b"x" * 32, "generated-selection")
                    read.assert_not_called()

    def test_wrong_extraction_image_path_rejected_before_native_import(self):
        admission = self.admission()
        admission["images"] = [{**self.images[0], "image_path": "generated-only/wrong.jpg"}, *self.images[1:]]
        with patch.object(self.preparation, "load", return_value=self.rows), patch.object(Path, "mkdir") as mkdir:
            with self.assertRaisesRegex(self.identity.IdentityError, "source path differs"):
                self.preparation.extract(admission, "unused", "unused", "unused", "generated-selection")
            mkdir.assert_not_called()

    def test_valid_preparation_reaches_existing_native_boundary_once(self):
        import builtins
        original = builtins.__import__
        def stop_native(name, *args, **kwargs):
            if name == "numpy":
                raise ReachedBoundary("native import")
            return original(name, *args, **kwargs)
        with patch.object(self.preparation, "load", return_value=self.rows) as read, \
             patch.object(Path, "mkdir") as mkdir, patch("builtins.__import__", side_effect=stop_native):
            with self.assertRaisesRegex(ReachedBoundary, "native import"):
                self.preparation.extract(self.admission(), "unused", "unused", "unused", "generated-selection")
            read.assert_called_once()
            mkdir.assert_called_once_with(exist_ok=False)
        self.assertNotIn("numpy", sys.modules)

    def test_valid_issuer_identity_reaches_original_target_boundary(self):
        with patch.object(self.views, "load", side_effect=[self.rows, ReachedBoundary("target boundary")]) as read:
            with self.assertRaisesRegex(ReachedBoundary, "target boundary"):
                self.views.FeatureIssuer(self.admission(), "unused", b"x" * 32, "generated-selection")
            self.assertEqual(read.call_count, 2)
            self.assertEqual(read.call_args.args[0], Path("unused/never-read-targets.json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
