"""Generated portable boundaries, not original EEG or a participant execution.

Full6400 arm/private fixtures live in memory. The virtual file reader checks every
declared size/hash; real ordinary-file reads, bundle capture, query projection,
CLI source binding and output writes have separate small filesystem controls.
Synthetic closure records exercise format validation, not process isolation.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('portable_erp_evaluator_controls', HERE / 'evaluator.py')
pair = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pair
spec.loader.exec_module(pair)
modules, SOURCE_PIN = pair.dependencies()
consumer, bundle = modules['consumer'], modules['bundle']
IDS = tuple('q-' + format(i, '032x') for i in range(6400))
DEMO_TEXT = json.dumps([{'trial_id': 'generated-demo-' + str(i), 'target': i % 2,
                         'channels': [[-0.0] * 1024, [0.125] * 1024]} for i in range(4)])
PROMPT = consumer.NO_TOOLS + '\n{{demonstrations_json}}\n{{query_json}}\n'


# Reuse full generated waveform text without caching 6400 large contexts.
QUERY_TEMPLATE = consumer.encoded({'trial_id': IDS[0], 'channels': [[-0.0] * 1024, [0.25] * 1024]}).decode()
CONTEXT_TEMPLATES = {condition: consumer.compose_context(PROMPT, DEMO_TEXT, QUERY_TEMPLATE, condition)
                     for condition in pair.CONDITIONS}


def context(identifier, condition):
    text = CONTEXT_TEMPLATES[condition].replace(IDS[0], identifier)
    return {'trial_id': identifier, 'condition': condition, 'prompt': text,
            'context_sha256': hashlib.sha256(text.encode()).hexdigest()}


class MemorySession:
    trial_ids = IDS
    manifest_pin = {'bytes': 1, 'sha256': '0' * 64}

    def __init__(self, *_):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def context(self, identifier, condition):
        return context(identifier, condition)


def frozen_bundle():
    declaration = {'schema': bundle.SCHEMA, 'entry_module': 'candidate',
                   'modules': ['candidate.py'], 'config': 'config.json'}
    # Compiling this is allowed. Executing it is an unmistakable control error.
    source = b'raise AssertionError("candidate code must never execute in grading")\n'
    config = b'{}\n'
    members = {name: {**pair.pin(body), 'base64': base64.b64encode(body).decode()}
               for name, body in [('candidate.py', source), ('config.json', config)]}
    client = bundle.launcher(declaration, members)
    core = {'schema': bundle.FROZEN_SCHEMA, 'manifest': declaration, 'members': members,
            'config': {}, 'launcher': pair.pin(client), 'runtime_scope': bundle.RUNTIME_SCOPE}
    return {**core, 'bundle_identity': pair.pin(bundle.encoded(core))}, client


def selected_contract():
    frozen, _ = frozen_bundle()
    descriptor = {'bytes': 1, 'sha256': '0' * 64}
    return {'schema': 'erp-full6400-selected-pair-v1', 'selected': True,
            'condition_id': consumer.CONDITION_ID, 'public_root': str(HERE / 'generated-public'),
            'public_manifest': descriptor, 'source_bindings': SOURCE_PIN,
            'operator_source': pair.pin((HERE / 'evaluator.py').read_bytes()),
            'bundles': {c: {'path': str(HERE / ('generated-' + c)),
                            'file': pair.pin(bundle.encoded(frozen)), 'bundle_identity': frozen['bundle_identity']}
                        for c in pair.CONDITIONS},
            'interpreter': {'path': str(Path(sys.executable).absolute()), 'file': descriptor},
            'limits': {'episode_work_seconds': 30, 'episode_cleanup_seconds': 5, 'campaign_seconds': 1000},
            'information_policy': dict(pair.POLICY),
            'authoring_exposure_declaration': 'Generated controls only; no original data or participant execution.',
            'direct_provider_qualification': 'unqualified_local_driver'}


class ArmStore:
    """Full6400 generated data with lazy per-episode serialization, no disk corpus."""
    def __init__(self):
        self.contract = selected_contract()
        self.contract_pin = pair.pin(pair.encode(self.contract))
        self.frozen, self.client = frozen_bundle()
        self.roots = {c: HERE / ('generated-arm-' + c) for c in pair.CONDITIONS}
        self.private = HERE / 'generated-private'
        self.static = {}
        self.private_reads = []
        self.overrides = {}
        self.descriptors = {}
        self.original_read = pair.read
        self._context_tail = {}
        # Each arm has a known, analytically different prediction rule.
        for condition in pair.CONDITIONS:
            root = self.roots[condition]
            predictions = b''.join(pair.encode({'trial_id': identifier, 'target_probability': self.probability(i, condition)})
                                   for i, identifier in enumerate(IDS))
            collection = {'status': 'complete_unscored_submission', 'condition': condition, 'responses': 6400,
                          'predictions': pair.pin(predictions), 'manifest_pin': self.contract['public_manifest']}
            collection_body = pair.encode(collection)
            episodes = [{'trial_id': identifier, 'status': 'ok', 'end': pair.pin(self.end(i, condition))}
                        for i, identifier in enumerate(IDS)]
            arm = {'schema': 'erp-full6400-numeric-arm-v1', 'status': 'closed_unscored_arm', 'condition': condition,
                   'contract': self.contract_pin, 'source_bindings': SOURCE_PIN,
                   'public_manifest': self.contract['public_manifest'],
                   'bundle_identity': self.frozen['bundle_identity'], 'query_count': 6400,
                   'attempt_inventory_count': 6400, 'private_target_reads': 0, 'scoring_performed': False,
                   'predictions': pair.pin(predictions), 'collection': pair.pin(collection_body), 'episodes': episodes}
            arm_body = pair.encode(arm)
            self.descriptors[condition] = {'root': str(root), 'receipt': pair.pin(arm_body)}
            for name, body in [('ARM.json', arm_body), ('FROZEN.json', bundle.encoded(self.frozen)),
                               ('CLIENT.py', self.client), ('collection/predictions.jsonl', predictions),
                               ('collection/COMPLETE.json', collection_body)]:
                self.static[root / name] = body
        joins = []
        files = {'public/PACKET.json': self.contract['public_manifest']}
        for person_index, person in enumerate(pair.PEOPLE):
            opaque = 'p-' + format(person_index, '024x')
            path = 'private/people/' + opaque + '.json'
            body = pair.encode({'participant_id': person, 'opaque_person_id': opaque,
                               'trials': [{'trial_id': IDS[person_index * 200 + j], 'target': int(j < 40)}
                                          for j in range(200)]})
            row = {'participant_id': person, 'opaque_person_id': opaque, 'trials': 200,
                   'record': pair.pin(body), 'path': path}
            joins.append(row); files[path] = pair.pin(body); self.static[self.private / path] = body
        join_body = pair.encode(joins)
        files['private/PARTICIPANT_JOIN.json'] = pair.pin(join_body)
        self.static[self.private / 'private/PARTICIPANT_JOIN.json'] = join_body
        complete = {'schema': 'erp-core-full32-packet-census-v1', 'status': 'full32_packet_materialized_no_models',
                    'full_cohort_complete': True, 'query_count': 6400, 'files': files, 'uncommitted_files': [],
                    'participants': [{'participant_id': p, 'status': 'packet_person_complete'} for p in pair.PEOPLE]}
        self.static[self.private / 'COMPLETE.json'] = pair.encode(complete)
        self.private_descriptor = {'root': str(self.private), 'complete': pair.pin(self.static[self.private / 'COMPLETE.json'])}

    def probability(self, index, condition):
        return (0.9 if index % 200 < 40 else 0.1) if condition == pair.CONDITIONS[0] else 0.5

    def response(self, index, condition):
        body = pair.encode({'trial_id': IDS[index], 'target_probability': self.probability(index, condition)})
        return pair.PREFIX.pack(len(body)) + body

    def incoming(self, index, condition):
        return pair.context_frame(context(IDS[index], condition), condition)

    def end(self, index, condition):
        incoming = self.incoming(index, condition)
        return pair.encode({'schema': 'erp-full6400-owned-episode-v1', 'status': 'ok',
                            'trial_id': IDS[index], 'condition': condition, 'returncode': 0, 'pid': 12345,
                            'owned_cleanup': {'pid': 12345, 'cleanup_complete': True, 'reaped': True,
                                              'group_absence_observed': True},
                            'stdout_EOF_observed': True, 'normal_exit_observed': True,
                            'generated_protocol_only': False, 'input': pair.pin(incoming),
                            'context_sha256': pair.pin(incoming[4:])['sha256'], 'output': pair.pin(self.response(index, condition))})

    def read(self, path, cap, expected=None, budget=None, empty=False):
        path = Path(path).absolute()
        if path == self.private or self.private in path.parents:
            self.private_reads.append(str(path))
        if path in self.static:
            body = self.static[path]
        else:
            body = None
            for condition, root in self.roots.items():
                if root in path.parents:
                    relative = path.relative_to(root).parts
                    if len(relative) == 2 and relative[0].isdigit():
                        index = int(relative[0])
                        body = {'END.json': self.end, 'INPUT.bin': self.incoming, 'OUTPUT.bin': self.response}[relative[1]](index, condition)
                    break
            if body is None:
                return self.original_read(path, cap, expected, budget, empty)
        body = self.overrides.get(path, body)
        pair.need((0 if empty else 1) <= len(body) <= cap, 'Generated virtual file size cap')
        pair.need(expected is None or pair.pin(body) == expected, 'Generated virtual file commitment mismatch')
        if budget is not None:
            pair.need(budget['read'] + len(body) <= pair.EVALUATOR_READ_CAP, 'Evaluator read cap')
            budget['read'] += len(body)
        return body

    def replace_end(self, condition, index, change):
        root = self.roots[condition]
        end = pair.decode(self.end(index, condition)); change(end)
        body = pair.encode(end); self.overrides[root / f'{index:04d}/END.json'] = body
        arm = pair.decode(self.static[root / 'ARM.json'])
        arm['episodes'][index]['end'] = pair.pin(body)
        self.static[root / 'ARM.json'] = pair.encode(arm)
        self.descriptors[condition]['receipt'] = pair.pin(self.static[root / 'ARM.json'])


class ConsumerControls(unittest.TestCase):
    def test_complete_four_demo_contexts_differ_only_in_permission(self):
        a, b = (context(IDS[0], c) for c in pair.CONDITIONS)
        self.assertEqual(set(a), {'trial_id', 'condition', 'prompt', 'context_sha256'})
        self.assertEqual(a['prompt'].replace(consumer.NO_TOOLS, consumer.PROGRAMME_TOOLS), b['prompt'])
        self.assertIn(DEMO_TEXT, a['prompt']); self.assertIn('[-0.0,-0.0', a['prompt'])
        for forbidden in ('participant_id', 'opaque_person_id', 'roster.json', 'queries/p-', 'sub-008'):
            self.assertNotIn(forbidden, a['prompt'])

    def test_prompt_insertion_does_not_reinterpret_demo_tokens_or_truncate(self):
        demos = DEMO_TEXT + '{{query_json}}'
        text = consumer.compose_context(PROMPT, demos, 'QUERY', pair.CONDITIONS[0])
        self.assertIn(demos, text); self.assertEqual(text.count('QUERY'), 1)
        with self.assertRaises(consumer.Refusal):
            consumer.compose_context(PROMPT, 'x' * consumer.CONTEXT_LIMIT, 'QUERY', pair.CONDITIONS[0])

    def test_response_identity_exact_keys_and_probability_boundaries(self):
        for probability in (0, 0.5, 1):
            self.assertEqual(consumer.parse_response(json.dumps({'trial_id': IDS[0], 'target_probability': probability}), IDS[0]), probability)
        for probability in (True, None, '0.5', -0.1, 1.1, float('nan'), float('inf')):
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                consumer.parse_response(json.dumps({'trial_id': IDS[0], 'target_probability': probability}), IDS[0])
        for text in ('{"trial_id":"wrong","target_probability":0.5}',
                     '{"trial_id":"' + IDS[0] + '","target_probability":0.5,"target":1}',
                     '{"trial_id":"' + IDS[0] + '","target_probability":0.5,"target_probability":0.9}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                consumer.parse_response(text, IDS[0])

    def test_real_query_span_projection_preserves_all_binary64_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); (root / 'queries').mkdir()
            name = 'queries/p-' + 'a' * 24 + '.jsonl'
            body = consumer.encoded({'trial_id': IDS[0], 'channels': [[-0.0] * 1024, [0.12345678901234566] * 1024]})
            (root / name).write_bytes(body)
            session = consumer.PacketSession.__new__(consumer.PacketSession)
            session._budget = None
            session._root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            session._closed = False; session._prompt = PROMPT; session._demos = DEMO_TEXT
            session._files = {name: consumer.descriptor(body)}
            session._rows = {IDS[0]: {'path': name, 'offset': 0, **consumer.descriptor(body)}}
            try:
                result = session.context(IDS[0], pair.CONDITIONS[0])
                self.assertIn(body.decode(), result['prompt'])
                changed = body.replace(b'0.12345678901234566', b'0.12345678901234567', 1)
                (root / name).write_bytes(changed)
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    session.context(IDS[0], pair.CONDITIONS[0])
            finally:
                session.close()

    def test_packet_constructor_rejects_changed_legacy_pin_before_waveforms(self):
        files = {**copy.deepcopy(consumer.LEGACY_PINS), 'roster.json': {'bytes': 1, 'sha256': '0' * 64}}
        files.update({'queries/p-' + format(i, '024x') + '.jsonl': {'bytes': 1, 'sha256': '0' * 64} for i in range(32)})
        files['demonstrations.json']['sha256'] = 'f' * 64
        manifest = {'schema': 'erp-core-full32-public-packet-v1', 'benchmark_id': 'NEURAL-077',
                    'condition_id': consumer.CONDITION_ID, 'people': 32, 'query_count': 6400,
                    'demonstration_count': 4, 'natural_class_prior_supplied': False, 'files': files}
        body = consumer.encoded(manifest)
        with tempfile.TemporaryDirectory() as temporary, patch.object(consumer.PacketSession, '_read', return_value=body) as reader:
            with self.assertRaisesRegex(ValueError, 'Unchanged four demonstrations'):
                consumer.PacketSession(Path(temporary).resolve(), consumer.descriptor(body))
            self.assertEqual(reader.call_count, 1)

    def test_collector_rejects_failed_first_attempt_and_preserves_exact_ledger(self):
        envelope = {'trial_id': IDS[0], 'condition': pair.CONDITIONS[0], 'context_sha256': '0' * 64,
                    'status': 'error', 'response': None, 'error': 'generated refusal'}
        body = consumer.encoded(envelope)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); (root / 'responses').write_bytes(body)
            with self.assertRaisesRegex(ValueError, 'no partial admission'):
                consumer.collect(MemorySession(), pair.CONDITIONS[0], root / 'responses', root / 'out', time.monotonic() + 5)
            self.assertEqual((root / 'out/attempts.jsonl').read_bytes(), body)
            failure = json.loads((root / 'out/FAILED.json').read_bytes())
            self.assertTrue(failure['first_responses_preserved']); self.assertEqual(failure['private_target_reads'], 0)
            self.assertFalse((root / 'out/predictions.jsonl').exists())


class EvaluatorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = ArmStore()

    def setUp(self):
        self.store.private_reads.clear(); self.store.overrides.clear()

    def test_full6400_prediction_coverage_and_strict_duplicate_missing_foreign(self):
        rows = [pair.encode({'trial_id': i, 'target_probability': 0.5}) for i in IDS]
        body = b''.join(rows)
        self.assertEqual(len(pair.parse_prediction_rows(body, IDS)), 6400)
        for bad in (b''.join(rows[:-1]), body + rows[0], pair.encode({'trial_id': 'q-' + 'f' * 32, 'target_probability': .5}) + b''.join(rows[1:])):
            with self.assertRaises(ValueError):
                pair.parse_prediction_rows(bad, IDS)

    def test_selection_policy_and_both_preprompt_bundles_are_required(self):
        pair.validate_contract(self.store.contract)
        for key in pair.POLICY:
            contract = copy.deepcopy(self.store.contract); contract['information_policy'][key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                pair.validate_contract(contract)
        contract = copy.deepcopy(self.store.contract); contract['selected'] = False
        with self.assertRaises(ValueError): pair.validate_contract(contract)
        contract = copy.deepcopy(self.store.contract); del contract['bundles'][pair.CONDITIONS[1]]
        with self.assertRaises(ValueError): pair.validate_contract(contract)

    def test_real_source_authentication_and_no_private_module_loader(self):
        current, identity = pair.dependencies()
        self.assertEqual(set(current), {'consumer', 'bundle'}); self.assertEqual(identity, SOURCE_PIN)
        pair.verify_operator(self.store.contract)
        wrong = copy.deepcopy(self.store.contract); wrong['operator_source']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'commitment mismatch'):
            pair.verify_operator(wrong)
        self.assertFalse(hasattr(pair, 'run_arm')); self.assertFalse(hasattr(pair, 'episode'))

    def test_bundle_capture_and_freeze_never_execute_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); source = root / 'source'; source.mkdir()
            (source / 'candidate.py').write_bytes(b'raise AssertionError("must not execute")\n')
            (source / 'config.json').write_bytes(b'{}\n')
            declaration = {'schema': bundle.SCHEMA, 'entry_module': 'candidate', 'modules': ['candidate.py'], 'config': 'config.json'}
            manifest = root / 'manifest.json'; manifest.write_bytes(pair.encode(declaration))
            result = pair.freeze(source, manifest, root / 'FROZEN.json')
            frozen = bundle.decode((root / 'FROZEN.json').read_bytes())
            self.assertEqual(result['bundle_identity'], frozen['bundle_identity'])
            self.assertEqual(pair.pin(bundle.verify(frozen)), frozen['launcher'])

    def test_metric_threshold_clipping_and_equal_person_weight(self):
        people = {'short': [('p', 1), ('n', 0)], 'long': [('x' + str(i), int(i < 40)) for i in range(200)]}
        predictions = {'p': .5, 'n': .5, **{'x' + str(i): (0.9 if i < 40 else 0.1) for i in range(200)}}
        score = pair.metric_rows(predictions, people)
        self.assertEqual(score['participant_macro_balanced_accuracy'], .75)
        self.assertAlmostEqual(score['participant_macro_natural_log_loss'], (math.log(2) - math.log(.9)) / 2)
        clipped = pair.metric_rows({'p': 0, 'n': 1}, {'x': [('p', 1), ('n', 0)]})
        self.assertEqual(clipped['participant_macro_balanced_accuracy'], 0)
        self.assertTrue(math.isfinite(clipped['participant_macro_natural_log_loss']))
        with self.assertRaises(ValueError): pair.metric_rows({'p': .5}, {'x': [('p', 1)]})

    def test_all6400_both_arms_and_full32_private_join_produce_exact_paired_scores(self):
        store = self.store
        with tempfile.TemporaryDirectory() as temporary, patch.object(pair, 'read', side_effect=store.read):
            result = pair.protected_evaluate(store.contract, *(store.descriptors[c] for c in pair.CONDITIONS),
                                             store.private_descriptor, Path(temporary).resolve() / 'score',
                                             contract_pin=store.contract_pin, deadline=time.monotonic() + 75,
                                             session_factory=MemorySession, modules=modules)
        self.assertEqual(result['people'], 32); self.assertEqual(result['queries'], 6400)
        self.assertEqual(result['primary_direct_minus_program_macro_BA'], .5)
        self.assertEqual(len(result['paired_person_differences']), 32)
        self.assertTrue(all(r['direct_minus_program_balanced_accuracy'] == .5 for r in result['paired_person_differences']))
        self.assertEqual([r['participant_id'] for r in result['scores'][pair.CONDITIONS[0]]['participants']], pair.PEOPLE)
        self.assertTrue(store.private_reads); self.assertFalse(result['provider_context_qualified'])
        self.assertIn('Not computed', result['bootstrap_interval'])

    def test_second_arm_corruption_never_opens_private_material(self):
        store = self.store; root = store.roots[pair.CONDITIONS[1]]
        store.overrides[root / 'CLIENT.py'] = store.client + b'\n'
        with patch.object(pair, 'read', side_effect=store.read), patch.object(pair, 'load_private_people', side_effect=AssertionError('private touched')) as private:
            with self.assertRaisesRegex(ValueError, 'commitment mismatch'):
                pair.protected_evaluate(store.contract, *(store.descriptors[c] for c in pair.CONDITIONS),
                                        object(), object(), contract_pin=store.contract_pin, deadline=time.monotonic() + 75,
                                        session_factory=MemorySession, modules=modules)
            private.assert_not_called()
        self.assertEqual(store.private_reads, [])

    def test_authenticated_but_unclosed_or_generated_episode_is_rejected(self):
        store = self.store; condition = pair.CONDITIONS[0]; root = store.roots[condition]
        old = store.static[root / 'ARM.json']; desc = copy.deepcopy(store.descriptors[condition])
        try:
            for field in ('generated_protocol_only', 'stdout_EOF_observed', 'normal_exit_observed'):
                store.replace_end(condition, 0, lambda end: end.__setitem__(field, field == 'generated_protocol_only'))
                with patch.object(pair, 'read', side_effect=store.read), self.assertRaisesRegex(ValueError, 'Unclosed or generated'):
                    pair._admit_public_arm(store.descriptors[condition], condition, store.contract, store.contract_pin,
                                           MemorySession(), modules, {'read': 0}, time.monotonic() + 10)
                self.assertEqual(store.private_reads, [])
        finally:
            store.static[root / 'ARM.json'] = old; store.descriptors[condition] = desc

    def test_first_frame_and_exact_context_are_authenticated(self):
        store = self.store; condition = pair.CONDITIONS[0]; root = store.roots[condition]
        for name in ('INPUT.bin', 'OUTPUT.bin'):
            store.overrides.clear(); body = store.incoming(0, condition) if name == 'INPUT.bin' else store.response(0, condition)
            store.overrides[root / '0000' / name] = body[:-1] + (b'X' if body[-1:] != b'X' else b'Y')
            with patch.object(pair, 'read', side_effect=store.read), self.assertRaisesRegex(ValueError, 'commitment mismatch'):
                pair._admit_public_arm(store.descriptors[condition], condition, store.contract, store.contract_pin,
                                       MemorySession(), modules, {'read': 0}, time.monotonic() + 10)

    def test_private_full32_support_and_public_join_refuse_omission(self):
        store = self.store; path = store.private / 'private/PARTICIPANT_JOIN.json'
        original = store.static[path]; complete_path = store.private / 'COMPLETE.json'; complete = store.static[complete_path]
        bad = pair.encode(pair.decode(original)[:-1]); amended = pair.decode(complete)
        amended['files']['private/PARTICIPANT_JOIN.json'] = pair.pin(bad)
        store.static[path] = bad; store.static[complete_path] = pair.encode(amended)
        try:
            desc = {'root': str(store.private), 'complete': pair.pin(store.static[complete_path])}
            with patch.object(pair, 'read', side_effect=store.read), self.assertRaisesRegex(ValueError, 'Exact full32 private roster'):
                pair.load_private_people(desc, store.contract['public_manifest'], set(IDS), {'read': 0})
        finally:
            store.static[path] = original; store.static[complete_path] = complete

    def test_cli_private_descriptor_path_is_lazy_even_when_missing(self):
        store = self.store
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); contract = root / 'contract.json'; arms = root / 'arms.json'
            contract.write_bytes(pair.encode(store.contract)); arms.write_bytes(pair.encode(store.descriptors))
            touched = []
            def fail_second(desc, condition, *_):
                touched.append(condition)
                if len(touched) == 2: raise ValueError('second arm fails before private descriptor')
                return {}
            with patch.object(pair, '_admit_public_arm', side_effect=fail_second), patch.object(consumer, 'PacketSession', MemorySession), \
                 patch.object(pair, 'dependencies', return_value=(modules, SOURCE_PIN)):
                with self.assertRaisesRegex(ValueError, 'second arm fails'):
                    pair.main(['evaluate', '--contract', str(contract), '--contract-bytes', str(store.contract_pin['bytes']),
                               '--contract-sha256', store.contract_pin['sha256'], '--public-arms', str(arms),
                               '--private-material', str(root / 'ABSENT_PRIVATE_DESCRIPTOR'), '--output', str(root / 'out'), '--work-seconds', '10'])
            self.assertEqual(touched, list(pair.CONDITIONS)); self.assertFalse((root / 'out').exists())

    def test_ordinary_file_pin_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); path = root / 'tiny'; path.write_bytes(b'captured\n')
            expected = pair.pin(b'captured\n')
            self.assertEqual(pair.read(path, 100, expected), b'captured\n')
            path.write_bytes(b'altered!\n')
            with self.assertRaisesRegex(ValueError, 'commitment mismatch'): pair.read(path, 100, expected)
            link = root / 'link'; link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'Symlink'): pair.read(link, 100)


if __name__ == '__main__':
    unittest.main(verbosity=2)
