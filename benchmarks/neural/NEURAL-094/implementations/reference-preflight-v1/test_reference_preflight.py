"""Generated complete-cohort custody controls; no authentic observations or fits."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
TASK = Path(os.environ.get('NEURAL094_TASK_ROOT', str(HERE.parents[1])))
NUMERICS = TASK / 'implementations/regional-comparison/complete_regional/source/numerics'


def load(name, path, expected=None):
    raw = path.read_bytes()
    if expected is not None:
        assert hashlib.sha256(raw).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load('n094_preflight_old', TASK / 'implementations/stable-loss-v2/score_adapter.py',
           'd88210d05247d95ca6ac244fadf549b07c4ff2889d4ed475639c5aa3b342db78')
new = load('n094_preflight_new', HERE / 'score_adapter.py')
core = load('n094_preflight_core', NUMERICS / 'metric_core.py',
            '41da920bd4d1d7ba1932e2ba9b6e37bf85a119276cdeb771e2d5218c5445ed60')
validator = load('n094_preflight_validator', NUMERICS / 'validator.py')


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def encoded(doc):
    return json.dumps(doc, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def descriptor(path, raw):
    return {'path': path, **new.short_pin(raw)}


class GeneratedCohort:
    """Invented 39-session/10-mouse interface with actual manifest validation."""
    def __init__(self):
        self.candidate_sha256, self.reference_sha256 = digest('candidate'), digest('reference')
        self.public, self.roster, self.saved = [], [], []
        self.references, self.private, self.calls = {}, {}, []
        for i in range(39):
            session_token = digest(f'session-{i}')
            tokens = [digest(f'case-{i}-{j}') for j in range(10)]
            packets, predictions, public_pins, arms = {}, {}, {}, {}
            for arm in new.ARMS:
                manifest = {'schema': 'neural094-candidate-public-packet-v1',
                    'candidate_id': 'NEURAL-094', 'arm': arm, 'phase': 'query',
                    'session_token': session_token, 'case_tokens': tokens,
                    'case_splits': ['query'] * 10,
                    'unit_count': int(arm == new.ARMS[1]),
                    'wheel_observations_present': True,
                    'neural_observations_present': arm == new.ARMS[1],
                    'query_labels_present': False, 'observation': validator.OBSERVATION,
                    'files': {name: {'bytes': 1, 'sha256': digest(f'{i}-{name}'), 'role': role}
                              for name, role in validator.roles(arm, 'query').items()}}
                raw = encoded(manifest)
                public_pins[arm] = descriptor(f'public/{i}/{arm}.json', raw)
                packets[arm] = {'pin': public_pins[arm], 'body': raw}
                prediction = {'schema': 'neural094-candidate-predictions-v1', 'arm': arm,
                    'session_token': session_token, 'candidate_sha256': self.candidate_sha256,
                    'class_order': list(new.CLASS_ORDER),
                    'predictions': [{'token': token, 'probabilities': [0.5, 0.3, 0.2]}
                                    for token in tokens]}
                predictions[arm] = encoded(prediction)
                arms[arm] = {'prediction': descriptor(f'predictions/{i}/{arm}.json', predictions[arm]),
                    'public_manifest': public_pins[arm], 'sealed_readonly': True,
                    'captured_after_producer_absence': True, 'producer_closed': True}
            private = {'schema': 'neural094-candidate-private-session-v1', 'candidate_id': 'NEURAL-094',
                'execution_authority': False, 'ordinal': i + 1, 'session': f'generated-session-{i}',
                'mouse': f'generated-mouse-{i % 10}', 'session_token': session_token,
                'source_row_or_unit_filtering_for_export_size': False,
                'source_integrity': {'choice_eligibility_unchanged_from093_source_geometry': True,
                                     'all39_support_passed': True},
                'public_manifests': {arm: {'query': public_pins[arm]} for arm in new.ARMS},
                'query': [{'token': token, 'source_row': j, 'target': j % 3}
                          for j, token in enumerate(tokens)]}
            raw = encoded(private)
            private_pin = descriptor(f'private/{i}.json', raw)
            self.private[private_pin['path']] = raw
            row = {key: private[key] for key in ('ordinal', 'session', 'mouse', 'session_token')}
            row.update(query_tokens=tokens, query_source_rows=list(range(10)),
                       public_manifests=public_pins, private_mapping=private_pin)
            self.roster.append(row)
            reference = {'schema': 'neural094-trusted-reference-predictions-v1',
                'reference_sha256': self.reference_sha256, 'ordinal': i + 1,
                'session_token': session_token, 'class_order': list(new.CLASS_ORDER),
                'query_tokens': tokens, 'query_source_rows': list(range(10)),
                'fresh094_choice_reference': True, 'selected_on_fit_validation_only': True,
                'refit_on_fit_validation_only': True, 'query_targets_used_for_fit_or_selection': False,
                'views': {view: [{'token': token, 'probabilities': [0.2, 0.4, 0.4]} for token in tokens]
                          for view in new.REFERENCES}}
            raw = encoded(reference)
            ref_pin = descriptor(f'references/{i}.json', raw)
            self.references[ref_pin['path']] = raw
            self.saved.append({'ordinal': i + 1, 'session_token': session_token,
                'models_committed_before_either_query': True, 'arms': arms,
                'trusted_reference_prediction': ref_pin,
                'trusted_reference_closed_before_private_grading': True})
            self.public.append({'ordinal': i + 1, 'session_token': session_token,
                                'query_packets': packets, 'predictions': predictions})
        self.commit = {'schema': 'neural094-all39-both-arm-prediction-commit-v1',
            'status': 'all78_predictions_committed_before_private_grading',
            'candidate_sha256': self.candidate_sha256, 'reference_sha256': self.reference_sha256,
            'private_grading_started': False, 'all_candidate_producers_stopped': True,
            'all_candidate_owned_resources_absent': True, 'sessions': self.saved}

    def private_loader(self, pin):
        self.calls.append(('private', pin['path']))
        return self.private[pin['path']]

    def reference_loader(self, pin):
        self.calls.append(('reference', pin['path']))
        return self.references[pin['path']]

    def score(self, module):
        return module.score_cohort(self.public, self.commit, self.roster,
            self.candidate_sha256, self.reference_sha256,
            self.private_loader, self.reference_loader, core, validator, np)

    def alter_reference(self, change, *, repin=True):
        pin = self.saved[-1]['trusted_reference_prediction']
        doc = json.loads(self.references[pin['path']])
        change(doc)
        raw = encoded(doc)
        self.references[pin['path']] = raw
        if repin:
            pin.update(new.short_pin(raw))


class ReferencePreflightControls(unittest.TestCase):
    def test_late_malformed_reference_reproduces_old_target_exposure(self):
        cohort = GeneratedCohort()
        cohort.alter_reference(lambda doc: doc['views']['selected_context'].pop())
        with self.assertRaisesRegex(ValueError, 'Complete required output rows'):
            cohort.score(old)
        self.assertEqual(sum(kind == 'private' for kind, _ in cohort.calls), 39)
        cohort.calls.clear()
        with self.assertRaisesRegex(ValueError, 'Complete required output rows'):
            cohort.score(new)
        self.assertEqual(sum(kind == 'reference' for kind, _ in cohort.calls), 39)
        self.assertFalse(any(kind == 'private' for kind, _ in cohort.calls))

    def test_complete_reference_bank_precedes_targets_and_preserves_score(self):
        cohort = GeneratedCohort()
        prior = cohort.score(old)
        cohort.calls.clear()
        actual = cohort.score(new)
        self.assertEqual([kind for kind, _ in cohort.calls], ['reference'] * 39 + ['private'] * 39)
        self.assertEqual(len(set(cohort.calls)), 78)
        self.assertEqual(actual.pop('trusted_reference_tables_validated_before_any_private_callback'), 39)
        self.assertEqual(actual.pop('trusted_reference_views_validated_before_any_private_callback'), 156)
        self.assertEqual(actual, prior)
        self.assertEqual(actual['required_mice'], 10)
        self.assertEqual(actual['required_sessions'], 39)
        self.assertEqual(actual['primary_contrast'], old.PRIMARY)

    def test_late_missing_reference_refuses_before_targets(self):
        cohort = GeneratedCohort()
        del cohort.references[cohort.saved[-1]['trusted_reference_prediction']['path']]
        with self.assertRaises(KeyError):
            cohort.score(new)
        self.assertFalse(any(kind == 'private' for kind, _ in cohort.calls))

    def test_late_stale_reference_bytes_refuse_before_targets(self):
        cohort = GeneratedCohort()
        cohort.alter_reference(lambda doc: doc.update(class_order=['left', 'NoGo', 'right']), repin=False)
        with self.assertRaisesRegex(ValueError, 'Exact frozen fresh094 reference prediction bytes'):
            cohort.score(new)
        self.assertFalse(any(kind == 'private' for kind, _ in cohort.calls))

    def test_all_reference_views_validate_probabilities_before_targets(self):
        for view in new.REFERENCES:
            with self.subTest(view=view):
                cohort = GeneratedCohort()
                cohort.alter_reference(lambda doc: doc['views'][view][-1].update(probabilities=[1, 1, 1]))
                with self.assertRaisesRegex(ValueError, 'probability sum tolerance'):
                    cohort.score(new)
                self.assertFalse(any(kind == 'private' for kind, _ in cohort.calls))

    def test_candidate_failure_precedes_any_loader(self):
        cohort = GeneratedCohort()
        arm = new.ARMS[-1]
        raw = cohort.public[-1]['predictions'][arm]
        doc = json.loads(raw)
        doc['predictions'].pop()
        raw = encoded(doc)
        cohort.public[-1]['predictions'][arm] = raw
        cohort.saved[-1]['arms'][arm]['prediction'].update(new.short_pin(raw))
        with self.assertRaisesRegex(ValueError, 'Complete required output rows'):
            cohort.score(new)
        self.assertEqual(cohort.calls, [])


if __name__ == '__main__':
    print(f'Generated controls only; Python {sys.version.split()[0]}, NumPy {np.__version__}; no native qualification.', flush=True)
    unittest.main(verbosity=2)
