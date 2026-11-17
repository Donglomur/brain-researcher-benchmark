"""Generated source controls only; no authentic EEG, labels or inference."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("waveform_context_export", Path(__file__).with_name("export_contexts.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def packet(root, *, count=400, duplicate=False, prompt=None):
    root.mkdir()
    ids = [f"development-{1 + index // 200:03d}-{index % 200:024x}" for index in range(400)]
    if duplicate:
        ids[1] = ids[0]
    # Short invented strings exercise byte preservation, not EEG shape validity.
    lines = ['{"trial_id":"' + identifier + '","channels":[[-0.0,1e+00],[0.000,2.50]]}\n'
             for identifier in ids[:count]]
    demo = '[{"target":0,"channels":[[-0.0]]},{"target":1,"channels":[[1e+00]]},' \
           '{"target":0,"channels":[[2.50]]},{"target":1,"channels":[[0.000]]}]\n'
    template = prompt or 'No tools.\nDEMONSTRATIONS:\n{{demonstrations_json}}\nCURRENT QUERY:\n{{query_json}}\n'
    bodies = {
        "queries.jsonl": "".join(lines), "demonstrations.json": demo,
        "prompt.txt": template, "response_schema.json": '{"type":"object"}\n',
        "manifest.json": json.dumps({"development_ids": ids, "query_count": 400,
            "demonstration_count": 4, "natural_class_prior_supplied": False}) + "\n",
    }
    pins = {}
    for name, text in bodies.items():
        raw = text.encode("utf-8")
        (root / name).write_bytes(raw)
        pins[name] = (len(raw), hashlib.sha256(raw).hexdigest())
    return pins, ids, lines, demo, template


class ExportTests(unittest.TestCase):
    def test_complete_400_cli_preserves_exact_context_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pins, ids, lines, demo, template = packet(base / "input")
            with mock.patch.object(module, "PINS", pins), contextlib.redirect_stdout(io.StringIO()) as stdout:
                status = module.main(["--packet", str(base / "input"), "--output", str(base / "output")])
            self.assertEqual(status, 0)
            receipt = json.loads(stdout.getvalue())
            raw = (base / "output/contexts.jsonl").read_bytes()
            rows = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual(len(rows), 400)
            for index, row in enumerate(rows):
                self.assertEqual(set(row), {"ordinal", "trial_id", "prompt"})
                self.assertEqual(row["ordinal"], index)
                self.assertEqual(row["trial_id"], ids[index])
                self.assertEqual(row["prompt"], template.replace("{{demonstrations_json}}", demo).replace("{{query_json}}", lines[index]))
            self.assertEqual(receipt["output"]["bytes"], len(raw))
            self.assertEqual(receipt["output"]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(json.loads((base / "output/COMPLETE.json").read_text()), receipt)
            self.assertEqual(receipt["explicit_packet_bytes_read"], sum(n for n, _ in pins.values()) + pins["queries.jsonl"][0])
            self.assertEqual(sorted(p.name for p in (base / "output").iterdir()), ["COMPLETE.json", "contexts.jsonl"])

    def test_each_changed_input_rejected_before_output(self):
        for name in module.PINS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                pins, *_ = packet(base / "input")
                path = base / "input" / name
                raw = path.read_bytes()
                path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
                with mock.patch.object(module, "PINS", pins), self.assertRaises(ValueError):
                    module.export_contexts(base / "input", base / "output")
                self.assertFalse((base / "output").exists())

    def test_complete_population_required_even_for_generated_pins(self):
        for options in ({"count":399}, {"duplicate":True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                pins, *_ = packet(base / "input", **options)
                with mock.patch.object(module, "PINS", pins), self.assertRaises(ValueError):
                    module.export_contexts(base / "input", base / "output")
                self.assertFalse((base / "output").exists())

    def test_existing_directory_and_dangling_symlink_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pins, *_ = packet(base / "input")
            (base / "existing").mkdir()
            (base / "existing/keep").write_bytes(b"untouched")
            (base / "dangling").symlink_to(base / "absent")
            with mock.patch.object(module, "PINS", pins):
                for name in ("existing", "dangling"):
                    with self.assertRaises(FileExistsError):
                        module.export_contexts(base / "input", base / name)
            self.assertEqual((base / "existing/keep").read_bytes(), b"untouched")
            self.assertTrue((base / "dangling").is_symlink())
            self.assertFalse((base / "absent").exists())

    def test_symlink_packet_member_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pins, *_ = packet(base / "input")
            path = base / "input/prompt.txt"
            path.rename(base / "template")
            path.symlink_to(base / "template")
            with mock.patch.object(module, "PINS", pins), self.assertRaises(OSError):
                module.export_contexts(base / "input", base / "output")
            self.assertFalse((base / "output").exists())

    def test_mid_export_query_mutation_has_no_completion_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pins, *_ = packet(base / "input")
            original = module.record_bytes
            calls = 0
            def mutate_after_first_row(value):
                nonlocal calls
                calls += 1
                if calls == 1:
                    path = base / "input/queries.jsonl"
                    raw = path.read_bytes()
                    path.write_bytes(raw.replace(b"2.50", b"2.51"))
                return original(value)
            with mock.patch.object(module, "PINS", pins), mock.patch.object(module, "record_bytes", mutate_after_first_row), self.assertRaises(ValueError):
                module.export_contexts(base / "input", base / "output")
            self.assertTrue((base / "output/contexts.jsonl").exists())
            self.assertFalse((base / "output/COMPLETE.json").exists())

    def test_limit_failure_retains_partial_output_without_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pins, *_ = packet(base / "input")
            with mock.patch.object(module, "PINS", pins), mock.patch.object(module, "OUTPUT_LIMIT", 1000), self.assertRaises(ValueError):
                module.export_contexts(base / "input", base / "output")
            self.assertTrue((base / "output/contexts.jsonl").exists())
            self.assertFalse((base / "output/COMPLETE.json").exists())

    def test_template_and_manifest_condition_are_fixed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pins, *_ = packet(base / "input", prompt="{{demonstrations_json}}\n{{query_json}}{{query_json}}")
            with mock.patch.object(module, "PINS", pins), self.assertRaises(ValueError):
                module.export_contexts(base / "input", base / "output")
            self.assertFalse((base / "output").exists())
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pins, *_ = packet(base / "input")
            path = base / "input/manifest.json"
            value = json.loads(path.read_text())
            value["natural_class_prior_supplied"] = True
            raw = json.dumps(value).encode("utf-8")
            path.write_bytes(raw)
            pins["manifest.json"] = (len(raw), hashlib.sha256(raw).hexdigest())
            with mock.patch.object(module, "PINS", pins), self.assertRaises(ValueError):
                module.export_contexts(base / "input", base / "output")
            self.assertFalse((base / "output").exists())
        self.assertEqual(set(module.PINS), {"queries.jsonl", "demonstrations.json", "prompt.txt", "response_schema.json", "manifest.json"})
        self.assertEqual(module.PINS["queries.jsonl"], (14521484, "1a34369834d022d0dc332293b6cd120df006195855c08087697bcdd823b1f126"))


if __name__ == "__main__":
    unittest.main()
