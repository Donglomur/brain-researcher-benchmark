"""Generated full-panel controls. No original packet, target, provider or model is opened.

Full-history controls substitute only the renderer with a deterministic, lossless
byte projection to avoid thousands of rasterizations. Separate controls exercise
the actual PNG renderer, decode its pixels and inspect every literal cell.
"""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import struct
import tempfile
import types
import unittest
from unittest.mock import patch
import zlib

import numpy as np

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('count_viewer_test_module', HERE / 'viewer.py')
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
WRITTEN = 0
ORIGINAL_SAVE = v.save


def counted_save(path, body):
    global WRITTEN
    ORIGINAL_SAVE(path, body)
    WRITTEN += len(body)


v.save = counted_save


def put(path, body):
    global WRITTEN
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body); WRITTEN += len(body)
    return path


def archive(values):
    b = io.BytesIO(); np.savez(b, **values); return b.getvalue()


def fast_image(metadata, counts, units, raster):
    # Explicit generated projection substitute, never available through the CLI.
    body = v.encoded({'metadata': metadata, 'counts': counts, 'units': units})
    return body, body


class Fixture:
    def __init__(self, root, real_renderer=False):
        self.root = Path(root)
        self.sources = v.Sources()
        self.sources.expected = copy.deepcopy(self.sources.expected)
        self.arrays = {}
        self.files = {}
        for split, n, offset in (('train', 748, 0), ('query', 258, 748)):
            c = np.arange(n, dtype=np.int64) % 40
            self.arrays[split] = {'case_id': np.array([f'dmfc-{i + offset:06d}' for i in range(n)], dtype='<U11'),
                 'condition': c, 'context': c // 5,
                 'nominal_ts_ms': np.array([800, 900, 1000, 1100, 1200] * 4 + [480, 560, 640, 720, 800] * 4, dtype='<f8')[c],
                 'clock_seconds': (np.arange(n, dtype='<f8') + offset) * 1.25,
                 'counts': (np.arange(n * 160, dtype='<u4') % 103).reshape(n, 4, 40)}
            self.arrays[split]['counts'][0, 0, 0] = 0
            self.arrays[split]['counts'][-1, 3, 39] = 4294967295
            if split == 'train':
                self.arrays[split].update(tp_ms=800. + c.astype('<f8') * 2, fold=np.arange(n, dtype='<i8') * 5 // n)
        units = v.encoded({'unit_id': list(range(1001, 1041)), 'source': 'generated full 40-unit support'})
        contract = v.encoded({'candidate_id': 'NEURAL-095', 'fixture': True})
        for view in v.VIEWS:
            bodies = {}
            fields = {}
            for split in ('train', 'query'):
                values = {k: x for k, x in self.arrays[split].items() if view == 'neural' or k != 'counts'}
                bodies[split + '.npz'] = archive(values); fields[split] = sorted(values)
            bodies.update({'units.json': units, 'contract.json': contract,
                'schema.json': v.encoded({'train_n': 748, 'query_n': 258, 'paired_observation_view': view,
                 'bin_edges_seconds_relative_to_Set': [-.2, -.15, -.1, -.05, 0.], 'bin_convention': '[left,right)',
                 'counts_available': view == 'neural', 'public_keys': fields})})
            self.files[view] = {}
            for name, body in bodies.items():
                self.files[view][name] = put(self.root / view / name, body)
                self.sources.expected['views'][view + '/' + name] = v.pin(body)
        if not real_renderer:
            self.sources.modules['render'] = types.SimpleNamespace(render=fast_image)
        self.packets = {view: v.Packet(view, files, self.sources) for view, files in self.files.items()}

    def history(self, view, prediction=800., all_training=False, browse_reverse=False):
        packet = self.packets[view]; session = v.Session(packet)
        rows = [packet.header()]
        if all_training:
            for i in range(748):
                row, _ = session.step({'op': 'show_train', 'index': i}); rows.append(row)
        if browse_reverse:
            for i in reversed(range(258)):
                row, _ = session.step({'op': 'show_query', 'index': i}); rows.append(row)
        for i, name in enumerate(packet.ids):
            row, _ = session.step({'op': 'show_query', 'index': i}); rows.append(row)
            value = prediction(i) if callable(prediction) else prediction
            row, _ = session.step({'op': 'answer', 'case_id': name, 'prediction_ms': value}); rows.append(row)
        rows.append(session.finish())
        return b''.join(map(v.encoded, rows))

    def histories(self, cue=800., neural=800.):
        return {view: put(self.root / (view + '.jsonl'), self.history(view, prediction))
                for view, prediction in zip(v.VIEWS, (cue, neural))}

    def truth(self):
        q = self.arrays['query']
        return {'case_id': q['case_id'].copy(), 'condition': q['condition'].copy(), 'context': q['context'].copy(),
                'tp_ms': np.full(258, 800., dtype='<f8')}

    def references(self):
        # Independently constructed constant-100-ms error panel, unequal group support.
        q = self.arrays['query']
        row = {'n': 258, 'mae_ms': 100., 'rmse_ms': 100., 'eight_context_macro_mae_ms': 100.}
        for key, field, n in (('by_condition', 'condition', 40), ('by_context', 'context', 8)):
            row[key] = {str(k): {'n': int(np.sum(q[field] == k)), 'mae_ms': 100.} for k in range(n)}
        return {'scores': {key: copy.deepcopy(row) for key in self.sources.modules['metrics'].METHODS}}


def unpack_png(body):
    assert body.startswith(b'\x89PNG\r\n\x1a\n')
    offset = 8; chunks = []; scan = b''
    while offset < len(body):
        n = struct.unpack('>I', body[offset:offset + 4])[0]
        name = body[offset + 4:offset + 8]; data = body[offset + 8:offset + 8 + n]
        crc = struct.unpack('>I', body[offset + 8 + n:offset + 12 + n])[0]
        assert zlib.crc32(name + data) == crc
        chunks.append(name)
        if name == b'IHDR':
            assert struct.unpack('>IIBBBBB', data) == (1400, 820, 8, 2, 0, 0, 0)
        if name == b'IDAT':
            scan += data
        offset += n + 12
    assert offset == len(body) and chunks == [b'IHDR', b'IDAT', b'IEND']
    decoded = zlib.decompress(scan)
    assert len(decoded) == 820 * (4200 + 1)
    assert all(decoded[y * 4201] == 0 for y in range(820))
    return b''.join(decoded[y * 4201 + 1:(y + 1) * 4201] for y in range(820))


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.generated-count-viewer-', dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.f = Fixture(self.temp.name)

    def test_complete_projection_all_cases_both_views(self):
        for view, packet in self.f.packets.items():
            self.assertEqual(len(packet.arrays['train']['case_id']), 748)
            self.assertEqual(len(packet.ids), 258)
            for split, n in (('train', 748), ('query', 258)):
                for i in range(n):
                    obs, body = packet.show(split, i)
                    projected = v.decode(body)
                    self.assertEqual(obs['metadata']['case_id'], self.f.arrays[split]['case_id'][i])
                    self.assertEqual(projected['metadata']['condition'], int(self.f.arrays[split]['condition'][i]))
                    self.assertEqual(projected['units'], list(range(1001, 1041)))
                    self.assertEqual(projected['counts'], self.f.arrays[split]['counts'][i].tolist() if view == 'neural' else None)
                    self.assertEqual('tp_ms' in projected['metadata'], split == 'train')
                    self.assertEqual('fold' in projected['metadata'], split == 'train')
        v.pair_packets(self.f.packets)

    def test_nominal_800_does_not_replace_condition_or_context(self):
        p = self.f.packets['neural']
        a, b = p.metadata('query', 0), p.metadata('query', 24)
        self.assertEqual(a['nominal_ts_ms'], 800.)
        self.assertEqual(b['nominal_ts_ms'], 800.)
        self.assertNotEqual(a['condition'], b['condition'])
        self.assertNotEqual(a['context'], b['context'])

    def test_replay_all_training_and_reverse_query_browse_preserves_order(self):
        body = self.f.history('neural', lambda i: -i - .25, all_training=True, browse_reverse=True)
        answer = v.replay(self.f.packets['neural'], body)
        np.testing.assert_array_equal(answer, -np.arange(258) - .25)

    def test_typed_answers_duplicate_missing_order_nonfinite_boolean_refused(self):
        p = self.f.packets['cue_only']; s = v.Session(p)
        for value in (True, '1', float('nan'), float('inf'), 10**1000):
            s.step({'op': 'show_query', 'index': 0})
            with self.assertRaises(ValueError): s.step({'op': 'answer', 'case_id': p.ids[0], 'prediction_ms': value})
        with self.assertRaises(ValueError): s.step({'op': 'answer', 'case_id': p.ids[1], 'prediction_ms': 0.})
        s.step({'op': 'answer', 'case_id': p.ids[0], 'prediction_ms': -2.})
        with self.assertRaises(ValueError): s.step({'op': 'answer', 'case_id': p.ids[0], 'prediction_ms': 1.})
        with self.assertRaises(ValueError): s.finish()
        for action in ({'op': 'show_query', 'index': True}, {'op': 'show_query', 'index': 258},
                       {'op': 'show_query', 'index': 0, 'tp_ms': 999.}, {'op': 'fit', 'index': 0}):
            with self.assertRaises(ValueError): s.step(action)

    def test_replay_view_roster_image_and_missing_event_tampering(self):
        body = self.f.history('neural')
        rows = [v.decode(x) for x in body.splitlines()]
        for mutate in (lambda r: r[0].update(view='cue_only'),
                       lambda r: r[0]['query_ids'].reverse(),
                       lambda r: r[1]['observation']['image'].update(sha256='0' * 64),
                       lambda r: r.pop(-2),
                       lambda r: r.insert(3, copy.deepcopy(r[2]))):
            changed = copy.deepcopy(rows); mutate(changed)
            with self.assertRaises(ValueError): v.replay(self.f.packets['neural'], b''.join(map(v.encoded, changed)))

    def test_pinned_input_refused_before_npz_decode(self):
        path = self.f.files['neural']['query.npz']
        body = path.read_bytes(); put(path, body[:-1] + bytes([body[-1] ^ 1]))
        with patch.object(self.f.sources.modules['project'], 'members', side_effect=AssertionError('decode called')):
            with self.assertRaisesRegex(ValueError, 'identity'): v.Packet('neural', self.f.files['neural'], self.f.sources)

    def test_forbidden_query_target_and_cue_counts_are_not_admitted(self):
        for view, extra, value in (('neural', 'tp_ms', np.ones(258)), ('cue_only', 'counts', self.f.arrays['query']['counts'])):
            values = {k: x for k, x in self.f.arrays['query'].items() if view == 'neural' or k != 'counts'}
            values[extra] = value; body = archive(values)
            path = self.f.files[view]['query.npz']; put(path, body)
            self.f.sources.expected['views'][view + '/query.npz'] = v.pin(body)
            with self.assertRaisesRegex(ValueError, 'NPZ members'): v.Packet(view, self.f.files[view], self.f.sources)

    def test_common_member_mismatch_refuses_pair(self):
        packet = self.f.packets['neural']; packet.common = copy.deepcopy(packet.common)
        packet.common['query']['clock_seconds'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'common members'): v.pair_packets(self.f.packets)

    def test_exact_integer_layout_and_actual_png_lossless(self):
        s = v.Sources(); render, raster = s.modules['render'], s.modules['raster']
        metadata = self.f.packets['neural'].metadata('train', 747)
        counts = self.f.arrays['train']['counts'][747].tolist()
        units = list(self.f.packets['neural'].units)
        layout = render.layout(metadata, counts, units)
        for u in range(40):
            self.assertIn((30, 201 + u * 15, str(units[u]), 2), layout)
            for b in range(4):
                self.assertIn((210 + b * 270, 201 + u * 15, str(counts[b][u]), 2), layout)
        self.assertIn((1020, 786, '4294967295', 2), layout)
        cases = [(metadata, counts), (self.f.packets['neural'].metadata('query', 0), [[0] * 40 for _ in range(4)]),
                 (self.f.packets['cue_only'].metadata('query', 0), None)]
        for meta, values in cases:
            image, pixels = render.render(meta, values, units, raster)
            self.assertEqual(unpack_png(image), pixels)
            self.assertEqual(len(pixels), 3444000)
            manual = raster.Canvas()
            for x, y, text, scale in render.layout(meta, values, units): manual.text(x, y, text, scale=scale)
            self.assertEqual(bytes(manual.pixels), pixels)
            self.assertEqual(unpack_png(manual.png()), pixels)
            print(json.dumps({'generated_png_bytes': len(image), 'rgb_bytes': len(pixels), 'split': meta['split'], 'view': meta['view']}))

    def test_collect_original_validator_complete_and_target_last_score(self):
        histories = self.f.histories(cue=820., neural=810.)
        out = self.f.root / 'collection'; v.collect(self.f.packets, histories, out)
        seen = []
        def ref(): seen.append('references'); return self.f.references()
        def truth(): seen.append('targets'); return self.f.truth()
        score = v.evaluate(self.f.packets, histories, out, ref, truth)
        self.assertEqual(seen, ['references', 'targets'])
        self.assertEqual(score['condition'], v.MODE)
        self.assertEqual(score['paired']['cue_minus_neural_mae_ms'], 10.)
        self.assertEqual(score['arms']['neural']['candidate']['mae_ms'], 10.)
        self.assertEqual(score['arms']['cue_only']['candidate']['rmse_ms'], 20.)
        self.assertEqual(set(score['arms']['neural']['reference_values']), set(self.f.sources.modules['metrics'].METHODS))
        self.assertEqual(len(score['paired']['by_condition']), 40)
        self.assertEqual(len(score['paired']['by_context']), 8)
        self.assertEqual(score['paired_arithmetic_checks'], 50)
        self.assertEqual(score['arms']['neural']['candidate_minus_reference']['cue_clock_ridge']['mae_ms'], -90.)
        self.assertFalse(score['native_understanding_proven'])

    def test_invalid_last_submission_blocks_all_private_and_reference_calls(self):
        histories = self.f.histories(); out = self.f.root / 'collection'
        v.collect(self.f.packets, histories, out)
        path = out / 'neural.npz'; path.chmod(0o600)
        body = path.read_bytes(); put(path, body[:-1] + bytes([body[-1] ^ 1]))
        def forbidden(): self.fail('Protected callback called')
        with self.assertRaises(ValueError): v.evaluate(self.f.packets, histories, out, forbidden, forbidden)

    def test_target_order_mismatch_and_negative_paired_gain_are_not_silently_changed(self):
        histories = self.f.histories(cue=805., neural=815.); out = self.f.root / 'collection'
        v.collect(self.f.packets, histories, out)
        score = v.evaluate(self.f.packets, histories, out, self.f.references, self.f.truth)
        self.assertEqual(score['paired']['cue_minus_neural_mae_ms'], -10.)
        truth = self.f.truth(); truth['case_id'] = truth['case_id'][::-1]
        with self.assertRaises(ValueError): v.evaluate(self.f.packets, histories, out, self.f.references, lambda: truth)

    def test_exact_successor_arithmetic_bound_into_viewer_path(self):
        histories = self.f.histories(cue=0., neural=1e-14); out = self.f.root / 'collection'
        v.collect(self.f.packets, histories, out)
        score = v.evaluate(self.f.packets, histories, out, self.f.references, self.f.truth)
        self.assertEqual(score['paired']['cue_minus_neural_mae_ms'], 1e-14)
        self.assertIn('exact rational', score['paired']['paired_loss_arithmetic'])

    def test_serve_durable_answers_and_no_target_feedback(self):
        p = self.f.packets['cue_only']
        actions = []
        for i, name in enumerate(p.ids):
            actions.extend([{'op': 'show_query', 'index': i}, {'op': 'answer', 'case_id': name, 'prediction_ms': 700. + i}])
        actions.append({'op': 'finish'})
        path = self.f.root / 'serve.jsonl'; sink = io.BytesIO()
        real_fsync = v.os.fsync
        acknowledgements = []
        class CheckingSink:
            def write(inner, body):
                row = v.decode(body)
                if 'accepted' in row:
                    journal = path.read_bytes()
                    self.assertIn(row['accepted'].encode(), journal.splitlines()[-1])
                    acknowledgements.append(row['accepted'])
                sink.write(body)
            def flush(inner): pass
        with patch.object(v.os, 'fsync', wraps=real_fsync) as sync:
            v.serve(p, path, io.BytesIO(b''.join(map(v.encoded, actions))), CheckingSink())
            self.assertEqual(sync.call_count, 518)
        global WRITTEN
        WRITTEN += path.stat().st_size
        self.assertEqual(acknowledgements, p.ids)
        result = v.replay(p, path.read_bytes())
        np.testing.assert_array_equal(result, 700. + np.arange(258))
        for line in sink.getvalue().splitlines()[1:]:
            row = v.decode(line)
            if 'observation' in row:
                self.assertNotIn('tp_ms', row['observation']['metadata'])
                self.assertNotIn('counts', row['observation'])

    def test_failed_answer_journal_prevents_acknowledgement_and_later_view(self):
        p = self.f.packets['cue_only']; path = self.f.root / 'failed-serve.jsonl'
        actions = [{'op': 'show_query', 'index': 0}, {'op': 'answer', 'case_id': p.ids[0], 'prediction_ms': 1.},
                   {'op': 'show_query', 'index': 1}]
        sink = io.BytesIO(); count = 0
        def fail_third(fd):
            nonlocal count
            count += 1
            if count == 3: raise OSError('generated fsync failure')
        with patch.object(v.os, 'fsync', side_effect=fail_third):
            with self.assertRaises(OSError): v.serve(p, path, io.BytesIO(b''.join(map(v.encoded, actions))), sink)
        global WRITTEN
        WRITTEN += path.stat().st_size
        self.assertEqual(len(sink.getvalue().splitlines()), 2)
        self.assertNotIn(b'accepted', sink.getvalue())

    def test_query_actions_and_errors_do_not_depend_on_protected_answer(self):
        p = self.f.packets['neural']; before = p.show('query', 17)
        unrelated_private = self.f.truth(); unrelated_private['tp_ms'][17] = 9876543.
        after = p.show('query', 17)
        self.assertEqual(before, after)
        # No target operand is present in Packet or Session; only train rows contain tp_ms.
        self.assertNotIn('tp_ms', p.arrays['query'])
        self.assertEqual(set(p.arrays['query']), v.COMMON | {'counts'})
        messages = []
        for _ in range(2):
            try: v.Session(p).step({'op': 'show_query', 'index': 999})
            except ValueError as exc: messages.append(str(exc))
        self.assertEqual(messages[0], messages[1])

    def test_actual_png_observation_survives_complete_history_replay(self):
        real = v.Sources().modules['render'].render
        rendered = []
        def hybrid(meta, counts, units, raster):
            if meta['split'] == 'query' and meta['index'] == 257:
                image, pixels = real(meta, counts, units, raster)
                self.assertEqual(unpack_png(image), pixels)
                rendered.append(v.pin(image))
                return image, pixels
            return fast_image(meta, counts, units, raster)
        self.f.sources.modules['render'] = types.SimpleNamespace(render=hybrid)
        for view in v.VIEWS:
            body = self.f.history(view, lambda i: i - 5.5)
            answer = v.replay(self.f.packets[view], body)
            np.testing.assert_array_equal(answer, np.arange(258) - 5.5)
            receipt = v.decode(body.splitlines()[-1])
            self.assertEqual(receipt['observation_count'], 258)
            self.assertGreater(receipt['rendered_rgb_bytes'], 3444000)
        self.assertEqual(len(rendered), 4)
        self.assertEqual(rendered[0], rendered[1])
        self.assertEqual(rendered[2], rendered[3])

    def test_bad_condition_context_and_nominal_boundary_refused(self):
        for field, index, value in (('context', 24, 0), ('nominal_ts_ms', 24, 900.),
                                    ('condition', 0, 40)):
            values = {key: array.copy() for key, array in self.f.arrays['query'].items()}
            values[field][index] = value
            body = archive(values)
            put(self.f.files['neural']['query.npz'], body)
            self.f.sources.expected['views']['neural/query.npz'] = v.pin(body)
            with self.assertRaises(ValueError): v.Packet('neural', self.f.files['neural'], self.f.sources)

    def test_actual_pinned_evaluator_loader_join_after_pair(self):
        histories = self.f.histories(cue=830., neural=820.)
        out = self.f.root / 'collection'; v.collect(self.f.packets, histories, out)
        sources = self.f.sources; sources.artifacts = copy.deepcopy(sources.artifacts)
        truth_body = archive(self.f.truth())
        identity_body = v.encoded({'schema_version': 1, 'case_id': self.f.packets['cue_only'].ids})
        grade = {**self.f.references(), 'status': 'continuous_fixed_reference_panel_scored', 'candidate_id': 'NEURAL-095',
                 'public_validation_before_private_decode': True, 'private_loader_invocations': 1,
                 'predictions': sources.artifacts['reference_prediction_identity']}
        grade_body = v.encoded(grade)
        commit = {'status': 'producer_removed_outputs_committed', 'all_owned_producers_absent': True,
                  'predictions': sources.artifacts['reference_prediction_identity'],
                  'public_identity': v.pin(identity_body), 'private_targets': v.pin(truth_body)}
        audit = {'status': 'passed', 'independent_scalar_checks': 280, 'score_sha256': v.pin(grade_body)['sha256']}
        bodies = {'public_identity.json': identity_body, 'query_targets.npz': truth_body,
                  'reference_grade.json': grade_body, 'reference_commit.json': v.encoded(commit), 'reference_audit.json': v.encoded(audit)}
        files = {name: put(self.f.root / 'evaluator' / name, body) for name, body in bodies.items()}
        sources.artifacts['files'] = {name: v.pin(body) for name, body in bodies.items()}
        reads = []; original = v.pinned
        def tracked(path, descriptor):
            reads.append(Path(path).name)
            return original(path, descriptor)
        with patch.object(v, 'pinned', side_effect=tracked):
            references, private = v.loaders(sources, files, self.f.packets['cue_only'].ids)
            self.assertEqual(reads, [])
            score = v.evaluate(self.f.packets, histories, out, references, private)
        self.assertEqual(reads, ['public_identity.json', 'reference_grade.json', 'reference_commit.json', 'reference_audit.json', 'query_targets.npz'])
        self.assertEqual(score['paired']['cue_minus_neural_mae_ms'], 10.)


if __name__ == '__main__':
    print(json.dumps({'python': platform.python_version(), 'numpy': np.__version__, 'zlib_build': zlib.ZLIB_VERSION,
                      'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION, 'generated_only': True}))
    try:
        unittest.main(verbosity=2)
    finally:
        print(json.dumps({'cumulative_generated_fixture_bytes_written': WRITTEN, 'retained_generated_fixture_bytes': 0,
                          'accounting_excludes_in_memory_arrays_and_pixels': True}))
