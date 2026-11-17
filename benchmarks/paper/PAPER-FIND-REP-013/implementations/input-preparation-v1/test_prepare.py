"""Generated software controls only: no authentic anatomy or target access."""
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location("purkinje_input_prepare", Path(__file__).with_name("prepare.py"))
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


def fixture_members():
    members = {}
    for i, stem in enumerate(P.STEMS):
        # A two-root forest and seven-column data must survive byte-for-byte.
        members[P.PREFIX + P.swc_name(stem)] = f"1 1 0 0 0 1 -1\n2 3 {i} 0 0 1 -1\n".encode()
        header = " ".join(P.SHOLL_HEADER)
        # Third-column lengths 2+3, distinctly different radii/volume/area.
        members[P.PREFIX + stem + " sholl.txt"] = (header + "\n1 2 2 90 80 0 0 0 0 0 0\n"
                                                               "2 3 3 99 88 0 0 0 0 0 0\n").encode()
    return members


def archive(members=None, extra=()):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in (fixture_members() if members is None else members).items():
            z.writestr(name, body)
        for name, body in extra:
            z.writestr(name, body)
    return out.getvalue()


RMD = "\n".join("source line " + str(i) for i in range(1, 1103)).encode()
DESCRIPTORS = {"TASK.md": b"generated task\n", "SCHEMA.json": b"{}\n"}


