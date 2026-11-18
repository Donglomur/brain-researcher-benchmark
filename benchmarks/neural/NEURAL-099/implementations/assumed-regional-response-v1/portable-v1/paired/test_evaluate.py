"""Generated evaluator controls; no authentic inputs or full-cohort scoring.

The full-size case is a synthetic internal-seam test, not production admission.
Only it substitutes the scorer. All other score fixtures use the frozen scorer.
Physical writes are confined to an explicit generated-fixture directory and
charged cumulatively, including replaced/deleted files and failed write attempts.
File payloads and encoded symlink targets are charged; directory/FIFO filesystem
metadata bytes are unmeasured, and those entries contain no regular-file payload.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as E
from access import profile
from observations import ObservationAdapter
from session import ARMS, EDGES, canonical, digest
from transports import build_request


def encoded(value):
    return canonical(value) + b'\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def visible(case):
    return {key: case[key] for key in E.VISIBLE}


def make_cases(full=False, single=False):
    cases, schedule_rows, cell_index = [], [], 0
    if full:
        specifications = [(203, ('MGd',))] * 3
        specifications += [(202, ('MGd', 'MGv'))] * 6
        specifications += [(201, ('MGd', 'MGv'))] * 17
    elif single:
        specifications = [(1, ('MGd',))]
    else:
        specifications = [(2, ('MGd', 'MGv')), (1, ('MGd',))]
    for animal_index, (trials, regions) in enumerate(specifications):
        animal = f'synthetic-animal-{animal_index:02d}'
        asset = f'synthetic-asset-{animal_index:02d}'
        denominators = {}
        for region in regions:
            denominators[region] = (29 if cell_index < 15 else 28) if full else 2
            cell_index += 1
        for row in range(trials):
            schedule_rows.append({'outer_fold': animal_index % 5, 'animal_id': animal,
                                  'asset_id': asset, 'source_trial_row': row})
            for region in regions:
                cases.append({'case_id': f'{asset}-{row:03d}-{region}',
                              'animal_id': animal, 'asset_id': asset, 'region': region,
                              'source_trial_row': row, 'source_trial_id': 100 + row,
                              'source_cluster_count': denominators[region],
                              'trial_start_seconds': 10.0 + row,
                              'trial_stop_seconds': 10.01 + row})
    return cases, schedule_rows


class SyntheticJournal:
    """Generate each record on demand; retain hashes, not serialized journals."""
    def __init__(self, *, full=False, single=False, rates=None, edit=None):
        self.cases, self.schedule_rows = make_cases(full=full, single=single)
        self.study_id = 'generated-evaluator-study'
        self.procedures = {ARMS[0]: '1' * 64, ARMS[1]: '2' * 64}
        self.nonce = 'a' * 64
        self.rates = rates or (lambda arm, case: [0] * 100)
        self.edit = edit or (lambda name, value: value)
        self.raw_edit = lambda name, body: body
        self.history_calls, self.gold_calls, self.events = [], 0, []
        self.fail_history_case = None
        self.fail_unchanged = False
        self.read_names = set()
        self.by_id = {case['case_id']: case for case in self.cases}
        self.groups = {}
        for case in self.cases:
            self.groups.setdefault((case['asset_id'], case['source_trial_row']), []).append(case)
        self.count_vector = [0] * 100
        adapter = ObservationAdapter(self.cases, self._plain_history)
        self.payload_hashes = []
        for row in self.schedule_rows:
            observations = adapter.observations(row['asset_id'], row['source_trial_row'],
                                                view='timing_history')
            request = build_request(profile(ARMS[0]), observations, self.study_id, 'f' * 64)
            self.payload_hashes.append(request['payload_sha256'])
        self.record_count = len(self.schedule_rows) * 2
        self.names = {'BEGIN.json', 'COMPLETE.json'} | {
            f'{index:06d}.json' for index in range(self.record_count)}
        self.begin = self.edit('BEGIN.json', {
            'schema': 'neural099-paired-study-start/v1', 'study_id': self.study_id,
            'attempt_nonce': self.nonce, 'production': False,
            'case_metadata_sha256': digest(self.cases), 'procedures': self.procedures,
            'arms': list(ARMS), 'profiles': [profile(arm) for arm in ARMS],
            'cases_per_arm': len(self.cases), 'trials_per_arm': len(self.schedule_rows),
            'schedule_sha256': digest(self.schedule_rows),
            'state': 'incomplete_no_score_or_label_release',
        })
        chain, total, maximum = '0' * 64, 0, 0
        for name in ['BEGIN.json'] + [f'{i:06d}.json' for i in range(self.record_count)]:
            body = self._body(name)
            chain = sha(bytes.fromhex(chain) + bytes.fromhex(sha(body)))
            total += len(body)
            maximum = max(maximum, len(body))
        completion = {
            'schema': 'neural099-paired-completion/v1', 'study_id': self.study_id,
            'attempt_nonce': self.nonce, 'production': False,
            'state': 'all_configured_predictions_locked',
            'cases_per_arm': {arm: len(self.cases) for arm in ARMS},
            'trials_per_arm': len(self.schedule_rows), 'fold_groups': 5,
            'case_metadata_sha256': digest(self.cases), 'procedures': self.procedures,
            'score_and_label_release': 'eligible_for_separate_evaluator_admission_only',
            'scores_computed': 0, 'target_values_released': 0,
        }
        self.complete = self.edit('COMPLETE.json', dict(
            completion, requires_successful_operator_finish_receipt=True,
            locked_records=self.record_count, prior_chain_sha256=chain))
        body = encoded(self.complete)
        total += len(body)
        chain = sha(bytes.fromhex(chain) + bytes.fromhex(sha(body)))
        self.total_bytes = total
        self.max_bytes = max(maximum, len(body))
        self.finish = {'operation': 'finish', 'completion': dict(
            completion, journal_receipt={'record_sha256': sha(body),
                                        'chain_sha256': chain, 'logical_bytes': total})}

    def _plain_history(self, key, *, released_case_id):
        if key != released_case_id:
            raise AssertionError('Wrong generated history identity')
        return {'case': visible(self.by_id[key]), 'history_rates': [0.0] * 100}

    def history(self, key, *, released_case_id):
        self.history_calls.append(key)
        self.events.append('history')
        if key == self.fail_history_case:
            raise ValueError('Generated final history failure')
        return self._plain_history(key, released_case_id=released_case_id)

    def gold(self):
        self.gold_calls += 1
        self.events.append('gold')
        return [{'case': visible(case), 'counts': self.count_vector}
                for case in self.cases]

    def record(self, index):
        ordinal, arm_index = divmod(index, 2)
        row, arm = self.schedule_rows[ordinal], ARMS[arm_index]
        predictions = [{'case_id': case['case_id'], 'rates': self.rates(arm, case)}
                       for case in self.groups[(row['asset_id'], row['source_trial_row'])]]
        token = digest({'study_id': self.study_id, 'attempt_nonce': self.nonce,
                        'procedures': self.procedures, 'ordinal': ordinal,
                        'schedule_row': row})
        value = {
            'schema': 'neural099-locked-prediction/v1', 'study_id': self.study_id,
            'attempt_nonce': self.nonce, 'trial_ordinal': ordinal,
            'outer_fold': row['outer_fold'], 'condition_id': arm,
            'procedure_sha256': self.procedures[arm], 'trial_token': token,
            'payload_sha256': self.payload_hashes[ordinal],
            'predictions_sha256': digest(predictions), 'predictions': predictions,
        }
        value = self.edit(f'{index:06d}.json', value)
        # Semantic mutation fixtures deliberately keep prediction commitments valid.
        value['predictions_sha256'] = digest(value['predictions'])
        return value

    def _body(self, name):
        if name == 'BEGIN.json':
            return encoded(self.begin)
        if name == 'COMPLETE.json':
            return encoded(self.complete)
        return encoded(self.record(int(name[:-5])))

    def read(self, name, cap):
        if name not in self.names or name in self.read_names:
            raise ValueError('Generated journal member missing or read twice')
        body = self.raw_edit(name, self._body(name))
        if len(body) > cap:
            raise ValueError('Generated reader byte limit')
        self.read_names.add(name)
        return body

    def verify_unchanged(self):
        self.events.append('unchanged')
        if self.fail_unchanged:
            raise ValueError('Generated reader changed')

    def evaluate(self, **overrides):
        kwargs = dict(study_id=self.study_id, procedures=self.procedures,
                      finish=self.finish, history_projection=self.history,
                      load_response_gold=self.gold, max_record_bytes=self.max_bytes,
                      max_journal_bytes=self.total_bytes)
        kwargs.update(overrides)
        return E._evaluate_records(self.cases, self.schedule_rows, self, **kwargs)


class FixtureBudget:
    """One cumulative budget for this suite, including all deleted attempts."""
    cumulative = 0
    live = 0
    high_water = 0
    attempts = 0
    ceiling = 131072
    live_ceiling = 32768

    @classmethod
    def snapshot(cls):
        return {'cumulative_bytes': cls.cumulative, 'live_bytes': cls.live,
                'high_water_bytes': cls.high_water, 'attempts': cls.attempts,
                'accounting': 'conservative reserved payload and symlink-target bytes'}

    def __enter__(self):
        root = Path(os.environ.get('NEURAL099_GENERATED_FIXTURE_ROOT',
                                   str(Path(__file__).resolve().parent / 'generated-fixtures')))
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='evaluator-', dir=root)
        self.path = Path(self.temporary.name)
        os.chmod(self.path, 0o700)
        self.reserved = {}
        return self

    def reserve(self, path, size):
        path = Path(path)
        if not path.is_relative_to(self.path) or type(size) is not int or size < 0:
            raise AssertionError('Generated write outside fixture scope')
        FixtureBudget.attempts += 1
        old = self.reserved.get(path, 0)
        new_live = FixtureBudget.live - old + size
        if FixtureBudget.cumulative + size > self.ceiling or new_live > self.live_ceiling:
            raise AssertionError('Generated fixture budget exceeded')
        FixtureBudget.cumulative += size
        FixtureBudget.live = new_live
        FixtureBudget.high_water = max(FixtureBudget.high_water, new_live)
        self.reserved[path] = size

    def write(self, path, body):
        self.reserve(path, len(body))
        with open(path, 'wb') as stream:
            stream.write(body)
        os.chmod(path, 0o600)

    def symlink(self, target, path):
        self.reserve(path, len(os.fsencode(target)))
        os.symlink(target, path)

    def __exit__(self, exc_type, exc, traceback):
        # Failed cleanup retains its conservative live charge.
        self.temporary.cleanup()
        FixtureBudget.live -= sum(self.reserved.values())


def evidence():
    manifest_sha, finish_sha = 'b' * 64, 'c' * 64
    manifest = {'study_id': 'generated-evidence',
                'procedure_hashes': {ARMS[0]: '1' * 64, ARMS[1]: '2' * 64}}
    finish = {'operation': 'finish', 'completion': {
        'study_id': manifest['study_id'], 'procedures': manifest['procedure_hashes'],
        'production': True, 'state': 'all_configured_predictions_locked',
        'cases_per_arm': {arm: 9867 for arm in ARMS}, 'trials_per_arm': 5238}}
    closure = {'schema': 'neural099-selected-collection-closure/v1',
               'study_id': manifest['study_id'], 'manifest_sha256': manifest_sha,
               'finish_receipt_sha256': finish_sha, 'exit_code': 0,
               'owned_process_group_absent': True, 'lease_closed': True}
    return manifest, manifest_sha, finish, finish_sha, closure


class EvaluateTests(unittest.TestCase):
    def assert_no_gold(self, journal, *, no_history=False):
        self.assertEqual(journal.gold_calls, 0)
        if no_history:
            self.assertEqual(journal.history_calls, [])

    def test_01_full_synthetic_roster_streams_two_complete_arms(self):
        journal = SyntheticJournal(full=True)
        self.assertEqual(len(journal.cases), 9867)
        self.assertEqual(len(journal.schedule_rows), 5238)
        cells = {(c['asset_id'], c['region']): c['source_cluster_count'] for c in journal.cases}
        self.assertEqual((len(cells), sum(cells.values())), (49, 1387))
        self.assertEqual(len({c['animal_id'] for c in journal.cases}), 26)
        self.assertEqual(journal.record_count, 10476)
        calls = []
        def generated_score(cases, predictions, gold, *, edges_seconds, coarsening_factor):
            self.assertEqual((len(cases), len(predictions), len(gold)), (9867, 9867, 9867))
            self.assertTrue({p['case_id'] for p in predictions} == {c['case_id'] for c in cases},
                            'Complete synthetic prediction identity set differs')
            self.assertEqual(edges_seconds, EDGES)
            self.assertEqual(coarsening_factor, 5)
            calls.append(len(predictions))
            return {'generated_core_shape_only': True, 'cases': len(cases)}
        with patch.object(E.SCORER, 'score', side_effect=generated_score):
            result = journal.evaluate()
        self.assertEqual(calls, [9867, 9867])
        self.assertEqual(set(result['scores']), set(ARMS))
        self.assertEqual(result['locked_records'], 10476)
        self.assertEqual(len(journal.read_names), 10478)
        self.assertEqual(journal.gold_calls, 1)
        self.assertEqual(len(journal.history_calls), 9867)
        self.assertFalse(journal.begin['production'])

    def test_02_actual_scores_preserve_weighting_normalization_and_coarsening(self):
        def rates(arm, case):
            if case['animal_id'].endswith('01'):
                errors = [6] * 100
            elif case['region'] == 'MGv':
                errors = [0] * 100
            elif case['source_trial_row'] == 0:
                errors = [-2, -1, 0, 1, 2] * 20
            else:
                errors = [4] * 100
            return [500 + error for error in errors]
        journal = SyntheticJournal(rates=rates)
        journal.count_vector = [1] * 100  # 1 / (2 source clusters * .001s) = 500.
        result = journal.evaluate()
        for arm in ARMS:
            score = result['scores'][arm]
            fine, coarse = score['native_resolution'], score['coarsened_resolution']
            self.assertEqual(fine['animal_macro_mse']['value'], 20.25)
            self.assertAlmostEqual(fine['animal_macro_mae']['value'], 3.65)
            self.assertEqual(coarse['animal_macro_mse']['value'], 20.0)
            self.assertEqual(coarse['animal_macro_mae']['value'], 3.5)
            self.assertEqual(coarse['adjacent_bin_factor'], 5)
            self.assertEqual(coarse['bins_per_case'], 20)
            self.assertEqual((score['animals'], score['animal_region_cells'], score['cases']), (2, 3, 5))
            self.assertFalse(score['observation_coverage_verified'])
            self.assertFalse(score['empirical_readiness_claim'])

    def test_03_negative_and_large_integer_predictions_are_not_coerced(self):
        exact = SyntheticJournal(single=True, rates=lambda arm, case: [10**16 + 1] * 100)
        exact.count_vector = [2 * 10**13] * 100
        for score in exact.evaluate()['scores'].values():
            self.assertEqual(score['native_resolution']['animal_macro_mse']['value'], 1.0)
            self.assertEqual(score['native_resolution']['animal_macro_mae']['value'], 1.0)
        extreme = SyntheticJournal(single=True, rates=lambda arm, case:
                                   ([-2.5] * 100 if arm == ARMS[0] else [10**308 + 1] * 100))
        scores = extreme.evaluate()['scores']
        self.assertEqual(scores[ARMS[0]]['native_resolution']['animal_macro_mse']['value'], 6.25)
        self.assertEqual(scores[ARMS[0]]['native_resolution']['animal_macro_mae']['value'], 2.5)
        overflow = scores[ARMS[1]]['native_resolution']['animal_macro_mse']
        self.assertEqual(overflow, {'value': None, 'state': 'outside_float_range'})

    def test_04_last_second_arm_invalidity_reads_no_history_or_gold(self):
        for bad in ('shape', 'boolean', 'numeric_string'):
            with self.subTest(bad=bad):
                def edit(name, value):
                    if name == '000005.json':
                        if bad == 'shape': value['predictions'][0]['rates'].pop()
                        elif bad == 'boolean': value['predictions'][0]['rates'][-1] = False
                        else: value['predictions'][0]['rates'][-1] = '0'
                    return value
                journal = SyntheticJournal(edit=edit)
                with self.assertRaises(ValueError): journal.evaluate()
                self.assert_no_gold(journal, no_history=True)

    def test_05_same_wrong_final_payload_in_both_arms_never_releases_gold(self):
        def edit(name, value):
            if name in ('000004.json', '000005.json'):
                value['payload_sha256'] = 'e' * 64
            return value
        journal = SyntheticJournal(edit=edit)
        with self.assertRaisesRegex(ValueError, 'payload|token'):
            journal.evaluate()
        self.assertTrue(journal.history_calls)
        self.assert_no_gold(journal)

    def test_06_chain_and_exact_canonical_newline_are_required(self):
        for mutation in ('newline', 'whitespace', 'chain'):
            with self.subTest(mutation=mutation):
                journal = SyntheticJournal()
                def edit(name, body):
                    if name != '000005.json': return body
                    if mutation == 'newline': return body[:-1]
                    if mutation == 'whitespace': return b' ' + body
                    value = json.loads(body)
                    value['predictions'][0]['rates'][0] = 1
                    value['predictions_sha256'] = digest(value['predictions'])
                    return encoded(value)
                journal.raw_edit = edit
                with self.assertRaises(ValueError):
                    journal.evaluate(max_record_bytes=journal.max_bytes + 16,
                                     max_journal_bytes=journal.total_bytes + 16)
                self.assert_no_gold(journal, no_history=True)

    def test_07_complete_marker_cannot_replace_successful_finish_receipt(self):
        for mutation in ('missing', 'operation', 'chain', 'logical_bytes'):
            with self.subTest(mutation=mutation):
                journal = SyntheticJournal()
                if mutation == 'missing': journal.finish = {}
                elif mutation == 'operation': journal.finish['operation'] = 'current'
                elif mutation == 'chain':
                    journal.finish['completion']['journal_receipt']['chain_sha256'] = 'f' * 64
                else: journal.finish['completion']['journal_receipt']['logical_bytes'] += 1
                with self.assertRaises(ValueError): journal.evaluate()
                self.assert_no_gold(journal, no_history=True)

    def test_08_original_tokens_and_frozen_procedures_are_bound(self):
        for field in ('trial_token', 'procedure_sha256', 'attempt_nonce'):
            with self.subTest(field=field):
                def edit(name, value):
                    if name == '000005.json': value[field] = 'f' * 64
                    return value
                journal = SyntheticJournal(edit=edit)
                with self.assertRaises(ValueError): journal.evaluate()
                self.assert_no_gold(journal)

    def test_09_record_order_replay_and_duplicate_cases_are_rejected(self):
        for mutation in ('ordinal', 'arm', 'duplicate_case'):
            with self.subTest(mutation=mutation):
                def edit(name, value):
                    if name == '000001.json':
                        if mutation == 'ordinal': value['trial_ordinal'] = 1
                        elif mutation == 'arm': value['condition_id'] = ARMS[0]
                        else: value['predictions'][1]['case_id'] = value['predictions'][0]['case_id']
                    return value
                journal = SyntheticJournal(edit=edit)
                with self.assertRaises(ValueError): journal.evaluate()
                self.assert_no_gold(journal, no_history=True)

    def test_10_exact_inventory_and_complete_case_coverage_are_required(self):
        for mutation in ('missing_record', 'after_finish', 'second_finish', 'missing_case', 'extra_case'):
            with self.subTest(mutation=mutation):
                def edit(name, value):
                    if name == '000001.json':
                        if mutation == 'missing_case': value['predictions'].pop()
                        elif mutation == 'extra_case': value['predictions'].append(copy.deepcopy(value['predictions'][0]))
                    return value
                journal = SyntheticJournal(edit=edit)
                if mutation == 'missing_record': journal.names.remove('000005.json')
                elif mutation == 'after_finish': journal.names.add('000006.json')
                elif mutation == 'second_finish': journal.names.add('COMPLETE-2.json')
                with self.assertRaises(ValueError): journal.evaluate()
                self.assert_no_gold(journal, no_history=True)

    def test_11_profiles_roster_and_schedule_commitments_are_required(self):
        for field in ('profiles', 'case_metadata_sha256', 'schedule_sha256'):
            with self.subTest(field=field):
                def edit(name, value):
                    if name == 'BEGIN.json':
                        if field == 'profiles': value[field][0]['demonstration_labels'] = 1
                        else: value[field] = 'f' * 64
                    return value
                journal = SyntheticJournal(edit=edit)
                with self.assertRaises(ValueError): journal.evaluate()
                self.assert_no_gold(journal, no_history=True)

    def test_12_reader_change_and_finite_byte_limits_stop_before_gold(self):
        for mutation in ('changed', 'record_cap', 'total_cap'):
            with self.subTest(mutation=mutation):
                journal = SyntheticJournal()
                overrides = {}
                if mutation == 'changed': journal.fail_unchanged = True
                elif mutation == 'record_cap': overrides['max_record_bytes'] = journal.max_bytes - 1
                else: overrides['max_journal_bytes'] = journal.total_bytes - 1
                with self.assertRaises(ValueError): journal.evaluate(**overrides)
                self.assert_no_gold(journal, no_history=True)

    def test_13_external_evidence_requires_exact_selected_closed_production_pair(self):
        E._validate_evidence(*evidence())
        for mutation in ('false_exit', 'nonzero_exit', 'group', 'lease', 'extra', 'manifest_pin',
                         'finish_pin', 'production', 'partial_cases', 'partial_trials', 'wrong_study'):
            with self.subTest(mutation=mutation):
                manifest, manifest_sha, finish, finish_sha, closure = evidence()
                if mutation == 'false_exit': closure['exit_code'] = False
                elif mutation == 'nonzero_exit': closure['exit_code'] = 1
                elif mutation == 'group': closure['owned_process_group_absent'] = False
                elif mutation == 'lease': closure['lease_closed'] = False
                elif mutation == 'extra': closure['extra'] = True
                elif mutation == 'manifest_pin': closure['manifest_sha256'] = '0' * 64
                elif mutation == 'finish_pin': closure['finish_receipt_sha256'] = '0' * 64
                elif mutation == 'production': finish['completion']['production'] = False
                elif mutation == 'partial_cases': finish['completion']['cases_per_arm'][ARMS[1]] -= 1
                elif mutation == 'partial_trials': finish['completion']['trials_per_arm'] -= 1
                else: finish['completion']['study_id'] = 'another-study'
                with self.assertRaises(ValueError):
                    E._validate_evidence(manifest, manifest_sha, finish, finish_sha, closure)

    def test_14_real_journal_bounds_links_and_changed_files(self):
        with FixtureBudget() as budget:
            journal = budget.path / 'journal'
            journal.mkdir(mode=0o700)
            budget.write(journal / 'BEGIN.json', b'{}\n')
            with E._JournalFiles(str(journal), 1) as reader:
                self.assertEqual(reader.names, frozenset({'BEGIN.json'}))
                self.assertEqual(reader.read('BEGIN.json', 3), b'{}\n')
                with self.assertRaises(ValueError): reader.read('BEGIN.json', 3)
                reader.verify_unchanged()
                budget.write(journal / 'BEGIN.json', b'{"x":1}\n')
                with self.assertRaises(ValueError): reader.verify_unchanged()
            with E._JournalFiles(str(journal), 1) as reader:
                with self.assertRaises(ValueError): reader.read('BEGIN.json', 2)
            budget.write(journal / '000000.json', b'{}\n')
            with self.assertRaises(ValueError): E._JournalFiles(str(journal), 1)
            budget.symlink(journal / 'BEGIN.json', journal / 'COMPLETE.json')
            with E._JournalFiles(str(journal), 3) as reader:
                with self.assertRaises((OSError, ValueError)): reader.read('COMPLETE.json', 32)
            alias = budget.path / 'alias'
            budget.symlink(journal, alias)
            with self.assertRaises((OSError, ValueError)): E._JournalFiles(str(alias), 3)
            if hasattr(os, 'mkfifo'):
                os.mkfifo(journal / 'FIFO.json', 0o600)
                with E._JournalFiles(str(journal), 4) as reader:
                    with self.assertRaises(ValueError): reader.read('FIFO.json', 32)

    def test_15_pinned_reader_rejects_extent_digest_invalid_json_and_links(self):
        with FixtureBudget() as budget:
            path = budget.path / 'pin.json'
            body = b'{"answer":7}\n'
            budget.write(path, body)
            self.assertEqual(E._read_pin(str(path), len(body), sha(body), 128), {'answer': 7})
            for size, digest_value, cap in [(len(body)+1, sha(body), 128),
                                            (len(body), '0'*64, 128),
                                            (len(body), sha(body), len(body)-1)]:
                with self.assertRaises(ValueError): E._read_pin(str(path), size, digest_value, cap)
            for bad in (b'{"x":1,"x":2}\n', b'{"x":NaN}\n', b'{}{}\n'):
                budget.write(path, bad)
                with self.assertRaises(ValueError): E._read_pin(str(path), len(bad), sha(bad), 128)
            budget.write(path, body)  # Valid target: parsing cannot mask a followed link.
            alias = budget.path / 'alias.json'
            budget.symlink(path, alias)
            with self.assertRaises(OSError):
                E._read_pin(str(alias), len(body), sha(body), 128)

    def test_16_result_writer_is_exclusive_bounded_private_and_sync_checked(self):
        with FixtureBudget() as budget:
            value = {'scores': {'generated': 1}}
            body = encoded(value)
            path = budget.path / 'result.json'
            budget.reserve(path, len(body))
            receipt = E._write_result(str(path), value, 1024)
            self.assertEqual(path.read_bytes(), body)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(receipt, {'bytes': len(body), 'sha256': sha(body)})
            budget.reserve(path, len(body))
            with self.assertRaises(FileExistsError): E._write_result(str(path), value, 1024)
            too_small = budget.path / 'too-small.json'
            budget.reserve(too_small, len(body))
            with self.assertRaises(ValueError): E._write_result(str(too_small), value, len(body)-1)
            self.assertFalse(too_small.exists())
            failed = budget.path / 'failed.json'
            budget.reserve(failed, len(body))
            with patch.object(E.os, 'fsync', side_effect=OSError('generated sync failure')):
                with self.assertRaises(OSError): E._write_result(str(failed), value, 1024)
            self.assertTrue(failed.exists())  # retained partial result is not a success receipt

    def test_17_public_wrong_case_gate_precedes_any_packet_access(self):
        selected, manifest_sha, finish, finish_sha, closure = evidence()
        selected.update({'cases_path': '/generated/missing-cases.json',
                         'packet_path': '/generated/missing-packet', 'packet_binding': {},
                         'output_path': '/generated/missing-journal',
                         'max_record_bytes': 32768, 'max_journal_bytes': 65536})
        cases, _ = make_cases(single=True)
        with patch.object(E, '_read_pin', side_effect=[selected, finish, closure]), \
             patch.object(E, 'collection_manifest', return_value=selected), \
             patch.object(E, 'read_json', return_value=cases) as case_read, \
             patch.object(E, 'schedule', wraps=E.schedule) as schedule_spy, \
             patch.object(E.PACKET, 'verify_packet') as packet_spy, \
             patch.object(E, '_write_result') as output_spy:
            with self.assertRaises(ValueError):
                E.evaluate_sealed_pair(manifest_path='/generated/manifest', manifest_bytes=1,
                                       manifest_sha256=manifest_sha, finish_path='/generated/finish',
                                       finish_bytes=1, finish_sha256=finish_sha,
                                       closure_path='/generated/closure', closure_bytes=1,
                                       closure_sha256='d'*64, output_path='/generated/output')
            case_read.assert_called_once_with(selected['cases_path'], 3*1024**2, E.CASE_FILE_SHA)
            schedule_spy.assert_called_once_with(cases, production=True)
            packet_spy.assert_not_called()
            output_spy.assert_not_called()

    def test_18_last_history_failure_and_all_prior_checks_precede_gold(self):
        failed = SyntheticJournal()
        failed.fail_history_case = failed.cases[-1]['case_id']
        with self.assertRaisesRegex(ValueError, 'final history'):
            failed.evaluate()
        self.assertEqual(len(failed.history_calls), len(failed.cases))
        self.assert_no_gold(failed)
        complete = SyntheticJournal()
        complete.evaluate()
        gold_position = complete.events.index('gold')
        self.assertEqual(complete.events[:gold_position].count('history'), len(complete.cases))
        self.assertEqual(complete.events[:gold_position].count('unchanged'), 2)
        self.assertEqual(complete.events[-1], 'unchanged')
        self.assertEqual(complete.gold_calls, 1)


if __name__ == '__main__':
    unittest.main()
