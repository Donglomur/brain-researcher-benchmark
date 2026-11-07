"""Metadata-only delivery tests: identity, provenance and non-promotion failures."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'build_paper_delivery_manifests.py'
spec = importlib.util.spec_from_file_location('paper_delivery_builder', PATH)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def put(root, path, obj):
    p = root / path; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))


def fixture(root):
    source = 'docs/neuroscience-benchmarks/readiness/example.json'
    row = {'id': 'PAPER-example', 'source_id': 'example', 'title': 'Empirical contrast',
        'paper_url': 'https://example.invalid/paper', 'publication_year': 2025, 'venue': 'Fixture only',
        'central_reproduction_outputs': ['Between-animal contrast with paired controls'],
        'improvement_outputs': ['Held-out animal prediction'], 'data_urls': ['https://example.invalid/data'],
        'code_url': 'https://example.invalid/code', 'code_revision_or_archive_version': 'a' * 40,
        'entrypoints': ['analyze.py'], 'paired_access_conditions': ['paper_and_data', 'paper_data_official_code']}
    auditrow = {'id': row['id'], 'source_id': row['source_id'], 'title': row['title'],
        'evidence': [{'path': source, 'record_id': 'example'}],
        'documented_endpoint': {'documented_outputs': row['central_reproduction_outputs'], 'tolerance': None},
        'input_and_code_lineage': {'input_scope': 'trial-level data; checksum not independently verified'},
        'reference_execution_status': {'status': 'source_only'},
        'improvement_evaluation_status': {'status': 'unqualified'},
        'comparability_gates': ['Group animals; retain matched controls'],
        'resource_evidence': {'estimated': 'CPU', 'measured': None},
        'remaining_gates': ['Freeze target contrast'], 'next_action': 'Inspect trial IDs against the analysis loader',
        'origin_batch': {'name': 'a'}, 'integration_classification': 'no_empirical_reference_established'}
    source_row = {'id': 'example', 'input_version': 'v1',
        'data_inputs': [{'files': [{'name': 'trials.mat', 'bytes': 321, 'checksum': 'untyped-source-value',
                                 'etag': 'multipart-2', 'asset_id': 'source-asset'}]}],
        'official_code': {'url': row['code_url'], 'commit': row['code_revision_or_archive_version']}}
    put(root, builder.ROSTER, {'tasks': [row]})
    put(root, builder.AUDIT, {'tasks': [auditrow], 'current_reference_summary': {}, 'source_pins': {}})
    put(root, source, [source_row])
    return row, auditrow, source, source_row


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.row, self.auditrow, self.source, self.source_row = fixture(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        return builder.build_documents(self.root, expected_count=1)['PAPER-example']

    def test_source_checksum_and_etag_not_promoted_to_payload_sha(self):
        item = self.build()['input_assets']['exact_asset_records'][0]
        self.assertIsNone(item['content_sha256_explicit'])
        self.assertEqual(item['checksum_fields_as_recorded']['etag'], 'multipart-2')
        self.assertEqual(item['recorded_fields']['asset_id'], 'source-asset')

    def test_no_executor_registered_from_source_ready_label(self):
        self.source_row.update(status='artifact_ready', execution_qualified=True)
        put(self.root, self.source, [self.source_row])
        doc = self.build()
        self.assertEqual(doc['status'], 'specification_only')
        self.assertFalse(doc['admission']['runnable'])
        self.assertIsNone(doc['evaluation']['scorer_ref'])

    def test_mutating_source_changes_record_and_file_provenance(self):
        before = self.build()['provenance']['source_records_and_files'][0]
        self.source_row['input_version'] = 'v2'
        put(self.root, self.source, [self.source_row])
        after = self.build()['provenance']['source_records_and_files'][0]
        self.assertNotEqual(before['record_sha256'], after['record_sha256'])
        self.assertNotEqual(before['file']['sha256'], after['file']['sha256'])

    def test_duplicate_canonical_ids_fail(self):
        put(self.root, builder.ROSTER, {'tasks': [self.row, self.row]})
        with self.assertRaisesRegex(ValueError, 'count/uniqueness'):
            builder.build_documents(self.root, expected_count=2)

    def test_missing_or_different_audit_identity_fails(self):
        self.auditrow['id'] = 'PAPER-unrelated'
        put(self.root, builder.AUDIT, {'tasks': [self.auditrow]})
        with self.assertRaisesRegex(ValueError, 'exact order'): self.build()

    def test_unsafe_output_id_fails(self):
        self.row['id'] = 'PAPER-../../escape'
        put(self.root, builder.ROSTER, {'tasks': [self.row]})
        with self.assertRaisesRegex(ValueError, 'unsafe canonical'): self.build()

    def test_missing_source_record_is_not_silently_ignored(self):
        put(self.root, self.source, [{'id': 'different'}])
        with self.assertRaisesRegex(ValueError, 'unique source record missing'): self.build()

    def test_stale_declared_record_hash_rejected(self):
        self.auditrow['evidence'][0]['record_sha256'] = '0' * 64
        put(self.root, builder.AUDIT, {'tasks': [self.auditrow]})
        with self.assertRaisesRegex(ValueError, 'source record is stale'): self.build()

    def test_stale_declared_source_file_pin_rejected(self):
        put(self.root, builder.AUDIT, {'tasks': [self.auditrow], 'source_pins': {
            self.source: {'bytes': 1, 'sha256': '0' * 64}}})
        with self.assertRaisesRegex(ValueError, 'source pin is stale'): self.build()

    def test_code_tree_hash_not_extracted_as_input_payload(self):
        self.source_row['data_inputs'][0]['official_code'] = {'files': [{'name': 'oracle.py', 'sha256': 'f' * 64}]}
        put(self.root, self.source, [self.source_row])
        assets = self.build()['input_assets']['exact_asset_records']
        self.assertEqual([a['recorded_fields']['name'] for a in assets], ['trials.mat'])

    def test_current_hold_overrides_old_acquisition_action(self):
        put(self.root, builder.AUDIT, {'tasks': [self.auditrow], 'current_construction_holds': [
            {'id': self.row['id'], 'status': 'provenance_hold', 'remaining_gates': ['Unresolved event provenance']} ]})
        doc = self.build()
        self.assertIn('Unresolved event provenance', doc['next_implementation_action']['action'])
        self.assertEqual(doc['next_implementation_action']['historical_audit_action'], self.auditrow['next_action'])
        self.assertFalse(doc['admission']['research_qualified'])

    def test_declared_source_pointer_and_exact_record_hash_retained(self):
        doc = self.build()
        asset = doc['input_assets']['exact_asset_records'][0]
        self.assertEqual(asset['json_pointer'], '/data_inputs/0/files/0')
        self.assertEqual(doc['provenance']['source_records_and_files'][0]['record_sha256'],
                         builder.record_hash(self.source_row))

    def test_validation_refuses_silent_runtime_promotion(self):
        doc = self.build(); doc['evaluation']['executor_ref'] = 'some-script.py'
        with self.assertRaisesRegex(ValueError, 'unqualified executor'): builder.validate_document(doc)

    def test_deterministic_and_all_actual_canonical_ids(self):
        one = builder.build_documents()
        two = builder.build_documents()
        self.assertEqual(builder.encode(one), builder.encode(two))
        ids = [x['id'] for x in builder.load(builder.ROOT, builder.ROSTER)['tasks']]
        self.assertEqual(list(one), ids)
        self.assertEqual(len(one), 100)
        self.assertTrue(all(d['evaluation']['executor_ref'] is None and not d['admission']['runnable'] for d in one.values()))
        self.assertIn('row-ordered', one['PAPER-paper-signal-add-020']['next_implementation_action']['action'])
        self.assertTrue(one['PAPER-ROOT-ADD-013']['holds']['current_construction_holds'])
        microns = one['PAPER-FIND-020']['reproduction_evidence']['reconciliations']
        self.assertTrue(microns)
        self.assertIn('different pinned source formats', microns[0]['conclusion'])


if __name__ == '__main__': unittest.main()
