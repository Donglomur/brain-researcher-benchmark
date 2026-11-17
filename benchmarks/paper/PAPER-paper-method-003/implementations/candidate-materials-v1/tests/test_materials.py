"""Generated controls; the full source-shaped cohort is not authentic EEG."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("reve_materials", Path(__file__).resolve().parents[1] / "materials.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def npy_bytes(value=0.0, *, shape=(1, 64, 800), descr="<f8", fortran=False):
    header = repr({"descr": descr, "fortran_order": fortran, "shape": shape}).encode("latin1")
    header += b" " * ((-len(header) - 11) % 64) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + struct.pack("<d", value) * math.prod(shape)


PAYLOAD = npy_bytes(1.25)


def fixture():
    records, targets = [], []
    for person in range(1, 110):
        for run in m.RUNS:
            eid = f"S{person:03d}R{run:02d}-event001"
            split = m.split_for(person)
            records.append({"participant": person, "run": run, "split": split,
                            "signal": f"S{person:03d}R{run:02d}.npy", "shape": [1, 64, 800],
                            "event_ids": [eid], "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
                            "operator_private": "never-copy-this"})
            targets.append({"participant": person, "run": run, "split": split,
                            "event_id": eid, "label": person % 2 + (0 if run in (4, 8, 12) else 2),
                            "onset_sample_200hz": 1234})
    panel = {"schema": "reve-original-physionet-inputs-v1", "source_commit": m.SOURCE_COMMIT,
             "profile": m.PROFILE, "source_identity": "a" * 64, "units": "uV", "dtype": "float64",
             "sampling_hz": 200, "channels": m.CHANNELS, "historical_recipe_verified": False,
             "records": records, "counts": {"train": 420, "val": 114, "test": 120},
             "observed_epoch_count": 654, "published_epoch_count": 9837,
             "published_epoch_count_matches": False, "targets_identity": m.identity(targets)}
    panel["panel_identity"] = m.identity(panel)
    return panel, {"panel_identity": panel["panel_identity"], "targets": targets}


def repin(panel, target_doc=None):
    if target_doc is not None:
        panel["targets_identity"] = m.identity(target_doc["targets"])
    panel.pop("panel_identity", None)
    panel["panel_identity"] = m.identity(panel)
    if target_doc is not None:
        target_doc["panel_identity"] = panel["panel_identity"]


class MetadataControls(unittest.TestCase):
    def setUp(self):
        self.panel, self.targets = fixture()

    def test_complete_roster_and_label_projection(self):
        m.validate_panel(self.panel)
        labels = m.project_targets(self.panel, self.targets)
        self.assertEqual(len(labels), 534)
        self.assertTrue(all(int(eid[1:4]) <= 89 for eid in labels))

    def test_access_conditions_have_identical_data(self):
        labels = m.project_targets(self.panel, self.targets)
        a = m.make_manifest(self.panel, labels, "paper_data")
        b = m.make_manifest(self.panel, labels, "paper_data_code")
        self.assertEqual(a["data"], b["data"])
        self.assertEqual(a["data_identity"], b["data_identity"])
        self.assertNotEqual(a["materials_identity"], b["materials_identity"])
        self.assertIsNone(a["official_code"])
        self.assertEqual(b["official_code"]["sha256"], m.CODE_SHA256)
        self.assertEqual(a["paper"], b["paper"])

    def test_private_fields_and_test_labels_are_not_forwarded(self):
        labels = m.project_targets(self.panel, self.targets)
        manifest = m.make_manifest(self.panel, labels, "paper_data")
        self.assertNotIn("never-copy-this", json.dumps(manifest))
        self.assertNotIn("targets_identity", manifest)
        for row in manifest["data"]["records"]:
            self.assertEqual("labels" in row, row["split"] != "test")
            self.assertNotIn("operator_private", row)

    def test_missing_record(self):
        self.panel["records"].pop()
        repin(self.panel)
        with self.assertRaises(m.MaterialError):
            m.validate_panel(self.panel)

    def test_changed_person_split(self):
        self.panel["records"][420]["split"] = "train"
        repin(self.panel)
        with self.assertRaises(m.MaterialError):
            m.validate_panel(self.panel)

    def test_altered_profile(self):
        self.panel["profile"] = "paper128"
        repin(self.panel)
        with self.assertRaises(m.MaterialError):
            m.validate_panel(self.panel)

    def test_unbound_historical_promotion(self):
        self.panel["historical_recipe_verified"] = True
        repin(self.panel)
        with self.assertRaises(m.MaterialError):
            m.validate_panel(self.panel)

    def test_cross_record_event_id(self):
        self.panel["records"][0]["event_ids"] = ["S109R14-event001"]
        repin(self.panel)
        with self.assertRaises(m.MaterialError):
            m.validate_panel(self.panel)

    def test_signal_path_escape(self):
        self.panel["records"][0]["signal"] = "../operator/targets.json"
        repin(self.panel)
        with self.assertRaises(m.MaterialError):
            m.validate_panel(self.panel)

    def test_target_duplicate_after_repin(self):
        self.targets["targets"][-1] = self.targets["targets"][0]
        repin(self.panel, self.targets)
        with self.assertRaises(m.MaterialError):
            m.project_targets(self.panel, self.targets)

    def test_target_label_run_semantics(self):
        self.targets["targets"][0]["label"] = 3
        repin(self.panel, self.targets)
        with self.assertRaises(m.MaterialError):
            m.project_targets(self.panel, self.targets)

    def test_target_boolean_label(self):
        self.targets["targets"][0]["label"] = True
        repin(self.panel, self.targets)
        with self.assertRaises(m.MaterialError):
            m.project_targets(self.panel, self.targets)

    def test_count_mismatch_remains_visible(self):
        labels = m.project_targets(self.panel, self.targets)
        result = m.make_manifest(self.panel, labels, "paper_data")
        self.assertEqual(result["observed_epoch_count"], 654)
        self.assertEqual(result["published_epoch_count"], 9837)
        self.assertFalse(result["published_epoch_count_matches"])
        self.assertFalse(result["scientific_qualification"])

    def test_pinned_official_sources_are_not_fixture_values(self):
        self.assertEqual(m.PAPER_SHA256, "83cbe94dc11b77ea7fd4f1fe46bc896cd25e71eba99b5e449325f794d7d63973")
        self.assertEqual(m.CODE_SHA256, "687d7c5d3d45f8351d524c9ace8a8fb970b04324fbece4fc97072f7495622ed7")
        self.assertEqual((m.PAPER_BYTES, m.CODE_BYTES), (2717915, 259040))
        self.assertEqual(m.POSITIONS_SHA256, "f62ca8d7dd4b88e1422ea17348440a41ed0b73b9ff7d12c3b1229492c9b448a5")
        self.assertEqual(m.POSITIONS_BYTES, 59729)

    def test_same_complete_geometry_for_both_conditions(self):
        labels = m.project_targets(self.panel, self.targets)
        a = m.make_manifest(self.panel, labels, "paper_data")
        b = m.make_manifest(self.panel, labels, "paper_data_code")
        self.assertEqual(a["data"]["geometry"], b["data"]["geometry"])
        self.assertEqual(len(a["data"]["geometry"]["electrodes_in_signal_channel_order"]), 64)
        aliases = dict(zip(m.CHANNELS, m.ELECTRODES))
        self.assertEqual([aliases[k] for k in ("T7..", "T8..", "P7..", "P8..")], ["T3", "T4", "T5", "T6"])


class FileControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="reve-small-")
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.npy"
        self.output = self.root / "out.npy"
        self.source.write_bytes(PAYLOAD)
        self.row = {"shape": [1, 64, 800], "sha256": hashlib.sha256(PAYLOAD).hexdigest()}

    def tearDown(self):
        self.tmp.cleanup()

    def test_streamed_copy_exact_values_and_public_mode_under_private_umask(self):
        old = os.umask(0o077)
        try:
            self.assertEqual(m.copy_signal(self.source, self.output, self.row), len(PAYLOAD))
        finally:
            os.umask(old)
        self.assertEqual(self.output.read_bytes(), PAYLOAD)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o444)

    def test_nonfinite_signal_rejected(self):
        body = npy_bytes(float("nan"))
        self.source.write_bytes(body)
        self.row["sha256"] = hashlib.sha256(body).hexdigest()
        with self.assertRaisesRegex(m.MaterialError, "nonfinite"):
            m.copy_signal(self.source, self.output, self.row)

    def test_truncated_signal_rejected(self):
        self.source.write_bytes(PAYLOAD[:-8])
        with self.assertRaisesRegex(m.MaterialError, "payload length"):
            m.copy_signal(self.source, self.output, self.row)

    def test_digest_mismatch(self):
        self.row["sha256"] = "0" * 64
        with self.assertRaisesRegex(m.MaterialError, "digest mismatch"):
            m.copy_signal(self.source, self.output, self.row)

    def test_header_shape_mismatch(self):
        self.row["shape"] = [2, 64, 800]
        with self.assertRaisesRegex(m.MaterialError, "header differs"):
            m.copy_signal(self.source, self.output, self.row)

    def test_object_dtype_rejected(self):
        self.source.write_bytes(npy_bytes(descr="|O"))
        with self.assertRaisesRegex(m.MaterialError, "header differs"):
            m.copy_signal(self.source, self.output, self.row)

    def test_fortran_order_rejected(self):
        self.source.write_bytes(npy_bytes(fortran=True))
        with self.assertRaisesRegex(m.MaterialError, "header differs"):
            m.copy_signal(self.source, self.output, self.row)

    def test_signal_symlink_rejected(self):
        alias = self.root / "alias.npy"
        alias.symlink_to(self.source)
        with self.assertRaises(m.MaterialError):
            m.copy_signal(alias, self.output, self.row)

    def test_hardlink_alias_rejected(self):
        os.link(self.source, self.root / "alias.npy")
        with self.assertRaisesRegex(m.MaterialError, "hardlink"):
            m.copy_signal(self.source, self.output, self.row)

    def test_nonfinite_and_duplicate_json_rejected(self):
        for body in (b'{"x":NaN}', b'{"x":1,"x":2}'):
            self.source.write_bytes(body)
            with self.assertRaises(m.MaterialError):
                m.read_json(self.source)

    def test_wrong_pinned_document(self):
        with self.assertRaisesRegex(m.MaterialError, "digest differs"):
            m._copy_blob(self.source, self.output, "0" * 64, len(PAYLOAD))


class PublicationControls(unittest.TestCase):
    def test_publish_finalizes_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir(mode=0o700)
            (stage / "proof").write_bytes(b"complete")
            output = root / "published"
            m.publish(stage, output)
            self.assertFalse(stage.exists())
            self.assertEqual((output / "proof").read_bytes(), b"complete")
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o555)
            os.chmod(output, 0o700)

    def test_finalize_failure_removes_only_owned_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir(mode=0o700)
            (stage / "proof").write_bytes(b"complete")
            other = root / "unrelated"
            other.write_bytes(b"preserve")
            output = root / "published"
            real_chmod = os.chmod
            def fail_once(path, mode):
                if Path(path) == output and mode == 0o555:
                    raise PermissionError("generated finalization failure")
                return real_chmod(path, mode)
            with patch.object(m.os, "chmod", side_effect=fail_once):
                with self.assertRaisesRegex(PermissionError, "generated finalization"):
                    m.publish(stage, output)
            self.assertFalse(stage.exists())
            self.assertFalse(output.exists())
            self.assertEqual(other.read_bytes(), b"preserve")

    def test_cleanup_refuses_replacement_inode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir(mode=0o700)
            (stage / "proof").write_bytes(b"preserve")
            info = stage.stat()
            self.assertFalse(m.discard_owned_tree(stage, (info.st_dev, info.st_ino + 1)))
            self.assertEqual((stage / "proof").read_bytes(), b"preserve")


class FullCohortControl(unittest.TestCase):
    def test_full654_export_and_failure_cleanup(self):
        fixture_parent = os.environ.get("REVE_FIXTURE_ROOT")
        with tempfile.TemporaryDirectory(prefix="reve-full654-", dir=fixture_parent) as temporary:
            root = Path(temporary)
            source = root / "inputs"
            source.mkdir()
            panel, targets = fixture()
            generated_bytes = 0
            for row in panel["records"]:
                (source / row["signal"]).write_bytes(PAYLOAD)
                generated_bytes += len(PAYLOAD)
            p = source / "panel.json"
            t = root / "operator-targets.json"
            p.write_bytes(m.canonical(panel))
            t.write_bytes(m.canonical(targets))
            paper, code = root / "fixture-paper", root / "fixture-code"
            positions = root / "fixture-positions.json"
            paper.write_bytes(b"generated PDF stand-in; no scientific source claim")
            code.write_bytes(b"generated archive stand-in; no author code claim")
            geometry = {name: [0.1, 0.2, 0.3] for name in m.ELECTRODES}
            geometry.update({f"fixture{number}": [0.0, 0.0, 0.0] for number in range(543 - len(geometry))})
            positions.write_bytes(m.canonical(geometry))
            generated_bytes += p.stat().st_size + t.stat().st_size + paper.stat().st_size + code.stat().st_size + positions.stat().st_size
            replacements = {"PAPER_BYTES": paper.stat().st_size, "PAPER_SHA256": hashlib.sha256(paper.read_bytes()).hexdigest(),
                            "CODE_BYTES": code.stat().st_size, "CODE_SHA256": hashlib.sha256(code.read_bytes()).hexdigest(),
                            "POSITIONS_BYTES": positions.stat().st_size, "POSITIONS_SHA256": hashlib.sha256(positions.read_bytes()).hexdigest()}
            output = root / "participant"
            with patch.multiple(m, **replacements):
                old = os.umask(0o077)
                try:
                    result = m.export(p, t, paper, output, condition="paper_data_code", code_archive=code,
                                      expected_panel_identity=panel["panel_identity"], positions_path=positions, max_bytes=512 * 1024**2)
                finally:
                    os.umask(old)
                generated_bytes += result["created_bytes"]
                manifest = json.loads((output / "materials.json").read_bytes())
                self.assertEqual(result["recordings"], 654)
                self.assertEqual(result["participants"], 109)
                self.assertEqual(result["labelled_epochs"], 534)
                self.assertFalse(result["test_labels_delivered"])
                self.assertEqual(len(list((output / "signals").iterdir())), 654)
                self.assertEqual(len(list(output.iterdir())), 5)
                self.assertEqual(sum("labels" in r for r in manifest["data"]["records"]), 534)
                self.assertEqual(result["files"], 658)
                self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o555)
                self.assertEqual(stat.S_IMODE((output / "signals").stat().st_mode), 0o555)
                self.assertTrue(all(stat.S_IMODE(f.stat().st_mode) == 0o444 for f in (output / "signals").iterdir()))
                expected_manifest = m.make_manifest(panel, m.project_targets(panel, targets), "paper_data")
                self.assertEqual(manifest["data_identity"], expected_manifest["data_identity"])
                self.assertIsNone(expected_manifest["official_code"])
                self.assertNotIn("never-copy-this", (output / "materials.json").read_text())
                self.assertFalse(any("labels" in r for r in manifest["data"]["records"] if r["split"] == "test"))
                for row in panel["records"]:
                    published = output / "signals" / row["signal"]
                    self.assertEqual(hashlib.sha256(published.read_bytes()).hexdigest(), row["sha256"])
                    self.assertNotEqual(published.stat().st_ino, (source / row["signal"]).stat().st_ino)
                with self.assertRaisesRegex(m.MaterialError, "fresh output"):
                    m.export(p, t, paper, output, condition="paper_data", expected_panel_identity=panel["panel_identity"], positions_path=positions)
                with self.assertRaisesRegex(m.MaterialError, "selected operator identity"):
                    m.export(p, t, paper, root / "wrong", condition="paper_data", expected_panel_identity="0" * 64, positions_path=positions)
                with self.assertRaisesRegex(m.MaterialError, "insufficient"):
                    m.export(p, t, paper, root / "small", condition="paper_data", expected_panel_identity=panel["panel_identity"], positions_path=positions, max_bytes=100)
                # A real first-shard hash failure removes the partially copied tree.
                panel["records"][0]["sha256"] = "0" * 64
                repin(panel, targets)
                p.write_bytes(m.canonical(panel))
                t.write_bytes(m.canonical(targets))
                generated_bytes += p.stat().st_size + t.stat().st_size
                with self.assertRaisesRegex(m.MaterialError, "digest mismatch"):
                    m.export(p, t, paper, root / "failure", condition="paper_data", expected_panel_identity=panel["panel_identity"], positions_path=positions)
                generated_bytes += paper.stat().st_size + positions.stat().st_size + len(PAYLOAD)
                self.assertFalse((root / "failure").exists())
                self.assertFalse(list(root.glob(".reve-materials-*")))
            for directory, _dirs, _files in os.walk(output):
                os.chmod(directory, 0o700)
            print(json.dumps({"fixture_scope": "one generated epoch in each original654record; not authentic9837panel",
                              "known_created_and_reclaimed_bytes": generated_bytes,
                              "copy": "complete code-assisted export plus early first-shard refusal",
                              "authentic_data_or_model_calls": 0}))


if __name__ == "__main__":
    unittest.main()
