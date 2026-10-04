"""Source-free representation tests; original artifacts and sources are not read."""
import copy

import pytest

import artifact_reader as a
import proof_of_work as p


CONFIGS = ('nobp_all', 'bp_all', 'nobp_firstHalf', 'nobp_secondHalf')


@pytest.fixture
def rows():
    return [dict(config=name, subject_ids=['fabricated'], bandpass=name == 'bp_all',
                 embedding_status='ok', principal_status='ok', retained_span_status='ok',
                 apex_network='Default', bottom_network='Vis', between_within=1.,
                 between_within_status='ok', principal_gap=.2, retained_boundary_gap=.1)
            for name in CONFIGS]


@pytest.mark.parametrize('form', ['list', 'reversed_list', 'mapping', 'outer_only', 'mixed'])
def test_complete_equivalent_configuration_containers(rows, form):
    actual = copy.deepcopy(rows)
    if form == 'reversed_list': actual.reverse()
    elif form != 'list':
        actual = {row['config']: row for row in reversed(actual)}
        for i, row in enumerate(actual.values()):
            if form == 'outer_only' or form == 'mixed' and i % 2: del row['config']
    before = copy.deepcopy(actual)
    normalized = p.configuration_records(actual, rows)
    p.match(normalized, rows, 'configuration summaries')
    assert actual == before


@pytest.mark.parametrize('change', ['missing', 'unknown', 'conflict', 'duplicate_list',
    'missing_list_id', 'boolean_id', 'nested_id', 'non_record', 'mapping_non_record',
    'numeric_outer', 'empty_mapping', 'null', 'scalar', 'wrong_number', 'wrong_status',
    'wrong_membership', 'nan', 'bool_number'])
def test_malformed_identity_or_content_still_rejected(rows, change):
    actual = copy.deepcopy(rows)
    if change == 'missing': actual.pop()
    elif change == 'unknown': actual[0]['config'] = 'unknown'
    elif change == 'conflict':
        actual = {row['config']: row for row in actual}; actual[CONFIGS[0]]['config'] = CONFIGS[1]
    elif change == 'duplicate_list': actual[1] = copy.deepcopy(actual[0])
    elif change == 'missing_list_id': del actual[0]['config']
    elif change == 'boolean_id': actual[0]['config'] = True
    elif change == 'nested_id': actual[0]['config'] = ['nobp_all']
    elif change == 'non_record': actual[0] = 'nobp_all'
    elif change == 'mapping_non_record': actual = {row['config']: None for row in actual}
    elif change == 'numeric_outer': actual = {i: row for i, row in enumerate(actual)}
    elif change == 'empty_mapping': actual = {}
    elif change == 'null': actual = None
    elif change == 'scalar': actual = 'nobp_all'
    elif change == 'wrong_number': actual[0]['between_within'] = 2.
    elif change == 'wrong_status': actual[0]['embedding_status'] = 'inactive_parcel'
    elif change == 'wrong_membership': actual[0]['subject_ids'] = ['other']
    elif change == 'nan': actual[0]['between_within'] = float('nan')
    elif change == 'bool_number': actual[0]['between_within'] = True
    with pytest.raises(ValueError): p.match(p.configuration_records(actual, rows), rows, 'configuration summaries')


def test_duplicate_object_config_key_rejected_before_normalization():
    with pytest.raises(ValueError, match='duplicate JSON key'):
        a.parse_json(b'{"configuration_summaries":{"nobp_all":{},"nobp_all":{}}}')


@pytest.mark.parametrize('form', ['list', 'mapping'])
def test_configuration_source_inactive_status_alias(rows, form):
    for row in rows: row['embedding_status'] = 'inactive_parcel'
    actual = copy.deepcopy(rows)
    for row in actual: row['embedding_status'] = 'source_incomplete'
    if form == 'mapping': actual = {row['config']: row for row in actual}
    before = copy.deepcopy(actual)
    p.match(p.configuration_records(actual, rows), rows, 'configuration summaries')
    assert actual == before


@pytest.mark.parametrize('canonical_status', ['ok', 'multiscale_singular'])
def test_source_incomplete_cannot_alias_other_embedding_states(rows, canonical_status):
    rows[0]['embedding_status'] = canonical_status
    actual = copy.deepcopy(rows); actual[0]['embedding_status'] = 'source_incomplete'
    with pytest.raises(ValueError, match='literal mismatch'):
        p.match(p.configuration_records(actual, rows), rows, 'configuration summaries')


