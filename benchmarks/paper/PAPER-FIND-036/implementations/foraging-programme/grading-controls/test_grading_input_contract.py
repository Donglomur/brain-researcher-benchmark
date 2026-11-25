"""Generated collection-admission controls; no targets or producer execution."""
import copy
import sys
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1] / 'program'
sys.path.insert(0, str(PROGRAM))
import grade
from common import parse
from support import phases


def complete_collection():
    """All 1,320 distinct phase receipts, with small synthetic row counts."""
    records = [{
        'session_id': f'{i:024x}', 'rows': 10,
        'folds': [{'fold': f, 'train_order0': list(range(8)),
                   'query_order0': [8, 9]} for f in range(1, 6)],
    } for i in range(40)]
    contexts = phases(records, 32)
    deadline = 10000.0
    receipts = []
    for index, ctx in enumerate(contexts):
        started = 3.0 * index + 1
        receipts.append({
            'schema': 'foraging_owned_phase_v1', 'context': ctx,
            'status': 'captured', 'error': None,
            'all_resources_closed': True, 'producer_closed_before_capture': True,
            'cli_reaped': True, 'private_scoring_called': False,
            'natural_exit': {'Status': 'exited', 'Running': False, 'Dead': False,
                             'Pid': 0, 'ExitCode': 0, 'OOMKilled': False},
            'closures': [{'kind': kind, 'name': f'{index}-{j}', 'closed': True,
                          'absence_observed': True, 'creation_outcome_unknown': False}
                         for j, kind in enumerate(('container', 'container', 'volume'))],
            'started': started, 'finished': started + .25,
            'phase_work_deadline': started + 1,
            'phase_cleanup_deadline': started + 2,
            'original_work_deadline': deadline,
            'command_records': [{
                'returncode': 0, 'error_type': None,
                'client_reaped': True, 'cleanup_complete': True,
                'cleanup_before_original_cutoff': True,
                'owned_group_absence_observed': True,
                'leader_exited_with_group_alive': False,
                'group_probe_or_cleanup_error': None,
                'materialized_pipe_bytes': 0, 'observed_retained_bytes': 0,
            }],
            'artifacts': {'bytes': 1 if ctx['kind'] == 'fit' else ctx['output_bytes'],
                          'sha256': '0' * 64},
        })
    return records, {
        'model_cap_bytes': 32, 'contexts': contexts, 'phases': receipts,
        'all1320closed': True, 'private_grade_called': False,
        'original_origin': 0.0, 'original_deadline': deadline,
        'before_final_persistence': 5000.0,
    }


def set_original_clock(collection, name, value):
    collection[name] = value
    if name == 'original_deadline':
        for phase in collection['phases']:
            phase['original_work_deadline'] = value


class GradingInputContractTests(unittest.TestCase):
    def test_complete_finite_collection_remains_admitted(self):
        records, collection = complete_collection()
        before = copy.deepcopy(collection)
        self.assertEqual(grade.phase_admission(collection, records), collection['contexts'])
        self.assertEqual(collection, before)

    def test_nonfinite_original_clocks_rejected_including_json_overflow(self):
        records, baseline = complete_collection()
        # JSON exponent overflow follows parse_float, not parse_constant.
        values = [parse(b'1e309'), parse(b'-1e309'), float('nan')]
        for name in ('original_origin', 'original_deadline'):
            for value in values:
                with self.subTest(name=name, value=repr(value)):
                    collection = copy.deepcopy(baseline)
                    set_original_clock(collection, name, value)
                    with self.assertRaisesRegex(ValueError, 'finite original collection clocks'):
                        grade.phase_admission(collection, records)

    def test_missing_duplicate_and_nonfinite_phase_fail(self):
        records, baseline = complete_collection()
        for corruption in ('missing', 'duplicate', 'nonfinite'):
            with self.subTest(corruption=corruption):
                collection = copy.deepcopy(baseline)
                if corruption == 'missing':
                    collection['phases'].pop()
                elif corruption == 'duplicate':
                    collection['phases'][-1] = copy.deepcopy(collection['phases'][0])
                else:
                    collection['phases'][-1]['finished'] = parse(b'1e309')
                with self.assertRaises(ValueError):
                    grade.phase_admission(collection, records)

    def test_json_duplicate_and_nonfinite_literal_rejection_retained(self):
        for raw in (b'{"original_deadline":1,"original_deadline":2}',
                    b'{"original_deadline":NaN}', b'{"original_deadline":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse(raw)


if __name__ == '__main__':
    unittest.main()
