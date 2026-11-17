"""Exact multifile wire envelope; no geometry calculation or private inputs."""
import base64
import hashlib
import json
import schema as S

CAP = 12 * 1024 * 1024


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(files):
    need(type(files) is dict and set(S.REQUIRED) <= set(files) <= set(S.CAPS), 'file_membership')
    need(all(type(v) is bytes and 0 < len(v) <= S.CAPS[k] for k, v in files.items()), 'file_extent')
    need(sum(map(len, files.values())) <= S.TOTAL_CAP, 'aggregate_extent')
    body = (json.dumps({'schema': 'purkinje-program-files/v1', 'files': {
        name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
               'base64': base64.b64encode(raw).decode('ascii')}
        for name, raw in sorted(files.items())}}, separators=(',', ':'), allow_nan=False) + '\n').encode()
    need(len(body) <= CAP, 'wire_extent')
    return body


def decode(body):
    need(type(body) is bytes and 0 < len(body) <= CAP, 'wire_extent')
    def unique(rows):
        out = {}
        for k, v in rows:
            need(k not in out, 'duplicate_key')
            out[k] = v
        return out
    value = json.loads(body.decode('utf-8'), object_pairs_hook=unique,
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite_json')))
    need(type(value) is dict and set(value) == {'schema', 'files'} and
         value['schema'] == 'purkinje-program-files/v1', 'wire_schema')
    rows = value['files']
    need(type(rows) is dict and set(S.REQUIRED) <= set(rows) <= set(S.CAPS), 'file_membership')
    files = {}
    for name, row in rows.items():
        need(type(row) is dict and set(row) == {'bytes', 'sha256', 'base64'}, 'file_descriptor')
        need(type(row['bytes']) is int and 0 < row['bytes'] <= S.CAPS[name] and
             type(row['base64']) is str and len(row['base64']) == 4 * ((row['bytes'] + 2) // 3), 'encoded_extent')
        raw = base64.b64decode(row['base64'], validate=True)
        need(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'] and
             base64.b64encode(raw).decode('ascii') == row['base64'], 'exact_file_identity')
        files[name] = raw
    need(sum(map(len, files.values())) <= S.TOTAL_CAP, 'aggregate_extent')
    return files
