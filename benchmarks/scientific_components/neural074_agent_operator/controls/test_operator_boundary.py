"""Prospective finite engineering controls; NOT native/scientific qualification.

No production data or programme is used. The owner is an explicit in-process
inert double that interprets one literal assignment; it starts no subprocess.
Root must separately select execution, imports, NumPy and fresh temporary roots.
"""
import ast
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from n074.catalogue import DECLARED_PEOPLE, DECLARED_ENDPOINTS
from n074.programme import ProgrammeResult, Prediction
from n074.maps import MapValue
from n074.models import ARMS
from n074_operator.owned_io import Budget, Pin, Tree, Refusal, json_bytes, canonical_path
from n074_operator.selection import Selection, TrainingReader, ProtectedOwner
from n074_operator.host_contract import Carrier, Programme, HostPolicy, OwnerAdmission, OwnerReceipt
from n074_operator.candidate import (run_candidate, CandidateFailure, content_pin, identity,
                                     programme_identity, validate_receipt)
from n074_operator.packet import commit_packet, evaluate_committed, load_committed


def allowance():
    return Budget(read_bytes=16 * 1024 * 1024, write_bytes=16 * 1024 * 1024,
                  file_operations=10000, seconds=60)


def publish(path, body):
    path.write_bytes(body)
    return content_pin(body)


class InertOwner:
    """Engineering double only. These receipts cannot qualify the native owner."""
    def __init__(self, policy, status='completed', closed=True):
        self.policy, self.status, self.closed = policy, status, closed
        self.calls = 0

    def authenticate_selected_owner(self):
        p = self.policy
        return OwnerAdmission(p.identity, p.owner_source_identity, p.image_identity, p.qualification_identity)

    def run_fresh(self, programme, request, policy):
        self.calls += 1
        raw = Tree(programme.programme.root).capture(programme.programme.path, programme.programme.pin, allowance())
        syntax = ast.parse(raw.decode())
        if len(syntax.body) != 1 or type(syntax.body[0]) is not ast.Assign:
            raise ValueError('Only the selected inert literal assignment exists in this control owner')
        row = ast.literal_eval(syntax.body[0].value)  # no programme exec, imports or native process
        if type(row) is not tuple or len(row) != request.map_length:
            raise ValueError('Wrong inert row extent')
        output = Path(request.output_root); output.mkdir(mode=0o700)
        output_pin = None
        if self.status == 'completed':
            output_pin = publish(output/'predictions.f64', struct.pack('<' + 'd' * len(row), *row) * len(request.query_endpoints))
        context = 'inert-engineering-context-' + str(self.calls)
        evidence_root = Path(request.output_root + '-owner-evidence'); evidence_root.mkdir(mode=0o700)
        evidence_doc = {'schema': 'n074-native-owner-evidence-v1',
            'request_identity': request.identity, 'programme_identity': programme.identity,
            'policy_identity': policy.identity, 'owner_source_identity': policy.owner_source_identity,
            'image_identity': policy.image_identity, 'qualification_identity': policy.qualification_identity,
            'context_identity': context, 'output_root': request.output_root,
            'input_manifest': request.input_manifest.document(), 'producers_closed': self.closed,
            'all_owned_absent': self.closed, 'status': self.status,
            'output': None if output_pin is None else output_pin.document(),
            'native': {'engineering_inert_double_only': True, 'native_execution': False}}
        ep = publish(evidence_root/'evidence.json', json_bytes(evidence_doc, policy.maximum_metadata_bytes))
        return OwnerReceipt(request.identity, programme.identity, policy.identity, context,
            policy.owner_source_identity, policy.image_identity, policy.qualification_identity,
            request.input_manifest, request.output_root, self.closed, self.closed, self.status,
            None if self.status == 'completed' else 'inert intentional candidate failure', output_pin,
            Carrier(str(evidence_root), 'evidence.json', ep))


class OperatorBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='n074-operator-engineering-only-')
        cls.root = Path(cls.temp.name).resolve(strict=True)
        for name in ('training', 'targets', 'submission'):
            (cls.root/name).mkdir(mode=0o700)
        endpoints = [{'identity': i, 'task': task, 'contrast': contrast, 'family': task,
                      'dependency_group': task} for i, task, contrast in DECLARED_ENDPOINTS]
        first_person, first_family = DECLARED_PEOPLE[0], endpoints[0]['family']
        cases, descriptors = [], []
        raw = struct.pack('<dddd', 1., 2., 3., 4.); map_pin = content_pin(raw)
        for person in DECLARED_PEOPLE:
            for endpoint in endpoints:
                present = person != first_person or endpoint['family'] == first_family
                source = 'ENGINEERING_ONLY:' + person + ':' + endpoint['identity'] if present else None
                cases.append({'person': person, 'endpoint': endpoint['identity'],
                    'status': 'present' if present else 'absent', 'reason': 'inert engineering roster only',
                    'source_identity': source})
                if present:
                    name = 'map-%06d.f64' % len(descriptors)
                    descriptors.append({'person': person, 'endpoint': endpoint['identity'],
                                        'source_identity': source, 'path': name, 'pin': map_pin.document()})
                    publish(cls.root/'training'/name, raw); publish(cls.root/'targets'/name, raw)
        support = {'selection_identity': 'engineering-support-selection', 'protocol_identity': 'engineering-protocol',
            'taxonomy_identity': 'engineering-task-family', 'eligibility_identity': 'engineering-eligibility',
            'support_identity': 'engineering-four-values', 'map_length': 4, 'dtype': '<f8'}
        doc = {'schema': 'n074-agent-comparison-selection-v1', 'population': {'people': list(DECLARED_PEOPLE),
            'endpoints': endpoints, 'cases': cases, 'declaration_pin': 'engineering-declaration',
            'taxonomy_pin': support['taxonomy_identity'], 'eligibility_pin': support['eligibility_identity']},
            'designs': [{'endpoint': e['identity'], 'text': e['contrast'], 'coefficients': [],
                         'provenance': 'engineering-metadata-only'} for e in endpoints],
            'protocol': {'configurations': [{'rank': 1, 'component_penalty': 0., 'ridge_penalty': 1.,
                'max_iterations': 1, 'relative_tolerance': 1e-6}], 'tuning_metric': 'mean_squared_error',
                'spatial_support_identity': support['support_identity'], 'selection_identity': support['protocol_identity'],
                'max_fits': 1000000}, 'support': support, 'maps': descriptors,
            'maximum_map_bytes': 32, 'maximum_panel_prediction_bytes': 4 * 663 * 32,
            'scientific_decisions_identity': 'ENGINEERING_ONLY_NOT_SCIENTIFIC_SELECTION'}
        pin = publish(cls.root/'training'/'selection.json', json_bytes(doc, 2 * 1024 * 1024))
        cls.selection = Selection.load(Tree(str(cls.root/'training')), 'selection.json', pin, allowance())
        target_doc = {'schema': 'n074-protected-target-selection-v1', 'selection_identity': cls.selection.identity,
                      'support': support, 'maps': descriptors}
        cls.target_doc = target_doc
        cls.target_pin = publish(cls.root/'targets'/'targets.json', json_bytes(target_doc, 2 * 1024 * 1024))
        program_pin = publish(cls.root/'submission'/'program.py', b'prediction = (1.0, 2.0, 3.0, 4.0)\n')
        method_pin = publish(cls.root/'submission'/'method.txt', b'Inert engineering fixture; no scientific method or result.\n')
        cls.programme = Programme(Carrier(str(cls.root/'submission'), 'program.py', program_pin),
            Carrier(str(cls.root/'submission'), 'method.txt', method_pin), programme_identity(program_pin, method_pin))
        policy = HostPolicy('unset', 'engineering-inert-owner-only', 'engineering-no-container-image',
            hashlib.sha256(b'NOT_A_NATIVE_QUALIFICATION').hexdigest(), 3, 1, 1000, 1048576, 1, 1,
            1048576, 1048576, 1024, 1024, 1024, 262144)
        cls.policy = replace(policy, identity=identity({k: v for k, v in asdict(policy).items()
            if k not in ('identity', 'qualification_identity')}))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.local = Path(tempfile.mkdtemp(prefix='case-', dir=self.root))
        self.budget, self.eval_budget = allowance(), allowance()
        self.reader = TrainingReader(self.selection, Tree(str(self.root/'training')), self.budget)
        self.targets = ProtectedOwner(self.selection, self.reader.tree, Tree(str(self.root/'targets')),
                                      'targets.json', self.target_pin, self.eval_budget)
        self.target_calls = []
        original = self.targets.read_protected_target
        def counted(*args):
            self.target_calls.append(args)
            return original(*args)
        self.targets.read_protected_target = counted

    def build(self, owner=None):
        owner = InertOwner(self.policy) if owner is None else owner
        candidate = run_candidate(self.selection, self.programme, self.policy, self.reader, owner,
                                  str(self.local/'workspace'), self.budget)
        references = []
        for row in candidate.predictions:
            for arm in ARMS:
                value = None
                if row.value is not None:
                    value = replace(row.value, source_identity='P1:' + row.person + ':' + row.endpoint + ':' + arm)
                references.append(Prediction(row.person, row.family, row.endpoint, arm,
                    'predicted' if value is not None else 'ineligible_support', value,
                    None if value is not None else 'inert reference disposition'))
        s = self.selection
        reference = ProgrammeResult(s.protocol.selection_identity, s.population.taxonomy_pin,
            s.population.eligibility_pin, s.support.support_identity, tuple(references), (), (),
            'ENGINEERING_INERT_REFERENCE_ONLY', (), 'complete_source_attempt')
        return candidate, reference, owner

    def commit(self, candidate, reference):
        return commit_packet(self.selection, candidate, reference, self.programme, self.policy,
            str(self.local/'packet'), (str(self.root/'training'), str(self.root/'targets'), str(self.local/'workspace')),
            allowance(), 2 * 1024 * 1024)

    def test_actual_submission_commit_and_separate_evaluation(self):
        candidate, reference, owner = self.build()
        self.assertEqual(owner.calls, 1)
        self.assertEqual(len(candidate.predictions), 663)
        self.assertEqual(len(reference.predictions), 1989)
        committed = self.commit(candidate, reference)
        self.assertEqual(self.target_calls, [])
        loaded, refs = load_committed(self.selection, committed, self.programme, self.policy, allowance(), 2 * 1024 * 1024)
        self.assertEqual(loaded, candidate); self.assertEqual(refs, reference)
        result = evaluate_committed(self.selection, committed, self.programme, self.policy, self.targets,
                                    self.eval_budget, 2 * 1024 * 1024)
        self.assertEqual(len(result['comparisons']), 663)
        self.assertEqual(len(self.target_calls), sum(r.status == 'predicted' for r in candidate.predictions))
        self.assertTrue(all(e['balanced_effect'] is None for e in result['summary']['effects']))
        self.assertFalse(result['summary']['scientifically_qualified'])

    def test_late_candidate_disposition_rejected_before_target(self):
        candidate, reference, _ = self.build()
        bad = replace(candidate, predictions=candidate.predictions[:-1] +
                      (replace(candidate.predictions[-1], family='wrong-family'),))
        with self.assertRaises(ValueError): self.commit(bad, reference)
        self.assertEqual(self.target_calls, [])
        self.assertFalse((self.local/'packet').exists())

    def test_changed_native_prediction_cannot_be_recommitted(self):
        candidate, reference, _ = self.build()
        rows = list(candidate.predictions)
        index = next(i for i, r in enumerate(rows) if r.value is not None)
        raw = struct.pack('<dddd', 4., 3., 2., 1.)
        rows[index] = replace(rows[index], value=replace(rows[index].value, values=raw, sha256=content_pin(raw).sha256))
        with self.assertRaises(ValueError): self.commit(replace(candidate, predictions=tuple(rows)), reference)
        self.assertEqual(self.target_calls, [])

    def test_failed_candidate_keeps_complete_roster_and_no_targets(self):
        candidate, reference, _ = self.build(InertOwner(self.policy, status='candidate_failed'))
        self.assertTrue(any(r.status == 'candidate_failed' for r in candidate.predictions))
        committed = self.commit(candidate, reference)
        result = evaluate_committed(self.selection, committed, self.programme, self.policy,
                                    self.targets, self.eval_budget, 2 * 1024 * 1024)
        self.assertEqual(len(result['comparisons']), 663); self.assertEqual(self.target_calls, [])

    def test_unclosed_owner_preserves_exact_failure_evidence(self):
        with self.assertRaises(CandidateFailure) as caught:
            self.build(InertOwner(self.policy, closed=False))
        error = caught.exception
        self.assertIsNotNone(error.rejected)
        self.assertIs(error.original, error.__cause__)
        self.assertEqual(len(error.partial.predictions), 663)
        self.assertTrue(any(r.status == 'candidate_failed' for r in error.partial.predictions))
        self.assertFalse((self.local/'packet').exists())

    def test_wrong_training_selection_refused_before_workspace_creation(self):
        reader = TrainingReader(replace(self.selection, identity='different-selection'), self.reader.tree, allowance())
        with self.assertRaises(ValueError):
            run_candidate(self.selection, self.programme, self.policy, reader, InertOwner(self.policy),
                          str(self.local/'workspace'), self.budget)
        self.assertFalse((self.local/'workspace').exists())

    def test_changed_budget_cannot_keep_the_same_policy_identity(self):
        with self.assertRaises(ValueError):
            run_candidate(self.selection, self.programme, replace(self.policy, memory_bytes=2 * self.policy.memory_bytes),
                          self.reader, InertOwner(self.policy), str(self.local/'workspace'), self.budget)
        self.assertFalse((self.local/'workspace').exists())

    def test_overlapping_workspace_refused_before_mutation(self):
        destination = self.root/'training'/'forbidden-workspace'
        with self.assertRaises(ValueError):
            run_candidate(self.selection, self.programme, self.policy, self.reader, InertOwner(self.policy),
                          str(destination), self.budget)
        self.assertFalse(destination.exists())
        with self.assertRaises(ValueError): canonical_path('//' + str(self.root).lstrip('/') + '/x', True)

    def test_changed_target_pin_rejected_at_owner_admission(self):
        doc = json.loads(json.dumps(self.target_doc))
        doc['maps'][-1]['pin']['sha256'] = 'f' * 64
        pin = publish(self.root/'targets'/'bad-target-selection.json', json_bytes(doc, 2 * 1024 * 1024))
        with self.assertRaises(ValueError):
            ProtectedOwner(self.selection, self.reader.tree, Tree(str(self.root/'targets')),
                           'bad-target-selection.json', pin, allowance())
        self.assertEqual(self.target_calls, [])

    def test_reused_context_is_not_a_new_fold(self):
        candidate, _, _ = self.build()
        request, receipt = candidate.receipts[0]
        with self.assertRaises(ValueError):
            validate_receipt(receipt, request, self.programme, self.policy, {receipt.context_identity})

    def test_late_reference_file_tamper_has_zero_target_calls(self):
        candidate, reference, _ = self.build()
        committed = self.commit(candidate, reference)
        manifest = json.loads((Path(committed.root)/'PANEL.json').read_text())
        row = next(r for r in reversed(manifest['references']['predictions']) if r['value'] is not None)
        path = Path(committed.root)/row['value']['path']
        path.chmod(0o600); path.write_bytes(struct.pack('<dddd', 4., 3., 2., 1.))
        with self.assertRaises(Exception):
            evaluate_committed(self.selection, committed, self.programme, self.policy,
                               self.targets, self.eval_budget, 2 * 1024 * 1024)
        self.assertEqual(self.target_calls, [])


if __name__ == '__main__':
    unittest.main()
