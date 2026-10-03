"""Shared generic Power CSV syntax, not a signal or endpoint estimator.

The caller authenticates the immutable original bytes before calling parse_power.
No path access, source discovery, normalization of identities, or import-time work.
"""
import csv
import hashlib
import io
import math

import numpy as np

MAX_BYTES = 65536
MAX_FIELD_CHARACTERS = 256
COLUMNS = ('ROI', 'X', 'Y', 'Z')


def parse_power(raw, expected_rois=264):
    """Parse exact columns into unchanged literal IDs and finite float64 centers.

    Reject whitespace anywhere in a token, including quoted leading/trailing
    whitespace. Numeric notation is allowed; IDs remain their original strings.
    Source row order is returned unchanged. CRLF versus LF is ordinary CSV syntax.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('coordinate_bytes_or_cap')
    if type(expected_rois) is not int or not 1 <= expected_rois <= 4096:
        raise ValueError('coordinate_expected_count')
    text = raw.decode('utf-8')
    if '\0' in text:
        raise ValueError('coordinate_nul')
    reader = csv.reader(io.StringIO(text, newline=''), delimiter=',', strict=True)
    columns = next(reader, None)
    if columns != list(COLUMNS):
        raise ValueError('coordinate_columns')
    ids, coordinates = [], []
    for row in reader:
        if len(ids) >= expected_rois or len(row) != 4:
            raise ValueError('coordinate_rows_or_width')
        if any(not token or len(token) > MAX_FIELD_CHARACTERS or
               any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in token)
               for token in row):
            raise ValueError('coordinate_token')
        roi_id = row[0]
        if roi_id in ids:
            raise ValueError('coordinate_duplicate_id')
        try:
            xyz = [float(token) for token in row[1:]]
        except ValueError as exc:
            raise ValueError('coordinate_numeric_token') from exc
        if not all(math.isfinite(value) for value in xyz):
            raise ValueError('coordinate_nonfinite')
        ids.append(roi_id)
        coordinates.append(xyz)
    if len(ids) != expected_rois:
        raise ValueError('coordinate_count')
    xyz = np.asarray(coordinates, dtype=np.float64, order='C')
    definitions = [dict(roi_id=roi_id, center_mm=list(center), radius_mm=5.0)
                   for roi_id, center in zip(ids, coordinates)]
    return dict(columns=columns, roi_ids=ids, coordinates=xyz,
                roi_definitions=definitions)


def bin_record(bins):
    """Compact canonical distance-bin receipt; no signals or connectivity.

    Public digest: prefix + NUL-joined literal IDs + LF + all i<j C-order
    little-endian int64 pairs + columnstack(short,long) C-order uint8 bytes.
    """
    ids = bins['roi_ids']
    if (type(ids) is not list or len(ids) < 2 or len(ids) > 4096 or
            any(type(value) is not str or not value or
                any(ord(char) < 32 or ord(char) == 127 for char in value) for value in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('bin_roi_ids')
    expected = np.column_stack(np.triu_indices(len(ids), 1))
    pairs = np.asarray(bins['pairs'])
    if pairs.dtype.kind not in 'iu' or not np.array_equal(pairs, expected):
        raise ValueError('bin_complete_pair_axis')
    count = len(expected)
    if type(bins['n_pairs']) is not int or bins['n_pairs'] != count:
        raise ValueError('bin_pair_count')
    short, long = np.asarray(bins['short_range']), np.asarray(bins['long_range'])
    if (short.dtype.kind != 'b' or long.dtype.kind != 'b' or
            short.shape != (count,) or long.shape != (count,) or np.any(short & long)):
        raise ValueError('bin_membership')
    thresholds = [bins['q1_mm'], bins['q2_mm']]
    if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating))
           or not math.isfinite(float(value)) or value < 0 for value in thresholds):
        raise ValueError('bin_quantiles')
    q1, q2 = map(float, thresholds)
    if q1 > q2:
        raise ValueError('bin_quantile_order')
    digest = hashlib.sha256(b'DEVCONN_distance_bins_v2\n' +
        b'\0'.join(value.encode('utf-8') for value in ids) + b'\n' +
        np.asarray(pairs, dtype='<i8', order='C').tobytes(order='C') +
        np.column_stack((short, long)).astype('u1').tobytes(order='C')).hexdigest()
    return dict(q1_mm=q1, q2_mm=q2, n_pairs=count,
                n_short_edges=int(short.sum()), n_long_edges=int(long.sum()),
                membership_sha256=digest)
