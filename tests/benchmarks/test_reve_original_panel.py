"""Metadata/identity software controls, not authentic scientific results."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'benchmarks/paper/PAPER-paper-method-003/implementations/original-physionet/panel.py'
spec = importlib.util.spec_from_file_location('reve_original_panel', SOURCE)
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


def fixture():
    records = [{**r, 'signal': Path(r['path']).name.replace('.edf', '.npy'),
                'shape': [1, 64, 800], 'event_ids': [Path(r['path']).stem + '-event001'],
                'sha256': 'a'*64} for r in panel.roster()]
    return {'schema': 'reve-original-physionet-inputs-v1', 'source_commit': panel.SOURCE_COMMIT,
            'units': 'uV', 'dtype': 'float64', 'sampling_hz': 200, 'channels': panel.CHANNELS,
            'profile': panel.PROFILE, 'records': records, 'counts': {'train':420,'val':114,'test':120},
            'observed_epoch_count':654,'published_epoch_count':9837,'published_epoch_count_matches':False}


class OriginalPanelControls(unittest.TestCase):
    def load(self, value):
        value = copy.deepcopy(value)
        value['panel_identity'] = panel.identity(value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'panel.json'
            path.write_text(json.dumps(value))
            return panel.load_panel(path)

    def test_complete_literal_participant_split(self):
        rows = panel.roster()
        self.assertEqual(len(rows),654)
        self.assertEqual({r['participant'] for r in rows},set(range(1,110)))
        self.assertEqual([panel.split_for(p) for p in (70,71,89,90,109)],['train','val','val','test','test'])
        self.assertEqual(len(set(panel.CHANNELS)),64)
        self.assertEqual(self.load(fixture())['observed_epoch_count'],654)

    def test_same_size_changed_subject_is_rejected(self):
        value = fixture(); value['records'][0]['participant'] = 2
        with self.assertRaisesRegex(ValueError,'roster'): self.load(value)

    def test_paths_shapes_events_counts_rejected_even_after_rehash(self):
        for field, bad in [('signal','../operator/targets.json'),('shape',[1,64,799]),('event_ids',[])]:
            value = fixture(); value['records'][0][field] = bad
            with self.assertRaises(ValueError): self.load(value)
        value = fixture(); value['records'][1]['event_ids'] = value['records'][0]['event_ids']
        with self.assertRaisesRegex(ValueError,'duplicate'): self.load(value)
        value = fixture(); value['counts']['test'] = 119
        with self.assertRaisesRegex(ValueError,'census'): self.load(value)

    def test_unsupported_physical_profile_rejected(self):
        for key, bad in [('dtype','float32'),('sampling_hz',128),('units','V'),('source_commit','main')]:
            value = fixture(); value[key] = bad
            with self.assertRaises(ValueError): self.load(value)

    def test_official_checksum_requires_complete_panel(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sums'
            path.write_text('a'*64 + ' S001/S001R04.edf\n')
            with self.assertRaisesRegex(ValueError,'omit original runs'): panel.checksums(path)
            path.write_text('\n'.join('a'*64 + ' ' + r['path'] for r in panel.roster()))
            self.assertEqual(len(panel.checksums(path)),654)

    def test_historical_recipe_not_invented(self):
        with self.assertRaisesRegex(ValueError,'not been established'):
            panel.prepare('/nonexistent','/nonexistent',profile='paper128')


if __name__ == '__main__': unittest.main()
