"""Invented engineering fixtures only: no source CSVs, labels, or model execution."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import features as f
import source_prepare as p


def episode():
    rows = []
    for i in range(5):
        row = {k: float(j + i) for j, k in enumerate(f.BEHAVIOR + f.ERP, 1)}
        row.update(round=i + 1, trial_global=i + 1, episode=1, partner=7, choice=i % 2)
        rows.append((100 + i, row))
    return rows


def full_fixture():
    """A 41-person invented panel with deliberately unequal source eligibility."""
    ordered = sorted(map(str, range(1, 42)), key=lambda s: (
        hashlib.sha256(('NEURAL-005-processed-ERP-development-v1:' + s).encode()).hexdigest(), int(s)))
    train, dev = set(ordered[:26]), set(ordered[26:33])
    excluded = {'training': 490, 'development': 192}
    tables = {'BEH_ug.csv': []}
    tables.update({name: [] for name in p.ERP_FILES.values()})
    cases = []
    for person in map(str, range(1, 42)):
        for trial in range(1, 181):
            ep, rnd = (trial - 1) // 5 + 1, (trial - 1) % 5 + 1
            behavior = {'sub': person, 'trialLocal': str(rnd), 'trialGlobal': str(trial),
                        'block': str(ep), 'partnerID': str(ep), 'choice_num': str(trial % 2),
                        'choice': 'R' if trial % 2 else 'A'}
            behavior.update({k: '2' for k in f.BEHAVIOR})
            behavior.update(rpe='0', epe_valence='0', epe_arousal='0')
            if person not in train | dev:
                # If the converter touches reserved numerical values this fails.
                behavior['offer'] = 'RESERVED_NOT_A_NUMBER'
            tables['BEH_ug.csv'].append(behavior)
            group = 'training' if person in train else 'development'
            omit = person in train | dev and rnd <= 4 and excluded[group] > 0
            if omit:
                excluded[group] -= 1
            for key, name in p.ERP_FILES.items():
                # Row-specific amplitudes expose accidental reindexing after a skip.
                tables[name].append({key: 'NA' if omit and key == 'P2_offer'
                                      else str(len(tables['BEH_ug.csv']))})
            if person in dev and rnd <= 4 and not omit:
                cases.append({'participant': person, 'case_id': f'{person}:{ep}:{rnd}'})
    return tables, {'schema_version': 1, 'cases': cases}


class PreparationTests(unittest.TestCase):
    def test_independent_feature_arithmetic_and_masks(self):
        prefix = [row for _, row in episode()[:2]]
        expected = [2, 3, 2, 1, 2., 3., 4., 5., 6., 7.,
                    1, .5, 1, 1.5, 1., 2., 1., 2.5, 3.5, 4.5, 5.5, 6.5,
                    -1., 2., 2.]
        self.assertEqual(f.vector(prefix, 'history'), expected + [0] * 25)
        self.assertEqual(len(f.vector(prefix, 'prestimulus')), 53)
        self.assertEqual(len(f.vector(prefix, 'all_erp')), 57)
        changed = copy.deepcopy(prefix)
        for row in changed:
            for key in f.ERP:
                if key not in f.BASE:
                    row[key] += 1000
        self.assertEqual(f.vector(prefix, 'history'), f.vector(changed, 'history'))
        self.assertEqual(f.vector(prefix, 'prestimulus'), f.vector(changed, 'prestimulus'))
        self.assertNotEqual(f.vector(prefix, 'all_erp'), f.vector(changed, 'all_erp'))

    def test_current_missingness_does_not_use_future_completeness_or_bridge(self):
        rows = episode()
        rows[1][1]['P2_offer'] = None
        pairs = p.episode_pairs('8', 1, rows)
        self.assertEqual([r['request']['case_id'] for r in pairs], ['8:1:1', '8:1:3', '8:1:4'])
        # First target is still round two, despite round two's missing ERP.
        self.assertEqual(pairs[0]['target'], 1)
        self.assertEqual(pairs[0]['source_target'], 101)
        self.assertEqual(len(pairs[1]['request']['prefix']), 3)
        self.assertIsNone(pairs[1]['request']['prefix'][1]['P2_offer'])

    def test_future_mutation_cannot_change_current_features(self):
        rows = episode()
        before = f.vector(p.episode_pairs('8', 1, rows)[0]['request']['prefix'], 'all_erp')
        rows[1][1]['choice'] = 0
        rows[1][1]['offer'] = 10000.
        after = p.episode_pairs('8', 1, rows)[0]
        self.assertEqual(before, f.vector(after['request']['prefix'], 'all_erp'))
        self.assertEqual(after['target'], 0)
        self.assertNotIn('target', after['request'])

    def test_rejects_reordered_missing_duplicate_or_cross_partner_round(self):
        for change in ('order', 'missing', 'duplicate', 'partner', 'gap'):
            with self.subTest(change=change):
                rows = episode()
                if change == 'order':
                    rows[1], rows[2] = rows[2], rows[1]
                elif change == 'missing':
                    rows.pop(2)
                elif change == 'duplicate':
                    rows[2] = rows[1]
                elif change == 'partner':
                    rows[4][1]['partner'] = 8
                else:
                    rows[4][1]['trial_global'] += 1
                with self.assertRaises(ValueError):
                    p.episode_pairs('8', 1, rows)

    def test_common_support_before_mask_and_strict_metadata(self):
        for change in ('erp_missing', 'boolean', 'float_round', 'target_field'):
            with self.subTest(change=change):
                prefix = [episode()[0][1]]
                if change == 'erp_missing': prefix[0]['P3b_offer'] = None
                if change == 'boolean': prefix[0]['choice'] = True
                if change == 'float_round': prefix[0]['round'] = 1.0
                if change == 'target_field': prefix[0]['target'] = 0
                with self.assertRaises(ValueError):
                    f.vector(prefix, 'history')

    def test_full_conversion_preserves_indices_and_split_without_reserved_values(self):
        tables, panel = full_fixture()
        result = p.convert(tables, panel)
        train = result['train.json']
        dev = result['development_private.json']
        self.assertEqual(len(train['rows']), 3254)
        self.assertEqual(len(dev['cases']), 816)
        self.assertEqual(len(train['participant_ids']), 26)
        self.assertEqual(len(dev['participant_ids']), 7)
        self.assertFalse(set(train['participant_ids']) & set(dev['participant_ids']))
        self.assertEqual(sum(r['structural'] for r in result['preparation.json']['coverage'].values()), 33 * 144)
        for case in dev['cases']:
            request = case['request']
            self.assertEqual(request['prefix'][-1]['P3b_offer'], case['source_current'])
            self.assertEqual(case['source_target'], case['source_current'] + 1)
            self.assertEqual(case['target'], 1 - request['prefix'][-1]['choice'])
        self.assertFalse(result['preparation.json']['independent_ERP_trial_identity_verified'])

    def test_different_public_panel_and_equation_fail_closed(self):
        tables, panel = full_fixture()
        panel['cases'][0]['case_id'] = '999:1:1'
        with self.assertRaisesRegex(ValueError, 'public case panel'):
            p.convert(tables, panel)
        tables, panel = full_fixture()
        active = set(p.fixed_split(tables['BEH_ug.csv'])['training'])
        row = next(r for r in tables['BEH_ug.csv'] if r['sub'] in active)
        row['rpe'] = '1'
        with self.assertRaisesRegex(ValueError, 'source error equation'):
            p.convert(tables, panel)

    def test_hash_and_regular_file_admission(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'table.csv'
            body = b'field\nvalue\n'
            path.write_bytes(body)
            pin = {'bytes': len(body), 'sha256': p.digest(body)}
            self.assertEqual(p.read_pinned(path, pin), body)
            path.write_bytes(body.replace(b'value', b'other'))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                p.read_pinned(path, pin)
            link = Path(root) / 'link.csv'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                p.read_pinned(link, pin)

    def test_operator_entrypoint_writes_parity_or_nothing_and_authenticates_first(self):
        tables, panel = full_fixture()
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as operator:
            root = Path(workspace)
            here = root / 'benchmarks/neural/NEURAL-005/implementations/pinned-source-preparation-v1'
            here.mkdir(parents=True)
            source = root / 'invented-source'
            source.mkdir()
            pins = {'files': {}, 'expected_numerical_outputs': {}}
            for name, rows in tables.items():
                text = io.StringIO(newline='')
                writer = csv.DictWriter(text, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
                body = text.getvalue().encode()
                (source / name).write_bytes(body)
                pins['files'][name] = {'bytes': len(body), 'sha256': p.digest(body)}
            panel_body = p.encode(panel)
            panel_path = here.parent / 'registered-runtime/public/cases.json'
            panel_path.parent.mkdir(parents=True)
            panel_path.write_bytes(panel_body)
            pins['public_panel'] = {'bytes': len(panel_body), 'sha256': p.digest(panel_body)}
            for name, value in p.convert(tables, panel).items():
                if name != 'preparation.json':
                    body = p.encode(value)
                    pins['expected_numerical_outputs'][name] = {'bytes': len(body), 'sha256': p.digest(body)}
            pin_path = here / 'SOURCE_PINS.json'
            pin_path.write_bytes(p.encode(pins))
            with mock.patch.object(p, 'HERE', here):
                output = Path(operator) / 'success'
                result = p.prepare(source, output)
                self.assertEqual(result['status'], 'source_prepared')
                self.assertEqual(set(x.name for x in output.iterdir()),
                                 {'train.json', 'development_private.json', 'preparation.json'})
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                self.assertTrue(all(x.stat().st_mode & 0o777 == 0o600 for x in output.iterdir()))
                pins['expected_numerical_outputs']['train.json']['sha256'] = '0' * 64
                pin_path.write_bytes(p.encode(pins))
                rejected = Path(operator) / 'rejected'
                with self.assertRaisesRegex(ValueError, 'numerical artifact parity'):
                    p.prepare(source, rejected)
                self.assertFalse(rejected.exists())
                # Even a late-file source hash failure precedes the first CSV decode.
                name = list(pins['files'])[-1]
                path = source / name
                body = path.read_bytes()
                path.write_bytes(body[:-1] + b'!')
                with mock.patch.object(p, 'parse_csv', wraps=p.parse_csv) as parse:
                    with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                        p.prepare(source, Path(operator) / 'changed-source')
                    parse.assert_not_called()

    def test_csv_shape_and_integer_validation(self):
        for body in (b'x,x\n1,2\n', b'x\n' + b'1,2\n' * 7380,
                     b'x,y\n' + b'1\n' * 7380):
            with self.assertRaises(ValueError):
                p.parse_csv(body)
        for token in ('NaN', 'Infinity', '1.0000000000000000001', 'True'):
            with self.assertRaises(ValueError):
                p.exact_integer(token)
        self.assertEqual(p.exact_integer('201.0'), 201)


if __name__ == '__main__':
    unittest.main()
