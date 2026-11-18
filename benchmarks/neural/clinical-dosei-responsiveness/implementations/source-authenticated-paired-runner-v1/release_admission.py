"""Pure role-bound metadata admission. No files, arrays, models or scores opened.

The trusted host supplies complete immutable artifact bodies. Production roots
are fixed to the accepted release; hashes supplied by participants are never
authority. Generated admission is explicitly a different, non-authentic scope.
Historical closure is inherited from the accepted evidence, not a current
filesystem inventory. The existing projector checks current array identities.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

CASES = 7345
RECORDINGS = 171
CONDITION = 'native_marker_relative_30s_v1'
MAX_METADATA = 32 * 1024**2
PINS = {
    'cohort': 'cfb8f868825ac910114f3ccbfa2cd3b0a865ea05d76a2f23d99afba4d3305207',
    'success': 'b7e23a40b61fcb1622459c621116546c5717aed958910118fa58f1f9f4cb8650',
    'observations': '11d3a466e88c0ce6ed08ea8e487c7a8b23327019fe3215881b8f82bcd78021b4',
    'index_manifest': '67a4b89d123e3421f0ba63a17f22d5b9a6abde81419ef77e8e27104f6d59b838',
    'index_cases': 'af97ed83714d6ce362b3f3303acd4a1c60ebc5dba113e651da9e26c9d331cd78',
    'key': '6a73374a648c7e0ee054207a6b17e62b8d887679591f4ba211518d637a75c775',
    'numeric_cohort': '1faf6f9c9d1b5c202c8d80a86fb779c50040f4ca94ab2e6b660984335464a2ed',
    'numeric_proof': 'f83503c5a6031c9043579b84bd48ae6925ceb9ace491c2c9abf1198fe00bd202',
    'accepted_observation_evidence': '89509823b7cf570d7813868e737db16c7474972314d673fbf0284cad97bf396c',
}
CAPS = {'cohort': 524288, 'success': 131072, 'observations': 7521280,
        'index_manifest': 524288, 'index_cases': 15042560, 'key': 32,
        'numeric_cohort': 131072, 'numeric_proof': 262144,
        'accepted_observation_evidence': 65536}
OBS_FIELDS = {'schema', 'public_position', 'case_id', 'observation_sha256',
    'observation_bytes', 'default_png_sha256', 'default_png_bytes', 'source_rows',
    'coverage', 'channel_counts', 'projection_receipt_sha256', 'array_identity_binding_sha256'}


class AdmissionRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise AdmissionRefusal(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def binding(raw):
    return {'bytes': len(raw), 'sha256': sha(raw)}


def hash_string(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'exact digest required')
    return value


def integer(value, high=2**63-1):
    require(type(value) is int and 0 <= value <= high, 'bounded exact integer required')
    return value


def decode(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def finite(text):
        value = float(text)
        require(math.isfinite(value), 'nonfinite JSON value')
        return value
    def constant(_):
        raise AdmissionRefusal('nonfinite JSON constant')
    try:
        return json.loads(raw.decode('ascii'), object_pairs_hook=pairs,
                          parse_float=finite, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise AdmissionRefusal('invalid complete JSON') from exc


def same(left, right, message):
    require(canonical(left) == canonical(right), message)


def bound_body(raw, declared):
    require(type(declared) is dict and type(declared.get('path')) is str,
            'role-specific artifact binding required')
    require(integer(declared['bytes']) == len(raw) and hash_string(declared['sha256']) == sha(raw),
            'artifact body differs from role binding')


def records(rows):
    require(type(rows) is list and len(rows) == RECORDINGS, 'all171 records required')
    out = {}
    for row in rows:
        rid = row['recording_id']
        require(type(rid) is str and re.fullmatch('[1-9][0-9]*', rid) and rid not in out,
                'unique exact recording required')
        out[rid] = row
    return out


def lines(raw, cap):
    require(raw.endswith(b'\n'), 'final canonical newline required')
    values = []
    for line in raw.splitlines(keepends=True):
        require(len(values) < CASES and 0 < len(line) <= cap and line.endswith(b'\n'),
                'bounded exact7345 JSONL rows required')
        value = decode(line)
        require(canonical(value)+b'\n' == line, 'canonical JSONL required')
        values.append(value)
    require(len(values) == CASES, 'complete7345 row population required')
    return values


class AdmittedRelease:
    """Private host state; never transport this object to a participant."""
    def __init__(self, *, scope, manifest, observations, indices, receipts, secret,
                 disclosure, root, source_bindings):
        self.scope = scope
        self.manifest = manifest
        self.observations = observations
        self.indices = indices
        self.receipts = receipts
        self.secret = secret
        self.disclosure = disclosure
        self.array_root = root
        self.source_bindings = source_bindings


def _admit(blobs, member_blobs, modules, pins, scope):
    require(type(blobs) is dict and set(blobs) == set(PINS) and
            type(member_blobs) is dict and len(member_blobs) == RECORDINGS, 'complete role bodies required')
    require(type(pins) is dict and set(pins) == set(PINS), 'exact role roots required')
    total = 0
    for role, raw in blobs.items():
        require(type(raw) is bytes and 0 < len(raw) <= CAPS[role] and
                sha(raw) == hash_string(pins[role]), 'bounded authenticated role differs: '+role)
        total += len(raw)
    for rid, raw in member_blobs.items():
        require(type(rid) is str and re.fullmatch('[1-9][0-9]*', rid) and
                type(raw) is bytes and 0 < len(raw) <= 131072, 'bounded member body required')
        total += len(raw)
    require(total <= MAX_METADATA and len(blobs['key']) == 32, 'aggregate metadata/key capacity')
    if scope == 'accepted_release_v2':
        require(len(blobs['index_cases']) == 7296877, 'accepted private case extent differs')
    values = {k: decode(v) for k, v in blobs.items() if k not in ('observations', 'index_cases', 'key')}
    c, s, im, nc, proof, acceptance = (values[k] for k in
        ('cohort', 'success', 'index_manifest', 'numeric_cohort', 'numeric_proof', 'accepted_observation_evidence'))
    require(c['schema'] == 'dosei_complete_paired_observations_v1' and c['status'] == 'complete'
            and c['condition'] == CONDITION and integer(c['cases']) == CASES and
            integer(c['recordings']) == RECORDINGS, 'complete accepted observation cohort')
    require(s['schema'] == 'dosei_complete_paired_success_v1' and s['status'] == 'succeeded'
            and integer(s['cases']) == CASES and integer(s['recordings']) == RECORDINGS
            and s['all_cases_rendered'] is True, 'complete observation success')
    same(c['execution_binding'], s['execution_binding'], 'observation execution differs')
    bound_body(blobs['cohort'], s['cohort'])
    for declared in (s['observations'], c['observations']):
        bound_body(blobs['observations'], declared)
    same(s['observations'], c['observations'], 'closed observation identities differ')
    require(c['canonical_public_order'] == 'ascending opaque HMAC case ID' and
            c['public_order_label_or_outcome_dependent'] is False and
            c['all_cases_and_both_workflows_share_disclosure'] is True and
            c['code_and_viewer_observation_hashes_matched'] is True and
            c['source_labels_exported'] is False and c['biological_person_mapping_verified'] is False and
            c['verified_pre_challenge_onset'] is False, 'accepted scientific condition changed')
    disclosure = canonical(c['common_workflow_disclosure'])
    same(c['common_workflow_disclosure'], modules['host'].DISCLOSURE, 'scientific disclosure differs')
    require(sha(disclosure) == c['common_workflow_disclosure_sha256'], 'disclosure binding differs')
    require(acceptance['schema'] == 'dosei_complete_paired_observation_evidence_v1' and
            acceptance['independent_saved_verification']['exit_code'] == 0 and
            type(acceptance['independent_saved_verification']['exit_code']) is int and
            acceptance['independent_saved_verification']['contradictory_failure_present'] is False and
            acceptance['independent_saved_verification']['all_case_rows_order_source_joins_counts_and_closed_hashes_verified'] is True,
            'historical accepted complete saved proof required')
    ac = acceptance['construction']
    for field, role in (('complete_observation_manifest_sha256', 'observations'),
                        ('complete_cohort_sha256', 'cohort'), ('success_receipt_sha256', 'success')):
        require(ac[field] == sha(blobs[role]), 'accepted observation role provenance differs')
    require(ac['common_disclosure_sha256'] == sha(disclosure), 'accepted disclosure differs')
    for field, role in (('source_index_manifest', 'index_manifest'), ('source_case_stream', 'index_cases'),
                        ('numeric_cohort', 'numeric_cohort'), ('numeric_verification', 'numeric_proof')):
        bound_body(blobs[role], c[field])
    require(im['schema'] == 'dosei_complete_private_case_index_manifest_v1' and im['status'] == 'complete'
            and im['visibility'] == 'evaluator_private' and im['condition'] == CONDITION, 'complete private index')
    for field, role in (('cases', 'index_cases'), ('key', 'key'), ('numeric_cohort', 'numeric_cohort'),
                        ('verification_report', 'numeric_proof')):
        bound_body(blobs[role], im[field])
    require(nc['schema'] == 'dosei_complete_full_eeg_preparation_v1' and nc['status'] == 'succeeded'
            and integer(nc['complete_source_recordings']) == RECORDINGS, 'complete native metadata')
    require(proof['schema'] == 'dosei_full_saved_projection_verification_v1' and proof['status'] == 'succeeded'
            and proof['all171_projection_hashes_verified_in_one_structural_read'] is True, 'complete saved-array proof')
    ir, nr, cr, pr = (records(x) for x in (im['recordings'], nc['complete_member_receipts'],
                                        c['native_member_bindings'], proof['recordings']))
    require(set(ir) == set(nr) == set(cr) == set(pr) == set(member_blobs), 'all171 role joins required')
    receipts = {}
    roots = set()
    for rid, raw in member_blobs.items():
        for declared in (ir[rid]['native_receipt'], nr[rid]['receipt'], cr[rid]['receipt']):
            bound_body(raw, declared)
        receipt = decode(raw)
        require(receipt['schema'] == 'dosei_full_eeg_member_success_v1' and receipt['status'] == 'succeeded'
                and receipt['recording_id'] == rid and receipt['complete_source_EOF_CRC_SHA'] is True and
                receipt['all_three_streams_closed_and_size_stat_checked'] is True,
                'complete source member required')
        rows = integer(receipt['source_rows'], 4000000)
        require(rows > 0 and rows == integer(ir[rid]['clock']['row_count']) == integer(pr[rid]['source_rows'])
                and pr[rid]['all_stream_hashes_and_structural_checks_passed'] is True, 'source clock/proof join')
        require(set(receipt['outputs']) == {'time', 'eeg', 'quality'}, 'all native streams required')
        root = Path(receipt['outputs']['time']['path']).parent
        require(root.is_absolute(), 'absolute accepted array root required')
        roots.add(root)
        for kind in ('time', 'eeg', 'quality'):
            modules['host'].validate_binding(receipt['outputs'][kind], root, rid, kind, rows)
        receipts[rid] = receipt
    require(len(roots) == 1, 'one accepted immutable array namespace required')
    indices = lines(blobs['index_cases'], 2048)
    observations = lines(blobs['observations'], 1024)
    by_id = {}
    counts = Counter()
    previous = None
    for index in indices:
        clock, _, start, end, _ = modules['indexed'].validate_index(index, secret=blobs['key'], core=modules['core'])
        rid = index['evaluator']['recording_id']
        require(rid in receipts and index['case_id'] not in by_id, 'unique joined private case')
        same(index['clock'], ir[rid]['clock'], 'private case/source clock differs')
        order = (int(rid), index['evaluator']['source_row'])
        require(previous is None or order > previous, 'fixed numeric-record/source-row private order')
        previous = order
        by_id[index['case_id']] = index
        counts[rid] += 1
    require(set(counts) == set(receipts), 'all recording groups represented')
    for rid, n in counts.items():
        require(n == integer(ir[rid]['cases']), 'complete per-record case count')
    manifest = []
    coverage = Counter()
    ordered_ids = sorted(by_id)
    for position, row in enumerate(observations):
        require(type(row) is dict and set(row) == OBS_FIELDS and
                row['schema'] == 'dosei_paired_observation_manifest_row_v1' and
                type(row['public_position']) is int and row['public_position'] == position and
                row['case_id'] == ordered_ids[position], 'complete fixed observation order')
        index = by_id[row['case_id']]
        same(row['coverage'], index['coverage'], 'retained case coverage differs')
        require(integer(row['source_rows'], 7501) == index['end_row_exclusive']-index['start_row'],
                'same complete source slice required')
        for key in ('observation_sha256', 'default_png_sha256', 'projection_receipt_sha256', 'array_identity_binding_sha256'):
            hash_string(row[key])
        require(0 < integer(row['observation_bytes'], 2097152) and
                0 < integer(row['default_png_bytes'], 2097152), 'bounded complete packet/image')
        outputs = receipts[index['evaluator']['recording_id']]['outputs']
        array_ids = {kind: {key: outputs[kind][key] for key in
                     ('bytes', 'sha256', 'closed_file_signature')} for kind in ('time', 'eeg', 'quality')}
        require(row['array_identity_binding_sha256'] == sha(canonical(array_ids)), 'exact accepted array identity')
        coverage['full_interval' if index['coverage']['full_interval_recorded'] else 'short_prefix'] += 1
        if row['source_rows'] == 0:
            coverage['empty_window'] += 1
        manifest.append({key: row[key] for key in ('case_id', 'observation_sha256')})
    same(dict(coverage), c['source_temporal_coverage'], 'all coverage slots retained')
    modules['transport'].admit_manifest(manifest)
    source_bindings = {role: binding(raw) for role, raw in blobs.items()}
    source_bindings['members'] = {rid: binding(raw) for rid, raw in member_blobs.items()}
    return AdmittedRelease(scope=scope, manifest=manifest, observations={x['case_id']: x for x in observations},
        indices=[by_id[x] for x in ordered_ids], receipts=receipts, secret=blobs['key'], disclosure=disclosure,
        root=roots.pop(), source_bindings=source_bindings)


def admit_release(blobs, member_blobs, *, modules):
    """Authenticate exactly the fixed accepted release from complete supplied bytes."""
    return _admit(blobs, member_blobs, modules, PINS, 'accepted_release_v2')


def admit_generated_release(blobs, member_blobs, *, modules, generated_pins):
    """Fictional controls only; this result cannot enter the authentic assembler."""
    require(generated_pins != PINS and all(generated_pins.get(k) != v for k, v in PINS.items()),
            'generated fixture must not impersonate the accepted release')
    return _admit(blobs, member_blobs, modules, generated_pins, 'generated_only')