class PreparationControls(unittest.TestCase):
    def test_complete_panel_identity_units_and_exposure(self):
        members = fixture_members()
        files = P.derive(archive(members), RMD, DESCRIPTORS)
        self.assertEqual(len(files), 15)
        self.assertEqual(files["TASK.md"], DESCRIPTORS["TASK.md"])
        rows = json.loads(files["cells.json"])
        self.assertEqual(len(rows), 10)
        self.assertEqual([r["species"] for r in rows].count("human"), 5)
        self.assertEqual([r["species"] for r in rows].count("mouse"), 5)
        self.assertEqual(rows[1]["source_filename"], "H13 Split 1 Reconstructionswc.swc")
        for row in rows:
            self.assertEqual(files[row["file"]], members[P.PREFIX + row["source_filename"]])
            if row["species"] == "mouse":
                self.assertIsNone(row["specimen_label"])
                self.assertEqual(row["mouse_individual_mapping"], "unavailable")
        totals = files["author_sholl_totals.csv"].decode().splitlines()
        self.assertEqual(totals[0], "cell_id,author_sholl_length_um")
        self.assertEqual(len(totals), 11)
        self.assertTrue(all(line.endswith(",5") for line in totals[1:]))
        self.assertNotIn("branches.csv", files)

    def test_source_line_ranges_and_ambiguous_conventions_are_preserved(self):
        s = json.loads(P.source_semantics(RMD))
        snippets = s["numbered_snippets"]
        self.assertEqual([(v["line_start"], v["line_end"]) for v in snippets],
                         [(187, 191), (303, 319), (483, 489), (851, 879), (1091, 1102)])
        self.assertTrue(snippets[2]["text"].startswith("483: source line 483\n"))
        self.assertTrue(snippets[2]["text"].endswith("489: source line 489"))
        self.assertIn("historical author runtime is unresolved", s["interpretation_limit"])

    def test_cell_map_matches_the_preexisting_public_identity(self):
        # Cell labels/provenance are public metadata, independent of the
        # invented geometry. This protects the real downstream packet join.
        expected = json.loads(P.capture(P.PROFILE / "INPUT_PINS.json", P.INPUT_PINS))
        files = P.derive(archive(), RMD, DESCRIPTORS)
        self.assertEqual(P.pin(files["cells.json"]), expected["cells.json"])

    def test_every_missing_swc_and_sholl_is_rejected(self):
        members = fixture_members()
        for missing in members:
            with self.subTest(missing=missing):
                altered = {k: v for k, v in members.items() if k != missing}
                with self.assertRaisesRegex(ValueError, "complete exact ten-cell"):
                    P.selected_members(archive(altered))

    def test_extra_cell_and_guessed_h13_filename_are_rejected(self):
        original = fixture_members()
        for name in (P.PREFIX + "extra.swc", P.PREFIX + "H13 Split 1 Reconstruction.swc"):
            with self.subTest(name=name):
                members = dict(original)
                members[name] = b"1 1 0 0 0 1 -1\n"
                with self.assertRaisesRegex(ValueError, "complete exact ten-cell"):
                    P.selected_members(archive(members))

    def test_zip_duplicates_traversal_and_symlinks_are_rejected(self):
        first = next(iter(fixture_members()))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            duplicate = archive(extra=[(first, b"duplicate")])
        for body, message in ((duplicate, "duplicate"),
                              (archive(extra=[("../outside", b"x")]), "unsafe"),
                              (archive(extra=[("/absolute", b"x")]), "unsafe")):
            with self.assertRaisesRegex(ValueError, message):
                P.selected_members(body)
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(ValueError, "nonordinary"):
            P.selected_members(archive(extra=[(link, b"target")]))

    def test_sholl_shape_semantics_and_nonfinite_rejected(self):
        body = next(v for k, v in fixture_members().items() if k.endswith("sholl.txt"))
        for changed in (body.replace(b"DEND-LENGTH", b"WRONG-FIELD"),
                        body.replace(b"1 2 2 90", b"1 2 nan 90"),
                        body.replace(b"1 2 2 90", b"1 2 -2 90"),
                        body.replace(b"1 2 2 90", b"1 2 90")):
            with self.assertRaises(ValueError):
                P.sholl_total(changed)

    def test_wrong_derived_bytes_and_partial_panel_never_pass_input_pins(self):
        files = P.derive(archive(), RMD, DESCRIPTORS)
        expected = {n: P.pin(b) for n, b in files.items()}
        P.verify_outputs(files, expected)
        for name in files:
            with self.subTest(name=name):
                altered = dict(files)
                altered[name] += b"\n"
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    P.verify_outputs(altered, expected)
        del files["raw/H13_Split_1.swc"]
        with self.assertRaisesRegex(ValueError, "complete original input set"):
            P.verify_outputs(files, expected)

    def test_source_authentication_and_publish_no_overwrite(self):
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as folder:
            root = Path(folder)
            src = root / "source"
            src.write_bytes(b"source")
            self.assertEqual(P.capture(src, P.pin(b"source")), b"source")
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                P.capture(src, P.pin(b"mutant"))
            link = root / "link"
            link.symlink_to(src)
            with self.assertRaisesRegex(ValueError, "symlink"):
                P.capture(link, P.pin(b"source"))
            target = root / "output"
            P.publish({"raw/a.swc": b"a", "cells.json": b"[]"}, target)
            self.assertEqual((target / "raw/a.swc").read_bytes(), b"a")
            with self.assertRaisesRegex(ValueError, "fresh output"):
                P.publish({"cells.json": b"replacement"}, target)
            self.assertEqual((target / "cells.json").read_bytes(), b"[]")
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["link", "output", "source"])

    def test_full_operator_path_and_late_failure_without_publication(self):
        # Patch only authentication constants and source-profile location; the
        # real capture/derive/pin-validation/publish path executes on fixtures.
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as folder:
            root = Path(folder)
            profile = root / "profile"
            profile.mkdir()
            zipbody = archive()
            zpath, rpath = root / "source.zip", root / "source.Rmd"
            zpath.write_bytes(zipbody)
            rpath.write_bytes(RMD)
            outputs = P.derive(zipbody, RMD, DESCRIPTORS)
            pins = {n: P.pin(b) for n, b in outputs.items()}
            for name, body in DESCRIPTORS.items():
                (profile / name).write_bytes(body)
            pinbody = P.encode(pins)
            (profile / "INPUT_PINS.json").write_bytes(pinbody)
            with patch.multiple(P, PROFILE=profile, ARCHIVE=P.pin(zipbody),
                                RMD=P.pin(RMD), INPUT_PINS=P.pin(pinbody)):
                # The source-semantics hash follows the authenticated Rmd pin.
                outputs = P.derive(zipbody, RMD, DESCRIPTORS)
                pins = {n: P.pin(b) for n, b in outputs.items()}
                pinbody = P.encode(pins)
                (profile / "INPUT_PINS.json").write_bytes(pinbody)
                with patch.object(P, "INPUT_PINS", P.pin(pinbody)):
                    receipt = P.prepare(zpath, rpath, root / "published")
                    self.assertEqual(len(receipt["files"]), 16)
                    self.assertTrue(receipt["original_inputs_exact"])
                    self.assertFalse(receipt["paired_article_provisioned"])
                    self.assertFalse(receipt["paper_improvement"])
                    with self.assertRaises(FileNotFoundError):
                        P.prepare(zpath, rpath, root / "absent", root / "missing-paper")
                    self.assertFalse((root / "absent").exists())

    def test_failed_write_does_not_leave_a_partial_packet(self):
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as folder:
            root = Path(folder)
            destination = root / "output"
            with patch.object(Path, "open", side_effect=OSError("generated disk failure")):
                with self.assertRaisesRegex(OSError, "generated disk failure"):
                    P.publish({"cells.json": b"[]"}, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
