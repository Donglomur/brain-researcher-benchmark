"""Focused metadata controls for the byte-preserving LANGUAGE decision relocation.

The production metadata pin/authentication/projection methods run unchanged.
The small read transport is a metadata fixture, not a filesystem security test.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
HOME = 'benchmarks/paper/PAPER-ROOT-ADD-001'
OLD = HOME+'/proposals/figure3b-improvement-scope-v1/ROOT_SELECTION.json'
NEW = HOME+'/docs/proposals/figure3b-improvement-scope-v1/ROOT_SELECTION.json'


def module(name, path):
    value = importlib.util.module_from_spec(importlib.util.spec_from_file_location(name, path))
    exec(compile(path.read_bytes(), str(path), 'exec'), value.__dict__)
    return value


s = module('language_relocated_successor', ROOT/'src/neurobench/paper_language_reference.py')
checker = module('language_relocation_pin_checker', ROOT/'src/neurobench/repository_checks.py')


class Transport:
    def __init__(self, changes=None, missing=()):
        self.changes, self.missing = changes or {}, set(missing)
        self.requested, self.charged = [], 0

    def document(self, name):
        self.requested.append(name)
        if name in self.missing:
            raise FileNotFoundError(name)
        raw = self.changes[name] if name in self.changes else (ROOT/name).read_bytes()
        self.charged += len(raw)
        if len(raw) > 8*1024**2 or self.charged > 32*1024**2:
            raise ValueError('Bounded metadata fixture')
        return json.loads(raw), {'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    def read_pin(self, pin, label):
        return checker.metadata_pin(self, pin, pin['path'], label)


def handle(transport):
    return s.authenticate(task_id=s.TASK, revision_pin=s.figure3b_pin('descriptor'),
        primary_pin=s.figure3b_pin('improvement'), reproduction_pin=s.approved_pin('reproduction'),
        previous_pin=s.approved_pin('pre_outcomes'), retained_improvement_pin=s.approved_pin('retained_improvement'),
        read_pin=transport.read_pin)


class LanguageRelocationTests(unittest.TestCase):
    def test_new_locator_projects_exact_task_and_keeps_policy_and_unknowns(self):
        transport = Transport()
        auth = handle(transport)
        documents, legacy = auth.snapshot(), auth._legacy.snapshot()
        actual = s.project(legacy['archived_task.json'], auth)
        current = transport.read_pin(s.figure3b_pin('task'), 'relocated task')
        self.assertEqual(actual, current)
        self.assertEqual(actual['figure3b_improvement_scope_selection']['path'], NEW[len(HOME)+1:])
        self.assertEqual(auth.public_provenance['figure3b_scope_decision']['path'], NEW)
        self.assertIn(NEW, transport.requested)
        self.assertNotIn(OLD, transport.requested)
        self.assertEqual(documents['outcomes'], transport.read_pin(s.figure3b_pin('outcomes'), 'relocated outcomes'))
        self.assertEqual(documents['outcomes']['original_task_sha256'], s.figure3b_pin('task')['sha256'])
        self.assertEqual(len(legacy['reproduction']['findings']), 171)
        self.assertEqual(documents['descriptor']['unchanged_reproduction'], s.approved_pin('reproduction'))
        self.assertEqual(documents['outcomes']['contracts']['reproduction'], s._APPROVED['reproduction']['canonical'])
        self.assertEqual(set(documents['outcomes']['pairing']), {'reproduction', 'improvement'})
        for value in documents['outcomes']['pairing'].values():
            self.assertEqual(value['status'], 'unresolved')
            self.assertIsNone(value['protocol'])
        self.assertFalse(documents['descriptor']['selected_original_scope']['binary_win_enabled'])

    def test_old_locator_and_old_descriptor_have_no_fallback(self):
        raw = (ROOT/NEW).read_bytes()
        transport = Transport({OLD: raw}, missing=(NEW,))
        with self.assertRaises(FileNotFoundError):
            handle(transport)
        self.assertIn(NEW, transport.requested)
        self.assertNotIn(OLD, transport.requested)
        old = dict(s.figure3b_pin('descriptor'), bytes=40983,
                   sha256='0939f193af792a43b45ea50d84ad73b89e683b168a8c3e7073563b50a11687c5')
        with self.assertRaisesRegex(ValueError, 'Unreviewed LANGUAGE descriptor selector'):
            s.authenticate(task_id=s.TASK, revision_pin=old, primary_pin=s.figure3b_pin('improvement'),
                reproduction_pin=s.approved_pin('reproduction'), previous_pin=s.approved_pin('pre_outcomes'),
                retained_improvement_pin=s.approved_pin('retained_improvement'), read_pin=Transport().read_pin)

    def test_decision_raw_bytes_and_parsed_identity_remain_fixed(self):
        raw = (ROOT/NEW).read_bytes()
        self.assertEqual(len(raw), 3075)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '4038501cc3050e8bbd7f1968c05768f9a0ed0322725f9e167466b694965cb762')
        self.assertEqual(s._digest(json.loads(raw)), '3bdb0ac24e1ee2a06282ffcfe6be16c7022fa48edd34224576ece4b7f8f3fc6e')
        for changed in (raw+b' ', s._encode(dict(json.loads(raw), unauthorized=True))):
            with self.subTest(kind=len(changed)), self.assertRaisesRegex(ValueError, 'pin mismatch'):
                handle(Transport({NEW: changed}))

    def test_partial_task_outcome_or_descriptor_updates_are_rejected(self):
        task_path, out_path, desc_path = (s.figure3b_pin(name)['path'] for name in ('task', 'outcomes', 'descriptor'))
        task = json.loads((ROOT/task_path).read_bytes())
        task['figure3b_improvement_scope_selection']['path'] = OLD[len(HOME)+1:]
        outcome = json.loads((ROOT/out_path).read_bytes())
        outcome['original_task_sha256'] = '99fdf60c53326351273fbcf083b5a6db8a321a0c6a08d6f082a40ad9c6c874f5'
        descriptor = json.loads((ROOT/desc_path).read_bytes())
        descriptor['root_decision']['path'] = OLD
        for path, value, name in ((task_path, task, 'task'), (out_path, outcome, 'outcomes'),
                                   (desc_path, descriptor, 'descriptor')):
            with self.subTest(member=name), self.assertRaisesRegex(ValueError, 'pin mismatch'):
                s._figure3b_read(name, Transport({path: s._encode(value)}).read_pin)

    def test_historical_preimages_scientific_scope_and_protocols_cannot_change(self):
        path = s.figure3b_pin('descriptor')['path']
        original = json.loads((ROOT/path).read_bytes())
        changes = []
        changed = copy.deepcopy(original)
        changed['task_replacements'][0]['before'] = 'unauthorized predecessor'
        changes.append(changed)
        changed = copy.deepcopy(original)
        changed['selected_original_scope']['sessions'] = 13
        changes.append(changed)
        changed = copy.deepcopy(original)
        after = next(v['after'] for v in changed['outcome_replacements'] if v['pointer'] == '/pairing')
        after['improvement']['protocol'] = {'unauthorized': True}
        changes.append(changed)
        for value in changes:
            with self.assertRaisesRegex(ValueError, 'pin mismatch'):
                handle(Transport({path: s._encode(value)}))


if __name__ == '__main__':
    unittest.main(verbosity=2)
