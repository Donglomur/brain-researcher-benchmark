"""Generated software controls; no NWB, clinical decision or patient is real."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "registered-runtime" / "runtime" / "source"
sys.path.insert(0, str(SOURCE))
from core import Budget, Refusal, pin
from epoch_io import load_epoch
from schema import AUTHOR_REVISION, DATASET


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


repaired = module("n041_modality_retention_v2", HERE / "preparation.py")
predecessor = module("n041_registered_preparation", SOURCE / "preparation.py")


class GeneratedNative:
    """Minimal source-interface double; run(), review, ZIP and IO stay real."""

    starting_time = 0.0
    include_lfp = True
    probe = 7.5

    def __init__(self, path, expected, budget, limits):
        self.index = int(Path(path).stem.split("-")[-1])
        self.expected = expected
        self.lfp = np.arange(1000, dtype=float).reshape(1000, 1)
        self.trains = np.array([5.0, 5.25, 7.499, 7.5])
        self.file = {"units": {}}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def object(self, name, kind="dataset"):
        if name == "acquisition":
            return {"LFPs": {}} if self.include_lfp else {}
        if name == "acquisition/LFPs":
            return {"channel_conversion": True}
        if name == "acquisition/LFPs/data":
            class Data:
                ndim = 2
                shape = (1000, 1)
                attrs = {"conversion": 1e-6, "offset": 1e-5}
            return Data()
        if name == "units":
            return {"electrodes_index": True}
        if name == "units/spike_times":
            return self.trains
        if name == "general/extracellular_ephys/electrodes/location":
            return np.array(["hippocampus_left"])
        raise AssertionError("unexpected source object: " + name)

    def read(self, name, index=Ellipsis, **kwargs):
        fields = {
            "general/subject/subject_id": "generated-patient-" + str(self.index % 36),
            "general/session_id": "generated-session-" + str(self.index),
            "acquisition/LFPs/starting_time": np.float64(self.starting_time),
            "acquisition/LFPs/channel_conversion": np.array([2.0]),
            "acquisition/LFPs/data": self.lfp,
            "intervals/trials/loads": np.array([1] * 70 + [3] * 70),
            "intervals/trials/timestamps_Maintenance": np.full(140, 5.0),
            "intervals/trials/timestamps_Probe": np.full(140, self.probe),
            "units/spike_times_index": np.array([len(self.trains)]),
            "units/spike_times": self.trains,
            "units/electrodes": np.array([0]),
            "units/electrodes_index": np.array([1]),
            "acquisition/LFPs/electrodes": np.array([0]),
            "general/extracellular_ephys/electrodes/location": np.array(["hippocampus_left"]),
        }
        value = fields[name]
        if isinstance(value, str):
            return value
        result = value[index]
        if kwargs.get("text"):
            return str(result)
        return result

    def attribute(self, name, key, **kwargs):
        return {"rate": 400.0, "unit": "volts", "conversion": 1e-6, "offset": 1e-5}[key]

    def record(self):
        return {"generated_fixture_only": True, "source": self.expected}


def inputs(*, retain_lfp=False, include_lfp=True, global_excluded=False,
           no_modality=False):
    assets = []
    sessions = []
    regions = sorted(set(repaired.AREA.values()))
    for i in range(44):
        asset = {"asset_id": "generated-asset-" + str(i),
                 "patient_id": "generated-patient-" + str(i % 36),
                 "session_id": "generated-session-" + str(i),
                 "path": "generated-" + str(i) + ".nwb",
                 "pin": pin(b"generated source interface only")}
        assets.append(asset)
        element = {"row0": 0, "electrode_row0": 0, "bundle": "generated-bundle",
                   "eligible": True, "region": "Hippo", "reason": "",
                   "bad_trial_rows0": []}
        lfp = dict(element, bad_trial_rows0=[] if retain_lfp else list(range(140)))
        unit = dict(element, bad_trial_rows0=list(range(140)) if no_modality else [])
        sessions.append({
            "asset_id": asset["asset_id"], "source_session_id": asset["session_id"],
            "source_pin": asset["pin"],
            "preprocessing": dict.fromkeys(("bundle_spike_interpolation", "local_reference",
                "lowpass_175Hz", "downsample_400Hz", "notch_60_120Hz"), True),
            "lfp": [lfp] if include_lfp else [], "units": [unit],
            "trials": [{"row0": j, "eligible": j in (0, 70) and not global_excluded,
                        "reason": "" if j in (0, 70) and not global_excluded
                        else "generated global artifact decision"} for j in range(140)],
            "evidence": "generated control, never a scientific review",
            "eligibility_basis": "clinical_and_signal_artifact_only_blind_to_load_correctness_order",
            "clock_evidence": dict.fromkeys(("trial_seconds", "spike_seconds", "lfp_start_seconds",
                                            "upstream_temporal_support_reviewed"), True),
        })
    roster = {"schema": "n041_roster_v1", "dataset": DATASET, "assets": assets,
              "provenance": "generated software-control roster"}
    review = {"schema": "n041_clinical_review_v1", "dataset": DATASET,
              "author_revision": AUTHOR_REVISION, "regions": regions,
              "sessions": sessions, "provenance": "generated software-control decisions"}
    return roster, review


class ModalityRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="n041-generated-",
                                                dir=os.environ.get("N041_TEST_ROOT"))
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)
        self.limit = {"native": {}, "session_spikes": 100, "epoch_bytes": 32768}

    def run_preparation(self, implementation=repaired, *, starting_time=0.0,
                        probe=7.5, include_lfp=True, **options):
        roster, review = inputs(include_lfp=include_lfp, **options)
        now = time.monotonic()
        budget = Budget(now, now + 60.0, 64 * 1024**2, 64 * 1024**2)
        with patch.object(implementation, "Native", GeneratedNative), \
             patch.object(GeneratedNative, "starting_time", starting_time), \
             patch.object(GeneratedNative, "include_lfp", include_lfp), \
             patch.object(GeneratedNative, "probe", probe):
            result = implementation.run(roster, review, self.root, self.root / "out",
                                        bytes(range(32)), budget, self.limit)
        manifest = json.loads(Path(result["path"]).read_bytes())
        self.assertEqual(result["pin"], pin(Path(result["path"]).read_bytes()))
        return manifest, review["regions"], budget

    def test_original_bug_reproduced_with_retained_spikes(self):
        with self.assertRaisesRegex(Refusal, "complete equal maintenance interval"):
            self.run_preparation(predecessor)

    def test_predecessor_and_dependency_source_pins(self):
        pins = json.loads((HERE / "SOURCE_PINS.json").read_text())
        entries = [pins["predecessor"], pins["unchanged_test_readback"]]
        entries.extend(pins["unchanged_runtime_dependencies"])
        for entry in entries:
            self.assertEqual(hashlib.sha256((HERE / entry["path"]).read_bytes()).hexdigest(),
                             entry["sha256"])

    def test_spike_only_trial_survives_unused_short_lfp(self):
        manifest, regions, budget = self.run_preparation()
        self.assertEqual(len(manifest["rows"]), 44 * 140)
        rows = [r for r in manifest["rows"] if r["eligibility"]]
        self.assertEqual(len(rows), 88)
        self.assertEqual({r["load"] for r in rows}, {1, 3})
        self.assertEqual(len({r["identity"]["patient"] for r in rows}), 36)
        for row in rows:
            epoch = load_epoch(self.root / "out" / "epochs", row, budget, 32768, regions)
            self.assertEqual(epoch["lfp"].shape, (0, 1000))
            np.testing.assert_array_equal(epoch["spike_offsets"], [0, 3])
            np.testing.assert_allclose(epoch["spike_times"], [0.0, 0.25, 2.499], atol=1e-12)
            np.testing.assert_array_equal(epoch["unit_region"], [regions.index("Hippo")])
        for item in manifest["chronology"]:
            for key in ("first", "last_exclusive", "fractional_alignment_seconds", "source_rate"):
                self.assertIsNone(item[key])
            self.assertEqual(item["lfp_original_rows0"], [])
            self.assertEqual(item["unit_original_rows0"], [0])

    def test_retained_lfp_still_requires_complete_window(self):
        with self.assertRaisesRegex(Refusal, "complete equal maintenance interval"):
            self.run_preparation(retain_lfp=True)

    def test_joint_epoch_retains_lfp_scale_and_spike_stop(self):
        manifest, regions, budget = self.run_preparation(retain_lfp=True, starting_time=5.0)
        row = next(r for r in manifest["rows"] if r["eligibility"])
        epoch = load_epoch(self.root / "out" / "epochs", row, budget, 32768, regions)
        np.testing.assert_allclose(epoch["lfp"][0], np.arange(1000) * 2e-6 + 1e-5)
        np.testing.assert_array_equal(epoch["spike_offsets"], [0, 3])
        self.assertEqual(manifest["chronology"][0]["source_rate"], 400.0)
        self.assertEqual(manifest["chronology"][0]["last_exclusive"], 1000)

    def test_source_without_lfp_remains_supported(self):
        manifest, _, _ = self.run_preparation(include_lfp=False)
        self.assertEqual(sum(r["eligibility"] for r in manifest["rows"]), 88)

    def test_spike_only_window_cannot_cross_probe(self):
        with self.assertRaisesRegex(Refusal, "full equal spike interval before probe"):
            self.run_preparation(probe=7.49)

    def test_global_artifact_reason_survives_empty_modalities(self):
        manifest, _, _ = self.run_preparation(global_excluded=True, no_modality=True)
        self.assertEqual(len(manifest["rows"]), 44 * 140)
        self.assertFalse(any(r["eligibility"] for r in manifest["rows"]))
        self.assertEqual({r["reason"] for r in manifest["rows"]},
                         {"generated global artifact decision"})
        self.assertEqual(manifest["chronology"], [])

    def test_empty_modalities_receive_explicit_disposition(self):
        manifest, _, _ = self.run_preparation(no_modality=True)
        rows = [r for r in manifest["rows"] if r["trial_row0"] in (0, 70)]
        self.assertEqual(len(rows), 88)
        self.assertFalse(any(r["eligibility"] for r in rows))
        self.assertEqual({r["reason"] for r in rows},
                         {"no prospectively eligible neural modality"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
