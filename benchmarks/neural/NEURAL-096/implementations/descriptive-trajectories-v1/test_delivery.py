"""In-memory generated delivery controls; never open authentic neural data."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from xml.etree import ElementTree as ET

import delivery
import view


ROOT = Path("/generated-neural096-public-bundle")


def fixture(*, single=False):
    cells = []
    for index, (cell_id, split, segment, eye, direction) in enumerate(view.ordered_cells()):
        n_long = n_short = 0
        if index == 0:
            n_long, n_short = 75, 75
        elif index == 24:
            n_long, n_short = (54, 0) if single else (27, 27)
        cell = {"cell_id": cell_id, "source_split": split, "observation_segment": segment,
                "is_eye": eye, "theta": direction, "n_long": n_long, "n_short": n_short,
                "long_rate_hz": [[1.0 for _ in range(20)] for _ in range(54)] if n_long else None,
                "short_rate_hz": [[0.25 for _ in range(20)] for _ in range(54)] if n_short else None,
                "supported": bool(n_long and n_short),
                "missing_priors": [name for name, n in (("long", n_long), ("short", n_short)) if not n]}
        cells.append(cell)
    return {"schema": view.SCHEMA, "method": delivery.METHOD, "unit_ids": list(range(54)),
            "phase_bins": 20, "quarter_bin_slices": [[0, 5], [5, 10], [10, 15], [15, 20]],
            "rate_units": "spikes/s/source unit", "display_rate_max_hz": 1.0, "cells": cells,
            "information_condition": "matched_prior_specific_aggregate_trajectories",
            "limits": list(delivery.LIMITS)}


def make_binding(body):
    return {"preparation_completion_sha256": "2"*64,
            "preparation_receipt": {"bytes": 1, "sha256": "1"*64}, "observation": delivery.pin(body)}


@contextmanager
def memory_bundle(files):
    reads = []
    def read(path, limit):
        name = str(Path(path).relative_to(ROOT))
        reads.append(name)
        body = files[name]
        delivery.require(0 < len(body) <= limit, "generated read bound")
        return body
    with mock.patch.object(delivery, "_bundle_inventory"), mock.patch.object(delivery, "bounded", read):
        yield reads


class DeliveryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = fixture()
        # Deliberately noncanonical whitespace proves the programme bytes survive.
        cls.body = (json.dumps(cls.observation, indent=1) + "\n").encode()
        cls.binding = make_binding(cls.body)
        cls.files = dict(delivery.iter_payloads(cls.body, cls.binding))
        cls.files["MANIFEST.json"] = delivery.encoded(delivery._manifest(
            {name: delivery.pin(body) for name, body in cls.files.items()}, cls.binding))
        cls.sha = delivery.pin(cls.files["MANIFEST.json"])["sha256"]

    def test_complete_observation_only_payloads_preserve_numeric_bytes(self):
        self.assertEqual(set(self.files), set(delivery.PAYLOAD_NAMES) | {"MANIFEST.json"})
        self.assertEqual(len(self.files), 51)
        self.assertEqual(self.files["programme/observations.json"], self.body)
        index = delivery.strict_json(self.files["viewer/INDEX.json"])
        self.assertEqual([c["cell_id"] for c in index["cells"]], list(delivery.IDS))
        self.assertFalse(index["precision"]["identical_numerical_precision"])
        self.assertFalse(index["precision"]["image_provider_transport_qualified"])
        for cell in index["cells"]:
            self.assertNotIn("difference_hz", cell)
            self.assertNotIn("summary", cell)
            self.assertNotIn("long_rate_hz", cell)

    def test_observation_exact_whitelist_and_binding(self):
        for mutation in ("top", "cell", "scope", "missing_key"):
            altered = copy.deepcopy(self.observation)
            if mutation == "top":
                altered["private_answer"] = [42]
            elif mutation == "cell":
                altered["cells"][0]["difference_hz"] = []
            elif mutation == "scope":
                altered["limits"][0] = "Population inference established"
            else:
                del altered["cells"][0]["supported"]
            with self.subTest(mutation=mutation), self.assertRaises(delivery.DeliveryError):
                delivery.observation(delivery.encoded(altered))
        changed_binding = copy.deepcopy(self.binding)
        changed_binding["observation"]["sha256"] = "0"*64
        with self.assertRaises(delivery.DeliveryError):
            list(delivery.iter_payloads(self.body, changed_binding))

    def test_supported_missing_and_single_prior_svg_coverage(self):
        first = self.files[delivery.SVG_NAMES[0]]
        self.assertEqual(delivery.verify_svg(self.observation, delivery.IDS[0], first),
                         {"rate_rectangles": 2160, "missing_prior_panels": 0})
        empty = self.files[delivery.SVG_NAMES[1]]
        self.assertEqual(delivery.verify_svg(self.observation, delivery.IDS[1], empty),
                         {"rate_rectangles": 0, "missing_prior_panels": 2})
        one = fixture(single=True)
        svg = view.render_cell(one, delivery.IDS[24])
        self.assertEqual(delivery.verify_svg(one, delivery.IDS[24], svg),
                         {"rate_rectangles": 1080, "missing_prior_panels": 1})

    def test_svg_pixel_label_geometry_and_visible_text_tampering(self):
        original = self.files[delivery.SVG_NAMES[0]]
        mutations = [
            original.replace(b'fill="#0000ff"', b'fill="#0101ff"', 1),
            original.replace(b'data-unit-id="0"', b'data-unit-id="999"', 1),
            original.replace(b'stroke-width="1.5"', b'stroke-width="12"', 1),
            original.replace(b'width="1360"', b'width="1"', 1),
            original.replace(b'fill="white"', b'fill="black"', 1),
            original.replace(b'font-size="21"', b'font-size="0"', 1),
        ]
        for i, body in enumerate(mutations):
            with self.subTest(mutation=i), self.assertRaises(delivery.DeliveryError):
                delivery.verify_svg(self.observation, delivery.IDS[0], body)
        root = ET.fromstring(original)
        ns = "{http://www.w3.org/2000/svg}"
        panel = next(x for x in root.iter(ns + "g") if x.attrib.get("id") == "long-panel")
        panel.remove(next(panel.iter(ns + "rect")))
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_svg(self.observation, delivery.IDS[0], ET.tostring(root))

    def test_svg_active_external_and_answer_content_refused(self):
        original = self.files[delivery.SVG_NAMES[0]]
        mutations = [
            original.replace(b"</svg>", b"<script>alert(1)</script></svg>"),
            original.replace(b"url(#rate-scale)", b"url(https://example.invalid/hidden)"),
            original.replace(b"</svg>", b'<text x="0" y="0">private answer 42</text></svg>'),
            b'<!DOCTYPE svg [<!ENTITY x "secret">]>' + original,
            b'<?xml-stylesheet href="https://example.invalid/external.css"?>' + original,
            original.replace(b"</svg>", b"<!-- private answer 42 --></svg>"),
            (b'<?xml-stylesheet href="https://example.invalid/external.css"?>' + original).decode().encode("utf-16"),
        ]
        for i, body in enumerate(mutations):
            with self.subTest(mutation=i), self.assertRaises(delivery.DeliveryError):
                delivery.verify_svg(self.observation, delivery.IDS[0], body)

    def test_svg_swapped_prior_and_scale_labels_refused(self):
        ns = "{http://www.w3.org/2000/svg}"
        original = self.files[delivery.SVG_NAMES[0]]
        root = ET.fromstring(original)
        panels = [node for node in root.iter(ns + "g") if node.attrib.get("id") in ("long-panel", "short-panel")]
        long_label, short_label = panels[0][0], panels[1][0]
        long_label.text, short_label.text = short_label.text, long_label.text
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_svg(self.observation, delivery.IDS[0], ET.tostring(root))
        root = ET.fromstring(original)
        main = root[-1]
        main[10].text, main[18].text = main[18].text, main[10].text
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_svg(self.observation, delivery.IDS[0], ET.tostring(root))

    def test_svg_leaf_children_and_occluding_paint_order_refused(self):
        ns = "{http://www.w3.org/2000/svg}"
        root = ET.fromstring(self.files[delivery.SVG_NAMES[0]])
        panel = next(node for node in root.iter(ns + "g") if node.attrib.get("id") == "long-panel")
        rates = list(panel.iter(ns + "rect"))
        panel.remove(rates[1])
        rates[0].append(rates[1])
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_svg(self.observation, delivery.IDS[0], ET.tostring(root))
        root = ET.fromstring(self.files[delivery.SVG_NAMES[1]])
        panel = next(node for node in root.iter(ns + "g") if node.attrib.get("id") == "long-panel")
        background = next(panel.iter(ns + "rect"))
        marker = next(node for node in panel.iter(ns + "text") if node.text.startswith("UNSUPPORTED:"))
        panel.remove(background)
        panel.insert(list(panel).index(marker) + 1, background)
        with self.assertRaises(delivery.DeliveryError):
            delivery.verify_svg(self.observation, delivery.IDS[1], ET.tostring(root))

    def test_full_bundle_verification_reads_all_51_files(self):
        with memory_bundle(self.files) as reads:
            result = delivery.verify_bundle(ROOT, self.sha)
        self.assertEqual(result["files_verified"], 51)
        self.assertEqual(result["cells"], 48)
        self.assertEqual(result["supported_cells"], 2)
        self.assertEqual(result["unsupported_cells"], 46)
        self.assertEqual(result["rate_rectangles"], 4320)
        self.assertEqual(result["missing_prior_panels"], 92)
        self.assertEqual(len(reads), 51)
        self.assertEqual(set(reads), set(self.files))

    def test_typed_getters_have_explicit_narrow_read_scope(self):
        with memory_bundle(self.files) as reads:
            actual = delivery.get_view(ROOT, self.sha, delivery.IDS[0])
        self.assertEqual(actual, self.files[delivery.SVG_NAMES[0]])
        self.assertEqual(reads, ["MANIFEST.json", "programme/observations.json", "viewer/INDEX.json", delivery.SVG_NAMES[0]])
        with memory_bundle(self.files) as reads:
            self.assertEqual(delivery.read_programme(ROOT, self.sha), self.body)
        self.assertEqual(len(reads), 3)
        with memory_bundle(self.files) as reads:
            self.assertEqual(len(delivery.list_cells(ROOT, self.sha)["cells"]), 48)
        self.assertEqual(len(reads), 3)

    def test_arbitrary_cell_ids_refused_before_any_file_read(self):
        with mock.patch.object(delivery, "_load", side_effect=AssertionError("must not read")):
            for identifier in ("../../private/reference.json", "/etc/passwd", "", 0, None, [delivery.IDS[0]]):
                with self.subTest(identifier=identifier), self.assertRaises(delivery.DeliveryError):
                    delivery.get_view(ROOT, self.sha, identifier)

    def test_selected_hash_and_manifest_identity_are_required(self):
        changed = dict(self.files)
        changed[delivery.SVG_NAMES[0]] += b" "
        with memory_bundle(changed), self.assertRaises(delivery.DeliveryError):
            delivery.get_view(ROOT, self.sha, delivery.IDS[0])
        with memory_bundle(self.files), self.assertRaises(delivery.DeliveryError):
            delivery.read_programme(ROOT, "0"*64)

    def test_getter_does_not_claim_unselected_svg_integrity(self):
        changed = dict(self.files)
        changed[delivery.SVG_NAMES[1]] += b" "
        with memory_bundle(changed):
            self.assertEqual(delivery.get_view(ROOT, self.sha, delivery.IDS[0]), self.files[delivery.SVG_NAMES[0]])
        with memory_bundle(changed), self.assertRaises(delivery.DeliveryError):
            delivery.verify_bundle(ROOT, self.sha)

    def test_manifest_and_index_private_fields_refused(self):
        for which in ("MANIFEST.json", "viewer/INDEX.json"):
            changed = dict(self.files)
            data = delivery.strict_json(changed[which])
            data["private_reference"] = {"answer": 42}
            changed[which] = delivery.encoded(data)
            manifest = delivery.strict_json(changed["MANIFEST.json"])
            if which != "MANIFEST.json":
                manifest["files"][which] = delivery.pin(changed[which])
                changed["MANIFEST.json"] = delivery.encoded(manifest)
            new_sha = delivery.pin(changed["MANIFEST.json"])["sha256"]
            with self.subTest(which=which), memory_bundle(changed), self.assertRaises(delivery.DeliveryError):
                delivery.read_programme(ROOT, new_sha)

    def test_tiny_file_inventory_extra_and_symlink_refusal(self):
        # Empty ordinary files exercise inventory paths, not the payload reader.
        # No SVG or array fixture is written to disk.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            for name in ("programme", "viewer", "viewer/cells"):
                (root / name).mkdir()
            for name in ("MANIFEST.json", *delivery.PAYLOAD_NAMES):
                (root / name).touch()
            delivery._bundle_inventory(root)
            unexpected = root / "private-reference.json"
            unexpected.write_bytes(b"bad")
            with self.assertRaises(delivery.DeliveryError):
                delivery._bundle_inventory(root)
            unexpected.unlink()
            selected = root / delivery.SVG_NAMES[0]
            selected.unlink()
            selected.symlink_to(root / "MANIFEST.json")
            with self.assertRaises(delivery.DeliveryError):
                delivery._bundle_inventory(root)

    def test_preparation_loader_never_opens_private_numeric_values(self):
        prep = Path("/generated-neural096-preparation")
        participant = {"schema": "neural096-matched-participant-delivery/v1", "method": delivery.METHOD,
                       "files": {"observations.json": delivery.pin(self.body)},
                       "access": "Same aggregate observation in typed viewer and numerical programme conditions.",
                       "private_files_delivered": False, "runtime_or_model_delivery_qualified": False}
        participant_body = delivery.encoded(participant)
        files = {"participant/observations.json": delivery.pin(self.body),
                 "participant/MANIFEST.json": delivery.pin(participant_body),
                 "private/reference.json": {"bytes": 1, "sha256": "3"*64},
                 "private/expected-answer.json": {"bytes": 1, "sha256": "4"*64}}
        receipt_body = delivery.encoded({"schema": "neural096-descriptive-operator-preparation/v1",
                                        "method": delivery.METHOD, "files": files,
                                        "original_preparation": {"receipt_sha256": delivery.ORIGINAL_RECEIPT_SHA,
                                                                 "source_sha256": delivery.ORIGINAL_SOURCE_SHA}})
        complete_body = delivery.encoded({"schema": "neural096-preparation-completion/v1",
                                         "receipt": delivery.pin(receipt_body),
                                         "total_payload_bytes": len(receipt_body) + sum(x["bytes"] for x in files.values())})
        available = {"COMPLETE.json": complete_body, "private/RECEIPT.json": receipt_body,
                     "participant/observations.json": self.body, "participant/MANIFEST.json": participant_body}
        reads = []
        def read(path, limit):
            name = str(Path(path).relative_to(prep))
            reads.append(name)
            self.assertIn(name, available, "private numerical values must stay closed")
            self.assertLessEqual(len(available[name]), limit)
            return available[name]
        with mock.patch.object(delivery, "_inventory"), mock.patch.object(delivery, "bounded", read):
            body, binding = delivery.load_prepared_observation(prep, delivery.pin(complete_body)["sha256"])
        self.assertEqual(body, self.body)
        self.assertEqual(binding["observation"], delivery.pin(self.body))
        self.assertEqual(set(reads), set(available))


if __name__ == "__main__":
    unittest.main()
