"""Read-only content audit of the exact accepted PFC participant packet.

No download, copying, fitting, scoring or publication. This audits the complete
declared input boundary; license/attribution and release selection remain the
operator's separate, evidence-backed decision. Opaque IDs are not a claim of
anonymization. Run only under the selected provisioning read/resource budget.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

PACKET_BYTES = 5368996
PACKET_SHA256 = '8f6dc8ffff5e6ab4aa3be41dd3e9b0847c829b345142204d154124847908b21e'
FAMILIES = tuple('/'.join((r, p, s)) for r in ('gaoRois', 'dataRois')
                 for p in ('refall', 'refPFC') for s in ('nolays', 'lays', 'laydepth'))
CONTEXTS = tuple('/'.join((r, p, s)) for r in ('gaoRois', 'dataRois')
                 for p in ('refall', 'refPFC')
                 for s in ('deepRois', 'nolayRois', 'layeredRois', 'deepSupRois'))
TASKS = {'Passive', 'Aversion', 'Detection', 'Context', 'Attention'}
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
UUID4 = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
LABEL = re.compile(r'[A-Za-z0-9_ .|()+-]{1,256}\Z')
DIAGNOSTIC_TEXT = ('Accepted historical diagnostic remains inherited; neither its author values '
                   'nor named current reconstruction are biological ground truth.')


class Refusal(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Refusal(message)


def keys(value, expected, where):
    need(type(value) is dict and set(value) == set(expected), where + ': exact keys')


def hashed_id(value):
    return type(value) is str and HEX64.fullmatch(value) is not None


def no_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value, 'duplicate JSON key')
        value[key] = item
    return value


def reject_constant(value):
    raise Refusal('nonfinite JSON constant: ' + value)


def decode(body):
    return json.loads(body.decode('utf-8'), object_pairs_hook=no_duplicate_keys,
                      parse_constant=reject_constant)


def read_exact(path, expected_bytes, expected_sha256):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute ordinary path required')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink path refused')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'ordinary single-link file required')
    need(before.st_size == expected_bytes, 'packet size mismatch')
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        need(stamp(before) == stamp(os.fstat(fd)), 'file changed before read')
        chunks = []
        remaining = expected_bytes
        digest = hashlib.sha256()
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            need(bool(chunk), 'truncated packet')
            chunks.append(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
        need(os.read(fd, 1) == b'', 'packet grew')
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()), 'file changed during read')
        need(digest.hexdigest() == expected_sha256, 'packet digest mismatch')
        return b''.join(chunks)
    finally:
        os.close(fd)


def inspect_content(packet):
    keys(packet, ('schema', 'units', 'families', 'contexts', 'animals', 'records', 'historical_diagnostics'), 'packet')
    need(packet['schema'] == 'PFC_FULL99_FIXED_MAP_PACKET_V1', 'packet schema')
    units, families, contexts = packet['units'], packet['families'], packet['contexts']
    animals, records = packet['animals'], packet['records']
    need(type(units) is list and len(units) == 19186, 'complete fitting-unit support')
    need(type(families) is list and len(families) == 12, 'complete family support')
    need(type(contexts) is list and len(contexts) == 16, 'complete context support')
    need(type(animals) is list and len(animals) == 68 and all(hashed_id(a) for a in animals), 'animal IDs')
    need(animals == sorted(set(animals)), 'unique sorted animal roster')
    need(type(records) is list and len(records) == 99, 'complete recording support')
    roster = {}
    for record in records:
        keys(record, ('id', 'animal', 'task'), 'record')
        need(hashed_id(record['id']) and hashed_id(record['animal']), 'record identity format')
        need(record['animal'] in animals and type(record['task']) is str and record['task'] in TASKS, 'record animal/task')
        need(record['id'] not in roster, 'duplicate recording')
        roster[record['id']] = (record['animal'], record['task'])
    for family, expected_key in zip(families, FAMILIES):
        keys(family, ('key', 'labels'), 'family')
        need(family['key'] == expected_key, 'family order')
        labels = family['labels']
        need(type(labels) is list and bool(labels) and
             all(type(s) is str and LABEL.fullmatch(s) is not None for s in labels), 'finite anatomical label grammar')
        need(labels == sorted(set(labels)), 'unique lexical family labels')
    ids, seen_animals = set(), set()
    for unit in units:
        keys(unit, ('id', 'recording', 'animal', 'task', 'category', 'labels'), 'unit')
        need(type(unit['id']) is str and UUID4.fullmatch(unit['id']) is not None, 'saved UUID4 unit ID')
        need(unit['id'] not in ids, 'duplicate unit')
        ids.add(unit['id'])
        need(hashed_id(unit['recording']) and hashed_id(unit['animal']), 'unit group identity')
        need(type(unit['task']) is str and unit['task'] in TASKS and
             roster.get(unit['recording']) == (unit['animal'], unit['task']), 'unit joins record')
        seen_animals.add(unit['animal'])
        need(type(unit['category']) is int and 0 <= unit['category'] < 8, 'category coordinate')
        labels = unit['labels']
        need(type(labels) is list and len(labels) == 12, 'all membership slots')
        for slot, label in enumerate(labels):
            need(type(label) is int and -1 <= label < len(families[slot]['labels']), 'membership coordinate')
            need(label >= 0 or '/refPFC/' in FAMILIES[slot], 'full reference cannot omit a unit')
    need(sorted(seen_animals) == animals, 'complete fitting-animal roster')
    hierarchy_contexts = 0
    encodings = {'deepRois': 'laydepth', 'nolayRois': 'nolays', 'layeredRois': 'lays', 'deepSupRois': 'laydepth'}
    for context, expected_key in zip(contexts, CONTEXTS):
        keys(context, ('key', 'family', 'indices', 'hierarchy'), 'context')
        need(context['key'] == expected_key, 'context order')
        route, ref, subset = expected_key.split('/')
        expected_family = FAMILIES.index('/'.join((route, ref, encodings[subset])))
        need(type(context['family']) is int and context['family'] == expected_family, 'context parent family')
        indices = context['indices']
        need(type(indices) is list and bool(indices) and all(type(i) is int for i in indices), 'context indices')
        need(indices == sorted(set(indices)) and all(0 <= i < len(families[expected_family]['labels']) for i in indices), 'context coordinate range')
        should_have_hierarchy = route == 'gaoRois' and subset in ('deepRois', 'nolayRois')
        h = context['hierarchy']
        if should_have_hierarchy:
            hierarchy_contexts += 1
            need(type(h) is list and len(h) == len(indices), 'complete hierarchy coordinates')
            need(all((type(v) in (int, float) and math.isfinite(v)) or
                     (type(v) is str and v in ('NaN', '+Infinity', '-Infinity')) for v in h), 'hierarchy value domain')
        else:
            need(h is None, 'unexpected hierarchy')
    need(hierarchy_contexts == 4, 'all four Gao hierarchy contexts')
    d = packet['historical_diagnostics']
    keys(d, ('source_comparison_report', 'comparisons', 'shuffle_differences', 'dependent_roi_gao_differences',
             'unavailable_comparisons', 'logical_qe_difference', 'source_geometry_views', 'source_geometry_recomputed',
             'historical_equivalence', 'full_paper_reproduction', 'interpretation'), 'historical metadata')
    keys(d['source_comparison_report'], ('bytes', 'sha256'), 'owner-derived report descriptor')
    need(type(d['source_comparison_report']['bytes']) is int and d['source_comparison_report']['bytes'] > 0 and
         hashed_id(d['source_comparison_report']['sha256']), 'report identity without path or content')
    for name in ('comparisons', 'shuffle_differences', 'dependent_roi_gao_differences', 'unavailable_comparisons'):
        need(type(d[name]) is int and d[name] >= 0, 'finite diagnostic status count')
    need(type(d['source_geometry_views']) is int and d['source_geometry_views'] == 48, 'historical view count')
    need(d['logical_qe_difference'] == 'Separate and unchanged' and d['interpretation'] == DIAGNOSTIC_TEXT, 'exact public diagnostic prose')
    need(all(d[name] is False for name in ('source_geometry_recomputed', 'historical_equivalence', 'full_paper_reproduction')), 'historical scope flags')
    return {'content_boundary_passed': True, 'units': len(units), 'recordings': len(records),
            'animals': len(animals), 'families': len(families), 'contexts': len(contexts),
            'protected_answer_fields_present': False, 'owner_derived_report_digest_present': True,
            'opaque_ids_are_anonymization_guarantee': False}


def audit_packet(path):
    body = read_exact(path, PACKET_BYTES, PACKET_SHA256)
    result = inspect_content(decode(body))
    return {'schema': 'pfc_exact_participant_packet_content_audit_v1', **result,
            'packet_bytes': PACKET_BYTES, 'packet_sha256': PACKET_SHA256,
            'explicit_packet_bytes_read': PACKET_BYTES + 1, 'data_copied_or_exported': False,
            'license_or_publication_decision': False, 'model_fits': 0, 'scientific_reference_recomputed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_packet(args.packet), sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
