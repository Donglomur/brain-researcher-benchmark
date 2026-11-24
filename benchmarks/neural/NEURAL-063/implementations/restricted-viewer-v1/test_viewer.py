"""Generated software controls; no authentic observations or participant trials."""
import contextlib
import copy
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural063_restricted_viewer", HERE / "viewer.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def views(split="query"):
    rows = []
    for i in range({"query": 19, "fit": 73}[split]):
        token = f"{split}-{i:03}"
        row = {"id": "event-" + token, "mouse": "mouse-" + token,
               "session": "session-" + token, "experiment": "plane-" + token, "split": split,
               "previous": [{"image": f"image-{j}", "omitted": j == 0,
                             "start_relative_seconds": -2.25 + .75 * j} for j in range(3)],
               "context": {"cre_line": "generated-cre", "targeted_structure": "VISp", "image_set": "generated",
                           "experience_level": "Familiar", "passive": False, "imaging_depth": 175, "session_number": 1},
               "history": [j / 100 for j in range(-11, 1)]}
        if split == "fit":
            row["target"] = [i / 100, .2, -.3]
        rows.append(row)
    n = {"schema": "neural063_rows_v2", "split": split, "rows": rows}
    t = copy.deepcopy(n)
    for row in t["rows"]:
        del row["history"]
    return t, n


def answers(manifest):
    return [{k: row[k] for k in ("presentation_sha256", "request_sha256", "id", "information")} | {"values": [.1, -.2, .3]}
            for row in manifest["pages"]]


