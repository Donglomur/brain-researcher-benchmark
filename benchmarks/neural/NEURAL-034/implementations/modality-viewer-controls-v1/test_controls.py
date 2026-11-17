"""Generated modality checks; no source arrays, participants or scientific score."""
import base64
import copy
from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
import zlib

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('neural034_generated_modality_controls', HERE / 'controls.py')
C = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = C
SPEC.loader.exec_module(C)
PNG = b'\x89PNG\r\n\x1a\nGENERATED_PROTOCOL_FIXTURE'


class Repeated:
    def __init__(self, value, size):
        self.value, self.size = value, size

    def __getitem__(self, index):
        assert type(index) is int and 0 <= index < self.size
        return self.value


class GuardedArrays(dict):
    def __init__(self, values, forbidden=()):
        super().__init__(values)
        self.forbidden, self.accesses = set(forbidden), []

    def __getitem__(self, key):
        self.accesses.append(key)
        if key in self.forbidden:
            raise AssertionError('EXCLUDED_MODALITY_WAS_READ')
        return super().__getitem__(key)


class Packet:
    def __init__(self, fold=0, calcium=0.0, behavior=0, forbidden=()):
        self.fold, self.ids = fold, list(C.IDS[fold])
        self.pin = {'bytes': 0, 'sha256': hashlib.sha256(b'generated in-memory fixture').hexdigest()}
        window = [[calcium for _ in range(12)] for _ in range(300)]
        state = [behavior for _ in range(300)]
        self.arrays = GuardedArrays({
            'train_windows': Repeated(window, 120), 'query_windows': Repeated(window, 20),
            'train_behavior': Repeated(state, 120), 'query_behavior': Repeated(state, 20),
            'train_labels': [0, 1] * 60,
        }, forbidden)

    def observation(self, *args):
        raise AssertionError('UNPROJECTED_PACKET_OBSERVATION_WAS_CALLED')


def fast_render(record, gain, raster, base, condition):
    expected = {'role', 'index'} | ({'label'} if record['role'] == 'training' else set())
    expected |= {'windows'} if 'calcium' in C.select(condition) else set()
    expected |= {'behavior'} if 'behavior' in C.select(condition) else set()
    if set(record) != expected:
        raise AssertionError('Renderer received an excluded or missing field')
    return PNG, []


def pixels(body):
    assert body[:8] == b'\x89PNG\r\n\x1a\n'
    chunks, offset = [], 8
    while offset < len(body):
        size = struct.unpack('>I', body[offset:offset + 4])[0]
        kind = body[offset + 4:offset + 8]
        data = body[offset + 8:offset + 8 + size]
        assert struct.unpack('>I', body[offset + 8 + size:offset + 12 + size])[0] == zlib.crc32(kind + data)
        chunks.append((kind, data))
        offset += 12 + size
    assert offset == len(body) and [k for k, _ in chunks] == [b'IHDR', b'IDAT', b'IEND']
    assert struct.unpack('>IIBBBBB', chunks[0][1]) == (1400, 820, 8, 2, 0, 0, 0)
    raw = zlib.decompress(chunks[1][1])
    stride = 1400 * 3 + 1
    assert len(raw) == stride * 820 and all(raw[i * stride] == 0 for i in range(820))
    return b''.join(raw[i * stride + 1:(i + 1) * stride] for i in range(820))


