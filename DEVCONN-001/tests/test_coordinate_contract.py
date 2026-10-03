"""Manufactured CSV syntax only; no original Power asset."""
import inspect
import hashlib

import numpy as np
import pytest

import coordinate_contract as c


def test_exact_api_preserves_literal_ids_order_and_signed_coordinates():
    raw = b'ROI,X,Y,Z\r\n02,-1.25,2e0,-0\r\n1,0,3.5,-4\r\n'
    result = c.parse_power(raw, expected_rois=2)
    assert result['columns'] == ['ROI', 'X', 'Y', 'Z']
    assert result['roi_ids'] == ['02', '1']
    np.testing.assert_array_equal(result['coordinates'], [[-1.25, 2., -0.], [0., 3.5, -4.]])
    assert result['coordinates'].dtype == np.float64 and result['coordinates'].flags.c_contiguous
    assert result['roi_definitions'] == [
        {'roi_id': '02', 'center_mm': [-1.25, 2., -0.], 'radius_mm': 5.},
        {'roi_id': '1', 'center_mm': [0., 3.5, -4.], 'radius_mm': 5.}]
    assert raw == b'ROI,X,Y,Z\r\n02,-1.25,2e0,-0\r\n1,0,3.5,-4\r\n'


def test_literal_not_numeric_identity_and_independent_arrays():
    raw = b'ROI,X,Y,Z\n1,0,0,0\n01,1,2,3\n'
    result = c.parse_power(raw, 2)
    assert result['roi_ids'] == ['1', '01']
    result['coordinates'][0, 0] = 99.
    assert result['roi_definitions'][0]['center_mm'][0] == 0.
    assert c.parse_power(raw, 2)['coordinates'][0, 0] == 0.


@pytest.mark.parametrize('header', ['roi,X,Y,Z', 'ROI,x,Y,Z', 'ROI,X,Y,Z,extra',
                                   'ROI,X,X,Z', ' ROI,X,Y,Z', 'ROI\tX\tY\tZ'])
def test_exact_original_columns(header):
    with pytest.raises(ValueError, match='coordinate_columns'):
        c.parse_power((header + '\n1,0,0,0\n').encode(), 1)


@pytest.mark.parametrize('row', ['1,0,0', '1,0,0,0,1', '', ',0,0,0',
    '1,,0,0', ' 1,0,0,0', '1,0 ,0,0', '1,0,\t0,0', '1,"0\n",0,0',
    '1,0,0,\u00a00', '1,\x00,0,0', '1,0,\x01,0', '1,0,\x7f,0'])
def test_ragged_blank_whitespace_control_tokens(row):
    with pytest.raises(ValueError):
        c.parse_power(('ROI,X,Y,Z\n' + row + '\n').encode(), 1)


@pytest.mark.parametrize('value', ['NaN', 'nan', 'Inf', 'Infinity', '-inf', '1e999', 'True', 'n/a', '1_foo'])
def test_coordinate_values_must_be_finite_numeric(value):
    with pytest.raises(ValueError):
        c.parse_power(f'ROI,X,Y,Z\n1,{value},0,0\n'.encode(), 1)


@pytest.mark.parametrize('raw', [b'ROI,X,Y,Z\n1,0,0,0\n1,1,1,1\n',
    b'ROI,X,Y,Z\n1,0,0,0\n', b'ROI,X,Y,Z\n1,0,0,0\n2,1,1,1\n3,2,2,2\n'])
def test_complete_unique_exact_row_count(raw):
    with pytest.raises(ValueError): c.parse_power(raw, 2)


@pytest.mark.parametrize('count', [True, False, 0, -1, 1., '1', 4097])
def test_expected_count_typed_and_bounded(count):
    with pytest.raises(ValueError): c.parse_power(b'ROI,X,Y,Z\n1,0,0,0\n', count)


@pytest.mark.parametrize('raw', [b'', b'x' * (c.MAX_BYTES + 1), bytearray(b'ROI,X,Y,Z'),
    'ROI,X,Y,Z', b'\xff', b'\xef\xbb\xbfROI,X,Y,Z\n1,0,0,0\n',
    b'ROI,X,Y,Z\n"unterminated,0,0,0\n'])
def test_raw_type_encoding_caps_and_malformed_quotes(raw):
    with pytest.raises((ValueError, UnicodeError, c.csv.Error)): c.parse_power(raw, 1)


def test_field_cap_and_no_file_or_estimator_api():
    with pytest.raises(ValueError, match='coordinate_token'):
        c.parse_power(b'ROI,X,Y,Z\n' + b'x' * 257 + b',0,0,0\n', 1)
    source = inspect.getsource(c)
    assert 'open(' not in source and 'Path(' not in source and 'nilearn' not in source


def example_bins():
    return dict(roi_ids=['1', '02', '3'], pairs=np.array([[0, 1], [0, 2], [1, 2]]),
                n_pairs=3, short_range=np.array([True, False, False]),
                long_range=np.array([False, True, False]), q1_mm=2., q2_mm=4.)


def test_bin_record_exact_public_encoding_and_no_mutation():
    bins = example_bins()
    expected = hashlib.sha256(b'DEVCONN_distance_bins_v2\n1\x0002\x003\n' +
        np.array([[0, 1], [0, 2], [1, 2]], dtype='<i8').tobytes() +
        bytes([1, 0, 0, 1, 0, 0])).hexdigest()
    assert c.bin_record(bins) == dict(q1_mm=2., q2_mm=4., n_pairs=3,
        n_short_edges=1, n_long_edges=1, membership_sha256=expected)
    np.testing.assert_array_equal(bins['pairs'], [[0, 1], [0, 2], [1, 2]])
    bins['roi_ids'][1] = '2'
    assert c.bin_record(bins)['membership_sha256'] != expected


@pytest.mark.parametrize('key,value', [
    ('roi_ids', ['1', '2\n', '3']), ('roi_ids', ['1', '2\0', '3']),
    ('roi_ids', ['1', '1', '3']), ('roi_ids', ['1', 2, '3']),
    ('pairs', [[0., 1.], [0., 2.], [1., 2.]]), ('pairs', [[0, 2], [0, 1], [1, 2]]),
    ('pairs', [[0, 1], [0, 2]]), ('n_pairs', True), ('n_pairs', 2),
    ('short_range', [1, 0, 0]), ('short_range', [True, True, False]),
    ('long_range', [False, True]), ('q1_mm', True), ('q1_mm', float('nan')),
    ('q1_mm', -1.), ('q1_mm', 5.), ('q2_mm', '4')])
def test_bin_record_typed_complete_geometry_only(key, value):
    bins = example_bins(); bins[key] = value
    with pytest.raises(ValueError): c.bin_record(bins)
