"""Lossless post-prediction observation text and complete32 response collection.

This module accepts already admitted observed inputs. It neither opens neural
files nor grants authority to release protected QUERY counts. The original host
must finish protected prediction/scoring before invoking it.
"""
from dataclasses import dataclass
import hashlib
from itertools import combinations
import json
import math

AREAS = ('VISp', 'VISl', 'VISal', 'VISrl', 'VISam', 'VISpm')
PAIRS = tuple(a + '|' + b for a, b in combinations(AREAS, 2))
MODES = ('running', 'pupil')
ARMS = ('restricted_observation', 'program_from_text')
META_FIELDS = {'schema', 'task_id', 'session_id', 'mouse_id', 'unit_ids',
               'areas', 'unit_metadata', 'rows', 'baseline_rates', 'support',
               'exposure_seconds', 'state_policy'}
PROTOCOL = {
    'kind': 'protocol', 'task_id': 'NEURAL-092',
    'scope': 'Later observed association reconstruction after protected prediction closure.',
    'units': 'QUERY counts are integer spikes in the original 1.9 second window; FIT baseline is spikes/second.',
    'pairing': 'Within QUERY, match exact condition_key and block and other state bin. Sort each side by (onset,id), zip once, never reuse.',
    'running': 'RUN minus REST within pupil LOW/MID/HIGH/MISSING; exclude TRANSITION/MISSING running.',
    'pupil': 'HIGH minus LOW within REST/RUN; exclude MID/MISSING pupil and other running states.',
    'effect': 'For each unit mean paired (high count/1.9 - low count/1.9) divided by its positive FIT baseline; equal unit mean per area. No pairs or absent area means null.',
    'matched': 'For each of all15 area pairs, bin FITbaseline by [1,2,4,8,16,32,64], presence_ratio by [.97,.99], isi_violations by [.1,.3], amplitude_cutoff by [.05]. Exact boundary enters next bin. Within each bin sort units by SHA256(UTF8 unit_id), then unit_id, retain minimum count on each side; subtract first area mean minus second.',
    'response': 'Return both modes, all six areas and all15 matched pairs; explicit null for unsupported contrasts. No expected biological sign. Pupil is a separate full32 endpoint.',
    'interpretation': 'Observed numerical reconstruction, not a causal effect, protected prediction score, or broad scientific reasoning grade.',
}


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(',', ':'), allow_nan=False).encode('ascii')


def decode(raw):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite JSON number')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Delivery:
    """Immutable byte payload shared without additions by both access arms."""
    manifest: bytes
    pages: tuple

    def read_page(self, index):
        if type(index) is not int or not 0 <= index < len(self.pages):
            raise ValueError('declared page index required')
        return self.pages[index]


