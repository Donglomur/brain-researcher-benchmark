"""Generated software controls only; no authentic metadata or EEG is loaded."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).with_name("trial_roster.py")
SPEC = importlib.util.spec_from_file_location("n079_trial_roster_v2", MODULE)
roster = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(roster)


def fixture():
    """Unsorted row order and repeated video IDs make index mistakes visible."""
    times = [-0.1 + i / 500 for i in range(1800)]
    people = []
    for p in range(1, 7):
        eeg = {name: {} for name in roster.TRIAL_FIELDS}
        eeg.update(ch_names=[f"generated-channel-{i}" for i in range(127)], times=times)
        for s, session in enumerate(roster.SESSIONS):
            videos = list(range(s + 1, 1103, 8)) + [s + 1]
            videos.reverse()
            eeg["stimulus_id"][session] = videos
            eeg["run_number"][session] = [1 + i // 66 for i in range(len(videos))]
            eeg["trial_number"][session] = [1 + i % 66 for i in range(len(videos))]
        eye = copy.deepcopy(eeg)
        del eye["ch_names"]
        for session in roster.SESSIONS:
            for name in roster.TRIAL_FIELDS:
                eye[name][session].reverse()
        people.append({"person": f"sub-{p:02d}", "eeg": eeg, "eye": eye})
    return {"schema": "n079_primitive_trial_metadata_v1", "people": people}


class RosterControls(unittest.TestCase):
    def test_full_source_order_and_distinct_repeats(self):
        value = fixture()
        value["people"].reverse()
        out = roster.build_roster(value)
        self.assertEqual(len(out["sessions"]), 48)
        row = out["sessions"][0]
        expected = value["people"][-1]["eeg"]["stimulus_id"]["ses-01"]
        self.assertEqual(row["trial_video_ids"], expected)
        self.assertEqual([r["eye_row"] for r in row["source_rows"]], list(reversed(range(len(expected)))))
        self.assertEqual(row["source_rows"][0]["video_id"], row["source_rows"][-1]["video_id"])
        self.assertNotEqual(row["source_rows"][0]["trial"], row["source_rows"][-1]["trial"])
        self.assertEqual(sorted(row["train_rows"] + row["query_rows"]), list(range(len(expected))))
        self.assertEqual(sum(out["people"][0]["eeg_counts_per_video"]), 1110)
        self.assertNotEqual(row["trial_roster_pin"], out["sessions"][8]["trial_roster_pin"])

    def test_eye_rejection_never_discards_eeg(self):
        value = fixture()
        baseline = roster.build_roster(value)
        eye = value["people"][0]["eye"]
        for name in roster.TRIAL_FIELDS:
            eye[name]["ses-01"].pop(0)
            # Add an eye-only retained trial with a legitimate repeated video.
            eye[name]["ses-01"].append({"stimulus_id": 1, "run_number": 16, "trial_number": 66}[name])
        out = roster.build_roster(value)
        before, after = baseline["sessions"][0], out["sessions"][0]
        self.assertEqual(before["trial_video_ids"], after["trial_video_ids"])
        self.assertEqual(before["trial_roster_pin"], after["trial_roster_pin"])
        self.assertEqual(after["unpaired_eeg_rows"], [len(after["source_rows"]) - 1])
        self.assertEqual(len(after["eye_only_rows"]), 1)
        self.assertEqual(out["people"][0]["unpaired_eeg_trials"], 1)
        self.assertEqual(out["people"][0]["eye_only_trials"], 1)

    def test_absent_eye_and_empty_eye_sessions_are_explicit(self):
        value = fixture()
        value["people"][0]["eye"] = None
        for name in roster.TRIAL_FIELDS:
            value["people"][1]["eye"][name]["ses-01"] = []
        out = roster.build_roster(value)
        self.assertEqual(out["people"][0]["paired_eye_trials"], 0)
        self.assertFalse(out["sessions"][0]["eye_metadata_present"])
        self.assertTrue(out["sessions"][8]["eye_metadata_present"])
        self.assertEqual(len(out["sessions"][8]["unpaired_eeg_rows"]), len(out["sessions"][8]["source_rows"]))

    def test_identity_and_support_failures(self):
        changes = [
            lambda x: x["people"][0]["eye"]["stimulus_id"]["ses-01"].__setitem__(0, 1102),
            lambda x: x["people"][0]["eeg"]["trial_number"]["ses-01"].__setitem__(1, 1),
            lambda x: x["people"][0]["eeg"]["stimulus_id"]["ses-01"].__setitem__(1, True),
            lambda x: x["people"][0]["eeg"]["times"].__setitem__(0, float("nan")),
            lambda x: x["people"][1]["eeg"]["ch_names"].reverse(),
            lambda x: x["people"][0]["eeg"].__setitem__("noise_ceiling", []),
            lambda x: x["people"].__setitem__(1, x["people"][0]),
        ]
        for change in changes:
            value = fixture()
            change(value)
            with self.subTest(change=change), self.assertRaises(ValueError):
                roster.build_roster(value)
        value = fixture()
        for modality in ("eeg", "eye"):
            meta = value["people"][0][modality]
            for session in roster.SESSIONS:
                meta["stimulus_id"][session] = [1 if v == 1102 else v for v in meta["stimulus_id"][session]]
        with self.assertRaisesRegex(ValueError, "Missing EEG videos"):
            roster.build_roster(value)

    def test_cli_bytes_pinning_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "metadata.json", Path(directory) / "roster.json"
            body = json.dumps(fixture()).encode()
            source.write_bytes(body)
            command = [sys.executable, "-I", "-B", str(MODULE), "--metadata", str(source), "--output", str(output)]
            run = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(run.stdout)["sessions"], 48)
            self.assertEqual(json.loads(output.read_bytes())["input_bytes_pin"]["bytes"], len(body))
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            source.write_text('{"schema":"x","schema":"y"}')
            output.unlink()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
