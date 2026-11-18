"""Generated public-only controls; never opens authentic data or a private target."""
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural035_test_viewer", HERE / "viewer.py")
viewer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = viewer
spec.loader.exec_module(viewer)
core_path = HERE.parent / "astrocyte-programme" / "program" / "order_core.py"
core_spec = importlib.util.spec_from_file_location("neural035_existing_admission", core_path)
core = importlib.util.module_from_spec(core_spec)
core_spec.loader.exec_module(core)


def opaque(label):
    return hashlib.sha256(label.encode()).hexdigest()


class GeneratedArray:
    """Generated array ABI witness, not a NumPy or authentic packet qualification."""
    def __init__(self, blocks, cells):
        self.shape = (blocks, 300, cells)
        self.offset = 0

    def __getitem__(self, index):
        block, sample, cell = index
        if cell == 0:
            return -1e308 if sample % 2 == 0 else 1e308
        if cell == 1:
            return 7.0
        if cell == 2:
            return 5e-324 if sample % 2 == 0 else 1e-323
        return float((sample + 7 * cell + block * 13) % 300 + self.offset)


class Poison:
    @property
    def shape(self):
        raise AssertionError("unadmitted array accessed")


def generated_rows():
    rows = []
    for i, cells in enumerate([73] * 4 + [72] * 10):
        sid = opaque(f"generated-session-{i}")
        meta = {"session_id": sid, "cell_ids": [opaque(f"generated-cell-{i}-{c}") for c in range(cells)],
                "file": sid + '.npz', "bytes": 1, "sha256": opaque(f"generated-hash-{i}"),
                "calibration_starts_seconds": [0, 30, 60, 90], "validation_starts_seconds": [150],
                "queries": [{"query_id": opaque(f"generated-query-{i}-{q}"), "start_seconds": start}
                            for q, start in enumerate([210, 270])]}
        rows.append({"metadata": meta, "calibration": GeneratedArray(4, cells),
                     "validation": GeneratedArray(1, cells)})
    return rows


class ViewerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = generated_rows()
        cls.manifest = copy.deepcopy({"schema": "neural035-public-v1", "sessions": [r['metadata'] for r in cls.rows]})
        cls.observations = viewer.Observations.from_loaded(cls.rows)

    def setUp(self):
        self.view = viewer.Viewer(self.observations)
        self.first = self.observations.sessions[0]

    def render(self, cells, block=0):
        return self.view.act({"action": "view", "session_id": self.first.session_id, "block": block, "cells": cells})

    def test_catalogue_retains_complete_public_support_without_source_file_fields(self):
        result = self.view.act({"action": "catalogue"})
        self.assertEqual(len(result['sessions']), 14)
        self.assertEqual(sum(len(s['cell_ids']) for s in result['sessions']), 1012)
        self.assertEqual(sum(len(s['queries']) for s in result['sessions']), 28)
        for s in result['sessions']:
            self.assertEqual(set(s), {'session_id', 'cell_ids', 'queries'})
            self.assertEqual([q['start_seconds'] for q in s['queries']], [210, 270])
        result['sessions'][0]['cell_ids'].clear()
        self.assertEqual(len(self.view.act({'action': 'catalogue'})['sessions'][0]['cell_ids']), 73)

    def test_all_five_blocks_render_every_sample_and_extreme_finite_values(self):
        ns = {'s': 'http://www.w3.org/2000/svg'}
        for block in range(5):
            result = self.render([0, 1, 2, 72], block)
            root = ET.fromstring(result['svg'])
            lines = root.findall('s:polyline', ns)
            self.assertEqual(len(lines), 4)
            for line in lines:
                points = [tuple(map(float, p.split(','))) for p in line.attrib['points'].split()]
                self.assertEqual(len(points), 300)
                self.assertGreater(points[0][0], 90)
                self.assertLess(points[-1][0], 1080)
                self.assertTrue(all(b[0] > a[0] for a, b in zip(points, points[1:])))
                self.assertTrue(all(75 <= p[1] <= 690 for p in points))
            self.assertEqual(len({p.split(',')[1] for p in lines[1].attrib['points'].split()}), 1)
            self.assertNotIn('href=', result['svg'])
            self.assertNotIn('<script', result['svg'])
            self.assertLessEqual(len(result['svg'].encode()), viewer.SVG_CAP)

    def test_no_future_block_or_untyped_selection_or_query_array_action(self):
        for bad in [5, 210, -1, True, 0.0, 'validation']:
            with self.assertRaises(ValueError): self.render([0], bad)
        for bad in [[], [0, 0], [True], [-1], [73], list(range(9))]:
            with self.assertRaises(ValueError): self.render(bad)
        with self.assertRaises(ValueError):
            self.view.act({'action': 'view', 'session_id': self.first.session_id,
                           'block': 0, 'cells': [0], 'path': '/private/query.npz'})
        with self.assertRaises(ValueError): self.view.act({'action': 'query_trace'})
        self.assertEqual(self.view._views, 0)

    def test_duplicate_json_nonfinite_unknown_keys_and_oversize_are_rejected(self):
        cases = [b'{"action":"catalogue","action":"finish"}',
                 b'{"action":"answer","query_id":"x","ordering_scores":[NaN]}',
                 b'{"action":"catalogue","data":true}', b'\xff', b'{}',
                 b' ' * (viewer.REQUEST_CAP + 1)]
        for raw in cases:
            with self.assertRaises(ValueError): self.view.handle(raw)
        self.assertEqual(self.view.handle(b'{"action":"catalogue"}')['kind'], 'catalogue')

    def test_answer_is_atomic_and_immutable_and_covers_every_cell(self):
        qid = self.first.queries[0][0]
        valid = [.5] * len(self.first.cell_ids)
        for bad in [valid[:-1], [True] + valid[1:], [float('inf')] + valid[1:],
                    [-.001] + valid[1:], [1.001] + valid[1:]]:
            with self.assertRaises(ValueError):
                self.view.act({'action': 'answer', 'query_id': qid, 'ordering_scores': bad})
        self.assertEqual(self.view._answers, {})
        self.view.act({'action': 'answer', 'query_id': qid, 'ordering_scores': valid})
        valid[0] = .25
        self.assertEqual(self.view._answers[qid][0], .5)
        with self.assertRaises(ValueError):
            self.view.act({'action': 'answer', 'query_id': qid, 'ordering_scores': valid})

    def test_complete_export_passes_existing_original_output_admission(self):
        with self.assertRaises(ValueError): self.view.act({'action': 'finish'})
        rows = [(s, qid) for s in self.observations.sessions for qid, _ in s.queries]
        for index, (s, qid) in enumerate(reversed(rows)):
            scores = [c / (len(s.cell_ids)-1) for c in range(len(s.cell_ids))]
            self.view.act({'action': 'answer', 'query_id': qid, 'ordering_scores': scores})
            if index == 26:
                with self.assertRaises(ValueError): self.view.act({'action': 'finish'})
        result = self.view.act({'action': 'finish'})
        doc = json.loads(result['submission'])
        accepted = core.validate_submission(doc, self.manifest)
        self.assertEqual(len(accepted), 28)
        self.assertEqual([r['query_id'] for r in doc['predictions']], [q for _, q in rows])
        self.assertLessEqual(len(result['submission']), viewer.SUBMISSION_CAP)
        for action in ['catalogue', 'finish']:
            with self.assertRaises(ValueError): self.view.act({'action': action})

    def test_view_budget_does_not_prevent_complete_answer_collection(self):
        self.view._views = viewer.VIEW_BUDGET
        with self.assertRaises(ValueError): self.render([0])
        for s in self.observations.sessions:
            for qid, _ in s.queries:
                self.view.act({'action': 'answer', 'query_id': qid, 'ordering_scores': [.5]*len(s.cell_ids)})
        self.assertEqual(self.view.act({'action': 'finish'})['kind'], 'submission')

    def test_manifest_rejection_precedes_array_access(self):
        rows = [{'metadata': copy.deepcopy(s), 'calibration': Poison(), 'validation': Poison()}
                for s in self.manifest['sessions']]
        rows[0]['metadata']['queries'][0]['start_seconds'] = 150
        with self.assertRaisesRegex(ValueError, 'original ordered query windows'):
            viewer.Observations.from_loaded(rows)
        rows[0]['metadata']['queries'][0]['start_seconds'] = 210
        rows[0]['private_queries'] = object()
        with self.assertRaisesRegex(ValueError, 'only loaded public fields'):
            viewer.Observations.from_loaded(rows)

    def test_geometry_is_complete_before_copy_and_nonfinite_fails(self):
        rows = generated_rows()
        rows[0]['calibration'].shape = (4, 299, 73)
        with self.assertRaisesRegex(ValueError, 'complete public array geometry'):
            viewer.Observations.from_loaded(rows)
        rows = generated_rows()
        class Nonfinite(GeneratedArray):
            def __getitem__(self, index): return float('nan')
        rows[0]['calibration'] = Nonfinite(4, 73)
        with self.assertRaisesRegex(ValueError, 'finite numeric value'):
            viewer.Observations.from_loaded(rows)

    def test_copied_observations_do_not_follow_operator_input_mutation(self):
        before = self.render([3])['svg']
        self.rows[0]['calibration'].offset += 1000
        self.assertEqual(self.render([3])['svg'], before)
        self.rows[0]['calibration'].offset -= 1000

    def test_direct_constructor_rejects_collapsed_sessions_queries_and_cell_cohort(self):
        original = self.observations.sessions
        s = original[0]
        variants = [
            (original[1],) + original[1:],
            (replace(s, queries=original[1].queries),) + original[1:],
            (replace(s, queries=((s.queries[0][0], 150), s.queries[1])),) + original[1:],
            (replace(s, cell_ids=s.cell_ids[:-1],
                     blocks=tuple(block[:-1] for block in s.blocks)),) + original[1:],
            (replace(s, cell_ids=(s.cell_ids[1],) + s.cell_ids[1:]),) + original[1:],
        ]
        for sessions in variants:
            with self.subTest(kind=repr(sessions[0].queries)):
                with self.assertRaises(ValueError): viewer.Viewer(viewer.Observations(sessions))

    def test_direct_constructor_rejects_truncated_mutable_or_nonfinite_traces(self):
        original = self.observations.sessions
        s = original[0]
        shortened = (s.blocks[0][0][:-1],) + s.blocks[0][1:]
        nonfinite = ((float('nan'),) + s.blocks[0][0][1:],) + s.blocks[0][1:]
        boolean = ((True,) + s.blocks[0][0][1:],) + s.blocks[0][1:]
        malformed = [s.blocks[:-1], (s.blocks[0][:-1],) + s.blocks[1:],
                     (shortened,) + s.blocks[1:], (nonfinite,) + s.blocks[1:],
                     (boolean,) + s.blocks[1:], list(s.blocks)]
        for blocks in malformed:
            with self.assertRaises(ValueError):
                viewer.Viewer(viewer.Observations((replace(s, blocks=blocks),) + original[1:]))

    def test_direct_constructor_requires_immutable_record_types(self):
        for bad in [viewer.Observations(list(self.observations.sessions)),
                    viewer.Observations(self.observations.sessions[:-1]),
                    viewer.Observations((object(),) + self.observations.sessions[1:])]:
            with self.assertRaises(ValueError): viewer.Viewer(bad)


if __name__ == '__main__':
    unittest.main(verbosity=1)
