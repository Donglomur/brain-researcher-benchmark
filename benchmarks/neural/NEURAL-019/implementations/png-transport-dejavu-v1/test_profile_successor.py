"""Generated DejaVu profile controls; no authentic data, files or model calls."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("n019_dejavu_preflight", HERE / "runtime_preflight.py")
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)
ARGS = None
TEMP_BYTES = 0


def write_temp(path, raw):
    global TEMP_BYTES
    if TEMP_BYTES + len(raw) > 32768:
        raise AssertionError("generated temporary cumulative quota")
    with Path(path).open("xb") as handle:
        handle.write(raw)
    TEMP_BYTES += len(raw)
    return Path(path)


def generated():
    page = np.arange(140 * 137, dtype=np.uint16).reshape(140, 137)
    page[-1, -1] = 65535
    velocity = np.zeros((1340, 140, 2), dtype=np.float64)
    velocity[:, :, 0] = np.arange(140) / 8 - 9
    velocity[:, :, 1] = -np.arange(140) / 16
    velocity[0, 0] = [-np.finfo(np.float64).max, np.finfo(np.float64).tiny]
    velocity[-1, -1] = [-0.125, 0.0625]
    groups = np.arange(1340, dtype=np.int64) % 28
    return dict(train_counts=np.broadcast_to(page, (1340, 140, 137)),
                assessment_counts=np.broadcast_to(page, (126, 140, 137)), train_velocity=velocity,
                train_trial_ids=np.asarray([f"generated-train-{i}" for i in range(1340)]),
                assessment_trial_ids=np.asarray([f"generated-query-{i}" for i in range(126)]),
                neural_unit_ids=np.asarray([f"generated-unit-{i}" for i in range(137)]),
                train_group_ids=groups, train_cv_fold_ids=groups % 4,
                neural_left_edges_ms=np.arange(-250, 450, 5), velocity_left_edges_ms=np.arange(-150, 550, 5),
                velocity_axes=np.asarray(["x", "y"]), velocity_units=np.asarray("m/s"),
                panel_fingerprint=np.asarray("a" * 64))


def request(role="assessment", trial=125, u0=121, u1=137, b0=120, b1=140):
    return dict(action="view", role=role, trial=trial, unit_start=u0, unit_stop=u1,
                bin_start=b0, bin_stop=b1)


class ProfileControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = pf.load_selected(HERE / "PACKAGE.json", ARGS.manifest_sha256, ARGS.viewer)
        cls.p, cls.viewer, cls.renderer = cls.package.transport, cls.package.viewer, cls.package.renderer
        cls.data = generated()

    def session(self, actions=500):
        return self.viewer.Session(self.data, max_actions=actions)

    def transport(self, session, now=None):
        now = [0.0] if now is None else now
        return self.p.Transport(session, self.renderer, session_id="a" * 64,
                                max_frames=500, deadline=100, clock=lambda: now[0])

    def frame(self, transport, action):
        return self.p.encode(dict(session="a" * 64, sequence=transport._sequence, request=action))

    def test_selected_loader_binds_frames_and_complete_collector(self):
        transport = self.transport(self.session())
        response = json.loads(transport.exchange(self.frame(transport, request())))
        self.assertEqual(response["response"]["kind"], "image")
        event = transport.events()[0]["render"]
        binding = dict(self.package.binding)
        self.assertEqual(event["font_profile"]["package_binding"], binding)
        self.assertTrue(event["font_profile"]["selected_package"])
        self.assertEqual(event["font_profile"]["profile_id"], pf.PROFILE_ID)
        identity = {k: event[k] for k in ("profile_identity_sha256", "svg_sha256", "png_sha256")}
        self.assertEqual(event["stimulus_identity_sha256"], pf.sha(pf.json_bytes(identity)))
        wanted = np.empty((126, 140, 2), dtype=np.float64)
        for trial in range(126):
            wanted[trial, :, 0] = trial - 63.5
            wanted[trial, :, 1] = -np.arange(140) / 8
            action = dict(action="answer", trial=trial, velocity=wanted[trial].tolist())
            transport.exchange(self.frame(transport, action))
        transport.exchange(self.frame(transport, dict(action="finish")))
        values, receipt = transport.export()
        np.testing.assert_array_equal(values["velocity"], wanted)
        self.assertEqual(set(values), {"velocity", "trial_ids", "velocity_left_edges_ms",
                                      "velocity_axes", "velocity_units", "panel_fingerprint"})
        np.testing.assert_array_equal(values["trial_ids"], self.data["assessment_trial_ids"])
        self.assertEqual(receipt["font_profile"]["package_binding"], binding)
        self.assertFalse(receipt["scientific_mode_selected"])
        self.assertFalse(receipt["perceptual_readability_qualified"])

    def test_all_units_bins_two_roles_geometry_and_tokens(self):
        session = self.session()
        ns = "{http://www.w3.org/2000/svg}"
        for role, trial in (("assessment", 125), ("calibration", 1339)):
            seen = set()
            for u0 in range(0, 137, 16):
                for b0 in range(0, 140, 20):
                    u1, b1 = min(137, u0 + 16), min(140, b0 + 20)
                    result = session.dispatch(self.p.encode(request(role, trial, u0, u1, b0, b1)))
                    root = ET.fromstring(result["svg"])
                    cells = [node for node in root.iter(ns + "text") if "data-unit" in node.attrib]
                    self.assertEqual(len(cells), (u1-u0)*(b1-b0))
                    for node in cells:
                        u, b = int(node.attrib["data-unit"]), int(node.attrib["data-bin"])
                        self.assertNotIn((u, b), seen)
                        seen.add((u, b))
                        self.assertEqual((int(node.attrib["x"]), int(node.attrib["y"])),
                                         (93 + (b-b0)*54, 112 + (u-u0)*24))
                        field = "train_counts" if role == "calibration" else "assessment_counts"
                        self.assertEqual(int(node.text), int(self.data[field][trial, b, u]))
                    calibration = [node for node in root.iter(ns + "text")
                                   if "data-calibration-bin" in node.attrib]
                    self.assertEqual(len(calibration), b1-b0 if role == "calibration" else 0)
                    for node in calibration:
                        b = int(node.attrib["data-calibration-bin"])
                        expected = f"{-150+5*b} | {repr(float(self.data['train_velocity'][trial,b,0]))} | {repr(float(self.data['train_velocity'][trial,b,1]))}"
                        self.assertEqual(node.text, expected)
                    png, record = self.renderer.render(result)
                    self.assertEqual(record["svg_sha256"], self.p.pin(result["svg"].encode()))
                    self.assertEqual(record["png_sha256"], self.p.pin(png))
                    self.assertEqual(record["count_cells"], len(cells))
                    self.assertLessEqual(len(png), 262144)
            self.assertEqual(seen, {(u, b) for u in range(137) for b in range(140)})
        self.assertEqual(len(set(self.data["train_group_ids"].tolist())), 28)
        # Eight assessment maze groups are protocol metadata only: no private group labels enter.
        self.assertNotIn("assessment_group_ids", self.data)

    def test_boundary_trials_extremes_glyphs_and_refusals(self):
        session = self.session()
        for role, trial in (("calibration", 0), ("calibration", 1339), ("assessment", 0), ("assessment", 125)):
            for bounds in ((0, 1, 0, 1), (121, 137, 120, 140)):
                result = session.dispatch(self.p.encode(request(role, trial, *bounds)))
                _, record = self.renderer.render(result)
                self.assertFalse(record["authentic_readability_qualified"])
        result = session.dispatch(self.p.encode(request("calibration", 0, 0, 1, 0, 1)))
        self.assertIn("-1.7976931348623157e+308", result["svg"])
        self.assertIn("2.2250738585072014e-308", result["svg"])
        for replacement in ("Training group " + "W" * 64 + ";", "Training group Ω;"):
            bad = dict(result, svg=result["svg"].replace("Training group 0;", replacement))
            with self.assertRaises(ValueError):
                self.renderer.render(bad)
        font = self.renderer._font
        missing = bytes(font.getmask("\U0010ffff"))
        self.assertTrue(all(bytes(font.getmask(chr(c))) != missing and font.getmask(chr(c)).getbbox()
                            for c in range(33, 127)))
        self.assertEqual(len({(font.getmask(str(n)).size, bytes(font.getmask(str(n)))) for n in range(10)}), 10)

    def test_missing_wrong_stale_manifest_refuses_before_execution(self):
        for digest in (None, "", "z"*64, "0"*64):
            with self.subTest(digest=digest), mock.patch.object(pf, "compile_module") as execute:
                with self.assertRaises((ValueError, TypeError)):
                    pf.load_selected(HERE / "PACKAGE.json", digest, ARGS.viewer)
                execute.assert_not_called()
        with tempfile.TemporaryDirectory(dir=ARGS.temp_root) as name:
            changed = write_temp(Path(name)/"PACKAGE.json", (HERE/"PACKAGE.json").read_bytes()+b" ")
            with mock.patch.object(pf, "compile_module") as execute:
                with self.assertRaises(ValueError):
                    pf.load_selected(changed, ARGS.manifest_sha256, ARGS.viewer)
                execute.assert_not_called()

    def test_changed_component_profile_font_notice_refuse_before_execution(self):
        original_read = pf.read_bounded
        with tempfile.TemporaryDirectory(dir=ARGS.temp_root) as name:
            corrupt = write_temp(Path(name)/"corrupt", b"changed\n")
            for target in ("png_transport.py", "runtime_preflight.py", "PROFILE.json",
                           "assets/DejaVuSansMono.ttf", "assets/LICENSE_DEJAVU"):
                target_path = (HERE/target).absolute()
                def redirected(path, *args, **kwargs):
                    return original_read(corrupt if Path(path).absolute() == target_path else path, *args, **kwargs)
                with self.subTest(target=target), mock.patch.object(pf, "read_bounded", side_effect=redirected), mock.patch.object(pf, "compile_module") as execute:
                    with self.assertRaises(ValueError):
                        pf.load_selected(HERE/"PACKAGE.json", ARGS.manifest_sha256, ARGS.viewer)
                    execute.assert_not_called()
            # The bounded reader also refuses equal-extent content changes and symlinks.
            original = write_temp(Path(name)/"original", b"abcdefgh")
            with self.assertRaises(ValueError):
                original_read(corrupt, 8, identity=[8, pf.sha(original.read_bytes())])
            link = Path(name)/"link"
            link.symlink_to(original)
            with self.assertRaises(OSError):
                original_read(link, 8)

    def test_selected_inventory_profile_and_wrong_viewer_refuse(self):
        original = json.loads((HERE/"PACKAGE.json").read_text())
        variants = []
        added = copy.deepcopy(original); added["files"]["arbitrary.py"] = [1, "a"*64]; variants.append(added)
        changed = copy.deepcopy(original); changed["profile_id"] = "monaco"; variants.append(changed)
        changed = copy.deepcopy(original); changed["files"]["assets/LICENSE_DEJAVU"][1] = "b"*64; variants.append(changed)
        with tempfile.TemporaryDirectory(dir=ARGS.temp_root) as name:
            for i, variant in enumerate(variants):
                raw = pf.json_bytes(variant)
                path = write_temp(Path(name)/f"manifest-{i}.json", raw)
                with mock.patch.object(pf, "compile_module") as execute:
                    with self.assertRaises(ValueError):
                        pf.load_selected(path, pf.sha(raw), ARGS.viewer)
                    execute.assert_not_called()
        with mock.patch.object(pf, "compile_module") as execute:
            with self.assertRaises(ValueError):
                pf.load_selected(HERE/"PACKAGE.json", ARGS.manifest_sha256, HERE/"png_transport.py")
            execute.assert_not_called()

    def test_low_level_calls_cannot_inherit_selected_lineage(self):
        spec = importlib.util.spec_from_file_location("n019_dejavu_unselected_control", HERE/"png_transport.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        renderer = module.Renderer((HERE/"assets/DejaVuSansMono.ttf").read_bytes())
        self.assertFalse(renderer.profile["selected_package"])
        self.assertIsNone(renderer.profile["package_binding"])
        self.assertTrue(self.renderer.profile["selected_package"])
        self.assertNotEqual(renderer.profile["profile_identity_sha256"], self.renderer.profile["profile_identity_sha256"])

    def test_freetype_reference_is_observation_not_universal_gate(self):
        versions = dict(pf.REFERENCE_RUNTIME, freetype="different-generated-software-version")
        with mock.patch.object(pf, "renderer_versions", return_value=versions):
            observed = pf.observation(self.package.binding)
        self.assertEqual(observed["status"], "renderer_prerequisites_observed")
        self.assertFalse(observed["reference_runtime_matches"])
        self.assertFalse(observed["runtime_admitted"])
        for field, value in (("pillow", "11.1.0"), ("numpy_distribution_version", None)):
            with mock.patch.object(pf, "renderer_versions", return_value=dict(pf.REFERENCE_RUNTIME, **{field:value})):
                self.assertEqual(pf.observation(self.package.binding)["status"], "held")

    def test_selected_source_final_frame_and_export_deadlines(self):
        class Collector:
            def receipt(self): return {"actions":0,"answered":0,"closed":False}
            def dispatch(self, raw): return {"kind":"answer_committed","trial":0,"answered":1}
            def submission(self): return {"generated_sentinel":True}
        for boundary in ("response", "delivered"):
            now = [0.0]; transport = self.transport(Collector(), now)
            raw = self.frame(transport, {"action":"answer"}); original = self.p.encode
            def slow(value):
                encoded = original(value)
                if (boundary == "response" and "response" in value) or value.get("status") == boundary:
                    now[0] = 101
                return encoded
            with mock.patch.object(self.p, "encode", side_effect=slow):
                with self.assertRaises(ValueError): transport.exchange(raw)
            self.assertTrue(transport.receipt()["invalidated"])
            self.assertEqual([e["status"] for e in transport.events()], ["refused"])
        now = [0.0]; transport = self.transport(Collector(), now)
        transport._events.append({"status":"delivered","collection_complete":True})
        original_receipt = transport.receipt
        def slow_receipt():
            value = original_receipt(); now[0] = 101; return value
        with mock.patch.object(transport, "receipt", side_effect=slow_receipt):
            with self.assertRaises(ValueError): transport.export()
        self.assertTrue(transport._invalidated)

    def test_stdlib_verify_only_cli_does_not_require_optional_imports(self):
        command = [sys.executable, "-I", "-S", "-B", str(HERE/"runtime_preflight.py"),
                   "--manifest-sha256", ARGS.manifest_sha256, "--viewer", str(ARGS.viewer), "--verify-only"]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr[:512])
        self.assertLess(len(result.stdout) + len(result.stderr), 4096)
        value = json.loads(result.stdout)
        self.assertEqual(value["status"], "selected_package_bytes_verified")
        self.assertFalse(value["renderer_constructed"])
        self.assertNotIn("observed_runtime", value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--viewer", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    ARGS = parser.parse_args()
    ARGS.temp_root.mkdir(exist_ok=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProfileControls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"generated_only": True, "controls": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors),
                      "skips": len(result.skipped), "temp_bytes_cumulative": TEMP_BYTES,
                      "png_files_written": 0, "profile_id": pf.PROFILE_ID}, sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
