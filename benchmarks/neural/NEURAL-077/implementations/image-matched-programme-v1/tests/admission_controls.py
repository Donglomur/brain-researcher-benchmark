"""Real full6400 structural gates over explicit generated retained-capture maps.

The only substituted seams are read/iterdir and the per-episode capture auditor.
Each supplied audit validates its opaque ID, context, static profile and closure
pins. Real arm inventory, complete-roster, first-response NPZ, pairing and lazy
private-access ordering remain unchanged. A separate control runs the actual
Session/transport/client/codec/custody auditor. No live outcomes are simulated.
"""
import copy
from contextlib import ExitStack
import io
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import generated_support as g
import test_visual_full32 as integrated


class Captures:
    def __init__(self, e):
        import numpy as np
        self.e = e
        self.m = g.ByteMap()
        self.a = integrated.FIXTURES / 'structural-direct'
        self.b = integrated.FIXTURES / 'structural-programme'
        self.a.mkdir(); self.b.mkdir()
        self.ids = e['packet'].ids
        self.data = dict(e['data'], rows=[{'trial_id': x} for x in self.ids])
        self.data.pop('_session', None)
        self.provider, self.image = e['deps']['provider'], e['image']
        self.fields = {'profile': g.PROFILE, 'profile_commitment': e['profile'].PROFILE_COMMITMENT}
        self.limits = self.provider.budgets(e['t'], 30, 86400, 8388608, 512*1024**2, 128*1024**2,
                                           1024**4, 1024**4, profile=g.PROFILE)
        self.client = b'# Generated frozen image-only candidate; never executed.\n'
        self.contract = {**self.fields, 'limits': self.limits['transport'], 'frozen_monotonic': 1.0,
                         'campaign_seconds': 86400, 'packet_path': str(e['packet'].root),
                         'protected_roots': [str(integrated.FIXTURES/'private-never-opened')],
                         'public_manifest': e['packet'].manifest_pin,
                         'bundle': {'launcher': g.pin(self.client)}, 'runtime': {'bytes': 1},
                         'sandbox_executable': {'bytes': 1}, 'source': e['deps']['identity']}
        self.cpin = g.pin(g.encode(self.contract))
        self.aman = {'schema': 'neural077_visual_provider_campaign_v1',
                     'route': self.provider.profile_spec(g.PROFILE)[2], 'condition': g.CONDITIONS[0],
                     'queries': 6400, 'demonstrations': 4, 'source': e['deps']['bindings'],
                     'operator': self.provider.v.identity(e['deps']['s']),
                     'packet': self.data['packet'], 'limits': self.limits,
                     'started_monotonic': 2.0, 'deadline': 86402.0, 'retry_policy': 'none',
                     'local_participant_sandbox': None, 'participant_code_executed_locally': False,
                     'remote_context_qualified': False, 'provider_capacity_qualified': False,
                     'scientific_qualification': False, **self.fields}
        self.bman = {'schema': 'neural077_image_programme_campaign_v1', 'condition': g.CONDITIONS[1],
                     'contract': self.cpin, 'source': e['deps']['identity'], 'packet': self.data['packet'],
                     'queries': 6400, 'demonstrations': 4, 'started_monotonic': 2.0, 'deadline': 86402.0,
                     'limits': self.contract['limits'], 'client': self.contract['bundle']['launcher'],
                     'runtime': self.contract['runtime'], 'sandbox_executable': self.contract['sandbox_executable'],
                     'sandbox': 'macos', 'retry_policy': 'none', 'private_target_reads': 0,
                     'scoring_performed': False, **self.fields}
        self.m.directories[self.a] = {'MANIFEST.json', 'sessions', 'providers', 'collection', 'ARM.json'}
        self.m.directories[self.b] = {'CLIENT.py', 'MANIFEST.json', 'sessions', 'collection', 'ARM.json'}
        names = {f'{i:04d}' for i in range(6400)}
        for root, folder in ((self.a, 'sessions'), (self.a, 'providers'), (self.b, 'sessions')):
            self.m.directories[root/folder] = names.copy()
        self.m.add(self.b/'CLIENT.py', self.client)
        apin = self.m.add(self.a/'MANIFEST.json', self.aman)
        bpin = self.m.add(self.b/'MANIFEST.json', self.bman)
        self.audits = []; self.audit_records = {}; ends = []; frames = []
        for i, trial in enumerate(self.ids):
            name = f'{i:04d}'
            prompt = e['v'].scientific_prompt(trial, 'four_demo')
            header = {'episode_id': format(i + 1, '032x'), 'trial_id': trial,
                      'prompt': prompt, **self.fields}
            # Tiny generated frame bytes exercise matching framing only. Actual
            # raster/codec pixels are independently tested by bounded controls.
            raw_a = e['t'].wire(header, b'\x89PNG\r\n\x1a\nGENERATED')
            raw_b = e['t'].wire(dict(header, episode_id=format(i+6401, '032x'),
                        prompt=e['deps']['adapter'].programme_prompt(prompt)), b'\x89PNG\r\n\x1a\nGENERATED')
            a_frame = self.m.add(self.a/'sessions'/name/'transport/0000-out.bin', raw_a)
            frames.append(self.m.add(self.b/'sessions'/name/'transport/0000-out.bin', raw_b))
            response = g.encode({'trial_id': trial, 'target_probability': 0.25})
            self.m.add(self.b/'sessions'/name/'response.txt', response)
            common = {'trial_id': trial, 'context_sha256': g.pin(prompt.encode())['sha256'],
                      **self.fields, 'closure_complete': True, 'generated_capture': True}
            a_end = self.m.add(self.a/'sessions'/name/'transport/END.json', common)
            b_end = self.m.add(self.b/'sessions'/name/'transport/END.json', common)
            ends.append(b_end)
            c_end = self.m.add(self.a/'providers'/name/'custody/CLIENT_END.json', dict(common, initial_frame=a_frame))
            self.m.add(self.b/'sessions'/name/'transport/MANIFEST.json', dict(self.fields, episode_id=format(i+6401, '032x')))
            self.m.add(self.a/'sessions'/name/'transport/MANIFEST.json', dict(self.fields, episode_id=format(i+1, '032x')))
            self.audit_records[i] = common
            self.audits.append({'turns': 1, 'request_bytes': 1, 'response_bytes': 1,
                               'episode_id': format(i+1, '032x'), 'started_monotonic': float(i+2),
                               'finished_monotonic': float(i+2.5), 'provider_response_ids': ['generated-'+str(i)],
                               'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2},
                               'probability': 0.25, 'transport_end': a_end, 'client_end': c_end})
        stream = io.BytesIO()
        np.savez(stream, trial_ids=np.asarray(self.ids, dtype='<U34'), target_probability=np.full(6400, 0.25, dtype='<f8'))
        body = stream.getvalue()
        self.submission = body
        self.subpin = g.pin(body)
        for root in (self.a, self.b):
            self.m.add(root/'collection/submission.npz', body)
        collection = {'schema': 'neural077_transport_collection_v1', 'status': 'complete_unscored_transport_collection',
                      'queries': 6400, 'submission_sha256': self.subpin['sha256'], 'scoring_performed': False,
                      'provider_qualification': 'not_established', 'packet_sha256': self.data['packet'], **self.fields}
        ac = self.m.add(self.a/'collection/TRANSPORT_COMPLETE.json', dict(collection, condition=g.CONDITIONS[0],
                       performance_claim='none', configuration_sha256=g.pin(g.encode(self.fields))['sha256']))
        bc = self.m.add(self.b/'collection/TRANSPORT_COMPLETE.json', dict(collection, condition=g.CONDITIONS[1],
                       performance_claim='none', configuration_sha256=g.pin(g.encode(self.fields))['sha256']))
        self.aarm = {'schema': self.provider.ARM, 'status': 'closed_unscored_visual_provider_arm',
                      'route': self.aman['route'], 'condition': g.CONDITIONS[0], 'queries': 6400, 'demonstrations': 4,
                      'source': e['deps']['bindings'], 'operator': self.aman['operator'], 'manifest': apin,
                      'episodes': [{k: row[k] for k in ('transport_end', 'client_end')} for row in self.audits],
                      'totals': self.provider._sum(self.audits, self.limits, g.PROFILE), 'collection': ac,
                      'submission': self.subpin, 'local_participant_sandbox': None, 'remote_context_qualified': False,
                      'provider_capacity_qualified': False, 'scientific_qualification': False,
                      'private_target_reads': 0, 'scoring_performed': False, **self.fields}
        self.barm = {'schema': 'neural077_image_programme_arm_v1', 'status': 'closed_unscored_image_programme_arm',
                      'condition': g.CONDITIONS[1], 'queries': 6400, 'demonstrations': 4, 'contract': self.cpin,
                      'manifest': bpin, 'episodes': ends, 'initial_frames': frames, 'collection': bc,
                      'submission': self.subpin, 'finished_monotonic': 7000.0, 'sandbox': 'macos',
                      'private_target_reads': 0, 'scoring_performed': False,
                      'os_enforcement_independently_qualified': False, 'scientific_qualification': False, **self.fields}
        self.apin = self.m.add(self.a/'ARM.json', self.aarm)
        self.bpin = self.m.add(self.b/'ARM.json', self.barm)
        self.audit_calls = []
        # Complete virtual directory metadata drives the real bounded scandir
        # inventory, including every generated capture file and directory.
        for member in self.m.bodies:
            child = member
            while child.parent.is_relative_to(self.a) or child.parent.is_relative_to(self.b):
                self.m.directories.setdefault(child.parent, set()).add(child.name)
                child = child.parent


    def validate_audit(self, i, data):
        row = self.audit_records[i]
        trial = data['trial_ids'][i]
        expected = {'trial_id': trial, 'context_sha256': g.pin(self.e['v'].scientific_prompt(trial, 'four_demo').encode())['sha256'],
                    **self.fields, 'closure_complete': True, 'generated_capture': True}
        if row != expected:
            raise ValueError('Generated case/context/profile/closure audit mismatch')
        self.audit_calls.append(i)

    def audit_provider(self, root, provider_root, data, i, deps, manifest, *, budget=None):
        self.validate_audit(i, data)
        if budget is not None:
            budget.input(len(g.encode(self.audit_records[i])) + 1)
        if root.name != f'{i:04d}' or provider_root.name != f'{i:04d}' or any(manifest.get(k) != v for k, v in self.fields.items()):
            raise ValueError('Generated retained-capture selection mismatch')
        return self.audits[i]

    def audit_programme(self, root, data, i, deps, contract, client, *, budget=None):
        self.validate_audit(i, data)
        if budget is not None:
            budget.input(len(g.encode(self.audit_records[i])) + 1)
        if root.name != f'{i:04d}' or any(contract.get(k) != v for k, v in self.fields.items()):
            raise ValueError('Generated programme selection mismatch')
        return {'generated_capture': True}

    def patches(self):
        stack = ExitStack()
        old_read = self.e['deps']['s'].read
        old_capture = self.provider.v.capture
        def supplied_read(path, cap=1048576, expected=None, *, budget=None):
            if Path(path) in self.m.bodies:
                return self.m.read(path, cap, expected, budget=budget)
            return old_capture(path, cap, expected, budget=budget) if budget is not None else old_read(path, cap, expected)
        # s.path/protected_path remain real ordinary-path checks. Only iterdir
        # and the exact retained-capture bytes are supplied from this memory map.
        original_iterdir = Path.iterdir
        stack.enter_context(patch.object(Path, 'iterdir', lambda path: self.m.iterdir(path) if path in self.m.directories else original_iterdir(path)))
        stack.enter_context(patch.object(self.e['deps']['s'], 'read', supplied_read))
        stack.enter_context(patch.object(self.image, 'read', supplied_read))
        stack.enter_context(patch.object(self.provider.v, 'capture', supplied_read))
        original_inventory = self.image.capture_inventory
        def generated_inventory(root, *, max_entries, max_bytes):
            root = Path(root)
            if root not in (self.a, self.b):
                return original_inventory(root, max_entries=max_entries, max_bytes=max_bytes)
            files = [p for p in self.m.bodies if p.is_relative_to(root)]
            directories = [p for p in self.m.directories if p.is_relative_to(root)]
            extent = sum(len(self.m.bodies[p]) for p in files)
            if len(files)+len(directories)>max_entries or extent>max_bytes:
                raise ValueError('Generated retained inventory exceeds selected metadata limits')
            return {'files':len(files), 'directories':len(directories), 'retained_bytes_observed':extent,
                    'maximum_directory_stack':8, 'observation':'metadata_only_not_body_authentication_or_custody_seal'}
        stack.enter_context(patch.object(self.image, 'capture_inventory', generated_inventory))
        stack.enter_context(patch.object(self.provider, 'audit_episode', self.audit_provider))
        stack.enter_context(patch.object(self.image, 'audit_programme_episode', self.audit_programme))
        # NPZ snapshots are real files passed to the unchanged ZIP/NPY validator.
        for module in (self.e['deps']['s'], self.image):
            original_write = module.write
            def tracked(path, body, *args, _write=original_write, **kwargs):
                g.charge_write(body)
                return _write(path, body, *args, **kwargs)
            stack.enter_context(patch.object(module, 'write', tracked))
        return stack

    def a_gate(self):
        return self.provider._admit_loaded(self.a, self.apin, self.e['deps'], self.data, g.PROFILE)

    def b_gate(self):
        return self.image._admit_programme_loaded(self.b, self.bpin, self.contract, self.e['deps'], self.data)

    def matching(self):
        return self.image.match_arm_information(self.a, self.b, self.data, self.e['deps'], self.contract,
                                               self.aman, self.bman, self.apin, self.bpin)


class FullRosterAdmissionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = integrated.setup_environment()
        cls.f = Captures(cls.e)

    def test_10_full6400_both_arms_npz_and_matching_before_private_boundary(self):
        f = self.f; seen = []
        def private(a, b, matching):
            seen.append('private_boundary')
            self.assertEqual(tuple(a['predictions']), f.ids)
            self.assertEqual(tuple(b['predictions']), f.ids)
            self.assertEqual(a['predictions'], b['predictions'])
            self.assertTrue(matching['same_initial_raster_bytes'])
            return 'generated_boundary_only'
        with f.patches():
            result = f.image._ordered_pair(f.a_gate, f.b_gate, f.matching, private)
        self.assertEqual(result, 'generated_boundary_only')
        self.assertEqual(seen, ['private_boundary'])
        self.assertEqual(f.audit_calls.count(0), 2)
        self.assertEqual(f.audit_calls.count(6399), 2)
        self.assertEqual(len(f.audit_calls), 12800)
        self.assertLessEqual(f.apin['bytes'], f.provider.arm_cap(g.PROFILE))
        self.assertLessEqual(f.bpin['bytes'], f.image.final_reserve(f.contract))
        self.assertGreater(f.apin['bytes'], 262144)
        self.assertGreater(f.bpin['bytes'], 262144)

    def test_11_missing_substituted_duplicate_and_wrong_profile_refuse_before_private(self):
        f = self.f
        with f.patches():
            for names in (set(list(sorted(f.m.directories[f.a/'sessions']))[:-1]),
                          (f.m.directories[f.a/'sessions'] - {'0000'}) | {'6400'}):
                original = f.m.directories[f.a/'sessions']; f.m.directories[f.a/'sessions'] = names
                try:
                    with self.assertRaises(ValueError):
                        f.a_gate()
                finally:
                    f.m.directories[f.a/'sessions'] = original
            for condition in ('four_demo', 'numeric_direct_four_demo'):
                bad = copy.deepcopy(f.aarm); bad['condition'] = condition
                raw = g.encode(bad); original = f.m.bodies[f.a/'ARM.json']; oldpin = f.apin
                f.m.bodies[f.a/'ARM.json'] = raw; f.apin = g.pin(raw)
                try:
                    with self.assertRaises(ValueError):
                        f.a_gate()
                finally:
                    f.m.bodies[f.a/'ARM.json'] = original; f.apin = oldpin
            # The private facade keeps the donor ZIP/NPY kernel and requires
            # exact opaque-ID storage width; wider Unicode is not admitted.
            import numpy as np
            donor = f.data['validator'].validator; before = dict(donor.__dict__)
            codes = {name: before[name].__code__ for name in ('validate', '_public_ids', '_read_candidate')}
            path = integrated.FIXTURES/'duplicate-submission.npz'
            stream = io.BytesIO(); np.savez(stream, trial_ids=np.asarray(f.ids, dtype='<U35'), target_probability=np.full(6400, .25))
            self.assertLessEqual(len(stream.getvalue()), 1024**2)
            g.write(path, stream.getvalue())
            with self.assertRaises(donor.InvalidSubmission) as caught:
                f.data['validator'].validate(path, list(f.ids))
            self.assertEqual(str(caught.exception), 'Exact little-endian U34 full32 opaque IDs required')
            self.assertEqual(set(donor.__dict__), set(before))
            for name, value in before.items():
                self.assertIs(donor.__dict__[name], value)
            for name, code in codes.items():
                self.assertIs(donor.__dict__[name].__code__, code)
            # Duplicate first-response opaque IDs pass no NPZ or private boundary.
            ids = list(f.ids); ids[-1] = ids[0]
            stream = io.BytesIO(); np.savez(stream, trial_ids=np.asarray(ids, dtype='<U34'), target_probability=np.full(6400, .25))
            g.write(path, stream.getvalue())
            with self.assertRaises(Exception):
                f.data['validator'].validate(path, list(f.ids))
            for field, changed in (('trial_id', f.ids[1]), ('context_sha256', 'f'*64),
                                   ('profile', 'legacy400'), ('closure_complete', False)):
                original = dict(f.audit_records[0]); f.audit_records[0][field] = changed
                private = []
                try:
                    with self.assertRaises(ValueError):
                        f.image._ordered_pair(f.a_gate, f.b_gate, f.matching, lambda *args: private.append(True))
                    self.assertEqual(private, [])
                finally:
                    f.audit_records[0] = original

    def test_12_second_arm_and_custody_matching_fail_before_private(self):
        f = self.f; private = []
        with f.patches():
            original = f.m.directories[f.b/'sessions']; f.m.directories[f.b/'sessions'] = original - {'0000'}
            try:
                with self.assertRaises(ValueError):
                    f.image._ordered_pair(f.a_gate, f.b_gate, f.matching, lambda *args: private.append(True))
                self.assertEqual(private, [])
            finally:
                f.m.directories[f.b/'sessions'] = original
            path = f.b/'sessions/0000/transport/0000-out.bin'; original = f.m.bodies[path]
            header, png = f.e['t'].unpack(original)
            header['trial_id'] = f.ids[1]
            changed = f.e['t'].wire(header, png)
            f.m.bodies[path] = changed
            # Update the generated outer custody commitment: the real matching
            # validator must still reject substituted query/context information.
            oldframe = f.barm['initial_frames'][0]; oldpin = f.bpin
            f.barm['initial_frames'][0] = g.pin(changed)
            f.bpin = f.m.add(f.b/'ARM.json', f.barm)
            try:
                with self.assertRaises(ValueError):
                    f.matching()
                self.assertEqual(private, [])
            finally:
                f.m.bodies[path] = original; f.barm['initial_frames'][0] = oldframe
                f.bpin = f.m.add(f.b/'ARM.json', f.barm)
                self.assertEqual(f.bpin, oldpin)

    def test_13_shared_metric_helper_orientation_equal_person_weight_and_clipping(self):
        e = self.e
        core, pair = e['deps']['full32_core'], e['deps']['full32_pair']
        people, direct, programme = {}, {}, {}
        position = 0
        # Unequal generated person sizes are a pure aggregation stressor. They
        # do not claim to satisfy the original private200-trial/person join.
        for person in range(32):
            size = 100 if person < 16 else 300
            rows = []
            for j in range(size):
                trial = e['packet'].ids[position]; position += 1
                label = j % 2
                rows.append((trial, label))
                direct[trial] = float(label if person < 16 else 1-label)
                programme[trial] = 0.5
            people['generated-person-' + str(person)] = rows
        numeric = pair.paired_metrics(core, direct, programme, people)
        visual = pair.paired_metrics(core, direct, programme, people, g.CONDITIONS)
        self.assertEqual(list(numeric['scores']), list(pair.CONDITIONS))
        self.assertEqual(list(visual['scores']), list(g.CONDITIONS))
        self.assertEqual(list(numeric['scores'].values()), list(visual['scores'].values()))
        self.assertAlmostEqual(visual['primary_direct_minus_program_macro_BA'], 0.0)
        differences = visual['paired_person_differences']
        self.assertTrue(all(row['direct_minus_program_balanced_accuracy'] == 0.5 for row in differences[:16]))
        self.assertTrue(all(row['direct_minus_program_balanced_accuracy'] == -0.5 for row in differences[16:]))
        correct = -0.5 * (math.log(1-1e-15) + math.log(1-1e-15))
        wrong = -0.5 * (math.log(1e-15) + math.log(1-(1-1e-15)))
        observed = visual['scores'][g.CONDITIONS[0]]['participant_macro_natural_log_loss']
        self.assertAlmostEqual(observed, (correct+wrong)/2, places=10)
        self.assertAlmostEqual(visual['scores'][g.CONDITIONS[1]]['participant_macro_natural_log_loss'], math.log(2), places=12)
        with self.assertRaises(ValueError):
            pair.paired_metrics(core, direct, programme, people, ('four_demo', 'numeric_program_four_demo'))
        incomplete = dict(direct); incomplete.pop(next(iter(incomplete)))
        with self.assertRaises(ValueError):
            pair.paired_metrics(core, incomplete, programme, people, g.CONDITIONS)

    def test_14_actual_compare_full32_stops_at_lazy_private_descriptor(self):
        from contextlib import nullcontext
        f = self.f
        class PrivateBoundaryReached(Exception):
            pass
        private_path = integrated.FIXTURES/'private-never-opened/LOCATIONS.json'
        attempts = []; state = {'matched': False}
        class DeferredPrivate:
            def __fspath__(self):
                if not state['matched']:
                    raise AssertionError('Private path interpreted before both arms and matching')
                attempts.append('private_path')
                return str(private_path)
        private = DeferredPrivate()
        original_matching = f.image.match_arm_information
        def marked_matching(*args, **kwargs):
            result = original_matching(*args, **kwargs)
            state['matched'] = True
            return result
        with f.patches():
            original_read = f.image.read
            def guarded(path, cap=1048576, expected=None, *, budget=None):
                if Path(path) == private_path:
                    attempts.append('private_descriptor')
                    raise PrivateBoundaryReached('Generated boundary reached; no private body exists')
                return original_read(path, cap, expected, budget=budget)
            with patch.object(f.image, 'read', guarded), \
                 patch.object(f.image, 'match_arm_information', marked_matching), \
                 patch.object(f.provider, 'dataset_for', return_value=f.data), \
                 patch.object(f.image, 'packet_data', return_value=f.data), \
                 patch.object(f.image, 'deadline', side_effect=lambda seconds: nullcontext()), \
                 patch.object(f.e['deps']['full32_core'], 'load_private_people', side_effect=AssertionError('Private loader prohibited')):
                limits = {'work_seconds': 60, 'read_bytes': 256*1024**2,
                          'write_bytes': 4*1024**2}
                output = integrated.FIXTURES/'compare-private-boundary'
                with self.assertRaises(PrivateBoundaryReached):
                    f.image.compare_full32(f.a, f.apin, f.b, f.bpin,
                        integrated.FIXTURES/'generated-frozen-contract.json', f.cpin,
                        private, output, f.e['deps'], f.contract, limits)
                self.assertEqual(attempts.count('private_descriptor'), 1)
                self.assertIn('private_path', attempts)
                self.assertEqual(attempts[-1], 'private_descriptor')
                failure = json.loads((output/'FAILED.json').read_bytes())
                self.assertTrue(failure['accounting']['both_public_validated_before_private'])
                self.assertTrue(failure['accounting']['matching_completed_before_private'])
                self.assertEqual(failure['accounting']['private_reference_attempts'], 1)
                self.assertEqual(failure['accounting']['target_loader_attempts'], 0)
                self.assertEqual(failure['accounting']['failure_write_bytes_reserved'], 65536)
                self.assertEqual(failure['accounting']['artifact_bytes_charged_before_failure'],
                                 65536 + 2*f.subpin['bytes'])
                # An incomplete second arm reaches neither descriptor nor target.
                names = f.m.directories[f.b/'sessions']; f.m.directories[f.b/'sessions'] = names-{'0000'}
                attempts.clear(); state['matched'] = False
                try:
                    with self.assertRaises(ValueError):
                        f.image.compare_full32(f.a, f.apin, f.b, f.bpin,
                            integrated.FIXTURES/'generated-frozen-contract.json', f.cpin,
                            private, integrated.FIXTURES/'compare-incomplete', f.e['deps'], f.contract, limits)
                    self.assertEqual(attempts, [])
                finally:
                    f.m.directories[f.b/'sessions'] = names

    def test_15_visual_bootstrap_policy_vectors_and_numeric_default(self):
        e = self.e
        bootstrap = g.load('generated_full32_bootstrap_profile', integrated.ROOT/'full32-paired-bootstrap-v1/paired_bootstrap.py')
        people, a, b = {}, {}, {}
        for i, person in enumerate(bootstrap.PEOPLE):
            rows = []
            for j in range(200):
                trial = e['packet'].ids[i*200+j]; label = int(j < 40)
                rows.append((trial, label)); a[trial] = 0.75 if label else 0.25; b[trial] = 0.5
            people[person] = rows
        metrics = e['deps']['full32_pair'].paired_metrics(e['deps']['full32_core'], a, b, people)
        numeric = {'schema': 'erp-full32-protected-pair-evaluation-v1', 'status': 'complete_finite_cohort_pair',
                   'people': 32, 'queries': 6400, 'both_public_arms_and_owned_closures_validated_before_private': True,
                   'new_benchmarks': 0, 'contract': g.pin(b'generated-contract'),
                   'public_arm_receipts': [g.pin(b'generated-direct'), g.pin(b'generated-programme')], **metrics}
        numeric_vectors = bootstrap.validate_result(numeric)
        visual = dict(numeric, profile=g.PROFILE, conditions=list(g.CONDITIONS),
                      operator_route='full32_visual_provider_vs_frozen_image_programme_v1',
                      profile_commitment=e['profile'].PROFILE_COMMITMENT,
                      **e['deps']['full32_pair'].paired_metrics(e['deps']['full32_core'], a, b, people, g.CONDITIONS))
        visual_vectors = bootstrap.validate_result(visual, profile=g.PROFILE)
        self.assertEqual(list(numeric_vectors.values()), list(visual_vectors.values()))
        self.assertEqual(bootstrap.policy_for(), bootstrap.POLICY)
        policy = bootstrap.policy_for(g.PROFILE)
        changed = {'profile', 'completion_scope', 'secondary_unadjusted_intervals'}
        self.assertEqual({k:v for k,v in policy.items() if k not in changed},
                         {k:v for k,v in bootstrap.POLICY.items() if k not in changed})
        self.assertEqual(policy['secondary_unadjusted_intervals'], list(bootstrap.metrics_for(g.PROFILE)[1:]))
        policy_file = json.loads((integrated.ROOT/'full32-paired-bootstrap-v1/VISUAL_BOOTSTRAP_POLICY.v1.json').read_bytes())
        self.assertEqual(policy_file, policy)
        large_visual = copy.deepcopy(visual); large_visual['contract'] = {'bytes': 65537, 'sha256': 'a'*64}
        bootstrap.validate_result(large_visual, profile=g.PROFILE)
        large_numeric = copy.deepcopy(numeric); large_numeric['contract'] = {'bytes': 65537, 'sha256': 'a'*64}
        with self.assertRaises(ValueError):
            bootstrap.validate_result(large_numeric)
        with self.assertRaises(ValueError):
            bootstrap.validate_result(visual)
        bad = copy.deepcopy(visual); bad['scores'][g.CONDITIONS[0]]['participants'][0]['participant_id'] = 'foreign'
        with self.assertRaises(ValueError):
            bootstrap.validate_result(bad, profile=g.PROFILE)
        # This control intentionally does not execute the unchanged10,000 draws.

    def test_16_linear_inventory_and_provider_counters_source_boundaries(self):
        import ast
        image, provider = self.e['image'], self.e['deps']['provider']
        image_tree = ast.parse(Path(image.__file__).read_bytes())
        provider_tree = ast.parse(Path(provider.__file__).read_bytes())
        run = next(n for n in image_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_programme')
        loops = [n for n in ast.walk(run) if isinstance(n, (ast.For, ast.While))]
        calls = [n for loop in loops for n in ast.walk(loop) if isinstance(n, ast.Call)]
        prefix_calls = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'tree_bytes'
                        and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == 'output']
        self.assertEqual(prefix_calls, [], 'No whole accumulated output inventory inside query loop')
        self.assertTrue(any(isinstance(n.func, ast.Name) and n.func.id == 'tree_bytes' for n in calls),
                        'Each new episode retains an actual bounded extent measurement')
        self.assertTrue(any(isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and n.left.id == 'final_inventory'
                            and any(isinstance(x, ast.Name) and x.id == 'measured_bytes' for x in n.comparators)
                            for n in ast.walk(run)), 'Final inventory must reconcile cumulative measurements')
        provider_run = next(n for n in provider_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_arm')
        for loop in [n for n in ast.walk(provider_run) if isinstance(n, (ast.For, ast.While))]:
            self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'sum'
                                 for n in ast.walk(loop)), 'No repeated sum of prior provider rows inside query loop')
        root = integrated.FIXTURES/'extent-control'; root.mkdir()
        observed = 0
        for i, body in enumerate((b'aa', b'bbbb', b'cccccc')):
            session = root/str(i); session.mkdir(); g.write(session/'capture.bin', body)
            observed += image.tree_bytes(session)
        self.assertEqual(image.tree_bytes(root), observed)
        self.assertEqual(observed, 12)
        # Existing task-local Budget refuses before any body read. The sentinel
        # is reserved even when the ordinary file has not grown concurrently.
        import os
        import time
        source = integrated.FIXTURES/'budget-read.bin'; g.write(source, b'abc')
        Budget = self.e['deps']['full32_pair'].Budget
        original_fdopen = os.fdopen
        reads = []
        class ObservedStream:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                self.stream.__enter__(); return self
            def __exit__(self, *args):
                return self.stream.__exit__(*args)
            def fileno(self):
                return self.stream.fileno()
            def read(self, size=-1):
                reads.append(size)
                return self.stream.read(size)
        for reader in (image.read, self.e['v'].read_regular, provider.v.capture):
            with self.subTest(reader=reader.__name__):
                reads.clear()
                insufficient = Budget(3, 1024, time.monotonic()+30)
                with patch.object(os, 'fdopen', side_effect=lambda *args, **kwargs: ObservedStream(original_fdopen(*args, **kwargs))):
                    with self.assertRaises(ValueError):
                        reader(source, 1024, budget=insufficient)
                self.assertEqual(reads, [])
                self.assertEqual(insufficient.read, 0)
                exact = Budget(4, 1024, time.monotonic()+30)
                with patch.object(os, 'fdopen', side_effect=lambda *args, **kwargs: ObservedStream(original_fdopen(*args, **kwargs))):
                    self.assertEqual(reader(source, 1024, budget=exact), b'abc')
                self.assertEqual(reads, [4])
                self.assertEqual(exact.read, 4)
        observed = image.capture_inventory(root, max_entries=10, max_bytes=12)
        self.assertEqual(observed['retained_bytes_observed'], 12)
        self.assertEqual(observed['files'], 3)
        with self.assertRaises(ValueError):
            image.capture_inventory(root, max_entries=10, max_bytes=11)
        with self.assertRaises(ValueError):
            image.capture_inventory(root, max_entries=3, max_bytes=12)
        deep = integrated.FIXTURES/'depth-control'; deep.mkdir(); cursor = deep
        for i in range(9):
            cursor = cursor/str(i); cursor.mkdir()
        original_open, original_close = image.os.open, image.os.close
        owned = set(); peak = [0]
        def opened(*args, **kwargs):
            fd = original_open(*args, **kwargs); owned.add(fd); peak[0] = max(peak[0], len(owned)); return fd
        def closed(fd):
            original_close(fd); owned.discard(fd)
        with patch.object(image.os, 'open', opened), patch.object(image.os, 'close', closed):
            with self.assertRaises(ValueError):
                image.capture_inventory(deep, max_entries=100, max_bytes=100)
        self.assertEqual(owned, set())
        self.assertLessEqual(peak[0], 8)  # Explicit owned fds; iterator duplicates are separate.
