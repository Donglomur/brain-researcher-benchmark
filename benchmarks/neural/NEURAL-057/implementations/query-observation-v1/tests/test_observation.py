"""Generated format/delivery controls; no authentic EEG, taxonomy or model."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import observation as obs


def npy(rows, shape, descr="<f8", fortran=False, version=1):
    header = repr(dict(descr=descr, fortran_order=fortran, shape=shape)).encode("ascii")
    prefix = 10 if version == 1 else 12
    header += b" " * ((-len(header) - prefix - 1) % 64) + b"\n"
    return (b"\x93NUMPY" + bytes((version, 0))
            + len(header).to_bytes(prefix - 8, "little") + header
            + b"".join(struct.pack("<" + "d" * len(row), *row) for row in rows))


def generated(panel="PRE"):
    width = obs.DIMENSIONS[panel]
    rows = [[float(i) + j / 1000 for j in range(width)] for i in range(200)]
    rows[0][0] = -0.0
    rows[0][1] = math.ulp(0.0)
    raw = npy(rows, (200, width))
    doc = {"schema": "neural057-query-view-v1", "cell": {
        "person": "sub-01", "mode": "F", "panel": panel},
        "categories": ["generated-category-%02d" % i for i in range(53)],
        "query_ids": ["generated-query-%03d" % i for i in range(200)],
        "features": {"path": "features.npy", "bytes": len(raw), "sha256": obs.sha(raw)},
        "category_schema_sha256": "a" * 64, "fit_state_sha256": "b" * 64,
        "preparation_sha256": "c" * 64}
    return doc, rows, raw


def embedded(page):
    marker = '<script id="observations" type="application/json">'
    return json.loads(page.decode().split(marker, 1)[1].split("</script>", 1)[0])


class ObservationControls(unittest.TestCase):
    def test_all_panels_keep_every_value_row_category_and_identity(self):
        for panel, width in obs.DIMENSIONS.items():
            with self.subTest(panel=panel):
                doc, expected, raw = generated(panel)
                rows = obs.decode_features(raw, panel)
                page = obs.render(doc, rows, "d" * 64)
                actual = embedded(page)
                self.assertEqual(actual["values"], expected)
                self.assertEqual(len(actual["values"]), 200)
                self.assertEqual(len(actual["feature_labels"]), width)
                self.assertEqual(actual["query_ids"], doc["query_ids"])
                self.assertEqual(actual["categories"], doc["categories"])
                self.assertEqual(actual["features"]["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(actual["query_view_sha256"], "d" * 64)
                self.assertEqual(math.copysign(1, actual["values"][0][0]), -1)
                self.assertNotIn("fetch(", page.decode())
                self.assertNotIn("XMLHttpRequest", page.decode())

    def test_layout_matches_registered_concatenation_and_flatten_order(self):
        labels = obs.feature_labels("LATE")
        self.assertEqual(labels[:176], obs.feature_labels("IMAGE"))
        self.assertEqual(labels[176:346], obs.feature_labels("PRE"))
        self.assertEqual(labels[:346], obs.feature_labels("BASE"))
        self.assertEqual(labels[0], "IMAGE RGB cell r1 c1 R mean")
        self.assertEqual(labels[47], "IMAGE RGB cell r4 c4 B mean")
        self.assertEqual(labels[48], "IMAGE Sobel cell r1 c1 orientation bin 0 mean magnitude")
        self.assertEqual(labels[175], "IMAGE Sobel cell r4 c4 orientation bin 7 mean magnitude")
        self.assertEqual(labels[176], "PRE whitened axis 01 ordered sample 01")
        self.assertEqual(labels[185], "PRE whitened axis 01 ordered sample 10")
        self.assertEqual(labels[186], "PRE whitened axis 02 ordered sample 01")
        self.assertEqual(labels[345], "PRE whitened axis 17 ordered sample 10")
        self.assertEqual(labels[346], "LATE whitened axis 01 ordered sample 01")
        self.assertEqual(labels[-1], "LATE whitened axis 17 ordered sample 20")

    def test_closed_target_free_contract_rejects_boundary_changes(self):
        template, _, _ = generated()
        for kind in ("targets", "training", "duplicate_query", "missing_query", "category",
                     "path", "byte_boolean", "digest", "panel", "fit_schema"):
            doc = copy.deepcopy(template)
            if kind in ("targets", "training"):
                doc[kind] = ["should never appear"]
            elif kind == "duplicate_query":
                doc["query_ids"][199] = doc["query_ids"][0]
            elif kind == "missing_query":
                doc["query_ids"].pop()
            elif kind == "category":
                doc["categories"].pop()
            elif kind == "path":
                doc["features"]["path"] = "../targets.npy"
            elif kind == "byte_boolean":
                doc["features"]["bytes"] = True
            elif kind == "digest":
                doc["preparation_sha256"] = "missing"
            elif kind == "panel":
                doc["cell"]["panel"] = "OTHER"
            else:
                doc["schema"] = "neural057-fit-view-v1"
            with self.subTest(kind=kind), self.assertRaises(obs.ObservationError):
                obs.validate_view(doc)

    def test_npy_refuses_truncation_transpose_objects_nonfinite_or_extra_payload(self):
        _, rows, raw = generated()
        bad = [raw[:-1], raw + b"extra", npy(rows, (199, 170)),
               npy(rows, (200, 170), fortran=True), npy(rows, (200, 170), descr="|O"),
               npy(rows, (170, 200)), b"\x93NUMPY\x01\x00\xff\xff"]
        for value in (math.inf, math.nan):
            changed = copy.deepcopy(rows)
            changed[199][169] = value
            bad.append(npy(changed, (200, 170)))
        for i, body in enumerate(bad):
            with self.subTest(case=i), self.assertRaises(obs.ObservationError):
                obs.decode_features(body, "PRE")
        self.assertEqual(obs.decode_features(npy(rows, (200, 170), version=2), "PRE"),
                         obs.decode_features(raw, "PRE"))

    def test_embedded_names_cannot_inject_html_or_script(self):
        doc, rows, _ = generated()
        attack = '</script><script>alert("not data")</script>&'
        doc["categories"][0] = attack
        doc["query_ids"][0] = attack
        page = obs.render(doc, rows, "d" * 64)
        self.assertNotIn(attack.encode(), page)
        self.assertEqual(embedded(page)["categories"][0], attack)
        self.assertIn(b"textContent=name", page)

    def test_real_cli_checks_bytes_hash_and_exclusive_output(self):
        doc, rows, raw = generated()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            feature = base / "features.npy"
            query = base / "query.json"
            output = base / "observations.html"
            feature.write_bytes(raw)
            body = json.dumps(doc).encode()
            query.write_bytes(body)
            obs.main(["--query", str(query), "--output", str(output)])
            self.assertEqual(embedded(output.read_bytes())["query_view_sha256"], obs.sha(body))
            self.assertEqual(embedded(output.read_bytes())["values"], rows)
            with self.assertRaises(FileExistsError):
                obs.main(["--query", str(query), "--output", str(output)])
            self.assertEqual(query.read_bytes(), body)
            feature.write_bytes(raw[:-8] + struct.pack("<d", -1000))
            with self.assertRaisesRegex(obs.ObservationError, "SHA-256"):
                obs.load_query(query)
            feature.unlink()
            feature.symlink_to(query)
            with self.assertRaises(OSError):
                obs.load_query(query)

    def test_json_duplicate_keys_and_nonfinite_refused(self):
        for raw in (b'{"schema":1,"schema":2}', b'{"x":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(obs.ObservationError):
                obs.parse(raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