class Document(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.tags, self.cells, self.pre = [], [], []
        self.current = None
        self.feed(body.decode())

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag in ("td", "pre"):
            self.current = (tag, [])

    def handle_data(self, data):
        if self.current:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if self.current and tag == self.current[0]:
            (self.cells if tag == "td" else self.pre).append("".join(self.current[1]))
            self.current = None


class ViewerControls(unittest.TestCase):
    def setUp(self):
        self.t, self.n = views()

    def test_complete_pair_preserves_every_observation_and_no_other_queries(self):
        bundle, manifest, pages = v.prepare(self.t, self.n)
        self.assertEqual(manifest["events"], 19)
        self.assertEqual(len(pages), 38)
        self.assertEqual(manifest["direct_request_bundle_sha256"], v.d.digest(v.d.build(self.t, self.n)))
        for request, entry in zip(bundle["requests"], manifest["pages"]):
            body = pages[entry["file"]]
            doc = Document(body)
            self.assertEqual(len(body), entry["bytes"])
            self.assertEqual(v.hashlib.sha256(body).hexdigest(), entry["sha256"])
            row = request["observation"]
            values = [row[k] for k in ("id", "mouse", "session", "experiment", "split")]
            values += list(row["context"].values())
            values += [x for previous in row["previous"] for x in previous.values()]
            values += row.get("history", [])
            for value in values:
                shown = value if isinstance(value, str) else json.dumps(value)
                self.assertIn(shown, doc.cells)
            for other in self.n["rows"]:
                if other["id"] != row["id"]:
                    self.assertNotIn(other["id"], body.decode())
            self.assertEqual(any(tag == "svg" for tag, _ in doc.tags), request["information"] == "N")
            self.assertNotIn("query target", " ".join(doc.cells).lower())
            template = json.loads(doc.pre[0])
            self.assertEqual(template["presentation_sha256"], entry["presentation_sha256"])
            self.assertEqual(template["request_sha256"], entry["request_sha256"])
            self.assertEqual(set(template), {"presentation_sha256", "request_sha256", "id", "information", "values"})

    def test_svg_is_finite_at_extreme_history_and_has_exact_numeric_table(self):
        self.n["rows"][0]["history"] = [1e308, -1e308, 5e-324, -.00000000000001] + [0] * 8
        _, manifest, pages = v.prepare(self.t, self.n)
        body = pages[manifest["pages"][1]["file"]].decode()
        svg = body[body.index("<svg"):body.index("</svg>") + 6]
        parsed = ET.fromstring(svg)
        coords = parsed.find("polyline").attrib["points"]
        self.assertNotIn("nan", coords.lower())
        self.assertNotIn("inf", coords.lower())
        self.assertEqual(len(coords.split()), 12)
        self.assertIn("1e+308", Document(body.encode()).cells)
        self.assertIn("-1e+308", Document(body.encode()).cells)
        self.assertIn("5e-324", Document(body.encode()).cells)

    def test_text_is_escaped_and_no_executable_or_external_content(self):
        token = '<script src="https://example.invalid">& escape</script>'
        for source in (self.t, self.n):
            source["rows"][0]["context"]["cre_line"] = token
        _, manifest, pages = v.prepare(self.t, self.n)
        for entry in manifest["pages"][:2]:
            doc = Document(pages[entry["file"]])
            self.assertIn(token, doc.cells)
            for tag, attrs in doc.tags:
                self.assertNotIn(tag, ("script", "iframe", "object", "embed", "link", "a", "form", "img"))
                self.assertFalse({"src", "href", "onclick", "onload"} & set(attrs))
            csp = [attrs["content"] for tag, attrs in doc.tags if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy"]
            self.assertIn("default-src 'none'", csp[0])

    def test_fixed_demonstrations_preserve_targets_only_for_declared_fit_examples(self):
        ft, fn = views("fit")
        ids = [ft["rows"][4]["id"], ft["rows"][0]["id"]]
        bundle, manifest, pages = v.prepare(self.t, self.n, fit_timing=ft, fit_neural=fn, demonstration_ids=ids)
        self.assertEqual(manifest["exposure_condition"], "fixed_fit_demonstrations")
        for req, entry in zip(bundle["requests"], manifest["pages"]):
            doc = Document(pages[entry["file"]])
            self.assertLess(doc.cells.index(ids[0]), doc.cells.index(ids[1]))
            self.assertNotIn(ft["rows"][1]["id"], doc.cells)
            self.assertIn("0.04", doc.cells)
            self.assertEqual(sum(tag == "svg" for tag, _ in doc.tags), 3 if req["information"] == "N" else 0)

    def test_full_viewer_collection_is_distinct_from_direct_numeric(self):
        _, manifest, _ = v.prepare(self.t, self.n)
        result = v.collect(self.t, self.n, answers(manifest), expected_manifest_sha256=v.d.digest(manifest))
        self.assertEqual(result["mode"], "restricted_viewer")
        self.assertEqual(result["display_manifest_sha256"], v.d.digest(manifest))
        for info in ("T", "N"):
            self.assertEqual(len(result["predictions"][info]), 19)
            self.assertEqual(result["predictions"][info][0]["values"], [.1, -.2, .3])

    def test_response_binding_support_and_numeric_failures_remain_failures(self):
        _, manifest, _ = v.prepare(self.t, self.n)
        variants = []
        x = answers(manifest); x.pop(); variants.append(x)
        x = answers(manifest); x[0], x[1] = x[1], x[0]; variants.append(x)
        x = answers(manifest); x[0].pop("presentation_sha256"); variants.append(x)
        x = answers(manifest); x[0]["presentation_sha256"] = "0" * 64; variants.append(x)
        x = answers(manifest); x[0]["values"] = [True, 0, 0]; variants.append(x)
        x = answers(manifest); x[0]["values"] = [None, None, None]; variants.append(x)
        for response in variants:
            with self.assertRaises(v.d.ContractError):
                v.collect(self.t, self.n, response, expected_manifest_sha256=v.d.digest(manifest))
        with self.assertRaises(v.d.ContractError):
            v.collect(self.t, self.n, answers(manifest), expected_manifest_sha256="0" * 64)

    def test_invalid_or_incomplete_inputs_are_rejected_before_rendering(self):
        for key in ("target", "source_nwb"):
            t, n = views(); n["rows"][0][key] = [1, 2, 3]
            with self.assertRaises(v.d.ContractError), patch.object(v, "_render", side_effect=AssertionError("rendered early")):
                v.prepare(t, n)
        for source in (self.t, self.n):
            source["rows"].pop()
        with self.assertRaises(v.d.ContractError):
            v.prepare(self.t, self.n)

    def test_cli_render_collect_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "t.json").write_bytes(v.d.canonical(self.t))
            (root / "n.json").write_bytes(v.d.canonical(self.n))
            common = ["--timing", str(root / "t.json"), "--neural", str(root / "n.json")]
            argv = ["viewer.py", "render"] + common + ["--output", str(root / "pages")]
            out = io.StringIO()
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
                v.main()
            manifest = v.d.read_json(root / "pages" / "MANIFEST.json")
            self.assertEqual(out.getvalue().strip(), v.d.digest(manifest))
            self.assertEqual(len(list((root / "pages").glob("*.html"))), 38)
            with patch.object(sys, "argv", argv), self.assertRaises(FileExistsError):
                v.main()
            (root / "answers.json").write_bytes(v.d.canonical(answers(manifest)))
            argv = ["viewer.py", "collect"] + common + ["--responses", str(root / "answers.json"),
                    "--manifest-sha256", v.d.digest(manifest), "--output", str(root / "predictions.json")]
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                v.main()
            self.assertEqual(v.d.read_json(root / "predictions.json")["mode"], "restricted_viewer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
