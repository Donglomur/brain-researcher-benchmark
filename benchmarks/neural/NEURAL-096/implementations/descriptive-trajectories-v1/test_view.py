"""Generated observation-only renderer controls; no authentic data or model."""
import copy
import unittest
import xml.etree.ElementTree as ET

import view


NS = {"s": "http://www.w3.org/2000/svg"}


def fixture():
    cells = []
    for index, (key, split, segment, eye, direction) in enumerate(view.ordered_cells()):
        local = index % 24
        count = 3 if split == "train" else 1
        cells.append({
            "cell_id": key, "source_split": split, "observation_segment": segment,
            "is_eye": eye, "theta": direction, "n_long": count + int(local < 6),
            "n_short": count,
            "long_rate_hz": [[float((unit + phase) % 5) for phase in range(20)] for unit in range(54)],
            "short_rate_hz": [[float((unit + phase + 1) % 5) for phase in range(20)] for unit in range(54)],
        })
    return {"schema": view.SCHEMA, "phase_bins": 20, "unit_ids": list(range(54)),
            "display_rate_max_hz": 4.0, "cells": cells}


class RendererControls(unittest.TestCase):
    def test_all_unit_bin_cells_and_shared_scale(self):
        observation = fixture()
        body = view.render_cell(observation, observation["cells"][0]["cell_id"])
        self.assertLessEqual(len(body), view.MAX_SVG_BYTES)
        root = ET.fromstring(body)
        self.assertEqual(root.attrib["width"], str(view.WIDTH))
        self.assertEqual(root.attrib["height"], str(view.HEIGHT))
        panels = [root.find(f'.//s:g[@id="{prior}-panel"]', NS) for prior in ("long", "short")]
        for panel in panels:
            self.assertEqual(panel.attrib["data-scale-min"], "0")
            self.assertEqual(panel.attrib["data-scale-max"], "4")
            rates = panel.findall('s:rect[@class="rate"]', NS)
            self.assertEqual(len(rates), 54 * 20)
            self.assertEqual({(int(r.attrib["data-unit"]), int(r.attrib["data-bin"])) for r in rates},
                             {(unit, phase) for unit in range(54) for phase in range(20)})
            labels = panel.findall('s:text[@data-unit-id]', NS)
            self.assertEqual([int(label.text) for label in labels], list(range(54)))
            self.assertEqual(sum(line.attrib["stroke-width"] == "1.5"
                                 for line in panel.findall('s:line', NS)), 5)
        long_rates = panels[0].findall('s:rect[@class="rate"]', NS)
        short_rates = panels[1].findall('s:rect[@class="rate"]', NS)
        self.assertEqual(long_rates[1].attrib["fill"], short_rates[0].attrib["fill"])
        self.assertEqual(long_rates[0].attrib["fill"], "#ffffff")
        self.assertEqual(long_rates[4].attrib["fill"], "#0000ff")

    def test_support_absence_is_visible_and_not_zero_filled(self):
        observation = fixture()
        cell = observation["cells"][24]
        cell["n_short"] = 0
        cell["short_rate_hz"] = None
        cell["supported"] = False
        cell["missing_priors"] = ["short"]
        observation["cells"][25]["n_short"] += 1
        body = view.render_cell(observation, cell["cell_id"])
        root = ET.fromstring(body)
        panel = root.find('.//s:g[@id="short-panel"]', NS)
        self.assertEqual(len(panel.findall('s:rect[@class="rate"]', NS)), 0)
        self.assertIn("UNSUPPORTED: no trials", body.decode())
        self.assertIn("Short prior — n = 0", body.decode())
        cell["short_rate_hz"] = [[0.0] * 20 for _ in range(54)]
        with self.assertRaisesRegex(view.ViewError, "absent prior"):
            view.render_cell(observation, cell["cell_id"])

    def test_rejects_unknown_cell_reordered_incomplete_and_counts(self):
        observation = fixture()
        with self.assertRaisesRegex(view.ViewError, "unknown"):
            view.render_cell(observation, "any-file-or-query")
        with self.assertRaisesRegex(view.ViewError, "exact string"):
            view.render_cell(observation, {"cell_id": "train-segment0-eye0-direction0"})
        for mutation in ("reorder", "missing", "counts"):
            wrong = copy.deepcopy(observation)
            if mutation == "reorder":
                wrong["cells"][0], wrong["cells"][1] = wrong["cells"][1], wrong["cells"][0]
            elif mutation == "missing":
                wrong["cells"].pop()
            else:
                wrong["cells"][0]["n_long"] -= 1
            with self.subTest(mutation=mutation), self.assertRaises(view.ViewError):
                view.render_cell(wrong, observation["cells"][0]["cell_id"])

    def test_rejects_unselected_bad_matrix_and_clip_or_rescale(self):
        observation = fixture()
        for value in (float("nan"), float("inf"), -1, True, "3"):
            wrong = copy.deepcopy(observation)
            wrong["cells"][-1]["short_rate_hz"][-1][-1] = value
            with self.subTest(value=value), self.assertRaises(view.ViewError):
                view.render_cell(wrong, observation["cells"][0]["cell_id"])
        for scale in (3.0, 5.0, 0.0):
            wrong = copy.deepcopy(observation)
            wrong["display_rate_max_hz"] = scale
            with self.subTest(scale=scale), self.assertRaises(view.ViewError):
                view.render_cell(wrong, observation["cells"][0]["cell_id"])
        wrong = copy.deepcopy(observation)
        wrong["cells"][-1]["short_rate_hz"].pop()
        with self.assertRaisesRegex(view.ViewError, "unit rows"):
            view.render_cell(wrong, observation["cells"][0]["cell_id"])

    def test_no_injected_labels_reference_fields_or_external_content(self):
        observation = fixture()
        for field, value in (("cell_id", '<script>alert(1)</script>'), ("theta", "180")):
            wrong = copy.deepcopy(observation)
            wrong["cells"][0][field] = value
            with self.subTest(field=field), self.assertRaises(view.ViewError):
                view.render_cell(wrong, observation["cells"][0]["cell_id"])
        wrong = copy.deepcopy(observation)
        wrong["unit_ids"][0] = '<image href="https://example.invalid"/>'
        with self.assertRaisesRegex(view.ViewError, "integer source units"):
            view.render_cell(wrong, observation["cells"][0]["cell_id"])
        wrong = copy.deepcopy(observation)
        wrong["cells"][0]["reference_difference"] = "SECRET_REFERENCE"
        with self.assertRaisesRegex(view.ViewError, "declared observation"):
            view.render_cell(wrong, observation["cells"][0]["cell_id"])
        observation["unused_operator_field"] = "SECRET_REFERENCE"
        body = view.render_cell(observation, observation["cells"][0]["cell_id"])
        root = ET.fromstring(body)
        self.assertNotIn(b"SECRET_REFERENCE", body)
        self.assertIsNone(root.find('.//s:script', NS))
        self.assertFalse(any("href" in key for item in root.iter() for key in item.attrib))

    def test_full_signed_int64_unit_ids_and_all_zero_convention(self):
        observation = fixture()
        observation["unit_ids"][0] = -(2**63)
        for cell in observation["cells"]:
            cell["long_rate_hz"] = [[0.0] * 20 for _ in range(54)]
            cell["short_rate_hz"] = [[0.0] * 20 for _ in range(54)]
        observation["display_rate_max_hz"] = 1.0
        body = view.render_cell(observation, observation["cells"][0]["cell_id"])
        root = ET.fromstring(body)
        rates = root.findall('.//s:rect[@class="rate"]', NS)
        self.assertEqual({rate.attrib["fill"] for rate in rates}, {"#ffffff"})
        self.assertIn(str(-(2**63)).encode(), body)


if __name__ == "__main__":
    unittest.main()
