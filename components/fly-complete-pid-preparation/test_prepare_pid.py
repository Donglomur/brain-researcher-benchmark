"""Invented traces only; never reads the authentic binding's archive."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import prepare_pid as p
from pid_types import PID_COLUMNS


def trace(selected, optional='0', ending='\r\n'):
    lines = ['PyBMT data 20260101-000000', 'Format:' + ','.join(PID_COLUMNS)]
    for values in selected:
        fields = [optional] * 21
        for column, value in zip(p.SELECT, values):
            fields[column] = str(value)
        lines.append(','.join(fields))
    return (ending.join(lines) + ending).encode()


def pin(body, rows):
    return {'index': 0, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
            'rows': rows, 'role': 'trace'}


def run_trace(rows, **kwargs):
    body = trace(rows, **kwargs)
    return p.prepare_trace(body, pin(body, len(rows)))


def family(corrupt_last=False, duplicate=False):
    selected = [('0', '10', '0', '0', '0.1'), ('0.01', '11', '1', '1', '0.2'),
                ('0.02', '12', '0', '0', '0.3')]
    stream = io.BytesIO()
    members = []
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for i in range(14):
            body = trace(selected) if i % 2 == 0 else b'opaque-sidecar'
            name = 'trace-%02d.txt' % i if i % 2 == 0 else '__MACOSX/side-%02d' % i
            if duplicate and i == 13:
                name = 'trace-00.txt'
            archive.writestr(name, body)
            row = pin(body, 3) if i % 2 == 0 else {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(), 'rows': None}
            row.update(index=i, role='trace' if i % 2 == 0 else 'companion')
            members.append(row)
    body = stream.getvalue()
    binding = {'archive': {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}, 'members': members}
    if corrupt_last:
        binding['members'][12]['sha256'] = '0' * 64
    return body, binding


class Preparation(unittest.TestCase):
    def test_clock_origin_and_all_command_edges(self):
        rows, report = run_trace([('100', '1', '0', '0', '1'), ('100.01', '2', '1', '1', '2'),
                                  ('100.02', '3', '0', '0', '3')])
        clock = report['clock']['historical_coordinate']
        self.assertEqual(clock['first'], {'numerator': '1', 'denominator': '100'})
        self.assertEqual(clock['shift'], {'numerator': '-9999', 'denominator': '100'})
        self.assertEqual(report['clock']['rounded_rate_hz'], 100)
        self.assertEqual([e['to'] for e in report['odor']['transitions']], [1, 0])
        self.assertEqual(report['odor']['transitions'][0]['native_time_bracket_tokens'], ['100', '100.01'])
        self.assertEqual(rows[2]['tokens'][-1], '3')
        self.assertIsNone(report['physical_odor_offsets'])

    def test_exact_binary_commands_and_large_clock_resolution(self):
        rows, report = run_trace([('9007199254740992', '0', '0', '0', '1'),
                                  ('9007199254740992.01', '1', '1.0000000000000001', '1e0', '2'),
                                  ('9007199254740992.02', '2', '0', '0', '3')])
        self.assertEqual(report['clock']['rounded_rate_hz'], 100)
        self.assertEqual(rows[1]['flags'][2], 'nonbinary_command')
        self.assertEqual(report['wind']['transitions'], [])
        self.assertEqual(len(report['odor']['transitions']), 2)

    def test_nonfinite_underflow_and_missing_preserve_rows(self):
        rows, report = run_trace([('0', '0', '0', '0', '1'), ('0.01', '1', '1', 'NaN', '1e309'),
                                  ('0.02', '2', '1', '1', '1e-400'), ('0.03', '3', '0', '0', '')])
        self.assertEqual(len(rows), 4)
        self.assertEqual([r['flags'][4] for r in rows], [None, 'binary64_overflow', 'binary64_underflow', 'missing_or_nonfinite'])
        self.assertEqual([(e['before_row'], e['after_row']) for e in report['odor']['transitions']], [(3, 4)])
        self.assertFalse(report['odor']['on_episodes'][0]['onset_observed'])

    def test_optional_missingness_is_not_critical_failure(self):
        rows, report = run_trace([('0', '0', '0', '0', '1'), ('0.01', '1', '0', '0', '2')], optional='NaN', ending='\n')
        self.assertEqual(report['numeric_issues'], [])
        self.assertEqual(len(rows), 2)

    def test_native_lexical_padding_and_positive_half_rounding(self):
        rows, report = run_trace([(' 0 ', ' 10 ', '\t0', ' 0 ', ' +1.00e0 '),
                                  (' 0.4 ', ' 11 ', '1 ', '1\t', ' 2.00 ')])
        self.assertEqual(rows[0]['tokens'], [' 0 ', ' 10 ', '\t0', ' 0 ', ' +1.00e0 '])
        self.assertEqual(report['clock']['rounded_rate_hz'], 3)
        self.assertEqual(report['numeric_issues'], [])

    def test_frame_and_clock_discontinuities_remain_visible(self):
        _, report = run_trace([('0', '10', '0', '0', '0'), ('0.01', '12', '1', '1', '1'),
                                ('0.01', '12', '0', '0', '2'), ('0', '11', '1', '1', '3')])
        self.assertEqual([e['kind'] for e in report['clock']['frame_discontinuities']], ['missing_frames', 'duplicate', 'decreasing'])
        self.assertEqual([e['kind'] for e in report['clock']['duplicate_or_decreasing_pairs']], ['duplicate', 'decreasing'])
        self.assertIsNone(report['clock']['historical_coordinate'])
        self.assertFalse(report['odor']['transitions'][1]['clock_increasing'])

    def test_censored_and_complete_episodes_not_deleted(self):
        _, report = run_trace([(str(i / 100), str(i), '0', odor, '0')
                                for i, odor in enumerate(['1', '0', '1', '0', '1'])])
        episodes = report['odor']['on_episodes']
        self.assertEqual(len(episodes), 3)
        self.assertEqual([e['complete_command_cycle'] for e in episodes], [False, True, False])
        self.assertEqual(episodes[-1]['ending'], 'right_censored')

    def test_limits_and_unestablished_profile_refuse(self):
        for token in ('1e10000', '1e99999999999999999999'):
            with self.assertRaises(p.Held):
                run_trace([('0', '0', '0', '0', token)])
        body = trace([('0', '0', '0', '0', '1')]).replace(b'AnalogIn', b'not_PID')
        with self.assertRaisesRegex(p.Held, 'trace_lexical_profile'):
            p.prepare_trace(body, pin(body, 1))
        body = trace([('0', '0', '0', '0', '1')])
        with self.assertRaisesRegex(p.Held, 'complete_trace_rows'):
            p.prepare_trace(body, pin(body, 2))

    def test_complete_seven_family_and_private_outputs(self):
        body, binding = family()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'prepared'
            old = os.umask(0)
            try:
                result = p.prepare_archive(body, binding, output)
            finally:
                os.umask(old)
            self.assertEqual(result['trace_count'], 7)
            self.assertEqual(result['rows'], 21)
            self.assertEqual(len(result['products']), 14)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(x.stat().st_mode & 0o777 == 0o600 for x in output.iterdir()))
            original = (output / 'OUTCOME.json').read_bytes()
            with self.assertRaisesRegex(p.Held, 'output_already_exists'):
                p.prepare_archive(body, binding, output)
            self.assertEqual((output / 'OUTCOME.json').read_bytes(), original)

    def test_last_trace_corruption_preserves_failure_not_success(self):
        body, binding = family(corrupt_last=True)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'partial'
            with self.assertRaisesRegex(p.Held, 'trace_identity'):
                p.prepare_archive(body, binding, output)
            self.assertFalse((output / 'OUTCOME.json').exists())
            failure = json.loads((output / 'FAILURE.json').read_text())
            self.assertEqual(len(failure['products']), 12)
            self.assertEqual(failure['status'], 'failed_partial_preserved')

    def test_archive_identity_member_roles_extent_and_duplicate_refusal(self):
        body, binding = family()
        for change in ('archive', 'extent', 'role', 'missing'):
            altered = copy.deepcopy(binding)
            if change == 'archive': altered['archive']['sha256'] = 'f' * 64
            if change == 'extent': altered['members'][0]['bytes'] += 1
            if change == 'role': altered['members'][0]['role'] = 'companion'
            if change == 'missing': altered['members'].pop()
            with self.assertRaises(p.Held): p.checked_archive(body, altered)
        body, binding = family(duplicate=True)
        with self.assertRaisesRegex(p.Held, 'archive_member_path_or_alias'):
            p.checked_archive(body, binding)

    def test_production_cli_never_admits_generated_alternative(self):
        body, _ = family()
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'invented.zip'
            output = Path(temporary) / 'never-created'
            archive.write_bytes(body)
            with mock.patch('sys.argv', ['prepare_pid.py', '--archive', str(archive), '--output', str(output)]):
                with self.assertRaisesRegex(p.Held, 'archive_identity'):
                    p.main()
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
