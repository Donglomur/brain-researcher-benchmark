"""Invented directory controls. No archive acquisition or member inspection."""
import copy
import json
from pathlib import Path
import unittest
from census_join import join_complete_directories

ROOT = Path(__file__).parent
ASSETS = json.loads((ROOT / "ASSETS.json").read_text())
ROSTER = json.loads((ROOT / "ROSTER.json").read_text())


def panel():
    directories = []
    for asset in ASSETS:
        names = []
        for r in ROSTER:
            if r['declared_trials'] == 0:
                continue
            if asset['role'] == 'current':
                names.append(f"invented/doppler_S{r['session']}_R{r['run']}+normcorre.mat")
            elif r['recording_system'] == 'prototypeRT':
                names.append(f"invented/rt_fUS_data_S{r['session']}_R{r['run']}.mat")
        entries = [{'name': n, 'directory': False} for n in names]
        directories.append({'file_id': asset['file_id'], 'filename': asset['filename'],
                            'bytes': asset['bytes'], 'etag': '"invented-' + asset['role'] + '"',
                            'entries_count': len(entries),
                            'entries': entries})
    return directories


class CensusControls(unittest.TestCase):
    def test_whole_roster_and_missing_zero(self):
        result = join_complete_directories(panel(), ASSETS, ROSTER)
        self.assertEqual(len(result['records']), 49)
        zero = next(r for r in result['records'] if r['record_id'] == 'L-S45-R1')
        self.assertTrue(zero['zero_declared_count'])
        self.assertTrue(all(not v for v in zero['current_form_candidates'].values()))
        self.assertFalse(result['native_ready'])
        self.assertTrue(all(r['native_trial_count'] is None for r in result['records']))

    def test_ambiguous_members_never_selected(self):
        ds = panel()
        ds[0]['entries'].append({'name': 'elsewhere/doppler_S27_R99+normcorre.mat', 'directory': False})
        ds[0]['entries_count'] += 1
        result = join_complete_directories(ds, ASSETS, ROSTER)
        row = next(r for r in result['records'] if r['record_id'] == 'L-S27-R99')
        self.assertEqual(len(row['current_form_candidates']['task_aligned_normcorre']), 2)
        self.assertFalse(row['Run99_constituent_lineage_proven'])

    def test_unregistered_run_is_only_a_candidate(self):
        ds = panel()
        name = 'invented/doppler_S27_R2+normcorre.mat'
        ds[0]['entries'].append({'name': name, 'directory': False})
        ds[0]['entries_count'] += 1
        result = join_complete_directories(ds, ASSETS, ROSTER)
        row = next(r for r in result['records'] if r['record_id'] == 'L-S27-R99')
        self.assertEqual(row['same_session_other_run_candidates'], [name])
        self.assertIn(name, result['unmatched_mat_members']['current'])

    def test_all_schema_names_preserved(self):
        ds = panel()
        for name in ('docs/DescriptionOfFiles.pdf', 'docs/DescriptionOfVariables.pdf'):
            ds[1]['entries'].append({'name': name, 'directory': False})
            ds[1]['entries_count'] += 1
        result = join_complete_directories(ds, ASSETS, ROSTER)
        self.assertEqual(len(result['directory_provenance'][1]['schema_document_candidates']), 2)

    def test_complete_pair_and_extent_required(self):
        ds = panel()
        with self.assertRaises(ValueError): join_complete_directories(ds[:1], ASSETS, ROSTER)
        with self.assertRaises(ValueError): join_complete_directories([ds[0], ds[0]], ASSETS, ROSTER)
        ds[0]['bytes'] -= 1
        with self.assertRaises(ValueError): join_complete_directories(ds, ASSETS, ROSTER)

    def test_duplicate_and_incomplete_entry_sets_rejected(self):
        ds = panel()
        ds[0]['entries_count'] -= 1
        with self.assertRaises(ValueError): join_complete_directories(ds, ASSETS, ROSTER)
        ds = panel()
        ds[0]['entries'].append(copy.deepcopy(ds[0]['entries'][0]))
        ds[0]['entries_count'] += 1
        with self.assertRaises(ValueError): join_complete_directories(ds, ASSETS, ROSTER)

    def test_strong_entity_binding_retained(self):
        ds = panel()
        result = join_complete_directories(ds, ASSETS, ROSTER)
        self.assertEqual([r["etag"] for r in result["directory_provenance"]],
                         [r["etag"] for r in ds])
        for tag in (None, "", "unquoted", 'W/"weak"', '"bad\nline"', True):
            ds = panel()
            ds[0]["etag"] = tag
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                join_complete_directories(ds, ASSETS, ROSTER)

    def test_same_totals_cannot_substitute_roster(self):
        roster = copy.deepcopy(ROSTER)
        roster[0]['declared_trials'] += 1
        roster[1]['declared_trials'] -= 1
        with self.assertRaises(ValueError): join_complete_directories(panel(), ASSETS, roster)
        assets = copy.deepcopy(ASSETS)
        assets[0]['file_id'] = 'invented-other-asset'
        with self.assertRaises(ValueError): join_complete_directories(panel(), assets, ROSTER)


if __name__ == '__main__':
    unittest.main()
