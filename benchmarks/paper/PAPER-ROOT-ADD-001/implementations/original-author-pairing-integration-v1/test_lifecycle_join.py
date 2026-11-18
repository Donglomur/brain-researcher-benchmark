"""One generated durable-file/lifecycle composition; no native or model run.

The lifecycle observations are fabricated test operands, never OS evidence.
Generated results must remain unable to enter the original-reference wrapper.
All fixture files are retained, including after failure; no retry or cleanup.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
TASK = Path(os.environ.get('LANGUAGE_TEST_TASK_HOME', str(HERE.parents[1])))
PAIR = Path(os.environ.get('LANGUAGE_PAIRING_COMPONENT_DIR',
                          str(TASK/'implementations/original-author-pairing-v1')))
WORK = 64*1024**2
FIXTURE_CAP = 2*1024**2
PINS = {
    'original-figure3b-execution-v1/test_execution.py': '1a677bc5072a36d15ec07d6cb367d779f716ec4acb355adb04dac69f58355ed4',
    'original-figure3b-store-v1/test_store.py': '76a22b6749eaeeacf707b4ab1bb0d807af6be4fc4673541e4db88b72e210903c',
    'original-protected-layout-v1/test_layout.py': 'fb8fdff6d730c5211e009f90e65f362aa8322c87359817ad6397928d93b91279',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': sha(raw)}


def load(name, path, expected):
    raw = path.read_bytes()
    assert len(raw) <= 65536 and sha(raw) == expected
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


class LifecycleJoinControl(unittest.TestCase):
    def test_real_generated_files_join_lifecycle_and_refuse_original_promotion(self):
        for relative, expected in PINS.items():
            self.assertEqual(pin(TASK/'implementations'/relative)['sha256'], expected)
        r = load('_lifecycle_control_reference', PAIR/'executed_reference.py',
                 '2805dcef579b0412da577ca1c5fa433d0a0dffe255540deab4ce22c25b530949')
        pairing = load('_lifecycle_control_pairing', PAIR/'paired.py',
                       'c5da4304846f65c89a01fc3b5d22d0a4adf07fce32729db1f0e0e92dab1e4380')
        assay = load('_lifecycle_existing_assay',
                     TASK/'implementations/original-figure3b-execution-v1/test_execution.py',
                     PINS['original-figure3b-execution-v1/test_execution.py'])
        e = assay.e
        fixture = assay.load_fixture()
        geometry, data, _, plan = fixture.fixture()
        self.assertEqual((geometry['time_bins'], geometry['word_rows'], geometry['units']), (96, 10, 3))
        self.assertEqual(plan.scope, 'generated_prefix_control')
        if 'LANGUAGE_INTEGRATION_OUTPUT_ROOT' in os.environ:
            root = Path(os.environ['LANGUAGE_INTEGRATION_OUTPUT_ROOT']).absolute()
            self.assertFalse(any(p.is_symlink() for p in (root, *root.parents)))
            root.mkdir(mode=0o700, parents=True, exist_ok=False)
        else:
            root = Path(tempfile.mkdtemp(prefix='language-lifecycle-join-'))
        print('Retained generated integration fixture:', root, flush=True)
        out = fixture.s.prepare_generated(root/'store', plan, {'p1_1': data},
            working_limit=256*1024**2, output_limit=256*1024, metadata_limit=512*1024)
        count = out['metadata']['counts']['software_callbacks']
        self.assertTrue(6 <= count <= 30)
        self.assertEqual(out['metadata']['counts']['jobs'], 3)
        reader_module = assay.cli.load_reader(assay.source_pins())

        def reader():
            return reader_module.StoreReader(root/'store', expected_store_sha256=out['store']['sha256'],
                read_limit=16*1024**2, working_limit=256*1024**2)

        run = e.J.make_run(store_sha256=out['store']['sha256'], candidate_sha256='2'*64,
            schedule_sha256='3'*64, provider_source_sha256='4'*64, condition='paper_data',
            working_limit=WORK, generated_contexts=list(e.J.ENDPOINT.coordinates()[:3]),
            generated_requests=count)
        config = {'candidate_sha256': '2'*64, 'provider_source_sha256': '4'*64}
        synthetic_admission = {'generated_test_operand': True, 'native_execution': False}

        class SyntheticJournalProvider(assay.Provider):
            """Real permitted-bundle predictor; deliberately synthetic OS records."""
            def __init__(self):
                super().__init__()
                self.feature_bytes = None
                self.journal = [{'event': 'open', 'mode': 'exec_reset_bwrap_v1',
                    'config_sha256': r.sha(r.encoded(config)), 'admission': synthetic_admission,
                    'scientific_qualification': False}]

            def prepare_feature(self, path, spec, *, rows):
                self.feature_bytes = spec['bytes']
                return super().prepare_feature(path, spec, rows=rows)

            def run_request(self, handle, raw, descriptor):
                body, closure = super().run_request(handle, raw, descriptor)
                n = self.calls
                assert n <= 30
                self.journal.extend([
                    {'event': 'start', 'request': n, 'request_sha256': descriptor.public_id,
                     'feature_bytes': self.feature_bytes, 'bundle_bytes': len(raw),
                     'descriptor_bytes': len(descriptor.public_json)},
                    {'event': 'closed', 'request': n, 'closure': closure,
                     'observation': {'natural_exit_zero': True, 'owned_processes_absent': True,
                         'gate_joined_before_exec': True, 'pidfd_owned': True,
                         'cgroup_name': 'language-'+format(n, '032x'), 'cgroup_inode': 100+n,
                         'cgroup_device': 1, 'memory_events': {'oom_kill': 0}}}])
                return body, closure

            def finish(self):
                before = {'max_jobs': self.features, 'max_requests': self.calls,
                          'journal_bytes': sum(len(r.encoded(row)) for row in self.journal)}
                self.journal.append({'event': 'finish', 'counters_before_finish_record': before})
                raw = b''.join(r.encoded(row) for row in self.journal)
                assert len(raw) <= 256*1024
                with (root/'SYNTHETIC_LIFECYCLE.jsonl').open('xb') as stream:
                    assert stream.write(raw) == len(raw)
                return {'schema': 'language-exec-provider-receipt/v1', 'mode': 'exec_reset_bwrap_v1',
                    'config_sha256': r.sha(r.encoded(config)), 'admission': synthetic_admission,
                    'counters': {**before, 'journal_bytes': len(raw)}}

        # Complete gross caps before writes: store256KiB, packed/authority128KiB
        # each, collection/recovery receipt128KiB each, journal256KiB, summary16KiB.
        self.assertLessEqual((256+128+128+128+128+256+16)*1024, FIXTURE_CAP)
        provider = SyntheticJournalProvider()
        collected, collection_pin = e.collect(reader(), provider, run, root/'output', limits=assay.limits())
        self.assertEqual((provider.features, provider.calls), (3, count))
        self.assertTrue(provider.closed)
        self.assertEqual(collected['scope'], 'generated_engineering_control')
        manifest_raw = (root/'output/packed/MANIFEST.json').read_bytes()
        self.assertEqual(sha(manifest_raw), collected['join']['packed_manifest_sha256'])
        manifest = r.parse(manifest_raw)
        request_raw = r.owned_bytes(root/'output/packed/REQUESTS.bin',
            manifest['files']['REQUESTS.bin'], 30*e.J.P.REQUEST.size, r.Meter(128*1024))
        packed = list(e.J.P.REQUEST.iter_unpack(request_raw))
        self.assertEqual(len(packed), count)
        journal_raw = (root/'SYNTHETIC_LIFECYCLE.jsonl').read_bytes()
        records = r.lifecycle_records(journal_raw, count)
        source_reader = reader()
        authority = e.AuthorityReader(root/'output/authorities', run, collected['authorities'],
            receipt_sha256=sha(e.encoded(collected['authorities'])), read_limit=262144, working_limit=WORK)
        requests, identities, maps = [], [], []
        try:
            for session in source_reader.iter_sessions():
                try:
                    for item in session.iter_jobs(include_targets=False):
                        frozen = authority.next_job(qid=item['qid'], time_indices=item['time_indices'])
                        a, _, _ = e.J._job_snapshot(run, frozen, WORK)
                        for key in ('context', 'target_sha256', 'support_class_sha256', 'feature'):
                            self.assertEqual(a[key], item[key])
                        common, identity = r.common_lineage(a)
                        ordinal = len(identities)
                        self.assertEqual(a['coordinates'], e.J.ENDPOINT.coordinates()[ordinal])
                        for request in common['requests']:
                            held = struct.unpack('<d', bytes.fromhex(request['held_f64le']))[0]
                            rows = np.flatnonzero(item['qid'] == held)
                            self.assertEqual(request['query_rows'], len(rows))
                            maps.append((ordinal, request['request_sha256'], rows.tolist()))
                            requests.append((ordinal, request, a['feature']['bytes']))
                        identities.append(identity)
                finally:
                    session.close()
            authority_receipt = authority.finish()
        finally:
            e.close_owned(authority, source_reader)
        self.assertEqual((len(identities), len(requests)), (3, count))
        groups = r.verify_lifecycle(records, requests, packed, collected['provider'], config,
                                    mode='exec_reset_bwrap_v1')
        self.assertEqual(len(groups), count)
        mutations = {'closure_hash': 12, 'transport_hash': 10, 'held_qid': 6}
        for name, index in mutations.items():
            changed = list(packed)
            row = list(changed[0])
            row[index] = row[index]+1000. if index == 6 else bytes([row[index][0]^1])+row[index][1:]
            changed[0] = tuple(row)
            with self.subTest(tamper=name), self.assertRaisesRegex(ValueError, 'packed request'):
                r.verify_lifecycle(records, requests, changed, collected['provider'], config,
                                   mode='exec_reset_bwrap_v1')
        changed_requests = copy.deepcopy(requests)
        changed_requests[0][1]['query_rows'] += 1
        with self.assertRaisesRegex(ValueError, 'packed request'):
            r.verify_lifecycle(records, changed_requests, packed, collected['provider'], config,
                               mode='exec_reset_bwrap_v1')
        result, recovery_pin = e.recover(reader(), run, root/'output', collected,
            collection_sha256=collection_pin['sha256'], limits=assay.limits())
        expected = list(fixture.s.iter_selected_jobs(data))
        self.assertEqual(len(result['result']['generated_scores']), 3)
        for item, score in zip(expected, result['result']['generated_scores']):
            prediction = item['time_indices'][:, None].astype('<f8')**2+3
            np.testing.assert_equal(score['correlations'], e.J.ORIGINAL.pooled_pearson(item['y'], prediction))
        self.assertNotIn('candidate_scores', result['result'])
        self.assertFalse(result['scientific_qualification'])
        # No forged original scope, StoreReader replacement, _SEAL access or
        # production-method patch. Refusal occurs before any original recovery.
        with self.assertRaisesRegex(ValueError, 'generated products cannot become author evidence'):
            r.recover_executed(e, reader_module, run, collected, collection_pin,
                'executed_author_reference', config, store_root=root/'store', output_root=root/'output',
                evidence_root=root, store_limit=16*1024**2, store_working=256*1024**2,
                limits=assay.limits(), support_sha256='0'*64, extra_read_limit=1024**2,
                working_limit=256*1024**2)
        with self.assertRaisesRegex(ValueError, 'Raw-recovered sealed product required'):
            pairing.compare_products(result, result, r)
        before = sum(path.stat().st_size for path in root.rglob('*') if path.is_file())
        self.assertEqual(sum(path.stat().st_size for path in (root/'store').rglob('*') if path.is_file()), out['written_bytes'])
        summary = {'schema': 'language-generated-lifecycle-composition-control/v1',
            'status': 'passed', 'scope': 'generated_engineering_control', 'jobs': 3, 'requests': count,
            'fixture': {'time_bins': 96, 'word_rows': 10, 'units': 3, 'sessions': 1},
            'synthetic_lifecycle_not_native_evidence': True, 'production_methods_mocked': [],
            'authority_verification': authority_receipt, 'source_lineage_sha256': identities,
            'ordered_held_row_map_sha256': sha(e.encoded(maps)),
            'tamper_refusals': list(mutations)+['query_rows'], 'original_reference_promotion_refused': True,
            'aggregate_pairing_refused': True, 'original_reference_positive_path_executed': False,
            'scientific_qualification': False, 'native_executions': 0, 'estimator_fits': 0,
            'authentic_array_reads': 0, 'source_test': pin(Path(__file__)),
            'products': {str(path.relative_to(root)): pin(path) for path in
                (root/'store/STORE.json', root/'output/COLLECTION.json', root/'output/RECOVERY.json',
                 root/'output/packed/MANIFEST.json', root/'output/packed/REQUESTS.bin',
                 root/'output/authorities/META.bin', root/'output/authorities/REQUESTS.bin',
                 root/'SYNTHETIC_LIFECYCLE.jsonl')},
            'collection_pin': collection_pin, 'recovery_pin': recovery_pin,
            'application_bytes_before_summary': before, 'gross_application_write_cap_bytes': FIXTURE_CAP,
            'write_accounting': 'Exclusive or append-only generated files; no replacement, deletion or retry. Physical filesystem I/O not measured.'}
        raw = e.encoded(summary)
        self.assertLessEqual(len(raw), 16384)
        self.assertLessEqual(before+len(raw), FIXTURE_CAP)
        with (root/'CONTROL.json').open('xb') as stream:
            self.assertEqual(stream.write(raw), len(raw))
        print(json.dumps({'control': str(root/'CONTROL.json'), 'control_pin': pin(root/'CONTROL.json'),
            'gross_successful_application_bytes': before+len(raw), 'fixture_files':
            sum(path.is_file() for path in root.rglob('*')), 'jobs': 3, 'requests': count,
            'native_executions': 0, 'estimator_fits': 0}, sort_keys=True), flush=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
