"""Explicit operator-only full32 adapter for the unchanged image viewer.

Never provide this dataset, its roster, records, or PacketSession to a participant.
The participant boundary is viewer.Session.handle and the maintained transport:
the same four labelled demonstration images and one query image, with bounded
actions. This module does not render, preprocess, call models, or score.
"""
from __future__ import annotations

import hashlib
import json
import re
import types

PROFILE = 'erp-full32-visual-v1'
CONDITIONS = ('visual_direct_four_demo', 'visual_program_four_demo')
QUERY_COUNT = 6400
MODE = 'four_demo'
# This descriptor is static policy, not a packet or participant commitment.
# No source location, query roster, person grouping, or test prior belongs here.
DISPLAY_SPEC = {
    'schema': 'neural077_full32_visual_display_v1',
    'profile': PROFILE,
    'conditions': list(CONDITIONS),
    'mode': MODE,
    'demonstrations': 4,
    'channels': ['Cz', 'Pz'],
    'samples': 1024,
    'sampling_hz': 1024,
    'epoch_offsets_half_open': [-256, 768],
    'units': 'native stored EEG amplitude; calibration unresolved',
    'physical_display_delay': 'unresolved',
    'renderer': {'bytes': 8179, 'sha256': 'b8cc040978a38104a9adc7747748411e4abe61aa9df9c5a6cdd3c00902dd2a18'},
    'encoding': {
        'policy': 'lossless full32 PNG compression after unchanged raster rendering',
        'codec_implementation': 'visual-provider-pair-v1/transfer_png.py',
        'codec': {'bytes': 3327, 'sha256': '2edae69f982d71b2a27944c82f25199b2d1f11a7272449bbea84fa35ec762f95'},
        'compression_level': 9,
        'pixel_change': False,
        'filter_change': False,
        'runtime_identity': 'zlib compile/runtime versions retained in operator action descriptor',
        'cross_runtime_encoded_byte_stability': 'not claimed; audit verifies exact decoded scanlines',
    },
    'actions': ['inspect', 'select', 'window', 'scroll', 'zoom', 'gain', 'channels', 'finalize'],
    'gains': [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000],
    'maximum_actions': 128,
    'response': 'first finalize terminal, including invalid scalar',
    'participant_records': 'four labelled demonstration images and one unlabelled query image only',
}
PROFILE_COMMITMENT = hashlib.sha256(
    (json.dumps(DISPLAY_SPEC, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
).hexdigest()


def need(ok, message):
    if not ok:
        raise ValueError(message)


class QueryRows:
    """One-record cache over an authenticated operator index; no eager arrays."""
    def __init__(self, session):
        self.session = session
        self.trial_ids = session.trial_ids
        self._ordinal = None
        self._record = None

    def __len__(self):
        return len(self.trial_ids)

    def __getitem__(self, ordinal):
        need(type(ordinal) is int and 0 <= ordinal < len(self), 'Exact in-range query ordinal')
        need(not self.session._closed, 'Packet session closed')
        if ordinal != self._ordinal:
            record = self.session.query_record(self.trial_ids[ordinal])
            self._ordinal, self._record = ordinal, record
        return self._record

    def clear(self):
        self._ordinal, self._record = None, None


class ResponseParser:
    def __init__(self, consumer):
        self.consumer = consumer

    def parse(self, raw, trial_id):
        need(type(raw) is bytes, 'Exact response bytes')
        return self.consumer.parse_response(raw.decode('utf-8'), trial_id)


class SubmissionValidator:
    """Bind only full32 roster/dtype admission around the unchanged legacy kernel."""
    def __init__(self, validator):
        need(isinstance(validator, types.ModuleType), 'Trusted loaded validator module required')
        names = ('validate', '_public_ids', '_read_candidate')
        need(all(isinstance(getattr(validator, name, None), types.FunctionType) and
                 getattr(validator, name).__globals__ is validator.__dict__ for name in names),
             'Original validator functions and globals required')
        self.validator = validator
        self._donor = dict(validator.__dict__)
        self._code = {name: self._donor[name].__code__ for name in names}
        original_read = self._donor['_read_candidate']

        def public_ids(ordered_ids):
            validator.require(type(ordered_ids) in (list, tuple) and len(ordered_ids) == QUERY_COUNT,
                              'Exactly 6400 expected opaque IDs required')
            ids = list(ordered_ids)
            validator.require(all(type(x) is str and re.fullmatch(r'q-[0-9a-f]{32}', x) for x in ids)
                              and ids == sorted(set(ids)), 'Sorted unique full32 opaque roster required')
            return {'public_roster': ids}, ids

        def read_candidate(path, count):
            candidate = original_read(path, count)  # Original bounded ZIP/NPY preflight and loader.
            validator.require(candidate['trial_ids'].dtype.str == '<U34',
                              'Exact little-endian U34 full32 opaque IDs required')
            return candidate

        namespace = dict(self._donor)
        namespace.update(_public_ids=public_ids, _read_candidate=read_candidate)
        original = self._donor['validate']
        self._validate = types.FunctionType(original.__code__, namespace, original.__name__,
                                            original.__defaults__, original.__closure__)
        self._unchanged()

    def _unchanged(self):
        need(self.validator.__dict__.keys() == self._donor.keys() and
             all(self.validator.__dict__[key] is value for key, value in self._donor.items()) and
             all(self._donor[name].__code__ is code for name, code in self._code.items()),
             'Original validator namespace/code changed')

    def validate(self, path, ordered_ids):
        self._unchanged()
        try:
            return self._validate(path, ordered_ids)['public_roster']
        finally:
            self._unchanged()


def source(packet, manifest_pin, consumer, validator, budget=None):
    """Authenticate public metadata and the four demos; queries remain lazy."""
    session = consumer.PacketSession(packet, manifest_pin, budget=budget)
    try:
        need(len(session.trial_ids) == QUERY_COUNT, 'Complete full32 roster required')
        demos = session.demonstration_records()
        rows = QueryRows(session)
        return {
            'profile': PROFILE,
            'profile_commitment': PROFILE_COMMITMENT,
            'rows': rows,
            'trial_ids': session.trial_ids,
            'roster': tuple({'ordinal': i, 'trial_id': trial_id}
                            for i, trial_id in enumerate(session.trial_ids)),
            'demos': demos,
            'parser': ResponseParser(consumer),
            'validator': SubmissionValidator(validator),
            'manifest_pin': dict(session.manifest_pin),
            'packet': {'PACKET.json': session.manifest_pin['sha256'],
                       'demonstrations.json': consumer.LEGACY_PINS['demonstrations.json']['sha256']},
            '_session': session,
            '_budget': budget,
        }
    except BaseException:
        session.close()
        raise


def close(dataset):
    dataset['rows'].clear()
    dataset['_session'].close()
