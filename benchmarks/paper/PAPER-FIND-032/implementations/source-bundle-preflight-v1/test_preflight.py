"""Generated source text only; no official source imports or scientific data."""
import hashlib
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("find032_preflight", Path(__file__).with_name("preflight.py"))
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def bundle(base=b"corresp = {}\nevents_sound = [1, 2, 3, 4]\n", sound=None, omission=None):
    bodies = {"base": base,
              "sound": sound or b"from base import corresp, events_sound\n",
              "omission": omission or b"from base import corresp, cond2code, getFiltPat, dadd\n"}
    return {role: {"filename": preflight.ROLES[role], "revision": preflight.REVISION,
                   "body": body, "sha256": hashlib.sha256(body).hexdigest()}
            for role, body in bodies.items()}


class PreflightTests(unittest.TestCase):
    def test_reports_three_missing_helpers_without_importing_source(self):
        data = bundle(sound=b"raise RuntimeError('must never execute')\nfrom base import corresp\n")
        report = preflight.inspect_bundle(data)
        self.assertEqual(report["consumers"]["omission"]["missing_direct_base_bindings"],
                         ["cond2code", "dadd", "getFiltPat"])
        self.assertEqual(report["consumers"]["sound"]["missing_direct_base_bindings"], [])
        self.assertEqual(report["diagnostic"], "static_source_gap")
        self.assertFalse(report["source_executed"])

    def test_conditional_export_not_assumed_present(self):
        data = bundle(base=b"corresp = {}\nif False:\n    cond2code = {}\n")
        report = preflight.inspect_bundle(data)
        self.assertIn("cond2code", report["consumers"]["omission"]["missing_direct_base_bindings"])

    def test_direct_definitions_and_aliases_are_only_a_syntactic_diagnostic(self):
        data = bundle(base=b"corresp = {}\nevents_sound = []\ncond2code = {}\ndef getFiltPat():\n    pass\nfrom nonexistent import thing as dadd\n")
        report = preflight.inspect_bundle(data)
        self.assertEqual(report["diagnostic"], "no_direct_binding_gap_detected")
        for key in ("admission_issued", "source_executed", "upstream_authentication_established",
                    "runtime_executability_established", "publication_parity_established"):
            self.assertFalse(report[key])

    def test_explicit_deletion_remains_missing(self):
        data = bundle(base=b"corresp = {}\ncond2code = {}\ndel cond2code\n")
        self.assertIn("cond2code", preflight.inspect_bundle(data)["consumers"]["omission"]["missing_direct_base_bindings"])

    def test_wildcard_stays_unresolved(self):
        report = preflight.inspect_bundle(bundle(omission=b"from base import *\n"))
        self.assertTrue(report["consumers"]["omission"]["wildcard_import_unresolved"])
        self.assertEqual(report["diagnostic"], "static_source_gap")

    def test_relative_import_is_not_bound_to_top_level_source(self):
        report = preflight.inspect_bundle(bundle(omission=b"from .base import corresp\n"))
        self.assertTrue(report["consumers"]["omission"]["relative_base_import_unresolved"])
        self.assertEqual(report["consumers"]["omission"]["requested_base_names"], [])
        self.assertEqual(report["diagnostic"], "static_source_gap")

    def test_relative_module_binding_is_not_resolved_as_top_level_base(self):
        for statement in (b"from . import base\n", b"from .. import base as helpers\n"):
            report = preflight.inspect_bundle(bundle(omission=statement))
            consumer = report["consumers"]["omission"]
            self.assertTrue(consumer["relative_base_import_unresolved"])
            self.assertEqual(consumer["requested_base_names"], [])
            self.assertEqual(report["diagnostic"], "static_source_gap")

    def test_relative_wildcard_retains_both_unresolved_reasons(self):
        report = preflight.inspect_bundle(bundle(omission=b"from .base import *\n"))
        consumer = report["consumers"]["omission"]
        self.assertTrue(consumer["relative_base_import_unresolved"])
        self.assertTrue(consumer["wildcard_import_unresolved"])
        self.assertEqual(consumer["requested_base_names"], [])
        self.assertEqual(report["diagnostic"], "static_source_gap")

    def test_mixed_revision_refused(self):
        data = bundle()
        data["base"]["revision"] = "e6156bb4a411fb81603aee7a49eaa160b0133550"
        with self.assertRaisesRegex(preflight.BundleError, "same selected source revision"):
            preflight.inspect_bundle(data)

    def test_plural_or_traversing_role_filename_refused(self):
        for filename in ("reproduce_and_reorder_omissions.py", "../reproduce_and_reorder_omission.py"):
            data = bundle()
            data["omission"]["filename"] = filename
            with self.assertRaisesRegex(preflight.BundleError, "filename"):
                preflight.inspect_bundle(data)

    def test_stale_hash_refused(self):
        data = bundle()
        data["base"]["body"] += b"cond2code = {}\n"
        with self.assertRaisesRegex(preflight.BundleError, "sha256"):
            preflight.inspect_bundle(data)

    def test_unexpected_or_incomplete_roles_refused(self):
        for remove in (True, False):
            data = bundle()
            if remove:
                del data["omission"]
            else:
                data["extra"] = data["base"]
            with self.assertRaisesRegex(preflight.BundleError, "exact base"):
                preflight.inspect_bundle(data)

    def test_invalid_text_or_oversized_source_refused(self):
        for body in (b"\xff", b"def broken(\n", b"\x00", b"x" * (preflight.MAX_BODY_BYTES + 1)):
            data = bundle(base=body)
            with self.assertRaises(preflight.BundleError):
                preflight.inspect_bundle(data)


if __name__ == "__main__":
    unittest.main()
