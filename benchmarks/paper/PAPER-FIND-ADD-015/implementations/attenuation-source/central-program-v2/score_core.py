"""Public-first central-panel artifact comparison; no reconstruction or model fits."""
import ast
from decimal import Decimal, localcontext
import hashlib
import io
import json
import math
import struct
import zipfile

import numpy as np

CANDIDATE_ID = 'PAPER-FIND-ADD-015'
SUBMISSION_CAP = 2_700_000
SCORE_CAP = 1_000_000
MEMBER_CAPS = {'windows.npz': 1_400_000, 'paired_vectors.npz': 800_000,
               'report.json': 300_000}


class InvalidSubmission(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise InvalidSubmission(message)


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode()


def strict_json(body):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'Duplicate JSON key')
            out[key] = value
        return out
    def floating(token):
        value = float(token)
        need(math.isfinite(value), 'Finite JSON numbers')
        need(value != 0 or Decimal(token) == 0, 'No destructive JSON literal underflow')
        return value
    def constant(_):
        raise InvalidSubmission('No nonfinite JSON constants')
    return json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=pairs,
                      parse_float=floating, parse_constant=constant)


def exact_json(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(exact_json(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(exact_json(x, y) for x, y in zip(a, b))
    return a == b


def schema_node(node, root):
    if '$ref' in node:
        ref = node['$ref']
        need(ref.startswith('#/$defs/') and '/' not in ref[8:], 'Local declared schema reference')
        return root['$defs'][ref[8:]]
    return node


def validate_json(value, node, root, path='$', depth=0):
    need(depth <= 40, 'Bounded declared JSON depth')
    node = schema_node(node, root)
    typ = node.get('type')
    types = typ if isinstance(typ, list) else [typ] if typ else []
    type_matches = {
        'null': value is None, 'boolean': type(value) is bool,
        'integer': type(value) is int,
        'number': type(value) in (int, float) and (type(value) is int or math.isfinite(value)),
        'string': type(value) is str, 'array': type(value) is list,
        'object': type(value) is dict,
    }
    need(not types or any(type_matches[t] for t in types), 'JSON type: ' + path)
    if 'const' in node:
        need(exact_json(value, node['const']), 'JSON constant: ' + path)
    if 'enum' in node:
        need(any(exact_json(value, item) for item in node['enum']), 'JSON enum: ' + path)
    if type(value) in (int, float):
        need('minimum' not in node or value >= node['minimum'], 'JSON minimum: ' + path)
        need('maximum' not in node or value <= node['maximum'], 'JSON maximum: ' + path)
    if type(value) is str:
        need('maxLength' not in node or len(value) <= node['maxLength'], 'JSON string bound: ' + path)
    if type(value) is dict:
        props = node.get('properties', {})
        need(set(node.get('required', [])) <= set(value), 'Required JSON fields: ' + path)
        additional = node.get('additionalProperties', True)
        for key, item in value.items():
            if key in props:
                validate_json(item, props[key], root, path + '.' + key, depth + 1)
            else:
                need(additional is not False, 'Extra JSON field: ' + path)
                if isinstance(additional, dict):
                    validate_json(item, additional, root, path + '.' + key, depth + 1)
    if type(value) is list:
        need(len(value) >= node.get('minItems', 0), 'JSON list minimum: ' + path)
        need(len(value) <= node.get('maxItems', 300_000), 'JSON list maximum: ' + path)
        for i, item in enumerate(value):
            validate_json(item, node.get('items', {}), root, path + '[' + str(i) + ']', depth + 1)


def stored_members(body, expected, cap):
    """No extraction. Exact central-directory roster, local names, CRC and lengths."""
    need(type(body) is bytes and 0 < len(body) <= cap, 'Bounded artifact bytes')
    need(len(body) >= 22 and body[:4] == b'PK\x03\x04' and body[-22:-18] == b'PK\x05\x06',
         'Ordinary ZIP without prefix, trailing data or comment')
    sig, disk, cd_disk, count_disk, count, size, offset, comment = struct.unpack('<4s4H2IH', body[-22:])
    need(disk == cd_disk == comment == 0 and count == count_disk == len(expected)
         and offset + size == len(body) - 22, 'Single-disk exact ZIP directory')
    out = {}
    with zipfile.ZipFile(io.BytesIO(body), 'r') as archive:
        infos = archive.infolist()
        need(len(infos) == len(expected) and {i.orig_filename for i in infos} == set(expected),
             'Exact unique archive members')
        ranges = []
        for info in infos:
            name = info.orig_filename
            need(name == info.filename and '\x00' not in name and not info.is_dir(), 'Ordinary member name')
            need(info.compress_type == zipfile.ZIP_STORED and not info.flag_bits & ~0x800
                 and info.file_size == info.compress_size and 0 < info.file_size <= expected[name],
                 'Stored, unencrypted, bounded member')
            need((info.external_attr >> 16) & 0o170000 in (0, 0o100000), 'No archive links or special files')
            pos = info.header_offset
            need(0 <= pos < offset and body[pos:pos+4] == b'PK\x03\x04', 'Local header in payload region')
            header = struct.unpack('<4s5H3I2H', body[pos:pos+30])
            flags, method, nlen, xlen = header[2], header[3], header[-2], header[-1]
            encoding = 'utf-8' if flags & 0x800 else 'cp437'
            need(flags == info.flag_bits and method == info.compress_type
                 and body[pos+30:pos+30+nlen].decode(encoding) == name, 'Local and central headers agree')
            need(header[6] == info.CRC, 'Local and central CRC agree')
            extra = body[pos+30+nlen:pos+30+nlen+xlen]
            extras = {}; cursor = 0
            while cursor < len(extra):
                need(cursor + 4 <= len(extra), 'Complete local extra-field header')
                tag, length = struct.unpack('<HH', extra[cursor:cursor+4]); cursor += 4
                need(tag not in extras and cursor + length <= len(extra), 'Unique bounded local extra field')
                extras[tag] = extra[cursor:cursor+length]; cursor += length
            local_compressed, local_uncompressed = header[7], header[8]
            requested = [('uncompressed', local_uncompressed), ('compressed', local_compressed)]
            zip64 = extras.get(1, b'')
            need(len(zip64) == 8 * sum(value == 0xffffffff for _, value in requested),
                 'Only required local ZIP64 size fields')
            resolved = {}; cursor = 0
            for key, value in requested:
                if value == 0xffffffff:
                    value = int.from_bytes(zip64[cursor:cursor+8], 'little'); cursor += 8
                resolved[key] = value
            need(resolved['compressed'] == info.compress_size and resolved['uncompressed'] == info.file_size,
                 'Local and central sizes agree, including NumPy local ZIP64 sizes')
            end = pos + 30 + nlen + xlen + info.compress_size
            need(end <= offset, 'Member stays before directory')
            ranges.append((pos, end))
            data = archive.read(info)
            need(len(data) == info.file_size, 'Complete CRC-checked member')
            out[name] = data
        ranges.sort()
        need(ranges[0][0] == 0 and ranges[-1][1] == offset
             and all(a[1] == b[0] for a, b in zip(ranges, ranges[1:])), 'No overlapping or hidden local members')
    return out


def decode_npz(body, fields, cap):
    members = stored_members(body, {k + '.npy': cap for k in fields}, cap)
    arrays = {}
    for key, target in fields.items():
        raw = members[key + '.npy']
        need(raw[:6] == b'\x93NUMPY' and raw[6:8] in (b'\x01\x00', b'\x02\x00'), 'NPY version1/2')
        size_bytes = 2 if raw[6:8] == b'\x01\x00' else 4
        size = int.from_bytes(raw[8:8+size_bytes], 'little')
        need(0 < size <= 4096 and len(raw) >= 8 + size_bytes + size, 'Bounded complete NPY header')
        text = raw[8+size_bytes:8+size_bytes+size].decode('latin1')
        tree = ast.parse(text.strip(), mode='eval')
        need(isinstance(tree.body, ast.Dict), 'NPY dictionary header')
        keys = [ast.literal_eval(k) for k in tree.body.keys]
        need(len(keys) == 3 and set(keys) == {'descr', 'shape', 'fortran_order'}, 'Exact unique NPY header keys')
        header = ast.literal_eval(tree)
        need(header['fortran_order'] is False and type(header['shape']) is tuple
             and all(type(x) is int and x >= 0 for x in header['shape'])
             and list(header['shape']) == target['shape'], 'Exact C-order array shape')
        need(type(header['descr']) is str and header['descr'] == target['dtype'], 'Exact declared primitive dtype')
        dtype = np.dtype(header['descr'])
        need(not dtype.hasobject and dtype.fields is None, 'Primitive nonobject dtype')
        count = math.prod(header['shape'])
        start = 8 + size_bytes + size
        need(start + count * dtype.itemsize == len(raw), 'Exact NPY payload length')
        value = np.frombuffer(raw, dtype=dtype, count=count, offset=start).reshape(header['shape']).copy()
        if target['kind'] == 'numeric':
            need(dtype == np.dtype('<f8') and bool(np.isfinite(value).all()), 'Finite float64 numeric values')
        else:
            need(exact_json(value.tolist(), target['values']), 'Exact ordered public identities')
        arrays[key] = value
    return arrays


def public_report_semantics(report, spec):
    records = report['records']
    for row, public in zip(records, spec['record_metadata_from_public_source']):
        for key in ('prefix', 'condition_shapes', 'parity_trial_counts'):
            need(exact_json(row[key], public[key]), 'Exact public record metadata: ' + key)
        need(row['onset_frame'] >= row['window_frames'] > 0
             and all(row['onset_frame'] + row['window_frames'] <= shape[-1]
                     for shape in row['condition_shapes'].values()), 'Feasible public source window')
    for i, row in enumerate(report['fig2']['cross_half']):
        need(row['predictor_parity'] == i and row['outcome_parity'] == 1-i, 'Both ordered cross-half orientations')
    def primary(row, multiplicity):
        need(row['method_requested'] == 'auto' and row['continuity_correction'] is False
             and row['multiplicity'] == multiplicity, 'Fixed primary rank-test convention')
    for name, row in report['fig2']['groups'].items():
        if name == 'unclassified':
            need(row['source_statistical_O_minus_C'] is None
                 and row['source_test_disposition'] == 'descriptive_only_no_extra_test', 'No fourth Figure2 test')
        else:
            need(row['source_test_disposition'] == 'three_test_family', 'Figure2 test family')
            primary(row['source_statistical_O_minus_C'], 3)
    for row in report['multiopto']['groups'].values():
        primary(row['source_paired_during_minus_alone'], 3)
    for row in report['multivis']['variants'].values():
        primary(row['activated_minus_suppressed'], 1)
    for rows in (report['fig2']['high_group_fixed_method_diagnostic'],
                 report['multiopto']['suppressed_fixed_method_diagnostic']):
        for row, (method, correction) in zip(rows, (('auto', False), ('exact', False),
                                                    ('asymptotic', False), ('asymptotic', True))):
            need(row['method_requested'] == method and row['continuity_correction'] is correction
                 and row['multiplicity'] == 3, 'Ordered fixed rank-method diagnostics')


def admit(body, spec):
    members = stored_members(body, MEMBER_CAPS, SUBMISSION_CAP)
    arrays = {name: decode_npz(members[name], spec['exact_members'][name]['fields'], MEMBER_CAPS[name])
              for name in ('windows.npz', 'paired_vectors.npz')}
    report = strict_json(members['report.json'])
    root = spec['exact_members']['report.json']['json_schema']
    validate_json(report, root, root)
    public_report_semantics(report, spec)
    return {'arrays': arrays, 'report': report, 'sha256': hashlib.sha256(body).hexdigest()}


def project_reference(raw, spec):
    """Declared schema projection only; no recalculation from observations."""
    root = spec['exact_members']['report.json']['json_schema']
    source = dict(raw)
    source['schema_version'] = 1
    source['candidate_id'] = CANDIDATE_ID
    source.pop('interpretation', None)
    def project(value, node):
        node = schema_node(node, root)
        if type(value) is dict:
            props = node.get('properties')
            if props is None:
                return {k: project(v, node.get('additionalProperties', {})) for k, v in value.items()}
            need(set(node.get('required', [])) <= set(value), 'Private report has every declared field')
            return {k: project(value[k], sub) for k, sub in props.items() if k in value and k != 'interpretation'}
        if type(value) is list:
            return [project(v, node.get('items', {})) for v in value]
        return value
    out = project(source, root)
    validate_json(out, root, root)
    public_report_semantics(out, spec)
    return out


def decimal_value(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, np.integer)):
        return Decimal(int(value))
    return Decimal.from_float(float(value))


def metric(value):
    """A nonzero decimal error is never silently exposed as float zero."""
    number = float(value)
    return {'value': number if math.isfinite(number) and (number != 0 or value == 0) else None,
            'decimal': str(value),
            'float_representation': 'finite' if math.isfinite(number) and (number != 0 or value == 0)
            else 'overflow' if not math.isfinite(number) else 'underflow'}


class Errors:
    def __init__(self):
        self.n = self.changed = self.sign = 0
        self.absolute = self.square = self.maximum = Decimal(0)

    def add(self, candidate, expected):
        a, b = decimal_value(candidate), decimal_value(expected)
        error = abs(a-b)
        self.n += 1
        self.changed += a != b
        self.sign += (a < 0) != (b < 0) if a and b else 0
        self.absolute += error
        self.square += error*error
        self.maximum = max(self.maximum, error)

    def result(self):
        if not self.n:
            return {'n_values': 0, 'n_exact_mismatches': 0, 'n_nonzero_sign_mismatches': 0,
                    'mae': None, 'rmse': None, 'max_abs_error': None}
        return {'n_values': self.n, 'n_exact_mismatches': self.changed,
                'n_nonzero_sign_mismatches': self.sign,
                'mae': metric(self.absolute/self.n),
                'rmse': metric((self.square/self.n).sqrt()), 'max_abs_error': metric(self.maximum)}


def errors(candidate, expected):
    result = Errors()
    for a, b in zip(candidate, expected):
        result.add(a, b)
    return result.result()


def exact_float_contrast(first, second):
    # 1100 decimal digits cover the complete binary64 exponent span, including
    # a maximum finite common mode and a minimum subnormal difference.
    with localcontext() as context:
        context.prec = 1100
        return decimal_value(first) - decimal_value(second)


def report_errors(candidate, expected, root):
    """All leaves compared; variable-length lists have bounded aggregate diagnostics."""
    out = {}
    def walk(a, b, node, path):
        node = schema_node(node, root)
        if type(a) is dict and type(b) is dict:
            props = node.get('properties', {})
            for key in sorted(set(a) | set(b)):
                if key == 'interpretation' and path == '$':
                    continue
                walk(a[key], b[key], props.get(key, node.get('additionalProperties', {})), path + '.' + key)
        elif type(a) is list and type(b) is list:
            fixed = node.get('minItems') == node.get('maxItems') and 'minItems' in node
            if fixed:
                for i, (av, bv) in enumerate(zip(a, b)):
                    walk(av, bv, node.get('items', {}), path + '[' + str(i) + ']')
            else:
                nums = Errors(); mismatches = abs(len(a)-len(b)); examples = []
                for i, (av, bv) in enumerate(zip(a, b)):
                    if type(av) in (int, float) and type(bv) in (int, float):
                        nums.add(av, bv)
                    same = exact_json(av, bv)
                    mismatches += not same
                    if not same and len(examples) < 8:
                        examples.append(i)
                out[path] = {'kind': 'variable_list', 'candidate_length': len(a),
                             'reference_length': len(b), 'exact_mismatches_including_missing': mismatches,
                             'first_mismatching_common_indices': examples, 'numeric_common_entries': nums.result()}
        elif type(a) in (int, float) and type(b) in (int, float):
            out[path] = {'kind': 'numeric', 'errors': errors([a], [b])}
        else:
            out[path] = {'kind': 'categorical_or_null', 'matches': exact_json(a, b),
                         'candidate_type': type(a).__name__, 'reference_type': type(b).__name__}
    walk(candidate, expected, root, '$')
    return out


def scientific_metrics(candidate, expected):
    c, r = candidate['paired_vectors.npz'], expected['paired_vectors.npz']
    out = {}
    def grouped(name, key, identity):
        groups = list(dict.fromkeys(r[identity].tolist()))
        rows = []
        for group in groups:
            mask = r[identity] == group
            rows.append({'experiment_id': str(group), 'errors': errors(c[key][mask].flat, r[key][mask].flat)})
        mean_rmse = sum(Decimal(row['errors']['rmse']['decimal']) for row in rows)/len(rows)
        out[name] = {'equal_experiment_rmse': metric(mean_rmse), 'per_experiment': rows}
    for prefix in ('fig2_source', 'fig2_unclipped'):
        grouped(prefix + '_D', prefix + '__delta', 'fig2__experiment_id')
    for direction in (0, 1):
        for variant in ('clipped', 'unclipped'):
            grouped('fig2_cross_' + str(direction) + '_' + variant + '_D',
                    'fig2_cross_' + str(direction) + '__' + variant, 'fig2__experiment_id')
    for variant in ('source', 'unclipped'):
        grouped('multiopto_' + variant + '_J',
                'multiopto_' + variant + '_effect__during_minus_alone_power_difference', 'multiopto__experiment_id')
    for variant in ('source', 'unclipped', 'baseline_only', 'paper_method'):
        key = 'multivis_' + variant + '__delta'
        left = [exact_float_contrast(x[0], x[1]) for x in c[key]]
        right = [exact_float_contrast(x[0], x[1]) for x in r[key]]
        out['multivis_' + variant + '_K'] = errors(left, right)
    total = Errors()
    for key in candidate['windows.npz']:
        for av, bv in zip(candidate['windows.npz'][key].flat, expected['windows.npz'][key].flat):
            total.add(av, bv)
    out['all_per_trial_windows'] = total.result()
    return out


def grade(body, spec, private_loader):
    """The callback is unreachable until every public member has been admitted."""
    try:
        candidate = admit(body, spec)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, SyntaxError,
            UnicodeError, zipfile.BadZipFile, EOFError, struct.error, NotImplementedError) as exc:
        return {'status': 'invalid_submission', 'submission_valid': False,
                'reason': str(exc)[:512], 'private_reference_reads': 0, 'private_loader_calls': 0,
                'scientific_success': None, 'performance_floor': None}
    reference = private_loader()
    need(type(reference) is dict and set(reference) == set(MEMBER_CAPS), 'Exact private reference members')
    arrays = {name: decode_npz(reference[name], spec['exact_members'][name]['fields'], MEMBER_CAPS[name])
              for name in ('windows.npz', 'paired_vectors.npz')}
    report = project_reference(strict_json(reference['report.json']), spec)
    with localcontext() as context:
        context.prec = 80
        field_errors = {}
        for name in ('windows.npz', 'paired_vectors.npz'):
            field_errors[name] = {}
            for key, target in spec['exact_members'][name]['fields'].items():
                a, b = candidate['arrays'][name][key], arrays[name][key]
                field_errors[name][key] = (errors(a.flat, b.flat) if target['kind'] == 'numeric'
                    else {'n_values': int(a.size), 'identity_matches': bool(np.array_equal(a, b))})
        result = {'status': 'scored', 'submission_valid': True,
                  'submission_sha256': candidate['sha256'], 'private_reference_reads': 3,
                  'private_loader_calls': 1,
                  'private_reference_files': 3, 'array_fields_compared': 230,
                  'all_array_field_errors': field_errors,
                  'all_scientific_report_field_errors': report_errors(candidate['report'], report,
                      spec['exact_members']['report.json']['json_schema']),
                  'metrics': scientific_metrics(candidate['arrays'], arrays),
                  'scientific_success': None, 'performance_floor': None,
                  'overall_composite_reward': None,
                  'scope': 'All declared processed central-panel artifacts; no fit, population or whole-paper qualification.',
                  'metric_arithmetic': '80-significant-digit Decimal arithmetic on exact input floats; decimal values retained when finite JSON float representation overflows or underflows; zero has no error tolerance floor.'}
    need(len(json_bytes(result)) <= SCORE_CAP, 'Bounded complete score diagnostics')
    return result