class ModalityControls(unittest.TestCase):
    @staticmethod
    def limits():
        return C.T.Limits(161, 140, 64 * 1024**2, 900)

    def session(self, condition, packet=None, episode='0' * 32):
        return C.Session(packet or Packet(), C.Selection(condition, self.limits()), episode)

    @classmethod
    def setUpClass(cls):
        cls.original_pins = C.source_identity()
        cls.packets = {fold: Packet(fold) for fold in range(7)}
        cls.records = {}
        with patch.object(C.RENDERER, 'render', side_effect=fast_render):
            for condition_index, condition in enumerate(C.CONDITIONS):
                records = []
                for fold, packet in cls.packets.items():
                    session = C.Session(packet, C.Selection(condition, cls.limits()), f'{condition_index * 7 + fold + 1:032x}')
                    for index in range(120):
                        view = session.handle({'action': 'training', 'index': index})
                        assert view['context_label'] == index % 2
                    for index, query_id in enumerate(packet.ids):
                        session.handle({'action': 'query', 'index': index})
                        session.handle({'action': 'respond', 'query_id': query_id, 'probability': 0.5})
                    session.handle({'action': 'finish'})
                    records.append(session.finish_record())
                cls.records[condition] = records

    @classmethod
    def tearDownClass(cls):
        assert C.source_identity() == cls.original_pins
        print(json.dumps({'conditions': 3, 'complete_generated_fold_histories': 21,
                          'generated_fixture_disk_bytes': 0, 'authentic_input_reads': 0,
                          'participant_processes': 0, 'model_calls': 0, 'scientific_grader_calls': 0,
                          'coverage_images': 'Generated protocol stubs for enumeration; separate real generated raster checks.'}))

    def test_full_seven_fold_original_outputs_for_each_condition(self):
        with patch.object(C.RENDERER, 'render', side_effect=fast_render):
            collected = C.collect_matched(self.records, self.packets, self.limits())
            for condition, records in self.records.items():
                submission, receipt = collected[condition]
                self.assertEqual(set(submission), {'schema_version', 'probabilities'})
                self.assertEqual(submission['schema_version'], 1)
                self.assertEqual(submission['probabilities'], [
                    {'fold': fold, 'query_id': query_id, 'probability': 0.5}
                    for fold in range(7) for query_id in C.IDS[fold]])
                self.assertEqual(receipt['condition'], condition)
                self.assertEqual(receipt['predictions'], 140)
                self.assertFalse(receipt['participant_transport_qualified'])
                self.assertFalse(receipt['scientific_qualification'])
                self.assertTrue(all(len(r['actions']) == 161 and r['images'] == 140 for r in records))

    def test_selector_prevents_excluded_array_access_in_both_roles(self):
        for condition, excluded in (
            ('calcium_only_v1', ('train_behavior', 'query_behavior')),
            ('behavior_only_v1', ('train_windows', 'query_windows')),
        ):
            packet = Packet(forbidden=excluded)
            session = self.session(condition, packet)
            with patch.object(C.RENDERER, 'render', side_effect=fast_render):
                for role, index in (('training', 119), ('query', 19)):
                    response = session.handle({'action': role, 'index': index})
                    header, image = C.projection(response, condition)
                    self.assertEqual(image, PNG)
                    self.assertNotIn('fold', header)
            self.assertTrue(set(excluded).isdisjoint(packet.arrays.accesses))

    def test_excluded_modality_cannot_change_png_or_public_metadata(self):
        for condition, first, changed in (
            ('calcium_only_v1', Packet(behavior=0), Packet(behavior=1)),
            ('behavior_only_v1', Packet(calcium=-1e6), Packet(calcium=1e6)),
        ):
            for role, index in (('training', 119), ('query', 19)):
                a = self.session(condition, first).handle({'action': role, 'index': index})
                b = self.session(condition, changed).handle({'action': role, 'index': index})
                self.assertEqual(C.projection(a, condition), C.projection(b, condition))
                self.assertEqual(a['clipped_cells'], [])
                pixels(base64.b64decode(a['image']['base64']))

    def test_included_modality_changes_pixels_and_retains_original_lane_geometry(self):
        for condition, field in (('calcium_only_v1', 'calcium'), ('behavior_only_v1', 'behavior')):
            first, changed = Packet(), Packet(**{field: 1})
            a = self.session(condition, first).handle({'action': 'query', 'index': 0})
            b = self.session(condition, changed).handle({'action': 'query', 'index': 0})
            a_pixels = pixels(base64.b64decode(a['image']['base64']))
            b_pixels = pixels(base64.b64decode(b['image']['base64']))
            self.assertNotEqual(a_pixels, b_pixels)
            full = C.ProjectedPacket(changed, 'combined_calcium_behavior_v1').observation('query', 0)
            original, _ = C.BASE_RENDERER.render(full, 1.0, C.RASTER)
            original_pixels = pixels(original)
            lo, hi = ((137, 643) if field == 'calcium' else (680, 730))
            self.assertEqual(b_pixels[lo * 4200:hi * 4200], original_pixels[lo * 4200:hi * 4200])

    def test_combined_pixels_and_prior_public_projection_preserved(self):
        packet = Packet(calcium=3, behavior=1)
        projected = C.ProjectedPacket(packet, 'combined_calcium_behavior_v1')
        original = C.V.Session(projected, 161, C.RASTER, C.BASE_RENDERER)
        current = self.session('combined_calcium_behavior_v1', packet)
        for action in ({'action': 'training', 'index': 119}, {'action': 'query', 'index': 19}):
            want, got = original.handle(action), current.handle(action)
            got.pop('condition'); got.pop('visible_modalities')
            self.assertEqual(got, want)

    def test_renderer_rejects_injected_excluded_keys_and_invalid_included_data(self):
        for condition, excluded in (('calcium_only_v1', 'behavior'), ('behavior_only_v1', 'windows')):
            record = C.ProjectedPacket(Packet(), condition).observation('query', 0)
            for key in (excluded, 'label', 'source_path', 'query_targets'):
                with self.subTest(condition=condition, key=key), self.assertRaises(ValueError):
                    C.RENDERER.render({**record, key: 'PRIVATE_SENTINEL'}, 1.0, C.RASTER, C.BASE_RENDERER, condition)
        for condition, packet in (('calcium_only_v1', Packet(calcium=float('nan'))),
                                  ('behavior_only_v1', Packet(behavior=2))):
            with self.assertRaises(ValueError):
                self.session(condition, packet).handle({'action': 'query', 'index': 0})

    def test_role_whitelist_refuses_labels_raw_fields_and_hidden_clipping(self):
        with patch.object(C.RENDERER, 'render', side_effect=fast_render):
            for condition in C.CONDITIONS:
                response = self.session(condition).handle({'action': 'query', 'index': 0})
                for key, value in (('context_label', 1), ('windows', []), ('behavior', []),
                                   ('source_path', '/private'), ('fold', 0), ('cell_mean', 3)):
                    with self.subTest(condition=condition, key=key), self.assertRaises(ValueError):
                        C.projection({**response, key: value}, condition)
            behavior = self.session('behavior_only_v1').handle({'action': 'query', 'index': 0})
            with self.assertRaises(ValueError):
                C.projection({**behavior, 'clipped_cells': [1]}, 'behavior_only_v1')
            with self.assertRaises(ValueError):
                C.projection({**behavior, 'cells': 12}, 'behavior_only_v1')

    def test_frozen_condition_unknown_actions_and_failed_session(self):
        for condition in ('unknown', '', None, True):
            with self.assertRaises(ValueError):
                C.Selection(condition, self.limits())
        selection = C.Selection('calcium_only_v1', self.limits())
        with self.assertRaises(FrozenInstanceError):
            selection.condition = 'behavior_only_v1'
        session = self.session('calcium_only_v1')
        with self.assertRaises(AttributeError):
            session.condition = 'behavior_only_v1'
        with self.assertRaises(ValueError):
            session.handle({'action': 'condition', 'condition': 'behavior_only_v1'})
        with self.assertRaises(ValueError):
            session.handle({'action': 'query', 'index': 0})

    def test_fresh_state_and_first_final_response_boundary(self):
        with patch.object(C.RENDERER, 'render', side_effect=fast_render):
            first = self.session('calcium_only_v1')
            first.handle({'action': 'gain', 'units_per_division': 2})
            first.handle({'action': 'respond', 'query_id': C.IDS[0][0], 'probability': 0.3})
            for condition in C.CONDITIONS:
                fresh = self.session(condition)
                self.assertEqual((fresh._session.gain, fresh._session.seen, fresh._session.answers), (1.0, set(), {}))
                with self.assertRaises(ValueError):
                    fresh.handle({'action': 'respond', 'query_id': C.IDS[0][0], 'probability': 0.9})
            with self.assertRaises(ValueError):
                first.handle({'action': 'respond', 'query_id': C.IDS[0][0], 'probability': 0.9})
            with self.assertRaises(ValueError):
                first.finish_record()

    def test_collect_rejects_mixed_legacy_missing_or_duplicate_folds_before_render(self):
        good = self.records['calcium_only_v1']
        mixed = copy.deepcopy(good)
        mixed[3] = self.records['behavior_only_v1'][3]
        duplicate = copy.deepcopy(good)
        duplicate[6] = duplicate[0]
        reused = copy.deepcopy(good)
        reused[6]['manifest']['episode_id'] = reused[0]['manifest']['episode_id']
        with patch.object(C.RENDERER, 'render', side_effect=AssertionError('MUST_REFUSE_BEFORE_RENDER')):
            for records in (mixed, good[:-1], duplicate, reused, [{'schema': 'neural034-fold-viewer-session/v1'}] * 7):
                with self.assertRaises(ValueError):
                    C.collect('calcium_only_v1', records, self.packets, self.limits())

    def test_collect_rejects_relabeling_changed_source_budget_answer_and_history(self):
        for mutation in ('relabel', 'source', 'budget', 'answer', 'request', 'missing_answer'):
            records = copy.deepcopy(self.records['calcium_only_v1'])
            if mutation == 'relabel':
                records = copy.deepcopy(self.records['combined_calcium_behavior_v1'])
                for row in records:
                    row['manifest']['condition'] = 'calcium_only_v1'
            elif mutation == 'source':
                records[0]['manifest']['source']['controls.py']['sha256'] = '0' * 64
            elif mutation == 'budget':
                records[0]['manifest']['limits']['max_images'] = 141
            elif mutation == 'answer':
                records[0]['probabilities'][C.IDS[0][0]] = 0.9
            elif mutation == 'request':
                records[0]['actions'][0]['request']['index'] = 1
            else:
                records[0]['probabilities'].pop(C.IDS[0][19])
            with self.subTest(mutation=mutation), patch.object(C.RENDERER, 'render', side_effect=fast_render), self.assertRaises(ValueError):
                C.collect('calcium_only_v1', records, self.packets, self.limits())

    def test_matched_budget_time_support_and_public_condition_binding(self):
        for condition in C.CONDITIONS:
            selection = C.Selection(condition, self.limits())
            header = C.ready_header(selection, 'f' * 32)
            self.assertEqual(header['limits'], dict(C.asdict(self.limits()), max_request_bytes=4096, max_image_bytes=4 * 1024**2))
            self.assertEqual((header['training_windows'], header['query_windows']), (120, 20))
            self.assertEqual(header['condition'], condition)
            self.assertEqual(header['visible_modalities'], list(C.select(condition)))
            self.assertNotIn('fold', header)
            self.assertNotIn('input', header)
            self.assertNotIn('source', header)
        with self.assertRaises(ValueError):
            C.Selection('behavior_only_v1', C.T.Limits(160, 140, 64 * 1024**2, 900))
        with patch.object(C.RENDERER, 'render', side_effect=fast_render):
            session = self.session('behavior_only_v1')
            for _ in range(140):
                response = session.handle({'action': 'inspect'})
            self.assertEqual((response['samples'], response['sample_rate_hz'], response['window_seconds'],
                              response['first_sample_seconds'], response['last_sample_seconds']), (300, 10, 30, 0.05, 29.95))
            with self.assertRaises(ValueError):
                session.handle({'action': 'inspect'})

    def test_matched_collection_refuses_unequal_budgets_or_cross_condition_episode_reuse(self):
        with patch.object(C.RENDERER, 'render', side_effect=AssertionError('MUST_REFUSE_BEFORE_RENDER')):
            for mutation in ('budget', 'episode', 'missing_condition'):
                records = copy.deepcopy(self.records)
                if mutation == 'budget':
                    records['behavior_only_v1'][0]['manifest']['limits']['max_actions'] = 162
                elif mutation == 'episode':
                    records['behavior_only_v1'][0]['manifest']['episode_id'] = records['calcium_only_v1'][0]['manifest']['episode_id']
                else:
                    del records['behavior_only_v1']
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    C.collect_matched(records, self.packets, self.limits())


if __name__ == '__main__':
    unittest.main()
