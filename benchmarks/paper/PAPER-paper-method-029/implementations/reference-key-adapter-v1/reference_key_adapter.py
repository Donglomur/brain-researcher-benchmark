"""Author-exact reference key operations on caller-typed pandas frames.

No CSV I/O, join execution, prediction/scoring, normalization or silent repair.
See SOURCE_CONTRACT.md for the verified operations and stricter admission guards.
"""
from dataclasses import dataclass
import math
import numbers
import warnings

import numpy as np
import pandas as pd

AUTHOR_COMMIT = "edbff02edd6a08d3c6c829af45a957fd14bdc460"
AUTHOR_SOURCE_SHA256 = "638811c8038d1c0d43e03577d7ddd2243eb2bf9c5b061412288add7e51fd8566"
AUTHOR_GIT_BLOB = "27f1255c19db57380877250badddc38f64148578"
MAX_ROWS = 1000000
MAX_KEY_TEXT = 1024


class ReferenceKeyError(ValueError):
    """Reference keys cannot be admitted without guessing or silent repair."""


def _need(ok, message):
    if not ok:
        raise ReferenceKeyError(message)


@dataclass(frozen=True)
class ReferenceKey:
    identifier: str
    subject: str
    roi: str
    index_text: str
    row_position: int

    @property
    def components(self):
        return self.subject, self.roi, self.index_text


@dataclass(frozen=True)
class ReferencePair:
    key: ReferenceKey
    ceiling_position: int
    threshold_position: int


def _index_finite(series, integer_cast):
    """Admission check only: retain the original values/dtype for author operations."""
    for value in series.values:
        _need(not isinstance(value, (bool, np.bool_)), 'boolean feature index refused')
        _need(isinstance(value, (str, numbers.Real, np.integer, np.floating)),
              'unsupported or missing feature scalar')
        try:
            numeric = float(value)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ReferenceKeyError('nonnumeric feature index') from exc
        _need(math.isfinite(numeric), 'nonfinite feature index')
        if integer_cast and not isinstance(value, str):
            bound = 2 ** (np.dtype(int).itemsize * 8 - 1)
            # Prevent unsafe NumPy integer wrapping; strings retain astype(int)'s
            # own parsing/refusal behavior, rather than using int(float(text)).
            _need(-bound <= value < bound, 'feature outside native integer cast range')


def reference_keys(frame, *, axis, role):
    """Return exact author identifiers plus collision-checkable components.

    frame must already have the caller's reviewed pd.read_csv-equivalent dtypes.
    role is 'ceiling' or 'threshold'. Original input frames remain unchanged.
    """
    _need(type(frame) is pd.DataFrame, 'plain pandas DataFrame required')
    _need(axis in ('pattern', 'profile'), 'unknown reference axis')
    _need(role in ('ceiling', 'threshold'), 'unknown reference role')
    _need(0 < len(frame) <= MAX_ROWS, 'empty or oversized reference frame')
    _need(frame.columns.is_unique, 'duplicate column names')
    feature = 'Image index' if axis == 'pattern' else 'Vox_idx'
    value_column = 'Correlation' if role == 'ceiling' else 'Threshold 1'
    required = ('Subject', 'ROI', feature, value_column)
    _need(all(name in frame.columns for name in required), 'missing reference column')
    for name in ('Subject', 'ROI'):
        _need(all(isinstance(value, str) and 0 < len(value) <= MAX_KEY_TEXT
                  for value in frame[name].values), 'missing/nontext/oversized key component')
    values = frame[value_column].to_numpy()
    _need(values.dtype.kind in 'iuf' and bool(np.isfinite(values).all()),
          'nonfinite or nonnumeric reference value')
    _index_finite(frame[feature], integer_cast=(axis == 'pattern'))
    work = frame.copy(deep=True)
    try:
        if axis == 'pattern':
            if role == 'ceiling':
                work['Subject'] = work['Subject'].str.replace('-', '')
            with warnings.catch_warnings():
                warnings.simplefilter('error', RuntimeWarning)
                work['Image index'] = work['Image index'].astype(int)
        # Profile references deliberately have NO integer cast here.
        index_text = work[feature].values.astype(str)
        identifiers = work['Subject'].values + work['ROI'].values + index_text
    except (ValueError, TypeError, OverflowError, RuntimeWarning) as exc:
        raise ReferenceKeyError('author reference cast/concatenation failed') from exc
    keys, seen = [], {}
    for position, (subject, roi, index, identifier) in enumerate(zip(
            work['Subject'].values, work['ROI'].values, index_text, identifiers)):
        _need(bool(subject) and 0 < len(index) <= MAX_KEY_TEXT,
              'empty/oversized transformed key component')
        key = ReferenceKey(str(identifier), str(subject), str(roi), str(index), position)
        previous = seen.get(key.identifier)
        if previous is not None:
            if previous.components != key.components:
                raise ReferenceKeyError('canonical identifier collision within reference table')
            raise ReferenceKeyError('duplicate canonical reference key')
        seen[key.identifier] = key
        keys.append(key)
    return tuple(keys)


def align_reference_keys(ceiling, threshold, *, axis):
    """Strict one-to-one positional alignment; no author join or metric is executed.

    This refuses missing/extra keys and concatenation collisions instead of the
    author's permissive left join. Result order follows ceiling row order.
    """
    left = reference_keys(ceiling, axis=axis, role='ceiling')
    right = reference_keys(threshold, axis=axis, role='threshold')
    lookup = {key.identifier: key for key in right}
    for key in left:
        other = lookup.get(key.identifier)
        if other is not None and other.components != key.components:
            raise ReferenceKeyError('canonical identifier collision across reference tables')
    _need({key.identifier for key in left} == set(lookup),
          'missing/extra canonical reference keys')
    return tuple(ReferencePair(key, key.row_position, lookup[key.identifier].row_position)
                 for key in left)
