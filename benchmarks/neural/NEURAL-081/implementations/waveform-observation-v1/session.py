"""Complete permitted demonstrations and one query, using the fixed renderer.

This is a host-side projection, not source eligibility, transport, or isolation.
The host supplies the same complete training rows as the program context and
must deliver only serialized responses, never this object or its private loader.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import observation


def _alias(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ValueError('Opaque lowercase 32-hex row/group alias required')
    return value


@dataclass(frozen=True)
class _TrainingRow:
    row_alias: str
    group_alias: str
    label: int
    npy_sha256: str


class Session:
    """Private host object; public methods expose pixels and allowed labels only."""

    def __init__(self, query, rows, load_training_window):
        self._query = query
        self._rows = rows
        self._by_alias = {row.row_alias: row for row in rows}
        self._load_training_window = load_training_window

    def metadata(self):
        """Complete public support without opening any training waveform."""
        return {
            'schema': 'neural081_observation_session_v1',
            'query': self._query.metadata(),
            'training_count': len(self._rows), 'training_group_count': 9,
            'training': [
                {'row_alias': row.row_alias, 'group_alias': row.group_alias,
                 'label': row.label} for row in self._rows
            ],
            'coverage': 'Every host-admitted training row, followed by one unlabeled query',
            'qualification': 'Source projection only; host eligibility and complete delivery required',
        }

    def _training_observation(self, row):
        try:
            payload = self._load_training_window(row.row_alias)
        except Exception:
            # A loader diagnostic can include a private source path. The host
            # retains its private error context; public callers get no detail.
            raise ValueError('Authorized training observation is unavailable') from None
        if (type(payload) is not bytes or len(payload) > 135180
                or hashlib.sha256(payload).hexdigest() != row.npy_sha256):
            raise ValueError('Training window differs from the admitted bytes')
        return observation.prepare_observation(
            payload, context_alias=row.row_alias, view=self._query.view)

    def page(self, action):
        """Only four fixed pages of an admitted training row or current query."""
        if (type(action) is not dict or set(action) != {'action', 'row_alias', 'page'}
                or action['action'] != 'view_page'
                or type(action['page']) is not int or not 0 <= action['page'] < 4):
            raise ValueError('Only view_page with row_alias and integer page 0..3 is permitted')
        alias = _alias(action['row_alias'])
        request = {'action': 'view_page', 'page': action['page']}
        if alias == self._query.context_alias:
            return {'role': 'query', 'row_alias': alias, 'image': self._query.page(request)}
        row = self._by_alias.get(alias)
        if row is None:
            raise ValueError('Only the complete training roster or current query is available')
        rendered = self._training_observation(row)
        return {'role': 'training', 'row_alias': alias, 'group_alias': row.group_alias,
                'label': row.label, 'image': rendered.page(request)}

    def direct_packets(self):
        """Stream every complete labeled demonstration, then the unlabeled query.

        The host must finish this iterator and deliver every packet before
        admitting a direct prediction. A prefix is not a complete observation.
        No demonstration selection, sampling, or numerical reduction occurs.
        """
        for row in self._rows:
            yield {'role': 'training', 'row_alias': row.row_alias,
                   'group_alias': row.group_alias, 'label': row.label,
                   'observation': self._training_observation(row).direct()}
        yield {'role': 'query', 'row_alias': self._query.context_alias,
               'observation': self._query.direct()}


def prepare_session(query_npy, *, context_alias, view, training_rows,
                    expected_training_aliases, load_training_window):
    """Join complete program-context row order to pinned labeled demonstrations.

    ``expected_training_aliases`` comes independently from the complete admitted
    train_rows.json used by the matched program condition. ``training_rows`` has
    exactly row_alias, group_alias, label, and npy_sha256 per permitted row. The
    host binds each pin to the corresponding already prepared authorized window.
    This validates the supplied roster; it cannot authenticate source provenance
    or discover omitted source rows if the host supplies two incomplete inputs.
    """
    alias = _alias(context_alias)
    if (type(expected_training_aliases) is not list
            or not 108 <= len(expected_training_aliases) <= 90000):
        raise ValueError('Complete nine-person training alias list required')
    expected = tuple(_alias(value) for value in expected_training_aliases)
    if len(set(expected)) != len(expected) or alias in expected:
        raise ValueError('Training aliases must be unique and exclude the query')
    if type(training_rows) is not list or len(training_rows) != len(expected):
        raise ValueError('Every expected training row is required')
    if not callable(load_training_window):
        raise ValueError('Private authorized training-window loader required')
    rows, groups = [], {}
    for wanted, item in zip(expected, training_rows):
        if (type(item) is not dict
                or set(item) != {'row_alias', 'group_alias', 'label', 'npy_sha256'}):
            raise ValueError('Exact permitted training metadata required')
        row_alias, group_alias = _alias(item['row_alias']), _alias(item['group_alias'])
        label, digest = item['label'], item['npy_sha256']
        if row_alias != wanted:
            raise ValueError('Training order and support must match the program context')
        if type(label) is not int or label not in observation.CLASS_IDS:
            raise ValueError('Canonical nonconsecutive instructed-excerpt label required')
        if type(digest) is not str or re.fullmatch('[0-9a-f]{64}', digest) is None:
            raise ValueError('Exact prepared training-window SHA256 required')
        rows.append(_TrainingRow(row_alias, group_alias, label, digest))
        groups.setdefault(group_alias, set()).add(label)
    if len(groups) != 9 or any(labels != set(observation.CLASS_IDS) for labels in groups.values()):
        raise ValueError('All twelve classes in each of nine permitted training groups required')
    # Capture detached immutable metadata before opening any query waveform.
    query = observation.prepare_observation(query_npy, context_alias=alias, view=view)
    return Session(query, tuple(rows), load_training_window)
