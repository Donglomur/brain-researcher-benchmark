"""Generated source-citation controls; no source acquisition or task execution."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('source_link_catalog', ROOT / 'src/neurobench/catalog.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


def pairs(doc):
    return {(row['kind'], row['url']) for row in catalog.external_links(doc)}


class SourceCitationTests(unittest.TestCase):
    def test_seven_candidate_schemas_export_declared_primary_sources(self):
        for suffix in ('DFINE', 'DPAD', 'DUNL', 'NPVC', 'PLEXUS', 'POYO', 'SBIND'):
            doc = {'id': 'PAPER-CANDIDATE-20261114-' + suffix, 'track': 'paper',
                   'provenance': {'paper': {'url': 'https://example.org/article'},
                                  'official_code': {'repo': 'https://example.org/official-code',
                                                    'required_dependency': {'repository': 'https://example.org/dependency'}},
                                  'data': [{'url': 'https://example.org/observations',
                                            'license': 'https://example.org/license'}],
                                  'historical': {'url': 'https://example.org/old-source'}}}
            with self.subTest(suffix=suffix):
                self.assertEqual(pairs(doc), {('paper', 'https://example.org/article'),
                                             ('code', 'https://example.org/official-code'),
                                             ('data', 'https://example.org/observations')})

    def test_structured_experience_distinct_top_level_schema(self):
        doc = {'id': 'PAPER-ADMISSION-STRUCTURED-EXPERIENCE-20261113', 'track': 'paper',
               'paper': {'url': 'https://example.org/article'},
               'official_repository': {'url': 'https://example.org/code'},
               'data_source': {'exact_metadata_url': 'https://example.org/archive', 'acquired': False}}
        self.assertEqual(pairs(doc), {('paper', 'https://example.org/article'),
                                     ('code', 'https://example.org/code'), ('data', 'https://example.org/archive')})

    def test_scope_schemas_keep_preprocessing_code_out_of_data(self):
        for suffix in ('LATENTCIRCUIT', 'REM-DYNAMICS'):
            doc = {'id': 'PAPER-SCOPE-20261114-' + suffix, 'track': 'paper',
                   'provenance': {'official_code': {'repository': 'https://example.org/code',
                                                    'required_dependency': {'repository': 'https://example.org/dependency'}},
                                  'data': {'url': 'https://example.org/deposit',
                                           'source_page': 'https://example.org/dataset',
                                           'neural_url': 'https://example.org/observations.zip',
                                           'preprocessing_code_url': 'https://example.org/preprocessing.zip'}}}
            with self.subTest(suffix=suffix):
                self.assertEqual(pairs(doc), {('code', 'https://example.org/code'),
                                             ('code', 'https://example.org/preprocessing.zip'),
                                             ('data', 'https://example.org/deposit'),
                                             ('data', 'https://example.org/dataset'),
                                             ('data', 'https://example.org/observations.zip')})

    def test_five_public_paper_queries_survive_without_opening_query_policy(self):
        cases = {
            'PAPER-paper-method-012': 'https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012934',
            'PAPER-paper-method-add-004': 'https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013385',
            'PAPER-paper-method-replacement-006': 'https://openreview.net/forum?id=FVuqJt3c4L',
            'PAPER-paper-method-replacement-008': 'https://openreview.net/forum?id=LDjBDk3Czb',
            'PAPER-paper-method-replacement-012': 'https://openreview.net/forum?id=zt3RKc6VBp',
        }
        for identifier, url in cases.items():
            doc = {'id': identifier, 'track': 'paper', 'paper_identity': {'url': url}}
            with self.subTest(identifier=identifier):
                self.assertEqual(pairs(doc), {('paper', url)})
                for rejected in (url + '&token=secret', url + '#fragment',
                                 url.replace('https://', 'https://name:password@'),
                                 url.replace('https://', 'https://wrong-host.invalid/'),
                                 url + ' '):
                    self.assertEqual(pairs({**doc, 'paper_identity': {'url': rejected}}), set())
                self.assertEqual(pairs({**doc, 'id': 'UNREVIEWED'}), set())
                self.assertEqual(pairs({**doc, 'track': 'neural'}), set())
                self.assertEqual(pairs({**doc, 'paper_identity': {}, 'data': {'url': url}}), set())

    def test_npvc_public_dataset_identifier_query_is_data_only(self):
        url = 'https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NL1CAQ'
        doc = {'id': 'PAPER-CANDIDATE-20261114-NPVC', 'track': 'paper',
               'provenance': {'data': [{'url': url}]}}
        self.assertEqual(pairs(doc), {('data', url)})
        self.assertEqual(pairs({**doc, 'provenance': {'data': [{'url': url + '&token=secret'}]}}), set())
        self.assertEqual(pairs({**doc, 'provenance': {'paper': {'url': url}}}), set())

    def test_only_five_exact_route_zero_preimages_are_data(self):
        cases = {
            'PAPER-paper-method-012': 'https://doi.org/10.1371/journal.pcbi.1012934.s002',
            'PAPER-paper-method-add-004': 'https://portal.brain-map.org/explore/circuits/visual-coding-neuropixels',
            'PAPER-paper-method-replacement-006': 'https://braintreebank.dev/',
            'PAPER-paper-method-replacement-008': 'https://braintreebank.dev/',
            'PAPER-paper-method-replacement-012': 'https://figshare.com/articles/dataset/19448531',
        }
        weight, metadata = 'https://example.org/model.ckpt', 'https://example.org/electrode-selection.json'
        for identifier, url in cases.items():
            doc = {'id': identifier, 'track': 'paper', 'input_assets': {'routes': [url, weight, metadata]}}
            with self.subTest(identifier=identifier):
                self.assertEqual(pairs(doc), {('data', url), ('source', weight), ('source', metadata)})
                self.assertEqual(pairs({**doc, 'id': 'UNREVIEWED'}),
                                 {('source', url), ('source', weight), ('source', metadata)})
                self.assertNotIn(('data', url), pairs({**doc, 'track': 'neural'}))
                self.assertEqual(pairs({**doc, 'input_assets': {'routes': [weight, url]}}),
                                 {('source', weight), ('source', url)})
                self.assertEqual(pairs({**doc, 'input_assets': {'routes': [url + '/changed']}}),
                                 {('source', url + '/changed')})

    def test_missing_optional_fields_and_unreviewed_nested_schema(self):
        self.assertEqual(pairs({}), set())
        source = {'paper': {'url': 'https://example.org/article'},
                  'official_code': {'repo': 'https://example.org/code'},
                  'data': [{'url': 'https://example.org/data'}]}
        for identifier, track in [('PAPER-UNREVIEWED', 'paper'), ('PAPER-CANDIDATE-20261114-DFINE', 'neural')]:
            self.assertEqual(pairs({'id': identifier, 'track': track, 'provenance': source}), set())
        for bad in (None, [], True, 'not an object'):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'input_assets must be an object'):
                catalog.external_links({'input_assets': bad})

    def test_input_is_unchanged_and_output_is_stable(self):
        doc = {'id': 'PAPER-CANDIDATE-20261114-DFINE', 'track': 'paper',
               'status': 'unqualified', 'admission': {'runnable': False, 'research_qualified': False},
               'evaluation': {'outcome': 'unknown'}, 'holds': ['not run'],
               'resources': {'measured': False}, 'provenance': {'data': [{'url': 'https://example.org/data'}]},
               'sources': ['https://example.org/source', 'https://example.org/source'],
               'data': {'url': 'https://example.org/unsafe?token=secret'}}
        before = copy.deepcopy(doc)
        first = catalog.external_links(doc)
        self.assertEqual(first, catalog.external_links(doc))
        self.assertEqual(first, sorted(first, key=lambda x: (x['kind'], x['url'])))
        self.assertEqual(doc, before)
        self.assertEqual(pairs(doc), {('data', 'https://example.org/data'), ('source', 'https://example.org/source')})


if __name__ == '__main__':
    unittest.main()
