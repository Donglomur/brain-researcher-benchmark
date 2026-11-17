"""Generated-only controls; optional exact cached-author-loop parity control."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("replay", HERE / "replay.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
AUTHOR_SOURCE = None


def rows():
    return [{"trial_type": trial, "img_cat": category, "temp_cond": k}
            for trial in r.TRIALS for category in r.CATEGORIES for k in range(6)]


def table(source_rows):
    # Every response cell encodes its row and sample index. Query rows can be
    # detected independently without depending on the projector's own labels.
    lines = [" ".join(r.HEADER)]
    for i, row in enumerate(source_rows):
        values = [str(1000000 + i * 1000 + j) for j in range(819)]
        lines.append(" ".join([row['trial_type'], row['img_cat'], str(row['temp_cond'])] + values))
    return ("\n".join(lines) + "\n").encode()


def metadata(source_rows, raw):
    return {"schema": "temporal026-ordered-source-metadata/v1", "electrodes": [
        {"electrode_id": e['id'], "source_data_sha256": hashlib.sha256(raw).hexdigest(),
         "rows": copy.deepcopy(source_rows)} for e in r.cohort()]}


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.raw = table(cls.rows)
        cls.metadata = metadata(cls.rows, cls.raw)
        cls.manifest = r.freeze(cls.metadata, 20261117)
        cls.pinned = cls.manifest['manifest_sha256']
        cls.electrode = r.cohort()[0]['id']

    def test_full_original_panel_and_source_roster(self):
        self.assertEqual(len(self.manifest['electrodes']), 79)
        regions = {region: sum(e['varea'] == region for e in r.cohort()) for region in ('V1-V3', 'VOTC', 'LOTC')}
        self.assertEqual(regions, {'V1-V3': 17, 'VOTC': 15, 'LOTC': 47})
        subjects = {s: sum(e['subject'] == s for e in r.cohort()) for s in ('sub-p11','sub-p12','sub-p13','sub-p14')}
        self.assertEqual(subjects, {'sub-p11':38,'sub-p12':7,'sub-p13':10,'sub-p14':24})
        allocations = r.validate_manifest(self.manifest, self.pinned)
        for item in allocations.values():
            self.assertEqual(sorted(i for f in item['folds'] for i in f['test_rows']), list(range(72)))
            for f in item['folds']:
                self.assertEqual(len(f['train_rows']), 66)
                self.assertEqual(len(f['test_rows']), 6)
                self.assertFalse(set(f['train_rows']) & set(f['test_rows']))

    def test_seeded_replay_is_identical_and_electrode_streams_differ(self):
        self.assertEqual(r.freeze(self.metadata, 20261117), self.manifest)
        self.assertNotEqual(self.manifest['electrodes'][0]['folds'], self.manifest['electrodes'][1]['folds'])
        self.assertNotEqual(self.manifest['electrodes'][0]['folds'], r.freeze(self.metadata, 20261118)['electrodes'][0]['folds'])
        for seed in [True, -1, 2**256, 0.5]:
            with self.assertRaises(ValueError):
                r.freeze(self.metadata, seed)

    def test_native_author_loop_parity(self):
        if AUTHOR_SOURCE is None:
            self.skipTest('Pass --author-fit-source for independently pinned AST parity')
        raw = AUTHOR_SOURCE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), r.FIT_SOURCE_SHA256)
        native = ast.parse(raw)
        model_fit = next(n for n in native.body if isinstance(n, ast.FunctionDef) and n.name == 'model_fit')
        loop = next(n for n in model_fit.body if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == 'fold_idx')
        # Only test_idx=[] and the literal two-line random.sample/remove loop;
        # never execute imports, file reads, SciPy, model code or author fitting.
        selected = ast.Module(body=loop.body[:2], type_ignores=[])
        self.assertIsInstance(selected.body[0], ast.Assign)
        self.assertIsInstance(selected.body[1], ast.For)
        original = compile(ast.fix_missing_locations(selected), '<pinned-author-sampling-loop>', 'exec')
        for ordered in [self.rows, list(reversed(self.rows))]:
            for seed in [0, 19, 20261117]:
                pools = [[i for i, row in enumerate(ordered) if row['img_cat'] == c] for c in r.CATEGORIES]
                env = {'random': random.Random(seed), 'y_idx_per_cat': pools, 'img_cat':r.CATEGORIES}
                observed = []
                for _ in range(12):
                    exec(original, {'__builtins__':{'range':range, 'len':len}}, env)
                    observed.append(env['test_idx'][:])
                actual, _, _ = r.source_folds(ordered, seed)
                self.assertEqual([f['test_rows'] for f in actual], observed)

    def test_source_row_order_is_preserved(self):
        reverse = list(reversed(self.rows))
        raw = table(reverse)
        manifest = r.freeze(metadata(reverse, raw), 20261117)
        packet = r.project(raw, manifest, manifest['manifest_sha256'], self.electrode, 0, 'named_response_columns')
        for item in packet['training'] + packet['queries']:
            self.assertEqual({k:item[k] for k in reverse[0]}, reverse[item['source_row']])
        with self.assertRaisesRegex(ValueError, 'Ordered source'):
            changed = copy.deepcopy(manifest)
            changed_rows = changed['electrodes'][0]['rows']
            changed_rows[0], changed_rows[1] = changed_rows[1], changed_rows[0]
            changed['manifest_sha256'] = r.digest({k:v for k,v in changed.items() if k!='manifest_sha256'})
            r.project(raw, changed, changed['manifest_sha256'], self.electrode, 0, 'named_response_columns')

    def test_named_packet_contains_no_query_responses_in_all_twelve_folds(self):
        for fold in range(12):
            packet = r.project(self.raw, self.manifest, self.pinned, self.electrode, fold, 'named_response_columns')
            withheld = {x['source_row'] for x in packet['queries']}
            self.assertEqual(len(packet['training']), 66)
            self.assertEqual(packet['target_columns'], [str(i) for i in range(819)])
            for q in packet['queries']:
                self.assertEqual(set(q), {'source_row', 'trial_type', 'img_cat', 'temp_cond'})
            values = [v for item in packet['training'] for v in item['response']]
            self.assertFalse({int(v-1000000)//1000 for v in values} & withheld)
            for item in packet['training']:
                self.assertEqual(item['response'][0], 1000000 + item['source_row']*1000)
                self.assertEqual(item['response'][-1], 1000000 + item['source_row']*1000 + 818)

    def test_literal_column_discrepancy_is_explicit_and_exact(self):
        literal = r.project(self.raw, self.manifest, self.pinned, self.electrode, 0, 'source_positional_cv')
        named = r.project(self.raw, self.manifest, self.pinned, self.electrode, 0, 'named_response_columns')
        self.assertEqual(literal['queries'], named['queries'])
        self.assertEqual(literal['target_columns'], ['temp_cond'] + [str(i) for i in range(818)])
        for a,b in zip(literal['training'], named['training']):
            self.assertEqual(len(a['response']), 819)
            self.assertEqual(a['response'], [float(a['temp_cond'])] + b['response'][:-1])
        with self.assertRaises(ValueError):
            r.project(self.raw, self.manifest, self.pinned, self.electrode, 0, 'automatic')

    def test_missing_duplicate_and_unknown_conditions_are_rejected(self):
        for mutate in [lambda x:x.pop(), lambda x:x.append(x[0]), lambda x:x.__setitem__(1, x[0]),
                       lambda x:x[0].__setitem__('temp_cond', True), lambda x:x[0].__setitem__('img_cat','OTHER')]:
            changed = rows()
            mutate(changed)
            with self.assertRaises(ValueError):
                r.source_folds(changed, 0)

    def test_missing_duplicate_and_unknown_electrodes_are_rejected(self):
        for mutate in [lambda x:x.pop(), lambda x:x.__setitem__(1, x[0]),
                       lambda x:x[0].__setitem__('electrode_id', 'other'),
                       lambda x:x[0].__setitem__('source_data_sha256', 'unbound')]:
            changed = copy.deepcopy(self.metadata)
            mutate(changed['electrodes'])
            with self.assertRaises(ValueError):
                r.freeze(changed, 0)

    def test_frozen_digest_and_changed_source_refused(self):
        changed = copy.deepcopy(self.manifest)
        changed['electrodes'][0]['folds'][0]['test_rows'].reverse()
        with self.assertRaisesRegex(ValueError, 'digest'):
            r.project(self.raw, changed, self.pinned, self.electrode, 0, 'named_response_columns')
        with self.assertRaisesRegex(ValueError, 'Source table bytes'):
            r.project(self.raw+b'\n', self.manifest, self.pinned, self.electrode, 0, 'named_response_columns')

    def test_self_consistent_malformed_allocations_refused(self):
        for mutation in ['repeat_fold','training_overlap','category_order','boolean_index']:
            changed = copy.deepcopy(self.manifest)
            folds = changed['electrodes'][0]['folds']
            if mutation == 'repeat_fold':
                folds[1] = copy.deepcopy(folds[0]); folds[1]['fold'] = 1
            elif mutation == 'training_overlap':
                folds[0]['train_rows'][0] = folds[0]['test_rows'][0]
            elif mutation == 'category_order':
                folds[0]['test_rows'].reverse()
            else:
                folds[0]['test_rows'][0] = True
            changed['manifest_sha256'] = r.digest({k:v for k,v in changed.items() if k!='manifest_sha256'})
            with self.assertRaises(ValueError):
                r.validate_manifest(changed, changed['manifest_sha256'])

    def test_bad_table_schema_and_nonfinite_refused(self):
        malformed = [self.raw.replace(b'temp_cond', b'wrong', 1), self.raw.replace(b'1000000', b'nan', 1),
                     self.raw.replace(b'1000000', b'inf', 1), self.raw.replace(b'1000000 ', b'', 1),
                     self.raw.replace(b'onepulse BODIES', b'onepulse  BODIES', 1)]
        for raw in malformed:
            with self.assertRaises(ValueError):
                r.parse_source_table(raw)

    def test_cli_export_and_exclusive_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'meta.json').write_text(json.dumps(self.metadata))
            r.main(['freeze','--metadata',str(root/'meta.json'),'--seed','20261117','--output',str(root/'frozen.json')])
            (root/'data.txt').write_bytes(self.raw)
            args = ['project','--manifest',str(root/'frozen.json'),'--manifest-sha256',self.pinned,
                    '--source-table',str(root/'data.txt'),'--electrode',self.electrode,'--fold','0',
                    '--branch','named_response_columns','--output',str(root/'packet.json')]
            r.main(args)
            packet = json.loads((root/'packet.json').read_text())
            self.assertEqual(len(packet['training']), 66)
            self.assertEqual(len(packet['queries']), 6)
            with self.assertRaises(FileExistsError):
                r.main(args)

    def test_duplicate_json_keys_and_nonstandard_numbers_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'bad.json'
            for content in ['{"a":1,"a":2}', '{"a":NaN}']:
                target.write_text(content)
                with self.assertRaises(ValueError):
                    r.read_json(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--author-fit-source', type=Path)
    args, extra = parser.parse_known_args()
    AUTHOR_SOURCE = args.author_fit_source
    unittest.main(argv=['test_replay.py'] + extra)
