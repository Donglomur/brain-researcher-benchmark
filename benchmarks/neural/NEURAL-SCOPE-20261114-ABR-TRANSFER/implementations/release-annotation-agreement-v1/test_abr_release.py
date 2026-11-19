"""Bounded generated engineering controls. No native input or protected target read.

Selected campaign: PYTHONDONTWRITEBYTECODE=1 python test_abr_release.py --repository W
At most two complete generated paired collectors are written, under TemporaryDirectory.
The complete936 roster uses four synthetic samples/two traces per case; a separate
renderer control exercises all1953 samples and21 traces including repeat/zero levels.
Neither structural fixture is accepted by NativeTarget's fixed authentic source pin.
"""
import argparse
import copy
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

_spec = importlib.util.spec_from_file_location('abr_release', Path(__file__).with_name('abr_release.py'))
a = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a)

REPOSITORY = None
ARTIFACT_BYTES = 0


def identifier(kind, value):
    return hashlib.md5((kind + ':' + str(value)).encode()).hexdigest()


def fixture():
    cases, traces, refs, codes = [], [], [], {}
    stimuli = [{'kind': 'click'}] + [{'kind': 'tone', 'frequency_hz': f} for f in a.TONES]
    for animal in range(1, 105):
        for sindex, s in enumerate(stimuli):
            n = (animal - 1) * 9 + sindex
            cid = identifier('synthetic case', n)
            tids = []
            for repeat in range(2):
                tid = identifier('synthetic trace', 2*n + repeat); tids.append(tid)
                traces.append({'trace_id': tid, 'case_id': cid, 'stimulus': s,
                               'level_db': 0 if repeat == 0 else 95,
                               'sample_offset': (2*n + repeat)*4, 'sample_count': 4,
                               'axis': {'kind': 'sample_index', 'sample_period_ms': None,
                                        'first_sample_ms': None, 'unit': None,
                                        'reason': 'release CSV contains no physical axis or voltage calibration'}})
            cases.append({'case_id': cid, 'stimulus': s, 'trace_ids': tids, 'repeated_levels_preserved': False})
            # Generated exceptional codes, deliberately not the genuine case identities.
            code = 100 if n in (0, 10, 20) else 50
            codes[cid] = code
            refs.append({'case_id': cid, 'animal_source_id': animal, 'animal_id': identifier('synthetic animal', animal),
                         'genetic_background': 'C57BL/6NTacCdh23+' if animal <= 54 else 'C57BL/6N',
                         'annotation': {'stimulus': s, 'raw_token': str(code), 'source_numeric_value': code,
                                        'semantics': 'unresolved_exact_or_censored', 'source_line': animal + 1,
                                        'source_column': 'Click' if sindex == 0 else str(a.TONES[sindex-1]//1000) + ' kHz'},
                         'observed_level_min': 0, 'observed_level_max': 95, 'outside_observed_levels': code == 100,
                         'score_admission': False})
    roster = a.Roster(cases, traces, samples=4, trace_count=1872)
    def provider(cid):
        return roster.packet(cid, lambda meta: [0.0, -1.0, 1.0, float(meta['level_db']) / 95])
    return cases, traces, refs, codes, roster, provider


def count_writes(root):
    global ARTIFACT_BYTES
    ARTIFACT_BYTES += sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if ARTIFACT_BYTES > 2 * 1024**2:
        raise AssertionError('selected generated file-write budget exceeded')


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.traces, cls.refs, cls.codes, cls.roster, provider = fixture()
        cls.provider = staticmethod(provider)
        cls.raster = a.load_raster(REPOSITORY)

    def test_full_observed_roster_and_page_coverage(self):
        self.assertEqual(len(self.roster.ids), 936)
        self.assertEqual(len({r['animal_id'] for r in self.refs}), 104)
        for cid in self.roster.ids:
            packet = self.provider(cid)
            covered = [i for page in a.panels(packet) for i in page]
            self.assertEqual(covered, list(range(len(packet['traces']))))
            self.assertEqual([t['release_level_code'] for t in packet['traces']], [0, 95])
            self.assertEqual([len(t['samples']) for t in packet['traces']], [4, 4])
        self.assertEqual(sum(r['annotation']['source_numeric_value'] == 100 for r in self.refs), 3)

    def test_roster_missing_duplicate_bad_join_and_calibration(self):
        bad = copy.deepcopy(self.cases); bad[-1] = copy.deepcopy(bad[0])
        with self.assertRaises(ValueError): a.Roster(bad, self.traces, samples=4, trace_count=1872)
        with self.assertRaises(ValueError): a.Roster(self.cases[:-1], self.traces, samples=4, trace_count=1872)
        bad = copy.deepcopy(self.traces); bad[1]['sample_offset'] += 1
        with self.assertRaises(ValueError): a.Roster(self.cases, bad, samples=4, trace_count=1872)
        bad = copy.deepcopy(self.traces); bad[0]['axis']['unit'] = 'uV'
        with self.assertRaises(ValueError): a.Roster(self.cases, bad, samples=4, trace_count=1872)
        bad = copy.deepcopy(self.traces); bad[0]['animal_id'] = identifier('forbidden', 1)
        with self.assertRaises(ValueError): a.Roster(self.cases, bad, samples=4, trace_count=1872)
        bad = copy.deepcopy(self.cases); bad[0]['trace_ids'].append(bad[1]['trace_ids'][0])
        with self.assertRaises(ValueError): a.Roster(bad, self.traces, samples=4, trace_count=1872)

    def test_repeated_levels_not_deduplicated(self):
        cases, traces = copy.deepcopy(self.cases), copy.deepcopy(self.traces)
        traces[1]['level_db'] = 0; cases[0]['repeated_levels_preserved'] = True
        r = a.Roster(cases, traces, samples=4, trace_count=1872)
        packet = r.packet(r.ids[0], lambda _: [0, 1, -1, 0])
        self.assertEqual(len(packet['traces']), 2)
        self.assertEqual([t['release_level_code'] for t in packet['traces']], [0, 0])

    def test_reader_must_supply_every_finite_sample(self):
        with self.assertRaises(ValueError): self.roster.packet(self.roster.ids[0], lambda _: [1, 2, 3])
        with self.assertRaises(ValueError): self.roster.packet(self.roster.ids[0], lambda _: [1, 2, 3, math.nan])
        with self.assertRaises(ValueError): self.roster.packet(self.roster.ids[0], lambda _: [1, 2, 3, True])

    def test_real_renderer_1953_samples_all21_traces_and_native_axes(self):
        packet = self.provider(self.roster.ids[0]); packet['traces'] = []
        for i in range(21):
            values = [0.0] * 1953
            values[0], values[1], values[1000], values[-1] = -1.0, 0.5, 1.0, -0.25
            packet['traces'].append({'trace_id': identifier('full renderer trace', i),
                                     'release_level_code': 0 if i < 2 else i*5,
                                     'sample_indices': [0, 1952], 'samples': values})
        viewer = a.Viewer(packet, self.raster)
        self.assertEqual(viewer.action({'type': 'numeric'}), a.canonical(packet))
        self.assertEqual(viewer.action({'type': 'pages'})['pages'], 7)
        seen, count = [], 0
        for page in range(7):
            png, info = viewer.action({'type': 'page', 'page': page})
            self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertLess(len(png), 100000)
            seen += info['trace_indices']; count += info['samples_drawn']
            self.assertEqual(info['native_amplitude_scale'], 1)
            # Decode the actual emitted RGB image, not a mocked renderer result.
            position, compressed = 8, bytearray()
            while position < len(png):
                size = struct.unpack('>I', png[position:position+4])[0]
                kind = png[position+4:position+8]; data = png[position+8:position+8+size]
                crc = struct.unpack('>I', png[position+8+size:position+12+size])[0]
                self.assertEqual(crc, zlib.crc32(kind + data))
                if kind == b'IDAT': compressed.extend(data)
                position += 12 + size
            pixels = zlib.decompress(compressed)
            self.assertEqual(len(pixels), 820*(1+1400*3))
            self.assertIn(bytes(self.raster.BLUE), pixels)
        self.assertEqual(seen, list(range(21)))
        self.assertEqual(count, 21*1953)
        for invalid in ({'type': 'page', 'page': 7}, {'type': 'page', 'page': True},
                        {'type': 'crop', 'start': 0, 'stop': 10}, {'type': 'numeric', 'case_id': 'other'}):
            with self.assertRaises(ValueError): viewer.action(invalid)

    def test_extreme_finite_renderer_and_numeric_precision(self):
        packet = self.provider(self.roster.ids[-1])
        packet['traces'][0]['samples'] = [-sys.float_info.max, 0.0, sys.float_info.max, 5e-324]
        png, info = a.render(packet, 0, self.raster)
        self.assertEqual(info['samples_drawn'], 8)
        self.assertEqual(a.decode(a.Viewer(packet, self.raster).action({'type': 'numeric'})), packet)
        self.assertLess(len(png), 100000)

    def test_pure_animal_macro_oracle_differs_from_case_micro(self):
        refs = {'a': {'animal': 'one', 'code': 100}, 'b': {'animal': 'one', 'code': 100},
                'c': {'animal': 'two', 'code': 100}}
        result = a.metrics(refs, {'a': 100, 'b': 100.0, 'c': 95})
        self.assertEqual(result['animal_macro_exact_numeric_code_agreement'], 0.5)
        self.assertEqual(result['animal_macro_code_mae'], 2.5)
        self.assertEqual(result['animal_macro_within_5_code_units'], 1)
        self.assertEqual(result['case_count'], 3)

    def test_no_hidden_tolerance_rounding_or_extreme_overflow(self):
        refs = {'a': {'animal': 'one', 'code': 100}}
        result = a.metrics(refs, {'a': Decimal('100.000000000000001')})
        self.assertEqual(result['animal_macro_exact_numeric_code_agreement'], 0)
        self.assertGreater(result['animal_macro_code_mae'], 0)
        result = a.metrics(refs, {'a': -sys.float_info.max})
        self.assertEqual(result['animal_macro_exact_numeric_code_agreement'], 0)
        self.assertTrue(math.isfinite(result['animal_macro_code_mae']))
        a.canonical(result)  # Fail if JSON can only represent a nonfinite aggregate.
        with self.assertRaises(ValueError):
            a.prediction_number(a.decode(b'1e10000', decimal=True))

    def test_raw_reference_join_and_source_semantics(self):
        self.assertEqual(len(a.validate_references(self.refs, self.roster)), 936)
        mutations = [('case_id', self.refs[1]['case_id']), ('animal_id', self.refs[9]['animal_id']),
                     ('score_admission', True), ('observed_level_max', 100),
                     ('genetic_background', 'C57BL/6N')]
        for field, value in mutations:
            rows = copy.deepcopy(self.refs); rows[0][field] = value
            with self.assertRaises(ValueError): a.validate_references(rows, self.roster)
        for field, value in [('semantics', 'exact'), ('source_numeric_value', 95), ('raw_token', '95')]:
            rows = copy.deepcopy(self.refs); rows[0]['annotation'][field] = value
            with self.assertRaises(ValueError): a.validate_references(rows, self.roster)
        rows = copy.deepcopy(self.refs); rows[0]['annotation']['raw_token'] = '100.0'
        self.assertEqual(a.validate_references(rows, self.roster)[self.refs[0]['case_id']]['code'], 100)

    def test_no_authentic_admission_from_generated_completion_or_alias(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root/'COMPLETE.json').write_bytes(b'{"target_cases":936,"target_animals":104}')
            with self.assertRaises(ValueError): a.NativeTarget(root)
            p = root/'source'; p.write_bytes(b'abc')
            alias = root/'alias'; alias.symlink_to(p)
            with self.assertRaises(ValueError): a.read_pin(alias, (3, a.sha(b'abc')))
            with self.assertRaises(ValueError): a.read_pin(p, (3, '0'*64))
            count_writes(root)

    def test_strict_response_json(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff'):
            with self.assertRaises(ValueError): a.decode(raw, decimal=True)
        for x in (True, False, float('inf'), Decimal('NaN')):
            with self.assertRaises(ValueError): a.number(x)

    def _complete(self, root, invalid=False):
        pair = a.Pair(root/'pair', self.roster, self.provider, b'# fixed generated programme\n',
                      b'Label-free generated documentation.\n', source_identity=a.sha(b'generated fixture, not authentic'))
        with self.assertRaises(ValueError): pair.verify_seal()
        with self.assertRaises(ValueError): pair.seal()
        failures = 0
        for arm in ('direct', 'programme'):
            for index, cid in enumerate(self.roster.ids):
                raw_packet = pair.expose(arm)
                self.assertEqual(raw_packet, a.canonical(self.provider(cid)))
                if index == 0:
                    with self.assertRaises(ValueError): pair.expose(arm)
                prediction = self.codes[cid]
                if arm == 'direct' and prediction == 100:
                    prediction = 95
                raw = a.canonical({'case_id': cid, 'predicted_annotation_code': prediction})
                if invalid and arm == 'direct' and index < 7:
                    raw = (b'{}', b'{"case_id":"wrong","predicted_annotation_code":1}',
                           b'{"case_id":"'+cid.encode()+b'","predicted_annotation_code":true}',
                           b'{"case_id":"'+cid.encode()+b'","predicted_annotation_code":NaN}',
                           b'{"case_id":"'+cid.encode()+b'","predicted_annotation_code":1,"predicted_annotation_code":2}',
                           b'{"case_id":"'+cid.encode()+b'","predicted_annotation_code":null}',
                           b'x'*4097)[index]
                    failures += 1
                self.assertEqual(pair.submit(arm, cid, raw), {'accepted_first_final': True})
                if index == 0:
                    with self.assertRaises(ValueError): pair.submit(arm, cid, a.canonical({'case_id': cid, 'predicted_annotation_code': 50}))
            if arm == 'direct':
                with self.assertRaises(ValueError): pair.verify_seal()
        pair.seal()
        with self.assertRaises(ValueError): pair.expose('direct')
        return pair, failures

    def test_full936_paired_first_final_target_last_and_exact100_oracle(self):
        global ARTIFACT_BYTES
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); pair, _ = self._complete(root)
            result = pair.score(self.refs)
            direct = result['arms']['direct']; programme = result['arms']['programme']
            self.assertFalse(direct['aggregate_withheld'])
            self.assertEqual(direct['coverage'], {'required': 936, 'valid': 936, 'invalid': 0})
            metrics = direct['metrics']
            self.assertAlmostEqual(metrics['animal_macro_exact_numeric_code_agreement'], 933/936)
            self.assertAlmostEqual(metrics['animal_macro_code_mae'], 15/936)
            self.assertEqual(metrics['animal_macro_within_5_code_units'], 1)
            self.assertEqual(direct['strata']['source_code_100']['animal_macro_exact_numeric_code_agreement'], 0)
            self.assertEqual(programme['metrics']['animal_macro_exact_numeric_code_agreement'], 1)
            self.assertEqual(result['target_100_count'], 3)
            for key, value in a.HOLDS.items(): self.assertEqual(result[key], value)
            a.canonical(result)
            with self.assertRaises(ValueError): pair.score(self.refs)
            # An external file rewrite is detected before any reuse of target-last scoring.
            path = pair.root/('direct-'+self.roster.ids[0]+'.json')
            ARTIFACT_BYTES += path.stat().st_size
            path.write_bytes(b'{}')
            with self.assertRaises(ValueError): pair.verify_seal()
            count_writes(root)

    def test_invalid_first_finals_never_replaced_or_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); pair, failures = self._complete(root, invalid=True)
            result = pair.score(self.refs)
            direct = result['arms']['direct']
            self.assertEqual(failures, 7)
            self.assertTrue(direct['aggregate_withheld'])
            self.assertNotIn('metrics', direct)
            self.assertEqual(direct['coverage'], {'required': 936, 'valid': 929, 'invalid': 7})
            self.assertEqual(len(direct['failure_case_ids']), 7)
            self.assertEqual(result['arms']['programme']['metrics']['animal_macro_exact_numeric_code_agreement'], 1)
            count_writes(root)

    def test_production_rejects_substituted_provider_and_unsealed_inputs(self):
        # An intentionally incomplete native object is a negative seam sentinel.
        # No fixed source pin is replaced or accepted, and no native file is opened.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            native = object.__new__(a.NativeTarget)
            native.roster = self.roster
            native._targets_opened = False
            docs = root/'unreviewed-docs'; docs.write_bytes(b'labelled examples do not qualify')
            with self.assertRaises(ValueError):
                native.new_pair(root/'unqualified', b'fixed', documentation_path=docs)
            self.assertFalse((root/'unqualified').exists())
            pair = a.Pair(root/'pair', self.roster, self.provider, b'fixed', b'docs', source_identity=a.COMPLETE_PIN[1])
            with self.assertRaisesRegex(ValueError, 'originate'):
                native.score_sealed(pair)
            pair._native_target = native
            with self.assertRaisesRegex(ValueError, 'substituted'):
                pair.expose('direct')
            with self.assertRaisesRegex(ValueError, 'substituted'):
                native.score_sealed(pair)
            pair.provider = native.packet
            with self.assertRaisesRegex(ValueError, 'not sealed'):
                native.score_sealed(pair)
            self.assertFalse(native._targets_opened)
            count_writes(root)

    def test_roster_mutation_after_snapshot_is_refused(self):
        _, _, _, _, roster, _ = fixture()
        cid = roster.ids[0]
        tid = roster.cases[cid]['trace_ids'][0]
        roster.traces[tid]['level_db'] = 1
        with self.assertRaises(ValueError): roster.verify_case(cid)
        with self.assertRaises(ValueError): roster.verify()

    def test_programme_mutation_and_mismatched_arm_samples(self):
        global ARTIFACT_BYTES
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            pair = a.Pair(root/'changed', self.roster, self.provider, b'x', b'docs', source_identity=a.sha(b'fixture'))
            ARTIFACT_BYTES += 1
            (pair.root/'programme').write_bytes(b'y')
            with self.assertRaises(ValueError): pair.expose('direct')
            count_writes(root)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); calls = 0
            def changed(cid):
                nonlocal calls
                p = self.provider(cid); calls += 1
                if calls > 1: p['traces'][0]['samples'][0] = 0.125
                return p
            pair = a.Pair(root/'mismatch', self.roster, changed, b'x', b'docs', source_identity=a.sha(b'fixture'))
            pair.expose('direct'); cid = self.roster.ids[0]
            pair.submit('direct', cid, b'{}')
            with self.assertRaises(ValueError): pair.expose('programme')
            count_writes(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', type=Path, required=True)
    args = parser.parse_args(); REPOSITORY = args.repository
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'generated_control_file_bytes': ARTIFACT_BYTES, 'generated_write_cap_bytes': 2097152,
                      'native_original_body_reads': 0, 'model_calls': 0, 'authentic_claims': 0}))
    raise SystemExit(not result.wasSuccessful())
