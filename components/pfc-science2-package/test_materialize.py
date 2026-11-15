"""Invented asset bytes exercise the real PFC copier; no scientific code runs."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pfc_materializer", HERE / "materialize.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.environ["PFC_FIXTURE_ROOT"]) / self._testMethodName
        self.root.mkdir(parents=True)
        self.source = self.root / "source"
        self.source.mkdir()
        shutil.copytree(HERE / "task", self.source / "task")
        shutil.copyfile(HERE / "SOURCE_MANIFEST.json", self.source / "SOURCE_MANIFEST.json")
        self.assets = self.root / "assets"
        self.assets.mkdir()
        pins = {}
        for name in m.ASSETS:
            body = ("invented opaque bytes for " + name + "\n").encode()
            (self.assets / name).write_bytes(body)
            pins[name] = (len(body), hashlib.sha256(body).hexdigest())
        self.asset_patch = patch.object(m, "ASSETS", pins)
        self.asset_patch.start()
        self.addCleanup(self.asset_patch.stop)
        notices = []
        for name in m.NOTICE_NAMES:
            body = ("invented notice " + name + "\n").encode()
            (self.assets / name).write_bytes(body)
            notices.append(dict(name=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
        self.out = self.root / "tasks/life-sciences/neuroscience/pfc-conditional-reconstruction"
        self.out.parent.mkdir(parents=True)
        self.request = dict(schema="PFC_SCIENCE2_MATERIALIZE_V1", asset_root=str(self.assets),
                            output_root=str(self.out), notices=notices,
                            agent_image="ghcr.io/invented/pfc-agent@sha256:" + "a" * 64,
                            verifier_image="ghcr.io/invented/pfc-verifier@sha256:" + "b" * 64)

    def go(self, **kwargs):
        return m.materialize(self.request, source_root=self.source, **kwargs)

    def refuses_before_write(self):
        with self.assertRaises(ValueError):
            self.go()
        self.assertFalse(self.out.exists())

    def test_complete_real_source_copy_and_dockerfile_render(self):
        report = self.go()
        self.assertEqual(len(report["files"]), 28)
        self.assertEqual({r["path"] for r in report["files"]}, m.file_roster(self.out))
        for folder, image in (("environment", self.request["agent_image"]),
                              ("tests", self.request["verifier_image"])):
            body = (self.out / folder / "Dockerfile").read_text()
            self.assertTrue(body.startswith("FROM " + image + "\n"))
            self.assertNotIn("__REVIEWED_", body)
            self.assertFalse((self.out / folder / "Dockerfile.template").exists())
        self.assertFalse(report["native_harbor_validation"])
        self.assertFalse(report["image_content_platform_and_availability_verified"])
        self.assertFalse(report["author_metadata_verified"])
        self.assertFalse(report["submission_ready"])
        self.assertEqual(report["scientific_or_benchmark_count_delta"], 0)
        self.assertLess(report["managed_body_read_bytes"], 200000)

    def test_agent_context_has_no_verifier_or_oracle(self):
        self.go()
        expected = {"Dockerfile", "PACKET_SCHEMA.json"}
        expected.update("assets/" + name for name in m.ASSETS)
        expected.update("assets/notices/" + name for name in m.NOTICE_NAMES)
        self.assertEqual(m.file_roster(self.out / "environment"), expected)
        self.assertNotIn("COPY .", (self.out / "environment/Dockerfile").read_text())

    def test_separate_verifier_bakes_sources_and_shared_packet(self):
        self.go()
        self.assertIn("COPY . /tests/", (self.out / "tests/Dockerfile").read_text())
        self.assertNotIn("docker_image", (self.out / "task.toml").read_text())
        a = self.out / "environment/assets/participant-packet.json"
        b = self.out / "tests/assets/participant-packet.json"
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertNotEqual((a.stat().st_dev, a.stat().st_ino), (b.stat().st_dev, b.stat().st_ino))
        self.assertEqual(a.stat().st_nlink, 1)
        self.assertEqual(b.stat().st_nlink, 1)
        self.assertFalse((self.out / "tests/assets/category_matching.py").exists())
        for name in m.NOTICE_NAMES:
            self.assertEqual((self.out / "environment/assets/notices" / name).read_bytes(),
                             (self.out / "tests/assets/notices" / name).read_bytes())

    def test_science_oracle_and_task_contract_unchanged(self):
        self.go()
        for name in ("tests/grade.py", "tests/science/conditional_kernel.py",
                     "tests/science/continuous_analysis.py", "tests/science/endpoint_cli.py",
                     "solution/solution.py", "instruction.md", "task.toml"):
            self.assertEqual((self.out / name).read_bytes(), (HERE / "task" / name).read_bytes())
        schema = json.loads((self.out / "environment/PACKET_SCHEMA.json").read_bytes())
        self.assertIn("instruction.md", schema["output_shape"])
        self.assertNotIn("TASK.md", schema["output_shape"])
        self.assertTrue(os.access(self.out / "tests/test.sh", os.X_OK))
        self.assertTrue(os.access(self.out / "solution/solve.sh", os.X_OK))

    def test_changed_asset_refused(self):
        (self.assets / "paper.xml").write_bytes(b"replaced")
        self.refuses_before_write()

    def test_changed_notice_refused(self):
        (self.assets / "ATTRIBUTION.md").write_bytes(b"removed copyright")
        self.refuses_before_write()

    def test_extra_answer_asset_refused(self):
        (self.assets / "answers.jsonl").write_bytes(b"private answer")
        self.refuses_before_write()

    def test_missing_asset_refused(self):
        (self.assets / "LICENSE").unlink()
        self.refuses_before_write()

    def test_asset_symlink_refused(self):
        p = self.assets / "LICENSE"
        p.rename(self.root / "license-real")
        p.symlink_to(self.root / "license-real")
        self.refuses_before_write()

    def test_asset_hardlink_refused(self):
        os.link(self.assets / "LICENSE", self.root / "license-alias")
        self.refuses_before_write()

    def test_asset_root_symlink_refused(self):
        p = self.root / "assets-alias"
        p.symlink_to(self.assets, target_is_directory=True)
        self.request["asset_root"] = str(p)
        self.refuses_before_write()

    def test_mutable_image_refused(self):
        self.request["agent_image"] = "ghcr.io/invented/pfc:latest"
        self.refuses_before_write()

    def test_config_id_is_not_registry_manifest_reference(self):
        self.request["verifier_image"] = "sha256:" + "b" * 64
        self.refuses_before_write()

    def test_dockerfile_image_injection_refused(self):
        self.request["agent_image"] += "\nCOPY /private /app"
        self.refuses_before_write()

    def test_wrong_notice_order_refused(self):
        self.request["notices"].reverse()
        self.refuses_before_write()

    def test_notice_boolean_extent_refused(self):
        self.request["notices"][0]["bytes"] = True
        self.refuses_before_write()

    def test_altered_source_refused(self):
        (self.source / "task/tests/grade.py").write_bytes(b"reward=1")
        self.refuses_before_write()

    def test_source_injected_file_refused(self):
        (self.source / "task/environment/private-reference.json").write_bytes(b"answer")
        self.refuses_before_write()

    def test_changed_source_manifest_refused(self):
        (self.source / "SOURCE_MANIFEST.json").write_bytes(b"{}")
        self.refuses_before_write()

    def test_existing_output_preserved(self):
        self.out.mkdir()
        p = self.out / "prior.txt"
        p.write_bytes(b"prior result")
        with self.assertRaises(ValueError):
            self.go()
        self.assertEqual(p.read_bytes(), b"prior result")
        self.assertEqual(m.file_roster(self.out), {"prior.txt"})

    def test_wrong_taxonomy_refused(self):
        self.request["output_root"] = str(self.out.parent / "another-task")
        self.refuses_before_write()

    def test_read_allowance_refuses_before_materialization(self):
        with self.assertRaisesRegex(ValueError, "managed read allowance"):
            self.go(reader=m.Reads(maximum=100))
        self.assertFalse(self.out.exists())

    def test_output_corruption_refuses_and_retains_partial_files(self):
        out = self.out
        class CorruptingReads(m.Reads):
            def read(self, path, limit, expected=None):
                p = Path(path)
                if out in p.parents and p.name == "grade.py":
                    p.write_bytes(b"changed after write")
                return super().read(p, limit, expected)
        with self.assertRaises(ValueError):
            self.go(reader=CorruptingReads())
        self.assertTrue(self.out.exists())
        self.assertEqual((self.out / "tests/grade.py").read_bytes(), b"changed after write")

    def test_json_duplicate_keys_and_utf16_refused(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            m.decode(b'{"asset_root":"a","asset_root":"b"}')
        with self.assertRaises(UnicodeError):
            m.decode('{"schema":"x"}'.encode("utf-16"))

    def test_unbounded_empty_directory_tree_refused(self):
        for i in range(129):
            (self.assets / ("empty%03d" % i)).mkdir()
        self.refuses_before_write()


if __name__ == "__main__":
    unittest.main(verbosity=2)