def test_configuration_alias_does_not_change_other_statuses_or_per_subject_rule(rows):
    rows[0]['embedding_status'] = 'inactive_parcel'
    actual = copy.deepcopy(rows)
    actual[0].update(embedding_status='source_incomplete', principal_status='source_incomplete')
    with pytest.raises(ValueError, match='literal mismatch'):
        p.match(p.configuration_records(actual, rows), rows, 'configuration summaries')
    with pytest.raises(ValueError, match='literal mismatch'):
        p.match('source_incomplete', 'inactive_parcel', 'per_subject.embedding_status')


@pytest.fixture
def documentary():
    header = dict(shape=[1, 1, 1, 2], affine=[[1., 0., 0., 0.], [0., 1., 0., 0.],
        [0., 0., 1., 0.], [0., 0., 0., 1.]], source_dtype='<f4', spatial_units='mm',
        temporal_units='sec', raw_TR=2., raw_toffset=0., effective_scaling_slope=1., effective_scaling_intercept=0.)
    metadata = dict(schema_version='gradient-metadata-v2', status='ok', task_id='GRADIENT-001',
        source_manifest_sha256='a'*64, method_sha256='b'*64, output_schema_sha256='c'*64,
        source_files=[dict(path='fixture', role='provenance', participant_id=None, size_bytes=1, sha256='d'*64)],
        source_observed=dict(participant_ids=['fabricated'], source_order=['fabricated'], participant_column_names=['participant_id'],
            confound_column_names={'fabricated': ['fixture']}, headers={'fabricated': header}, atlas_header=copy.deepcopy(header),
            atlas_labels=[dict(parcel_id=1, label='fixture', network='Vis')],
            voxel_support_by_subject={'fabricated': [dict(parcel_id=1, n_voxels=1, support_sha256='e'*64)]},
            frame_alignment='released frame index', raw_clock_metadata={'fabricated': dict(raw_TR=2., raw_toffset=0., temporal_units='sec')},
            effective_TR_s=2., effective_origin_s=0.),
        software_versions={key: 'not_used' for key in ('python', 'numpy', 'scipy', 'nibabel', 'nilearn', 'brainspace')})
    actual = copy.deepcopy(metadata); actual.update(warnings=[], numerical_method_amendments='Descriptive method note.')
    return actual, {'metadata': metadata}


@pytest.mark.parametrize('amendments', ['Any nonempty description.', ['One description.'], ['First.', 'Second.']])
def test_documentary_amendments_string_or_list(documentary, amendments):
    actual, reference = documentary; actual['numerical_method_amendments'] = amendments
    before = copy.deepcopy(actual)
    p.metadata(actual, reference)
    assert actual == before


@pytest.mark.parametrize('amendments', [None, '', '  ', [], [''], [' '], ['valid', 1],
                                      ['valid', None], {}, {'note': 'valid'}, True, 1, [['nested']]])
def test_malformed_amendments_reject(documentary, amendments):
    actual, reference = documentary; actual['numerical_method_amendments'] = amendments
    with pytest.raises(ValueError, match='amendment description'): p.metadata(actual, reference)


@pytest.mark.parametrize('change', ['source_hash', 'source_units', 'source_clock', 'support', 'id', 'missing_field'])
def test_documentary_alias_does_not_weaken_source_truth(documentary, change):
    actual, reference = documentary; actual['numerical_method_amendments'] = ['Equivalent representation.']
    observed = actual['source_observed']
    if change == 'source_hash': actual['source_manifest_sha256'] = '0'*64
    elif change == 'source_units': observed['headers']['fabricated']['spatial_units'] = 'meter'
    elif change == 'source_clock': observed['raw_clock_metadata']['fabricated']['raw_TR'] = 1.
    elif change == 'support': observed['voxel_support_by_subject']['fabricated'][0]['n_voxels'] = 0
    elif change == 'id': observed['participant_ids'] = ['different']
    elif change == 'missing_field': del observed['source_order']
    with pytest.raises(ValueError): p.metadata(actual, reference)
