"""Portable generated cost semantics; optional exact external metadata preflight.

NEURAL034_COST_LOCATORS selects seven already-frozen operator JSON documents for
an additional in-memory exact-hash/render check. No configured source copy,
authentic input, subprocess, Docker call or scientific scoring is performed.
"""
from pathlib import Path
import copy
import importlib.util
import json
import os
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[4]
spec = importlib.util.spec_from_file_location('_neural034_cost_configure', HERE / 'configure.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
PREFIX = 2679.932040249051
PRIOR = 3159.932040249051
TOTAL = 3309.932040249051
NEXT = 3789.932040249051
COMMIT = 'f778af151a1cf949619c079dd0fc408192aca123'
RUN = 'neural034-scoped-runtime-prerequisite-01'


def generated_documents(historical):
    """Minimal independent scalar witnesses; no claim to authentic document hashes."""
    pins = copy.deepcopy(C.EVIDENCE_PINS)
    prior = {'candidate_id': 'NEURAL-034', 'runtime_id': 'neural034_ordinary_completion_v1',
        'cost_family_id': 'astrocyte_source_family', 'source_freeze': historical,
        'status': 'program_scored', 'known_seconds_before': PREFIX,
        'charged_seconds': 480, 'known_seconds_after': PRIOR,
        'all_owned_absent': True, 'all_process_groups_absent_and_reaped': True,
        'all_owned_cli_processes_absent': True, 'controller_direct_handle_reaped': True}
    result = {'schema': 'neural034-runtime-prerequisite-result/v1',
        'status': 'two_generated_units_closed_pending_independent_review',
        'cost_family_id': 'astrocyte_source_family', 'source_commit': COMMIT,
        'all_owned_absent': True, 'controller_reaped': True, 'controller_returncode': 0,
        'prior_costs_reset': False, 'historical_lifetime_complete': False,
        'cumulative_family_seconds': None, 'charged_wall_allowance_seconds': 150,
        'authentic_inputs': 0, 'model_calls': 0, 'scientific_scores': 0}
    protocol = {'schema': 'neural034-scoped-runtime-prerequisite/v1', 'run_id': RUN,
        'prior_costs_reset': False, 'limits': {'hard_wall_seconds': 150},
        'authentic_inputs': 0, 'model_calls': 0, 'scientific_scores': 0}
    review = {'schema': 'neural034-generated-prerequisite-saved-proof/v1',
        'status': 'two_generated_units_saved_proof_verified_pending_root_scoped_decision',
        'native_terminal': {'id': RUN, 'status': 'succeeded', 'exit_code': 0},
        'source_commit': COMMIT, 'result': pins['prerequisite_result'],
        'protocol': pins['prerequisite_protocol'],
        'group_absence': [{'absence_verified': True, 'signal': 0}, {'absence_verified': True, 'signal': 0}],
        'costs': {'prior_costs_reset': False, 'cumulative_family_seconds': None, 'stage_allowance_seconds': 150},
        'authentic_inputs': 0, 'model_calls': 0, 'scientific_scores': 0}
    adoption = {'schema': 'neural034-root-finite-cost-supplement/v1',
        'decision': 'adopt_exact_prior_ordinary_plus_generated150_for_source_construction',
        'cost_family_id': 'astrocyte_source_family', 'execution_authority': False,
        'allocation_authority': False, 'historical_lifetime_complete': False,
        'latest_family_confirmed_for_native_dispatch': False,
        'original_adopted_prefix': {'adoption': pins['prefix_adoption'],
            'proposal': pins['prefix_proposal'], 'known_source_family_seconds': PREFIX},
        'prior_ordinary_receipt': dict(prior, **pins['prior_ordinary']),
        'new_typed_supplement': {'run_id': RUN, 'source_commit': COMMIT,
            'result': pins['prerequisite_result'], 'protocol': pins['prerequisite_protocol'],
            'independent_saved_review': pins['saved_review'], 'charged_wall_allowance_seconds': 150},
        'prior_known_charged_wall_allowance_seconds': PRIOR,
        'additive_charged_wall_allowance_seconds': 150,
        'included_known_charged_wall_allowance_subtotal_seconds': TOTAL,
        'next_full_ordinary_allowance_seconds': 480, 'conditional_next_subtotal_seconds': NEXT}
    prefix = {'schema': 'root-astrocyte-cost-reconciliation-adoption-v1',
        'decision': 'adopt_explicit_disjoint_saved_receipt_reconciliation', 'execution_authority': False,
        'known_source_family_seconds': PREFIX, 'proposal': pins['prefix_proposal']}
    proposal = {'cost_family_id': 'astrocyte_source_family', 'proposed_known_source_family_seconds': PREFIX}
    return {'root_adoption': adoption, 'prior_ordinary': prior, 'prefix_adoption': prefix,
            'prefix_proposal': proposal, 'prerequisite_result': result,
            'prerequisite_protocol': protocol, 'saved_review': review}


class CostSupplementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = C.base(ROOT)
        original, current, manifest = cls.b._capture(ROOT)
        cls.predecessor = cls.b._render(original, current, manifest)
        cls.body = C.admission_body(cls.b, cls.predecessor[C.ADMISSION])
        cls.a = types.ModuleType('_neural034_generated_cost_admission')
        cls.a.__file__ = str(ROOT / cls.b.PORTABLE / C.ADMISSION)
        exec(compile(cls.body, cls.a.__file__, 'exec'), cls.a.__dict__)
        cls.source_pin = {'path': C.FREEZE, 'bytes': 1, 'sha256': 'f' * 64}
        cls.documents = generated_documents(cls.a.HISTORICAL_SOURCE_FREEZE)
        locators = os.environ.get('NEURAL034_COST_LOCATORS')
        if locators:
            mapping = cls.b.decode(cls.b.read(locators, cap=16384))
            raw = C.evidence(cls.b, mapping)
            files, receipt = C.successor(cls.b, cls.predecessor, raw)
            # Real exact metadata/source checks are separate from generated semantics.
            for name, body in cls.predecessor.items():
                if name not in (C.ADMISSION, C.FREEZE, 'SOURCE_MANIFEST.json'):
                    if files[name] != body:
                        raise AssertionError('Unexpected scientific/runtime source change: ' + name)
            for name in (C.ADMISSION, C.FREEZE, 'SOURCE_MANIFEST.json'):
                if files[C.ARCHIVE + name] != cls.predecessor[name]:
                    raise AssertionError('Immediate predecessor not preserved')
            for role in raw:
                corrupt = dict(raw, **{role: raw[role] + b' '})
                try:
                    C.authenticate_documents(corrupt)
                except ValueError:
                    pass
                else:
                    raise AssertionError('Changed exact evidence accepted: ' + role)
            cls.documents = {role: cls.b.decode(body) for role, body in raw.items()}
            cls.source_pin = receipt['source_freeze']
            def checked(entry):
                body = files[entry['path']]
                if C.pin(body) != {key: entry[key] for key in ('bytes', 'sha256')}:
                    raise ValueError('Exact in-memory source member')
                return body
            with patch.object(cls.a, 'checked', side_effect=checked):
                frozen, held = cls.a.source_gate(cls.source_pin)
            if frozen['historical_source_freeze'] != cls.a.HISTORICAL_SOURCE_FREEZE or len(held) != 34:
                raise AssertionError('Original source admission rejected successor closure')
            print(json.dumps({'external_exact_metadata_verified': True,
                              'changed_evidence_refusals': 7, 'original_source_gate_members': len(held),
                              'configuration': receipt}, sort_keys=True))

    def call(self, documents=None, selected=None, extra=None):
        documents = documents or self.documents
        lookups = []
        def pinned(row):
            lookups.append(copy.deepcopy(row))
            for role, fixed in C.EVIDENCE_PINS.items():
                if row == fixed:
                    return copy.deepcopy(documents[role])
            if extra is not None and row == extra[0]:
                return copy.deepcopy(extra[1])
            raise ValueError('Unexpected/unpinned evidence read')
        with patch.object(self.a, 'pinned', side_effect=pinned):
            value = self.a.known_cost(selected or C.EVIDENCE_PINS['root_adoption'], self.source_pin)
        return value, lookups

    def test_original_known_cost_body_is_preserved(self):
        old = self.predecessor[C.ADMISSION].decode()
        new = self.body.decode()
        first = 'def known_cost(pin,source_pin):\n'
        end = '\ndef runtime_environment(review):'
        old_body = old.split(first, 1)[1].split(end, 1)[0]
        new_body = new.split(first, 1)[1].split(end, 1)[0]
        branch = "    if pin==FINITE_COST_PINS['root_adoption']:return finite_cost_supplement(source_pin)\n"
        self.assertTrue(new_body.startswith(branch))
        self.assertEqual(new_body[len(branch):], old_body)
        self.assertEqual(C.pin(self.predecessor[C.FREEZE]), C.PREDECESSOR_FREEZE)
        self.assertEqual(C.pin(self.predecessor['SOURCE_MANIFEST.json']), C.PREDECESSOR_MANIFEST)

    def test_exact_finite_total_uses_original_prefix_and_prior(self):
        value, lookups = self.call()
        self.assertEqual(value, TOTAL)
        self.assertEqual(len(lookups), 7)
        self.assertEqual({row['path'] for row in lookups}, {row['path'] for row in C.EVIDENCE_PINS.values()})
        self.assertEqual(self.call(selected=C.EVIDENCE_PINS['prior_ordinary'])[0], PRIOR)
        self.assertEqual(self.call(selected=C.EVIDENCE_PINS['prefix_adoption'])[0], PREFIX)
        self.assertFalse(self.documents['root_adoption']['latest_family_confirmed_for_native_dispatch'])

    def test_ordinary_next480_behavior_remains_intact(self):
        selected = {'path': 'operator-cost/generated-next.json', 'bytes': 100, 'sha256': 'a' * 64}
        row = copy.deepcopy(self.documents['prior_ordinary'])
        row.update(source_freeze=self.source_pin, known_seconds_before=TOTAL,
                   known_seconds_after=NEXT, charged_seconds=480)
        for status in ('program_scored', 'execution_failed_preserved'):
            row['status'] = status
            self.assertEqual(self.call(selected=selected, extra=(selected, row))[0], NEXT)
        for changes in ({'charged_seconds': 150}, {'charged_seconds': True},
                        {'known_seconds_after': TOTAL}, {'all_owned_absent': False}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.call(selected=selected, extra=(selected, dict(row, **changes)))

    def test_semantic_mutations_refused(self):
        mutations = [
            ('root_adoption', ('decision',), 'adopt_unreviewed'),
            ('root_adoption', ('cost_family_id',), 'other_family'),
            ('root_adoption', ('latest_family_confirmed_for_native_dispatch',), True),
            ('root_adoption', ('execution_authority',), True),
            ('root_adoption', ('original_adopted_prefix', 'adoption', 'sha256'), '0' * 64),
            ('root_adoption', ('original_adopted_prefix', 'proposal', 'sha256'), '0' * 64),
            ('root_adoption', ('included_known_charged_wall_allowance_subtotal_seconds',), TOTAL + 150),
            ('root_adoption', ('additive_charged_wall_allowance_seconds',), True),
            ('root_adoption', ('additive_charged_wall_allowance_seconds',), 300),
            ('prefix_proposal', ('proposed_known_source_family_seconds',), PREFIX - 1),
            ('prior_ordinary', ('charged_seconds',), 150),
            ('prior_ordinary', ('all_owned_absent',), False),
            ('prerequisite_result', ('charged_wall_allowance_seconds',), True),
            ('prerequisite_result', ('charged_wall_allowance_seconds',), 300),
            ('prerequisite_result', ('status',), 'failed_preserved'),
            ('prerequisite_result', ('controller_reaped',), False),
            ('prerequisite_result', ('controller_returncode',), False),
            ('prerequisite_result', ('cumulative_family_seconds',), TOTAL),
            ('prerequisite_result', ('cost_family_id',), 'other_family'),
            ('prerequisite_protocol', ('run_id',), 'another_run'),
            ('saved_review', ('status',), 'verification_failed_preserved'),
            ('saved_review', ('result', 'sha256'), '0' * 64),
            ('saved_review', ('native_terminal', 'exit_code'), False),
            ('saved_review', ('group_absence', 0, 'absence_verified'), False),
        ]
        for role, path, value in mutations:
            docs = copy.deepcopy(self.documents)
            target = docs[role]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(role=role, path=path, value=value), self.assertRaises(ValueError):
                self.call(docs)

    def test_double_count_and_nested_locator_reads_refused(self):
        docs = copy.deepcopy(self.documents)
        docs['prior_ordinary'].update(known_seconds_before=PREFIX + 150,
                                     known_seconds_after=PRIOR + 150)
        with self.assertRaises(ValueError):
            self.call(docs)
        docs = copy.deepcopy(self.documents)
        # Document locators do not control any file read; identities remain fixed.
        docs['root_adoption']['prior_ordinary_receipt']['path'] = '/unopened/authentic-input.npz'
        docs['root_adoption']['new_typed_supplement']['result']['path'] = '/unopened/private-targets.json'
        value, lookups = self.call(docs)
        self.assertEqual(value, TOTAL)
        self.assertTrue(all(not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts
                            for row in lookups))

    def test_unpinned_or_incomplete_evidence_refused_before_write(self):
        with self.assertRaises(ValueError):
            C.authenticate_documents({})
        raw = {role: b'generated-untrusted\n' for role in C.EVIDENCE_PINS}
        with self.assertRaisesRegex(ValueError, 'root_adoption'):
            C.authenticate_documents(raw)
        with self.assertRaises(ValueError):
            C.evidence(self.b, {'root_adoption': '/unopened/anything'})
        with self.assertRaises(ValueError):
            self.call(selected={'path': C.EVIDENCE_PINS['root_adoption']['path'],
                                'bytes': 8125, 'sha256': '0' * 64})


if __name__ == '__main__':
    unittest.main(verbosity=2)
