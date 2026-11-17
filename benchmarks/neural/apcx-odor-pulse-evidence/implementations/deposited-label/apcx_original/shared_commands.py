"""Lossless command-diagnostic references; no data access or work on import.

Scientific values, legacy flags and unresolved branches are untouched. Sharing
content does not merge trial identities. Original canonical JSON lines can be
reconstructed and checked against a per-record and whole-stream witness.
"""
import hashlib
import json
import re

from . import census_core as core

SCHEMA = 'apcx-shared-command-reference-v1'
DIAGNOSTIC_RECORD_BYTES = 2 * 1024 * 1024 + 4096
ROW_RECORD_BYTES = 8192
TRIAL_RECORD_BYTES = 65536
REFERENCE = 'command_multiplicity_reference'
WITNESS = 'expanded_record_sha256'


def line_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(value):
    return hashlib.sha256(line_bytes(value)).hexdigest()


def hex_digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def trial_key(record, kind, groupable):
    if type(groupable) is not bool: raise ValueError('explicit grouping state')
    if not groupable: return None
    if kind == 'row':
        identity = record['identity_owner_only']
        value = {'animal': identity['Animal'], 'session': identity['Session'],
                 'released_trial': identity['Trial']}
    elif kind == 'trial':
        value = {k: record[k] for k in ('animal', 'session', 'released_trial')}
    else: raise ValueError('closed record kind')
    if (type(value['animal']) is not str or type(value['session']) is not str
            or type(value['released_trial']) is not int
            or not 0 <= value['released_trial'] < 2**31):
        raise ValueError('exact typed released trial identity')
    return core.fingerprint(value)['sha256']


def restore_record(projected, diagnostic):
    """Reconstruct the exact previous row/trial record, including every flag."""
    if type(projected) is not dict or type(diagnostic) is not dict:
        raise ValueError('ordinary projected record and diagnostic')
    value = dict(projected)
    if 'command_multiplicity_owner_only' in value:
        raise ValueError('mixed expanded and normalized representation')
    reference = value.pop(REFERENCE)
    witness = value.pop(WITNESS)
    if (type(reference) is not dict or set(reference) !=
            {'schema', 'kind', 'groupable', 'released_trial_key', 'diagnostic_sha256'}
            or reference['schema'] != SCHEMA or reference['kind'] not in ('row', 'trial')
            or not hex_digest(reference['diagnostic_sha256']) or not hex_digest(witness)):
        raise ValueError('exact command reference schema')
    if trial_key(value, reference['kind'], reference['groupable']) != reference['released_trial_key']:
        raise ValueError('trial reference does not join exact record identity')
    if core.fingerprint(diagnostic)['sha256'] != reference['diagnostic_sha256']:
        raise ValueError('complete typed diagnostic identity mismatch')
    if ('command_multiplicity_digest' in value and
            value['command_multiplicity_digest'] != reference['diagnostic_sha256']):
        raise ValueError('original diagnostic digest mismatch')
    value['command_multiplicity_owner_only'] = diagnostic
    if sha(value) != witness: raise ValueError('expanded record identity mismatch')
    return value


class SharedCommands:
    """One bounded content dictionary, plus distinct row/trial references.

    The existing scanner supplies the owned writer. Every diagnostic remains a
    whole ordinary record; files are never split to bypass a bound.
    """
    def __init__(self, writer, max_diagnostics):
        if type(max_diagnostics) is not int or max_diagnostics <= 0:
            raise ValueError('positive finite diagnostic count')
        self.writer = writer
        self.maximum = max_diagnostics
        self.contents = {}
        self.trial_variants = {}
        self.rows = self.trials = self.ungroupable_rows = 0
        self.expanded_hashes = {kind: hashlib.sha256() for kind in ('row', 'trial')}
        self.expanded_bytes = {kind: 0 for kind in ('row', 'trial')}

    def project(self, record, kind, groupable, allow_new=True):
        if type(record) is not dict or kind not in ('row', 'trial') or type(allow_new) is not bool:
            raise ValueError('explicit ordinary record projection')
        if REFERENCE in record or WITNESS in record:
            raise ValueError('reserved normalization keys already present')
        diagnostic = record['command_multiplicity_owner_only']
        if type(diagnostic) is not dict: raise ValueError('complete diagnostic mapping')
        digest = core.fingerprint(diagnostic)['sha256']
        encoded = line_bytes(diagnostic)
        key = trial_key(record, kind, groupable)
        if digest in self.contents:
            if self.contents[digest] != encoded: raise ValueError('diagnostic digest collision or mutation')
        else:
            if not allow_new: raise ValueError('trial references a diagnostic never emitted by any row')
            if len(self.contents) >= self.maximum: raise ValueError('whole diagnostic dictionary count cap')
            item = {'diagnostic_sha256': digest, 'command_multiplicity_owner_only': diagnostic}
            if len(line_bytes(item)) > DIAGNOSTIC_RECORD_BYTES:
                raise ValueError('whole diagnostic record bound')
            self.writer.write(item, maximum=DIAGNOSTIC_RECORD_BYTES)
            self.contents[digest] = encoded
        original = line_bytes(record)
        projected = {k: v for k, v in record.items() if k != 'command_multiplicity_owner_only'}
        projected[REFERENCE] = {'schema': SCHEMA, 'kind': kind, 'groupable': groupable,
            'released_trial_key': key, 'diagnostic_sha256': digest}
        projected[WITNESS] = hashlib.sha256(original).hexdigest()
        if line_bytes(restore_record(projected, diagnostic)) != original:
            raise ValueError('lossless complete record reconstruction')
        maximum = ROW_RECORD_BYTES if kind == 'row' else TRIAL_RECORD_BYTES
        if len(line_bytes(projected)) > maximum: raise ValueError('whole normalized record bound')
        if kind == 'row':
            self.rows += 1
            if key is None: self.ungroupable_rows += 1
            else: self.trial_variants.setdefault(key, set()).add(digest)
        else:
            self.trials += 1
            if key not in self.trial_variants or digest not in self.trial_variants[key]:
                raise ValueError('trial has no matching complete row reference')
        self.expanded_hashes[kind].update(original)
        self.expanded_bytes[kind] += len(original)
        return projected

    def report(self):
        return {'schema': SCHEMA, 'rows': self.rows, 'trial_records': self.trials,
            'diagnostic_records': len(self.contents), 'distinct_released_trial_keys': len(self.trial_variants),
            'ungroupable_rows_preserved': self.ungroupable_rows,
            'trial_keys_with_diagnostic_variants': sum(len(x) > 1 for x in self.trial_variants.values()),
            'expanded_record_streams': {kind: {'bytes': self.expanded_bytes[kind],
                'sha256': self.expanded_hashes[kind].hexdigest()} for kind in ('row', 'trial')},
            'content_sharing_merges_trial_identities': False, 'original_flags_removed': False,
            'unresolved_diagnostics_removed': False, 'scientific_primary_admitted': False,
            'candidate_export': False}

