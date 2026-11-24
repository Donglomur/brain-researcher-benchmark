"""Generated controls for the separately versioned fixed-view uncertainty rule."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
OLD = RASTER = CODEC = None
WRITE_BYTES = 0


def load(path):
    spec = importlib.util.spec_from_file_location('generated_reference', path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


ref = load(HERE/'reference.py')


def feature(value=0., coverage=1.):
    return {'values': [value if coverage else None] * 30, 'coverage': [coverage] * 30,
        'baseline_rms': [.1, .1], 'baseline_coverage': [1., 1.]}


def demos():
    return [feature(-.5), feature(.5), feature(-.5), feature(.5)]


def fit(module=ref):
    return module.fit_features(demos(), [str(i) * 64 for i in range(4)], profile=ref.PROFILE)


def rendered(post, transition=256):
    values = [0.] * transition + [post] * (1024 - transition)
    state = {'start_sample': -256, 'stop_sample': 768, 'units_per_division': 20,
             'record': 'query', 'channels': ['Cz', 'Pz']}
    original = RASTER.render({'channels': [values, values]}, state, 'four_demo')
    encoded, receipt = CODEC.encode_transport_image(original)
    CODEC.verify_equivalence(original, encoded, receipt)
    return encoded


class MethodControls(unittest.TestCase):
    def test_old_source_byte_exact_and_fitted_numerics_unchanged(self):
        self.assertEqual(hashlib.sha256(Path(OLD.__file__).read_bytes()).hexdigest(),
                         '08286eaab4be66d2dc66f646f475a851ab861ac0337279a5696faefbd9c8bfd6')
        old, new = fit(OLD), fit()
        for name in ('means', 'supports', 'scales', 'demonstration_labels', 'demonstration_sha256'):
            self.assertEqual(new[name], old[name])
        self.assertNotEqual(new['schema'], old['schema'])
        with self.assertRaises(ValueError): ref.validate_model(old)

    def test_positive_support_probabilities_are_exact_old_floats(self):
        rng = random.Random(20261124)
        for _ in range(120):
            ds = demos()
            for d in ds:
                d['baseline_coverage'] = [rng.choice((.2, .5, 1.)) for _ in range(2)]
                d['baseline_rms'] = [rng.uniform(.01, .5) for _ in range(2)]
                for j in range(30):
                    d['coverage'][j] = rng.choice((0., .125, .5, 1.))
                    d['values'][j] = rng.uniform(-2., 2.) if d['coverage'][j] else None
            pins = [str(i)*64 for i in range(4)]
            old = OLD.fit_features(ds, pins, profile=ref.PROFILE)
            new = ref.fit_features(ds, pins, profile=ref.PROFILE)
            q = feature()
            q['baseline_coverage'] = [rng.choice((.2, .5, 1.)) for _ in range(2)]
            for j in range(30):
                q['coverage'][j] = rng.choice((0., .25, 1.))
                q['values'][j] = rng.uniform(-2., 2.) if q['coverage'][j] else None
            before = ref.json_bytes(new)
            expected, old_quality = OLD.predict_features(q, old, profile=ref.PROFILE)
            actual, quality = ref.predict_features(q, new, profile=ref.PROFILE)
            self.assertEqual(actual.hex(), expected.hex())
            for key in old_quality: self.assertEqual(quality[key], old_quality[key])
            self.assertIs(quality['no_shared_support'], False)
            self.assertEqual(ref.json_bytes(new), before)

    def test_zero_support_returns_half_without_mutating_missing_values(self):
        q, model = feature(coverage=0.), fit()
        before = copy.deepcopy(q)
        p, quality = ref.predict_features(q, model, profile=ref.PROFILE)
        self.assertEqual(p, .5); self.assertIs(quality['no_shared_support'], True)
        self.assertEqual(quality['shared_support_fraction'], 0.)
        self.assertEqual(quality['shared_weights'], [0.] * 30)
        self.assertEqual(q, before)
        with self.assertRaisesRegex(ValueError, 'no shared visible support'):
            OLD.predict_features(q, fit(OLD), profile=ref.PROFILE)

    def test_positive_tie_is_not_zero_support(self):
        p, q = ref.predict_features(feature(), fit(), profile=ref.PROFILE)
        self.assertEqual(p, .5); self.assertIs(q['no_shared_support'], False)

    def test_disjoint_query_and_demo_support_is_zero(self):
        ds = demos()
        for d in ds:
            d['coverage'][15:] = [0.] * 15; d['values'][15:] = [None] * 15
        model = ref.fit_features(ds, ['0'*64]*4, profile=ref.PROFILE)
        q = feature(); q['coverage'][:15] = [0.] * 15; q['values'][:15] = [None] * 15
        p, quality = ref.predict_features(q, model, profile=ref.PROFILE)
        self.assertEqual(p, .5); self.assertIs(quality['no_shared_support'], True)
        self.assertEqual(sum(v > 0 for v in quality['coverage']), 15)

    def test_missing_baseline_is_explicit_missingness(self):
        q = feature(coverage=0.); q['baseline_coverage'] = [0., 0.]; q['baseline_rms'] = [None, None]
        p, quality = ref.predict_features(q, fit(), profile=ref.PROFILE)
        self.assertEqual(p, .5); self.assertEqual(quality['baseline_coverage'], [0., 0.])

    def test_malformed_features_fail_even_when_support_would_be_zero(self):
        for mutate in (lambda q: q.update(extra=1), lambda q: q['values'].pop(),
                       lambda q: q['values'].__setitem__(0, float('nan')),
                       lambda q: q['coverage'].__setitem__(0, float('inf')),
                       lambda q: q['coverage'].__setitem__(0, -1.),
                       lambda q: q['baseline_coverage'].__setitem__(0, True),
                       lambda q: q['baseline_rms'].__setitem__(0, 999.),
                       lambda q: q['coverage'].__setitem__(0, .5)):
            q = feature(coverage=0.); mutate(q)
            with self.assertRaises(ValueError): ref.predict_features(q, fit(), profile=ref.PROFILE)
        with self.assertRaises(ValueError): ref.predict_features(feature(coverage=0.), fit(), profile='wrong')

    def test_invalid_frozen_model_never_falls_back(self):
        for mutate in (lambda m: m.update(extra=1), lambda m: m.update(schema='wrong'),
                       lambda m: m['scales'].__setitem__(0, float('nan')),
                       lambda m: m['supports'][0].__setitem__(0, -1),
                       lambda m: m.update(source_sha256='0'*64)):
            model = copy.deepcopy(fit()); mutate(model)
            with self.assertRaises(ValueError): ref.predict_features(feature(coverage=0.), model, profile=ref.PROFILE)

    def test_impossible_no_common_demo_model_cannot_use_fallback(self):
        model = fit()
        model['supports'][0] = [0.] * 30
        model['means'][0] = [None] * 30
        with self.assertRaisesRegex(ValueError, 'demos have no shared supported features'):
            ref.predict_features(feature(coverage=0.), model, profile=ref.PROFILE)

    def test_invalid_demo_features_never_freeze(self):
        ds = demos(); ds[0]['baseline_rms'][1] = float('nan')
        with self.assertRaises(ValueError): ref.fit_features(ds, ['0'*64]*4, profile=ref.PROFILE)
        with self.assertRaisesRegex(ValueError, 'no shared supported features'):
            ref.fit_features([feature(coverage=0.) for _ in range(4)], ['0'*64]*4, profile=ref.PROFILE)

    def test_real_renderer_gain20_hidden_postmarker_has_no_imputed_signal(self):
        q = ref.extract_features(ref.decode_png(rendered(100., transition=240)))
        self.assertEqual(q['coverage'], [0.] * 30)
        self.assertTrue(all(v is None for v in q['values']))
        self.assertTrue(all(v > 0 for v in q['baseline_coverage']))
        p, quality = ref.predict_features(q, fit(), profile=ref.PROFILE)
        self.assertEqual(p, .5); self.assertIs(quality['no_shared_support'], True)

    def test_renderer_boundary_column_remains_positive_support(self):
        q = ref.extract_features(ref.decode_png(rendered(100.)))
        p, quality = ref.predict_features(q, fit(), profile=ref.PROFILE)
        old_p, _ = OLD.predict_features(q, fit(OLD), profile=ref.PROFILE)
        self.assertEqual(p.hex(), old_p.hex())
        self.assertGreater(quality['shared_support_fraction'], 0.)
        self.assertIs(quality['no_shared_support'], False)

    def test_decoder_failures_are_hard_failures(self):
        data = rendered(100.)
        for bad in (b'not png', data + b'X', data[:-1], data[:100]):
            with self.assertRaises(ValueError): ref.decode_png(bad)

    def test_fresh_cli_frozen_model_and_zero_query_audit(self):
        global WRITE_BYTES
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            root = Path(temp); paths = []
            for i, value in enumerate((-10., 10., -10., 10., 100.)):
                path = root/f'{i}.png'; body = rendered(value, transition=240 if value == 100. else 256); path.write_bytes(body)
                WRITE_BYTES += len(body); paths.append(str(path))
            model = root/'MODEL.json'; common = [sys.executable, '-I', '-S', '-B', str(HERE/'reference.py')]
            done = subprocess.run(common + ['fit', '--profile', ref.PROFILE, '--demos', *paths[:4], '--output', str(model)],
                                  capture_output=True, timeout=10)
            self.assertEqual(done.returncode, 0, done.stderr)
            body = model.read_bytes(); WRITE_BYTES += len(body); digest = hashlib.sha256(body).hexdigest()
            args = common + ['predict', '--profile', ref.PROFILE, '--model', str(model), '--model-sha256', digest,
                             '--query', paths[4], '--trial-id', 'generated']
            predicted = subprocess.run(args, capture_output=True, timeout=10)
            self.assertEqual(predicted.returncode, 0, predicted.stderr)
            value = json.loads(predicted.stdout)
            self.assertEqual(value['target_probability'], .5); self.assertTrue(value['quality']['no_shared_support'])
            self.assertEqual(len(value['quality']['coverage']), 30)
            self.assertEqual(model.read_bytes(), body)
            args[args.index('--model-sha256') + 1] = '0'*64
            args[args.index('--query') + 1] = str(root/'NO_QUERY')
            failed = subprocess.run(args, capture_output=True, timeout=10)
            self.assertEqual(failed.returncode, 2); self.assertEqual(failed.stdout, b'')
            self.assertIn(b'model digest mismatch', failed.stderr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--repository-root', type=Path, required=True)
    parser.add_argument('--case', action='append')
    args = parser.parse_args()
    impl = args.repository_root/'benchmarks/neural/NEURAL-077/implementations'
    OLD = load(impl/'four-demo-image-reference-v1/reference.py')
    RASTER = load(impl/'visual-viewer-v1/raster.py')
    CODEC = load(impl/'visual-provider-pair-v1/transfer_png.py')
    suite = (unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('MethodControls.' + name, sys.modules[__name__])
              for name in args.case) if args.case else unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'skipped': len(result.skipped), 'generated_write_bytes': WRITE_BYTES, 'authentic_inputs_opened': 0}))
    raise SystemExit(not result.wasSuccessful())