def render_panel(metadata, counts, expected_session_to_mouse, *,
                 max_page_bytes, max_total_bytes, count_chunk_units=32):
    """Project every source metadata field and every QUERY count, without answers.

    The expected map must come from the caller's authenticated original roster;
    accepting a map here does not authenticate it. Capacity limits are selected
    prospectively. Any oversize record/panel fails; there is no truncation.
    """
    expected = expected_session_to_mouse
    if (type(expected) is not dict or len(expected) != 32
            or any(type(k) is not str or not k or type(v) is not str or not v
                   for k, v in expected.items()) or len(set(expected.values())) != 32
            or set(metadata) != set(expected) or set(counts) != set(expected)):
        raise ValueError('exact original32 distinct mouse/session panel required')
    if (type(max_page_bytes) is not int or type(max_total_bytes) is not int
            or not 1 <= max_page_bytes <= max_total_bytes
            or type(count_chunk_units) is not int or count_chunk_units < 1):
        raise ValueError('positive prospective delivery bounds required')
    pages = []
    current = bytearray()
    total = 0
    records = 0
    census = []

    def add(record):
        nonlocal current, total, records
        raw = encode(record) + b'\n'
        if len(raw) > max_page_bytes or total + len(raw) > max_total_bytes:
            raise ValueError('complete observation exceeds selected capacity; no truncation')
        if len(current) + len(raw) > max_page_bytes:
            pages.append(bytes(current))
            current = bytearray()
        current.extend(raw)
        total += len(raw)
        records += 1

    add(PROTOCOL)
    for sid, mouse in expected.items():
        meta = metadata[sid]
        if (type(meta) is not dict or set(meta) != META_FIELDS
                or meta['schema'] != 'neuropixels_session_v1'
                or meta['task_id'] != 'NEURAL-092' or meta['session_id'] != sid
                or meta['mouse_id'] != mouse or meta['exposure_seconds'] != 1.9):
            raise ValueError('original observed metadata identity/exposure required')
        ids = meta['unit_ids']
        if (type(ids) is not list or not ids or len(set(ids)) != len(ids)
                or any(type(uid) is not str or not uid for uid in ids)
                or any(len(meta[k]) != len(ids) for k in
                       ('areas', 'unit_metadata', 'baseline_rates'))):
            raise ValueError('complete original unit axes required')
        rows = meta['rows']
        if (type(rows) is not list or not rows
                or len({r['id'] for r in rows}) != len(rows)
                or {r['split'] for r in rows} != {'FIT', 'VALIDATION', 'QUERY'}):
            raise ValueError('complete original trial axes required')
        query = [r for r in rows if r['split'] == 'QUERY']
        plane = counts[sid]
        if type(plane) is not list or len(plane) != len(query):
            raise ValueError('complete QUERY count rows required')
        add({'kind': 'session', 'session_id': sid, 'metadata': {
            k: v for k, v in meta.items()
            if k not in {'unit_ids', 'areas', 'unit_metadata', 'baseline_rates', 'rows'}}})
        for index, uid in enumerate(ids):
            baseline = meta['baseline_rates'][index]
            unit = meta['unit_metadata'][index]
            if (meta['areas'][index] not in AREAS or unit['unit_id'] != uid
                    or unit['area'] != meta['areas'][index]
                    or type(baseline) not in (float, int)
                    or not math.isfinite(baseline) or baseline <= 0):
                raise ValueError('original unit join/positive FIT baseline required')
            add({'kind': 'unit', 'session_id': sid, 'index': index,
                 'unit_id': uid, 'area': meta['areas'][index],
                 'baseline_rate': baseline, 'unit_metadata': unit})
        for index, row in enumerate(rows):
            add({'kind': 'trial', 'session_id': sid, 'index': index, 'row': row})
        for index, (row, values) in enumerate(zip(query, plane)):
            if (type(values) is not list or len(values) != len(ids)
                    or any(type(v) is not int or not 0 <= v < 2**63 for v in values)):
                raise ValueError('complete nonnegative int64 QUERY count plane required')
            for start in range(0, len(ids), count_chunk_units):
                stop = start + count_chunk_units
                add({'kind': 'counts', 'session_id': sid, 'query_index': index,
                     'query_id': row['id'], 'unit_start': start,
                     'unit_ids': ids[start:stop], 'counts': values[start:stop]})
        census.append({'session_id': sid, 'mouse_id': mouse,
                       'units': len(ids), 'query_rows': len(query),
                       'count_cells': len(ids) * len(query)})
    if current:
        pages.append(bytes(current))
    manifest = {'schema': 'neural092_observed_text_v1', 'task_id': 'NEURAL-092',
                'scope': 'post_prediction_observed_reconstruction', 'sessions': census,
                'pages': [{'index': i, 'bytes': len(raw), 'sha256': sha(raw)}
                          for i, raw in enumerate(pages)],
                'observation_sha256': sha(b''.join(pages)),
                'text_bytes': total, 'record_count': records,
                'max_page_bytes': max_page_bytes, 'max_total_bytes': max_total_bytes,
                'same_information_arms': list(ARMS),
                'host_barrier_or_no_tools_enforced': False, 'qualified': False}
    manifest_raw = encode(manifest)
    if total + len(manifest_raw) > max_total_bytes:
        raise ValueError('complete manifest plus observation exceeds selected capacity')
    return Delivery(manifest_raw, tuple(pages))


def collect_responses(delivery, arm, raw_responses, *, max_response_bytes):
    """Admit complete responses before calling the unchanged original scorer.

    Returns original scorer submission bytes and a transport receipt. No target
    recomputation, score, feedback, fallback answer, or successful subset exists.
    """
    if arm not in ARMS or type(max_response_bytes) is not int or max_response_bytes < 1:
        raise ValueError('declared arm and positive response cap required')
    manifest = decode(delivery.manifest)
    if (manifest['schema'] != 'neural092_observed_text_v1'
            or len(delivery.pages) != len(manifest['pages'])
            or any(d != {'index': i, 'bytes': len(raw), 'sha256': sha(raw)}
                   for i, (d, raw) in enumerate(zip(manifest['pages'], delivery.pages)))
            or sha(b''.join(delivery.pages)) != manifest['observation_sha256']):
        raise ValueError('complete original observation bytes required')
    expected = [r['session_id'] for r in manifest['sessions']]
    if len(expected) != 32 or len(set(expected)) != 32:
        raise ValueError('complete32 observation census required')
    if type(raw_responses) is not bytes or len(raw_responses) > max_response_bytes:
        raise ValueError('bounded captured response bytes required')
    response = decode(raw_responses)
    if (set(response) != {'arm', 'observation_sha256', 'sessions'}
            or response['arm'] != arm
            or response['observation_sha256'] != manifest['observation_sha256']
            or type(response['sessions']) is not dict
            or set(response['sessions']) != set(expected)):
        raise ValueError('same observation and complete32 response required')
    for modes in response['sessions'].values():
        if type(modes) is not dict or set(modes) != set(MODES):
            raise ValueError('both separate state modes required')
        for value in modes.values():
            if (type(value) is not dict or set(value) != {'areas', 'matched'}
                    or type(value['areas']) is not dict or set(value['areas']) != set(AREAS)
                    or type(value['matched']) is not dict or set(value['matched']) != set(PAIRS)):
                raise ValueError('all six areas and fifteen matched pairs required')
            for number in list(value['areas'].values()) + list(value['matched'].values()):
                if number is not None and (type(number) not in (int, float)
                                           or not math.isfinite(number)):
                    raise ValueError('finite signed effects or explicit null required')
    submission = encode({'schema': 'neuropixels_state_submission_v1',
                         'task_id': 'NEURAL-092', 'sessions': response['sessions']})
    receipt = {'arm': arm, 'observation_sha256': manifest['observation_sha256'],
               'submission_sha256': sha(submission), 'session_count': 32,
               'endpoint': 'later_observed_reconstruction',
               'score_computed': False, 'no_tools_enforced': False, 'qualified': False}
    return submission, receipt
