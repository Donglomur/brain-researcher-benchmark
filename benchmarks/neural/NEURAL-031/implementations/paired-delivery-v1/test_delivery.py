"""Generated full-panel controls. Never opens authentic inputs or private targets."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import delivery as d
from io031 import archive, arrays, decode, encoded, pin

WRITTEN = 0


def write(path, body):
    global WRITTEN
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    WRITTEN += len(body)


def fixture():
    # Same complete panel size and authentic per-mouse request counts. Values
    # and row identities here are wholly generated, not empirical observations.
    counts = [37, 23, 52, 94, 50, 21, 33, 64, 53, 24, 67, 18, 23, 31, 57, 22, 28, 24, 31, 22]
    mouse = np.repeat(np.arange(20, dtype=np.int64), counts)
    ids = np.arange(774, dtype=np.int64)
    x = np.column_stack((1 + ids / 1000, ids % 2, 100 + ids / 31, -200 + ids / 17)).astype(np.float64)
    x[::7, 2] = np.nan; x[::11, 3] = np.inf
    y = 1 + ids / 1000
    y[np.arange(0, 731, 17)] = np.nan  # Exactly 43 unavailable requests.
    packets, manifests = [], []
    for fold in range(20):
        train, query = mouse != fold, mouse == fold
        p = {'train_x': x[train], 'train_y': y[train], 'train_mouse': mouse[train],
             'train_rowid': ids[train], 'query_x': x[query], 'query_rowid': ids[query]}
        m = {'schema': 'neural031_outer_public_v1', 'candidate_id': 'NEURAL-031',
             'fold': fold, 'held_mouse': d.endpoint().MICE[fold],
             'training_mouse_indices': [i for i in range(20) if i != fold],
             'features': ['baseline_volume', 'basal_indicator', 'local_coactivity_norm', 'dendrite_coincident_norm'],
             'training_target': 'next_day_ratio_with_NaN_unavailable',
             'query_target_or_followup_metadata': False, 'train_rows': int(train.sum()),
             'query_rows': int(query.sum()), 'data': pin(archive(np, p))}
        packets.append(p); manifests.append(m)
    return packets, manifests, mouse, y


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='.generated031-', dir=HERE)
        cls.root = Path(cls.temp.name)
        cls.packets, cls.manifests, cls.mouse, cls.y = fixture()
        cls.original = cls.root / 'original'
        source = copy.deepcopy(d.inputs())
        for fold, (packet, manifest) in enumerate(zip(cls.packets, cls.manifests)):
            for key, name, body in (('data', 'data.npz', archive(np, packet)),
                                    ('manifest', 'manifest.json', encoded(manifest))):
                write(cls.original / f'public/fold{fold:02d}' / name, body)
                source['original_folds'][fold][key] = pin(body)
        files = d.project_packets(np, cls.packets, cls.manifests)
        for item in source['paired_views']:
            for key, name in (('data', 'data.npz'), ('manifest', 'manifest.json')):
                item[key] = pin(files[f"public/fold{item['fold']:02d}/{item['view']}/{name}"])
        source['support'] = pin(files['support.json'])
        cls.source = source
        cls.store = cls.root / 'paired'
        receipt = d.prepare(cls.original, cls.store, source)
        global WRITTEN
        WRITTEN += receipt['written_bytes']
        cls.support = decode(files['support.json'])
        cls.predictions = cls.root / 'predictions'
        for fold in range(20):
            for view in d.VIEWS:
                value = {'schema': 'neural031_ordinary_prediction_v1', 'candidate_id': 'NEURAL-031',
                         'fold': fold, 'view': view,
                         'input_manifest': cls.support['folds'][fold]['views'][view]['manifest'],
                         'rows': [{'row_id': row, 'prediction': 1.0}
                                  for row in cls.support['folds'][fold]['rowids']]}
                write(cls.predictions / f'fold{fold:02d}' / view / 'predictions.json', encoded(value))

    @classmethod
    def tearDownClass(cls):
        retained = sum(p.stat().st_size for p in cls.root.rglob('*') if p.is_file())
        print(json.dumps({'scope': 'generated controls only', 'fixture_write_bytes': WRITTEN,
                          'fixture_retained_bytes_before_cleanup': retained,
                          'fixture_retained_bytes_after_cleanup': 0, 'authentic_payload_opens': 0,
                          'participant_programs_executed': 0}))
        cls.temp.cleanup()

    def test_all_forty_views_preserve_original_support_and_shared_missingness(self):
        for fold in range(20):
            values = {}
            for view in d.VIEWS:
                prefix = self.store / f'public/fold{fold:02d}/{view}'
                values[view] = arrays(np, (prefix / 'data.npz').read_bytes(), d.KEYS)
                self.assertEqual(values[view]['query_rowid'].tolist(), self.support['folds'][fold]['rowids'])
            d.validate_views(np, self.packets[fold], values['baseline'], values['neural'])
            self.assertEqual(values['baseline']['query_x'].shape[1], 4)
            self.assertEqual(values['neural']['query_x'].shape[1], 6)
        self.assertEqual(self.support['request_rows'], 774)

    def test_every_export_contains_only_one_pinned_context(self):
        global WRITTEN
        for fold in range(20):
            for view in d.VIEWS:
                out = self.root / f'export-{fold}-{view}'
                receipt = d.export_context(self.store, out, fold, view, self.source)
                WRITTEN += receipt['written_bytes']
                self.assertEqual({p.name for p in out.iterdir()}, {'data.npz', 'manifest.json'})
                self.assertEqual(receipt['files'],
                                 {'data.npz': self.source['paired_views'][2 * fold + d.VIEWS.index(view)]['data'],
                                  'manifest.json': self.source['paired_views'][2 * fold + d.VIEWS.index(view)]['manifest']})
                self.assertFalse(receipt['isolation_enforced'])

    def test_complete_collection_is_accepted_by_unchanged_scorer(self):
        global WRITTEN
        out = self.root / 'collected'
        receipt = d.collect(self.store, self.predictions, out, self.source)
        WRITTEN += receipt['written_bytes']
        self.assertFalse(receipt['execution_provenance_verified'])
        ep = d.endpoint()
        sys.modules['endpoint'] = ep
        spec = importlib.util.spec_from_file_location('score031_generated', HERE.parent / 'ratio-scoring-v1/score.py')
        score = importlib.util.module_from_spec(spec); spec.loader.exec_module(score)
        target = {'schema': 'neural031_ratio_targets_v1', 'candidate_id': 'NEURAL-031',
                  'mice': list(ep.MICE), 'rows': []}
        for row in range(1143):
            request = row < 774
            observed = request and np.isfinite(self.y[row])
            target['rows'].append({'rowid': row, 'mouse': int(self.mouse[row]) if request else row % 20,
                                  'request': int(request), 'observed': int(observed),
                                  'y': float(self.y[row]) if observed else None,
                                  'baseline_new': row % 2, 'compartment': row % 2})
        path = self.root / 'generated_targets.json'; body = encoded(target); write(path, body)
        result = score.run(out / 'support.json', out / 'submission.json', path, pin(body)['sha256'])
        self.assertEqual(result['primary'], 0.0)
        self.assertEqual(receipt['predictions'], 1548)

    def test_incomplete_and_inconsistent_original_panels_fail(self):
        with self.assertRaises(ValueError):
            d.project_packets(np, self.packets[:-1], self.manifests[:-1])
        mutations = ('identity', 'label', 'predictor', 'membership')
        for mutation in mutations:
            packets, manifests = copy.deepcopy(self.packets), copy.deepcopy(self.manifests)
            if mutation == 'identity': manifests[0]['held_mouse'] = manifests[1]['held_mouse']
            if mutation == 'label': packets[0]['train_y'][1] += 5
            if mutation == 'predictor': packets[0]['train_x'][1, 0] += 5
            if mutation == 'membership': packets[0]['train_mouse'][1] = 0
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                d.project_packets(np, packets, manifests)

    def test_forged_output_pin_prevents_any_preparation_write(self):
        source = copy.deepcopy(self.source)
        source['paired_views'][-1]['manifest']['sha256'] = '0' * 64
        output = self.root / 'never-created'
        with self.assertRaises(ValueError):
            d.prepare(self.original, output, source)
        self.assertFalse(output.exists())

    def test_missing_extra_or_reordered_outputs_fail_before_publication(self):
        file = self.predictions / 'fold00/baseline/predictions.json'
        original = file.read_bytes()
        value = decode(original)
        changed = copy.deepcopy(value); changed['rows'].reverse()
        try:
            for label, body in (('order', encoded(changed)), ('duplicate', b'{"rows":[],"rows":[]}')):
                write(file, body)
                out = self.root / ('bad-' + label)
                with self.subTest(label=label), self.assertRaises(ValueError):
                    d.collect(self.store, self.predictions, out, self.source)
                self.assertFalse(out.exists())
            file.unlink()
            with self.assertRaises(ValueError):
                d.collect(self.store, self.predictions, self.root / 'bad-missing', self.source)
        finally:
            write(file, original)
        extra = self.predictions / 'fold00/neural/extra.json'; write(extra, b'{}')
        try:
            with self.assertRaises(ValueError):
                d.collect(self.store, self.predictions, self.root / 'bad-extra', self.source)
        finally:
            extra.unlink()

    def test_cross_fold_output_and_wrong_view_pin_fail(self):
        path = self.predictions / 'fold00/baseline/predictions.json'
        original = path.read_bytes()
        try:
            wrong_fold = (self.predictions / 'fold01/baseline/predictions.json').read_bytes()
            wrong_pin = decode(original)
            wrong_pin['input_manifest'] = self.support['folds'][0]['views']['neural']['manifest']
            for label, body in (('fold', wrong_fold), ('pin', encoded(wrong_pin))):
                write(path, body)
                with self.subTest(label=label), self.assertRaises(ValueError):
                    d.collect(self.store, self.predictions, self.root / ('bad-' + label), self.source)
        finally:
            write(path, original)

    def test_export_avoids_all_other_archives_and_refuses_symlinks(self):
        opened = []
        real_read = d.read
        def observe(path, *args):
            opened.append(str(path))
            return real_read(path, *args)
        with patch.object(d, 'read', side_effect=observe):
            receipt = d.export_context(self.store, self.root / 'single', 0, 'baseline', self.source)
        global WRITTEN
        WRITTEN += receipt['written_bytes']
        self.assertEqual([p for p in opened if p.endswith('.npz')],
                         [str(self.store / 'public/fold00/baseline/data.npz')])
        alias = self.root / 'alias'; alias.symlink_to(self.store, target_is_directory=True)
        with self.assertRaises(ValueError):
            d.export_context(alias, self.root / 'bad-alias', 0, 'baseline', self.source)

    def test_no_overwrite_or_partial_source_identity(self):
        with self.assertRaises(FileExistsError):
            d.export_context(self.store, self.store, 0, 'baseline', self.source)
        source = copy.deepcopy(self.source); source['paired_views'].pop()
        with self.assertRaises(ValueError): d.validate_inputs(source)
        source = copy.deepcopy(self.source); source['original_folds'].reverse()
        with self.assertRaises(ValueError): d.validate_inputs(source)

    def test_public_source_roster_is_complete_and_unchanged(self):
        source = d.inputs()
        self.assertEqual(len(source['original_folds']), 20)
        self.assertEqual(len(source['paired_views']), 40)
        self.assertEqual(source['support']['sha256'],
                         '83cd6ce39b2206c78ff32db1ab41c5e1f132cfb1e53b5aa0aca37f8fe2914e17')


if __name__ == '__main__':
    unittest.main(verbosity=2)
