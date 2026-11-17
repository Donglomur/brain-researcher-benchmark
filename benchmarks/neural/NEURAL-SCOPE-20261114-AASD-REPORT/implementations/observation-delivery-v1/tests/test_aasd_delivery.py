"""Small generated controls for the observation-to-existing-scorer path."""
import copy
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "aasd_delivery.py"
spec = importlib.util.spec_from_file_location("aasd_delivery", MODULE)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def inventory():
    people = [f"private-person-{i}" for i in range(18)]
    data = {"schema": "aasd-inventory-v1", "participants": people,
            "mixture_folds": {"private-a": 0, "private-b": 1, "private-c": 2},
            "mixture_map_provenance": "Generated control only", "trials": []}
    for person in people:
        for block in range(7):
            for j in range(10):
                trial = {"trial_id": f"{person}-block{block}-trigger{j}", "participant": person,
                         "block_id": f"private-block-{block}", "trial_in_block": j+1, "order": block*10+j+1,
                         "condition": "passive" if block == 6 else "active",
                         "status": "available" if j == 0 and block in (0, 1, 2, 6) else "missing",
                         "reason": "Generated missing slot", "mixture_family": ("private-a", "private-b", "private-c")[block%3],
                         "duration_ns": 4*d.a.NS, "duration_discrepancy_reason": "Short generated control only"}
                if trial["status"] == "available":
                    trial.update(sample_count=512, sample_origin_ns=0, valid_spans=[[0, 512]],
                                 initial_state=0, key_events=[{"time_ns": 2*d.a.NS, "state": 1}],
                                 state_mapping_provenance="Generated key mapping")
                data["trials"].append(trial)
    return data


def observation():
    return {"schema": "aasd-normalized-observation-v1", "channels": ["C3", "C4"], "eeg_unit": "uV",
            "eeg_samples": [[i/1000 for i in range(512)], [-i/1000 for i in range(512)]],
            "audio": {"sample_rate_hz": 8, "sample_origin_ns": 0,
                      "samples": [[i/100 for i in range(32)], [-i/100 for i in range(32)]]}}


class Delivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.inv = inventory()
        cls.public = cls.root / "public"
        cls.binding_path = cls.root / "private" / "binding.json"
        cls.loads = []
        def load(tid):
            cls.loads.append(tid)
            return observation()
        cls.receipt = d.export(cls.inv, load, cls.public, cls.binding_path)
        cls.binding = d.a.strict_load(cls.binding_path)
        cls.cases = d.a.prepare(cls.inv)["cases"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def responses(self, mode):
        labels = {c["case_id"]: c["label"] for c in self.cases}
        return [{"request_id": row["request_ids"][mode], "p_right": .9 if labels[row["case_id"]] else .1}
                for row in reversed(self.binding["rows"])]

    def test_all_active_and_passive_cases_and_trial_streaming(self):
        self.assertEqual(len(self.cases), 144)
        self.assertEqual(self.receipt["eligible_cases"], 144)
        self.assertEqual(len(self.loads), 72)
        self.assertEqual(len(set(self.loads)), 72)
        for mode in d.MODES:
            index = d.a.strict_load(self.public / mode / "index.json")
            self.assertEqual(len(index["requests"]), 144)
            self.assertTrue(all(set(r) == {"request_id"} for r in index["requests"]))
            self.assertEqual(len(list((self.public / mode / "audio").iterdir())), 1)
        self.assertEqual(len({(r["participant"], r["held_mixture_fold"]) for r in self.binding["rows"]}), 54)

    def test_exact_slices_full_audio_and_paired_information_equality(self):
        first = self.binding["rows"][0]
        packets = [d.a.strict_load(self.public / mode / "packets" / (first["request_ids"][mode]+".json")) for mode in d.MODES]
        self.assertNotEqual(packets[0]["request_id"], packets[1]["request_id"])
        self.assertEqual(packets[0]["observation"], packets[1]["observation"])
        common = packets[0]["observation"]
        self.assertEqual(common["eeg_samples"][0], [i/1000 for i in range(64, 320)])
        self.assertEqual(common["eeg_samples"][1], [-i/1000 for i in range(64, 320)])
        self.assertEqual(common["eeg_start_relative_to_target_ns"], -500_000_000)
        self.assertEqual(common["audio_origin_relative_to_target_ns"], -d.a.NS)
        self.assertEqual(common["valid_samples"], [True]*256)
        self.assertEqual(d.digest(common), first["observation_sha256"])
        waves = [d.a.strict_load(self.public / mode / "audio" / (packet["audio_resource"]+".json")) for mode, packet in zip(d.MODES, packets)]
        self.assertEqual(waves[0], waves[1])
        self.assertEqual(waves[0]["samples"], observation()["audio"]["samples"])
        self.assertEqual(d.digest(waves[0]), common["audio_sha256"])

    def test_public_allowlist_excludes_evaluator_metadata(self):
        secret_fields = {"label", "defined_label", "key_events", "initial_state", "case_id", "trial_id",
                         "participant", "condition", "fold", "cell_id", "block_id", "order", "guard_2s", "reasons"}
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(secret_fields & set(value))
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, str):
                self.assertNotIn("private-", value)
                self.assertNotIn("trigger", value)
        for path in self.public.rglob("*.json"):
            walk(d.a.strict_load(path))
            self.assertEqual(path.stat().st_mtime, 0)
        self.assertEqual(stat.S_IMODE(self.binding_path.stat().st_mode), 0o600)

    def test_complete_responses_reach_unchanged_endpoint(self):
        predictions = d.join_responses(self.inv, self.binding, "frozen_program", self.responses("frozen_program"))
        result = d.a.score(self.inv, predictions)
        self.assertEqual(result["primary"]["macro"]["balanced_accuracy"]["all_18"], 1)
        self.assertEqual(sum(p["n"] for p in result["primary"]["participants"]), 108)
        self.assertEqual(sum(p["n"] for p in result["passive_motor_report_diagnostic"]["participants"]), 36)

    def test_response_failures_never_change_denominator(self):
        original = self.responses("tool_assisted")
        for change in (lambda r: r.pop(), lambda r: r.append(r[0]),
                       lambda r: r[0].update(p_right=float("nan")),
                       lambda r: r[0].update(p_right=10**400),
                       lambda r: r[0].update(p_right=True), lambda r: r[0].update(p_right=1.01),
                       lambda r: r[0].update(label=1), lambda r: r[0].update(request_id="../binding"),
                       lambda r: r[0].update(request_id=self.binding["rows"][0]["request_ids"]["frozen_program"])):
            bad = copy.deepcopy(original)
            change(bad)
            with self.assertRaises(d.ContractError):
                d.join_responses(self.inv, self.binding, "tool_assisted", bad)
        passive_ids = {c["case_id"] for c in self.cases if c["condition"] == "passive"}
        removed = {r["request_ids"]["tool_assisted"] for r in self.binding["rows"] if r["case_id"] in passive_ids}
        with self.assertRaises(d.ContractError):
            d.join_responses(self.inv, self.binding, "tool_assisted", [r for r in original if r["request_id"] not in removed])

    def test_binding_and_inventory_changes_fail(self):
        response = self.responses("frozen_program")
        for change in (lambda b: b["rows"].pop(), lambda b: b["rows"][1].update(case_id=b["rows"][0]["case_id"]),
                       lambda b: b["rows"][0].update(held_mixture_fold=True),
                       lambda b: b["rows"][0]["request_ids"].update(tool_assisted=b["rows"][1]["request_ids"]["frozen_program"])):
            bad = copy.deepcopy(self.binding)
            change(bad)
            with self.assertRaises(d.ContractError):
                d.join_responses(self.inv, bad, "frozen_program", response)
        changed = copy.deepcopy(self.inv)
        changed["trials"][0]["initial_state"] = 1
        with self.assertRaises(d.ContractError):
            d.join_responses(changed, self.binding, "frozen_program", response)
        with self.assertRaises(d.ContractError):
            d.join_responses(self.inv, self.binding, "direct_observation", response)

    def test_nonfinite_outside_admitted_context_is_not_new_exclusion(self):
        source = observation()
        source["eeg_samples"][0][0] = float("nan")
        with tempfile.TemporaryDirectory() as tmp:
            result = d.export(self.inv, lambda _: source, Path(tmp)/"public", Path(tmp)/"binding.json")
            self.assertEqual(result["eligible_cases"], 144)

    def test_bad_observations_fail_atomically(self):
        changes = (lambda o: o.update(label=1), lambda o: o["eeg_samples"][0].pop(),
                   lambda o: o["eeg_samples"][0].__setitem__(64, float("nan")),
                   lambda o: o.update(eeg_unit="unknown"), lambda o: o.update(channels=["C3", "C3"]),
                   lambda o: o["audio"]["samples"].pop(), lambda o: o["audio"]["samples"][0].pop(),
                   lambda o: o["audio"]["samples"][0].__setitem__(0, 2),
                   lambda o: o["audio"].update(sample_origin_ns=1),
                   lambda o: o["audio"].update(sample_rate_hz=9))
        for change in changes:
            source = observation()
            change(source)
            with tempfile.TemporaryDirectory() as tmp:
                public, private = Path(tmp)/"public", Path(tmp)/"private.json"
                with self.assertRaises(d.ContractError):
                    d.export(self.inv, lambda _: source, public, private)
                self.assertFalse(public.exists())
                self.assertFalse(private.exists())
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_private_nested_output_and_existing_paths_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp)/"public"
            with self.assertRaises(d.ContractError):
                d.export(self.inv, lambda _: observation(), public, public/"private.json")
            public.mkdir()
            with self.assertRaises(d.ContractError):
                d.export(self.inv, lambda _: observation(), public, Path(tmp)/"private.json")
        with self.assertRaises(d.ContractError):
            d.export(self.inv, lambda _: observation(), self.root/"new-public", self.binding_path)

    def test_common_channel_order_is_required(self):
        calls = 0
        def load(_):
            nonlocal calls
            calls += 1
            source = observation()
            if calls == 2:
                source["channels"].reverse()
            return source
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(d.ContractError):
                d.export(self.inv, load, Path(tmp)/"public", Path(tmp)/"private.json")

    def test_cli_export_and_response_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/"inventory.json").write_text(json.dumps(self.inv))
            (root/"source.json").write_text(json.dumps(observation()))
            paths = {t["trial_id"]: "source.json" for t in self.inv["trials"] if t["status"] == "available"}
            (root/"map.json").write_text(json.dumps(paths))
            exported = subprocess.run([sys.executable, "-I", "-B", str(MODULE), "export",
                str(root/"inventory.json"), str(root/"map.json"), str(root/"public"), str(root/"binding.json")],
                capture_output=True, text=True, timeout=20)
            self.assertEqual(exported.returncode, 0, exported.stderr)
            binding = d.a.strict_load(root/"binding.json")
            responses = [{"request_id": row["request_ids"]["tool_assisted"], "p_right": .5} for row in binding["rows"]]
            (root/"responses.json").write_text(json.dumps(responses))
            joined = subprocess.run([sys.executable, "-I", "-B", str(MODULE), "join", str(root/"inventory.json"),
                str(root/"binding.json"), "tool_assisted", str(root/"responses.json"), str(root/"predictions.json")],
                capture_output=True, text=True, timeout=20)
            self.assertEqual(joined.returncode, 0, joined.stderr)
            predictions = d.a.strict_load(root/"predictions.json")
            result = d.a.score(self.inv, predictions)
            self.assertEqual(result["primary"]["macro"]["balanced_accuracy"]["all_18"], .5)
            self.assertEqual(len(predictions), 144)


if __name__ == "__main__":
    unittest.main()
