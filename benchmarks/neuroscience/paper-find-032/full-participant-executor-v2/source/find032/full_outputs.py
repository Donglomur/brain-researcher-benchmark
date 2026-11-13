"""Literal metadata reader for the complete FIND032 corrected output family.

This module opens no files, imports no scientific libraries, and decodes no NPZ
or PDF. Its return values request captures; they do not attest their contents,
producer, execution, scientific validity, or access-arm isolation. Both arms use
the same protocol. Actual payload capture precedes protected-reference access.
"""
import hashlib
import json
import math

from .core import Refusal
from .artifacts import product_name
from .products import ProductKey, participant_products
from .statistics import planned_family_names
from .roster import PARTICIPANTS, CONDITIONS, FIGURES


_PIN = {'name', 'bytes', 'sha256'}
_REASONS = (
    'no_actual_bracketing_onsets',
    'omission_context_has_no_sound_confusion_model',
    'observed_offset_outside_confusion_support',
)
_FISHER_REASONS = (
    'undefined within-person correlation; whole endpoint unavailable',
    'nonfinite Fisher coefficient; no historical clipping in corrected profile',
)
_BAYES = (
    'fisher_difference/sound/empirical',
    'fisher_difference/sound/theoretical',
    'fisher_difference/sound/most_likely_empirical',
)
_STRUCTURAL = (
    'accuracy_difference/sound/empirical/random',
    'accuracy_difference/omission/empirical/random',
)
_IDENTITY_KEYS = {'kind', 'input_sha256', 'event_indices', 'support_checked', 'fit_route'}


def _require(condition, message):
    if not condition:
        raise Refusal('full output metadata: ' + message)


def _keys(value, keys, where):
    _require(type(value) is dict and set(value) == set(keys), where + ' exact fields')


def _same(left, right):
    """JSON equality with exact scalar types; 1.0/True do not stand in for 1."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _integer(value, low, where):
    _require(type(value) is int and value >= low, where + ' integer extent')
    return value


def _sha(value):
    return (type(value) is str and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value))


def _limits(member_bytes, total_bytes):
    _integer(member_bytes, 1, 'member limit')
    _integer(total_bytes, 1, 'total limit')


def _pin(row, member_bytes, *, product=False):
    _keys(row, _PIN | ({'key'} if product else set()), 'file descriptor')
    name = row['name']
    _require(type(name) is str and name not in ('', '.', '..') and
             '/' not in name and '\\' not in name and '\x00' not in name,
             'one basename per descriptor')
    _integer(row['bytes'], 1, 'file')
    _require(row['bytes'] <= member_bytes and _sha(row['sha256']), 'file size/hash')
    return {k: row[k] for k in ('name', 'bytes', 'sha256')}


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON object key')
        result[key] = value
    return result


def _nonfinite(value):
    raise Refusal('full output metadata: nonfinite JSON number ' + value)


def _float(value):
    number = float(value)
    _require(math.isfinite(number), 'nonfinite JSON float')
    return number


def _decode(raw, pin, member_bytes):
    _pin(pin, member_bytes)
    _require(type(raw) is bytes and len(raw) == pin['bytes'], 'captured metadata extent')
    _require(hashlib.sha256(raw).hexdigest() == pin['sha256'], 'captured metadata hash')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_object,
                          parse_constant=_nonfinite, parse_float=_float)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Refusal('full output metadata: invalid finite UTF-8 JSON') from error


def _sequence(value, where):
    _require(type(value) is list, where + ' JSON array')
    return value


def _names(value, where):
    _sequence(value, where)
    _require(all(type(x) is str for x in value), where + ' string identities')
    _require(len(value) == len(set(value)), where + ' duplicate identities')
    return value


def _key_values(key):
    return [key.participant, key.stimulus, key.pipeline, key.condition, key.score]


def _reason_counts(value, where):
    _require(type(value) is dict and value and
             set(value).issubset({'supported', *_REASONS}), where + ' categories')
    for count in value.values():
        _integer(count, 1, where)
    return value


def _unavailable_row(row):
    _keys(row, {'status', 'reason', 'dependencies', 'subjects_required'}, 'group unavailable')
    _require(row['status'] == 'unavailable' and type(row['reason']) is str and
             type(row['subjects_required']) is int and row['subjects_required'] == 33,
             'group unavailable values')
    _names(row['dependencies'], 'unavailable dependencies')


def _cost(value):
    _keys(value, {'limits', 'reserved', 'known', 'unknown_reservations', 'native_costs'},
          'original logical cost')
    domains = {'read', 'write', 'files'}
    for key in ('limits', 'reserved', 'known'):
        _keys(value[key], domains, 'logical cost ' + key)
        for amount in value[key].values():
            _integer(amount, 1 if key == 'limits' else 0, 'logical cost ' + key)
    for domain in domains:
        _require(value['known'][domain] <= value['reserved'][domain] <= value['limits'][domain],
                 'logical cost ordering')
    pending = dict.fromkeys(domains, 0)
    for row in _sequence(value['unknown_reservations'], 'unknown reservations'):
        _require(type(row) is list and len(row) == 2 and
                 type(row[0]) is str and row[0] in domains, 'unknown reservation tuple')
        pending[row[0]] += _integer(row[1], 0, 'unknown reservation')
    for domain in domains:
        _require(pending[domain] <= value['reserved'][domain] - value['known'][domain],
                 'unknown reservation accounting')
    _require(value['native_costs'] == 'not_observed_by_controller', 'original logical cost scope')


def _result(raw, pin, member_bytes, total_bytes):
    _limits(member_bytes, total_bytes)
    _pin(pin, member_bytes)
    _require(pin['name'] == 'RESULT_MANIFEST.json' and pin['bytes'] <= total_bytes,
             'terminal manifest pin/name/total')
    result = _decode(raw, pin, member_bytes)
    _keys(result, {'profile', 'status', 'products', 'unavailable', 'structural_controls',
                  'scientific_qualification', 'native_qualification', 'cost_before_publication'},
          'RESULT_MANIFEST')
    _require(result['profile'] == 'corrected_methods_v1', 'corrected profile')
    _require(result['scientific_qualification'] is False and result['native_qualification'] is False,
             'original serializer has no scientific/native qualification')
    _cost(result['cost_before_publication'])
    planned = {key for person in PARTICIPANTS for key in participant_products(person)}
    planned_names = set(planned_family_names())
    missing, participant_unavailable, group_unavailable = set(), [], {}
    for row in _sequence(result['unavailable'], 'RESULT unavailable'):
        _require(type(row) is dict, 'unavailable row object')
        if 'participant' in row:
            _keys(row, {'participant', 'endpoint', 'reason', 'planned_cells', 'reason_counts'},
                  'participant unavailable')
            person, endpoint = row['participant'], row['endpoint']
            _require(type(person) is str and person in PARTICIPANTS and
                     type(endpoint) is str and endpoint in
                     {'theoretical_null/' + c for c in CONDITIONS},
                     'only original theoretical participant absence')
            _require(row['reason'] == 'complete observed theoretical support unavailable',
                     'participant unavailable reason')
            count = _integer(row['planned_cells'], 1, 'planned theoretical cells')
            _reason_counts(row['reason_counts'], 'participant reason counts')
            _require(count % 141 == 0 and sum(row['reason_counts'].values()) == count and
                     any(k != 'supported' for k in row['reason_counts']),
                     'participant full theoretical counts')
            key = ProductKey(person, 'sound', 'theoretical_null', endpoint.split('/')[1], 'accuracy')
            _require(key not in missing, 'duplicate participant unavailable')
            missing.add(key)
            participant_unavailable.append(row)
        else:
            _keys(row, {'endpoint', 'status', 'reason', 'dependencies', 'subjects_required'},
                  'RESULT group unavailable')
            name = row['endpoint']
            _require(type(name) is str and name in planned_names and name not in group_unavailable,
                     'known unique group unavailable endpoint')
            disposition = {k: v for k, v in row.items() if k != 'endpoint'}
            _unavailable_row(disposition)
            group_unavailable[name] = disposition
    _require(result['status'] == ('partial_scientific_support_unqualified'
             if result['unavailable'] else 'source_run_returned_unqualified'), 'terminal status')
    coverage_names = {'coverage_' + p + '.json' for p in PARTICIPANTS}
    fixed_names = coverage_names | {'GROUP_INDEX.json', 'group_oof_confusion.npz'} | {
        figure + '.pdf' for figure in FIGURES}
    possible_group = {'group_comparison_' + str(i).zfill(3) + '.npz' for i in range(52)} | {
        'group_BF10_' + str(i) + '.npz' for i in range(3)}
    files, product_rows, total = {}, {}, pin['bytes']
    for row in _sequence(result['products'], 'RESULT products'):
        _require(type(row) is dict, 'manifest file object')
        descriptor = _pin(row, member_bytes, product='key' in row)
        name = descriptor['name']
        _require(name not in files and name != pin['name'], 'unique nonrecursive file manifest')
        if 'key' in row:
            values = _sequence(row['key'], 'product key')
            _require(len(values) == 5 and all(type(x) is str for x in values), 'five product identities')
            key = ProductKey(*values)
            _require(key in planned and name == product_name(key) and key not in product_rows,
                     'original product identity/basename')
            product_rows[key] = row
        else:
            _require(name in fixed_names | possible_group, 'unrecognized output family')
        files[name] = descriptor
        total += descriptor['bytes']
        _require(total <= total_bytes, 'complete declared output exceeds total limit')
    _require(set(product_rows) == planned - missing, 'all planned participant products or exact theoretical absence')
    _require(fixed_names.issubset(files), 'all 33 coverage files, group index/confusion and six figures')
    metadata = [files['GROUP_INDEX.json']] + [files['coverage_' + p + '.json'] for p in PARTICIPANTS]
    return {'manifest': result, 'files': files, 'product_rows': product_rows,
            'missing': missing, 'participant_unavailable': participant_unavailable,
            'group_unavailable': group_unavailable, 'metadata_requests': metadata,
            'declared_total_bytes': total}


def inspect_result(result_raw, result_pin, *, member_bytes, total_bytes):
    """Authenticate terminal metadata and request exactly GROUP_INDEX +33 files.

    Explicit caps include RESULT_MANIFEST itself. Pins describe the exact bytes
    to capture, not verified disk observations. No payload requests are released
    at this stage. Admission is completed by validate_metadata on actual captures.
    """
    parsed = _result(result_raw, result_pin, member_bytes, total_bytes)
    return {'metadata_requests': parsed['metadata_requests'],
            'declared_files': list(parsed['files'].values()),
            'declared_total_bytes': parsed['declared_total_bytes']}


def _identity(row):
    _keys(row, _IDENTITY_KEYS, 'random structural metadata')
    _require(row['kind'] == 'same_original_random_recording' and _sha(row['input_sha256']) and
             row['support_checked'] == 'exact events/original-samples/labels/data/times' and
             row['fit_route'] == 'paired_condition_random', 'random structural literals')
    indices = _sequence(row['event_indices'], 'random selected event indices')
    _require(indices, 'nonempty structural selection')
    for index in indices:
        _integer(index, 0, 'selected event')
    _require(len(indices) == len(set(indices)), 'unique structural selected events')


def _coverage(raw, pin, person, member_bytes):
    value = _decode(raw, pin, member_bytes)
    _keys(value, {'participant', 'coverage', 'structural_random'}, 'coverage file')
    _require(value['participant'] == person, 'coverage participant join')
    _keys(value['coverage'], {'theoretical_coverage/' + c for c in CONDITIONS}, 'all theoretical conditions')
    _keys(value['structural_random'], {'structural_random/sound', 'structural_random/omission'},
          'both random structural records')
    for row in value['structural_random'].values():
        _identity(row)
    _require(value['structural_random']['structural_random/sound']['input_sha256'] ==
             value['structural_random']['structural_random/omission']['input_sha256'],
             'same original random recording for both stimuli')
    absent = []
    for condition in CONDITIONS:
        folds = _sequence(value['coverage']['theoretical_coverage/' + condition], 'five theoretical folds')
        _require(len(folds) == 5, 'exact five theoretical folds')
        complete, planned, counts = True, 0, {}
        # A target is a member of exactly one original cross-validation test fold.
        # Reasons expose only unsupported targets; supported targets are not
        # reconstructed from these reduced coverage summaries.
        previous_targets = set()
        for row in folds:
            _keys(row, {'complete', 'planned_cells', 'reason_counts', 'reasons'}, 'fold coverage')
            _require(type(row['complete']) is bool, 'fold complete type')
            number = _integer(row['planned_cells'], 1, 'fold planned cells')
            _require(number % 141 == 0, 'all 141 test offsets per planned target')
            _reason_counts(row['reason_counts'], 'fold reason counts')
            _require(sum(row['reason_counts'].values()) == number, 'fold count sum')
            reasons = _sequence(row['reasons'], 'all unsupported cells')
            seen, observed, targets = set(), {}, set()
            for reason in reasons:
                _keys(reason, {'target_event', 'test_offset_samples', 'context_event', 'reason'},
                      'unsupported cell')
                target = _integer(reason['target_event'], 0, 'target event')
                offset = reason['test_offset_samples']
                _require(type(offset) is int and -70 <= offset <= 70, 'test offset')
                category = reason['reason']
                _require(type(category) is str and category in _REASONS, 'unsupported category')
                if category == 'no_actual_bracketing_onsets':
                    _require(reason['context_event'] is None, 'unbracketed context is absent')
                else:
                    _integer(reason['context_event'], 0, 'observed context event')
                _require((target, offset) not in seen, 'unique planned unsupported cell')
                seen.add((target, offset))
                targets.add(target)
                observed[category] = observed.get(category, 0) + 1
            _require(observed == {k: v for k, v in row['reason_counts'].items() if k != 'supported'},
                     'every unsupported cell retained')
            _require(row['complete'] is (not reasons), 'fold disposition/reasons')
            _require(len(targets) <= number // 141 and not (targets & previous_targets),
                     'unsupported targets within distinct original folds')
            previous_targets.update(targets)
            complete = complete and row['complete']
            planned += number
            for category, count in row['reason_counts'].items():
                counts[category] = counts.get(category, 0) + count
        if not complete:
            absent.append({'participant': person, 'endpoint': 'theoretical_null/' + condition,
                           'reason': 'complete observed theoretical support unavailable',
                           'planned_cells': planned, 'reason_counts': counts})
    return value, absent


def _absence(reason, dependencies=()):
    return {'status': 'unavailable', 'reason': reason, 'dependencies': list(dependencies),
            'subjects_required': 33}


def _group_absences(unavailable, missing):
    """Admit only the original dependency graph, without computing correlations."""
    _require(type(unavailable) is dict, 'group unavailable object')
    planned = set(planned_family_names())
    _require(set(unavailable).issubset(planned), 'planned group unavailable identities')
    for row in unavailable.values():
        _unavailable_row(row)
    theory_missing = [c for c in CONDITIONS if any(
        ProductKey(p, 'sound', 'theoretical_null', c, 'accuracy') in missing for p in PARTICIPANTS)]
    required = {}
    for condition in theory_missing:
        for name in ('accuracy/sound/theoretical_null/' + condition,
                     'accuracy_difference/sound/theoretical/' + condition):
            required[name] = _absence('one or more complete subject theoretical endpoints unavailable',
                                      ('theoretical_null/' + condition,))
    theory_fisher = 'fisher/sound/theoretical_null'
    if theory_missing:
        required[theory_fisher] = _absence('complete four-condition theoretical support unavailable',
                                          ['theoretical_null/' + c for c in theory_missing])
    intrinsic = {'fisher/' + stim + '/' + pipeline
                 for stim in ('sound', 'omission') for pipeline in ('replication', 'empirical_null')}
    intrinsic.update('fisher/sound/' + pipeline + '/most_likely'
                     for pipeline in ('replication', 'empirical_null'))
    if not theory_missing:
        intrinsic.add(theory_fisher)
    for name in intrinsic:
        if name in unavailable:
            row = unavailable[name]
            _require(row['reason'] in _FISHER_REASONS and row['dependencies'] == [],
                     'original Fisher-domain absence')
            required[name] = row
    differences = {
        'fisher_difference/sound/empirical': ('fisher/sound/replication', 'fisher/sound/empirical_null'),
        'fisher_difference/omission/empirical': ('fisher/omission/replication', 'fisher/omission/empirical_null'),
        'fisher_difference/sound/theoretical': ('fisher/sound/replication', theory_fisher),
        'fisher_difference/sound/most_likely_empirical': (
            'fisher/sound/replication/most_likely', 'fisher/sound/empirical_null/most_likely'),
    }
    for name, operands in differences.items():
        dependencies = [operand for operand in operands if operand in required]
        if dependencies:
            required[name] = _absence('required complete Fisher endpoint unavailable', dependencies)
    _require(unavailable == required, 'exact original theoretical/Fisher dependency dispositions')


def _structural(value, coverages):
    _keys(value, set(_STRUCTURAL), 'exact two structural controls')
    for stimulus, name in zip(('sound', 'omission'), _STRUCTURAL):
        expected = {
            'status': 'structural_identity_null',
            'reason': 'identical random recording, selected support, paired fits and actual products',
            'subjects': 33,
            'coverage': [{'participant': person,
                          **coverages[person]['structural_random']['structural_random/' + stimulus]}
                         for person in PARTICIPANTS],
            'inference': None, 't': None, 'p': None, 'BF10': None,
            'interpretation': 'construction identity control, not evidence for a scientific null',
        }
        _require(_same(value[name], expected),
                 'structural disposition and all 33 exact coverage joins')


def _group(value, parsed, coverages, member_bytes):
    _keys(value, {'comparisons', 'BF10_names', 'policy', 'unavailable', 'structural_controls', 'products'},
          'GROUP_INDEX')
    _group_absences(value['unavailable'], parsed['missing'])
    _require(value['unavailable'] == parsed['group_unavailable'], 'RESULT/GROUP unavailability join')
    comparisons = _names(value['comparisons'], 'available comparisons')
    _require(comparisons == [name for name in planned_family_names() if name not in value['unavailable']],
             'complete sorted planned 52 comparison dispositions')
    bayes = _names(value['BF10_names'], 'available BF10')
    _require(bayes == [name for name in _BAYES if name in comparisons], 'all three BF10 dispositions')
    _structural(value['structural_controls'], coverages)
    _require(_same(value['structural_controls'], parsed['manifest']['structural_controls']),
             'RESULT/GROUP structural join')
    policy = value['policy']
    _keys(policy, {'fixed_seed', 'subjects', 'correlation', 'contrast', 'BF', 'cluster_family',
                  'available_cluster_maps', 'structural_control_maps', 'BF10_planned', 'BF10_available',
                  'BF10_unavailable', 'unavailable_cluster_maps', 'cross_map_FWER', 'historical_parity'},
          'group policy')
    seed = _integer(policy['fixed_seed'], 0, 'fixed seed')
    _require(seed < 2**32, 'original fixed seed range')
    expected = {
        'fixed_seed': seed, 'subjects': 33, 'correlation': 'Pearson ordinal predictability',
        'contrast': 'paired difference of Fisher z; never correlation of accuracy difference',
        'BF': 'BF10 Cauchy scale sqrt(2)/2', 'cluster_family': list(planned_family_names()),
        'available_cluster_maps': [name for name in comparisons if name not in _STRUCTURAL],
        'structural_control_maps': list(_STRUCTURAL), 'BF10_planned': list(_BAYES),
        'BF10_available': bayes,
        'BF10_unavailable': {name: value['unavailable'][name] for name in _BAYES if name not in bayes},
        'unavailable_cluster_maps': value['unavailable'], 'cross_map_FWER': 'not claimed',
        'historical_parity': False,
    }
    _require(_same(policy, expected),
             'unchanged full group policy')
    group_rows = _sequence(value['products'], 'GROUP products')
    expected_names = ['group_comparison_' + str(i).zfill(3) + '.npz' for i in range(len(comparisons))]
    expected_names += ['group_BF10_' + str(i) + '.npz' for i in range(len(bayes))]
    expected_names.append('group_oof_confusion.npz')
    _require(len(group_rows) == len(expected_names), 'complete group NPZ family')
    for row, name in zip(group_rows, expected_names):
        pin = _pin(row, member_bytes)
        _require(pin['name'] == name and parsed['files'].get(name) == pin, 'group index order/pin join')
    return comparisons, bayes, expected_names


def _request(pin, kind, *, npz_members=None, **metadata):
    request = {**pin, 'kind': kind, **metadata}
    if npz_members is not None:
        request['npz_members'] = [name + '.npy' for name in npz_members]
    return request


def validate_metadata(result_raw, result_pin, group_raw, coverage_bodies, *,
                      member_bytes, total_bytes, actual_names):
    """Join exact captured metadata, then return the complete payload capture list.

    coverage_bodies is {coverage basename: exact bytes}, exactly 33 entries.
    actual_names is the caller's observed complete output namespace, including
    RESULT_MANIFEST; this function does not inspect its filesystem or certify the
    observation. Every NPZ/PDF must subsequently be captured to its returned pin
    before any protected reference opens. NPZ members below are requirements for
    that later decoder, not observations made by this metadata-only function.
    """
    parsed = _result(result_raw, result_pin, member_bytes, total_bytes)
    _require(type(actual_names) in (list, tuple) and all(type(x) is str for x in actual_names),
             'actual namespace names')
    _require(len(actual_names) == len(set(actual_names)) and
             set(actual_names) == set(parsed['files']) | {'RESULT_MANIFEST.json'},
             'closed complete namespace, no extra or duplicate files')
    coverage_names = {'coverage_' + p + '.json' for p in PARTICIPANTS}
    _keys(coverage_bodies, coverage_names, 'exact captured coverage bodies')
    coverages, participant_absent = {}, []
    for person in PARTICIPANTS:
        name = 'coverage_' + person + '.json'
        coverage, absent = _coverage(coverage_bodies[name], parsed['files'][name], person, member_bytes)
        coverages[person] = coverage
        participant_absent.extend(absent)
    _require(participant_absent == parsed['participant_unavailable'], 'exact all-fold participant dispositions')
    group = _decode(group_raw, parsed['files']['GROUP_INDEX.json'], member_bytes)
    comparisons, bayes, group_names = _group(group, parsed, coverages, member_bytes)
    expected_result_absent = participant_absent + [
        {'endpoint': name, **group['unavailable'][name]} for name in sorted(group['unavailable'])]
    _require(parsed['manifest']['unavailable'] == expected_result_absent, 'original complete unavailable order')
    all_payload = set(group_names) | {figure + '.pdf' for figure in FIGURES} | {
        product_name(key) for key in parsed['product_rows']}
    _require(set(parsed['files']) == all_payload | coverage_names | {'GROUP_INDEX.json'},
             'no extra comparison, BF10 or payload slots')
    requests, keys = [], []
    for person in PARTICIPANTS:
        for key in participant_products(person):
            if key in parsed['missing']:
                continue
            values = _key_values(key)
            keys.append(values)
            requests.append(_request(parsed['files'][product_name(key)], 'participant_npz', key=values,
                                     npz_members=('value', 'train_times', 'test_times')))
    comparison_dispositions = []
    for name in planned_family_names():
        if name in group['unavailable']:
            comparison_dispositions.append({'name': name, **group['unavailable'][name]})
            continue
        index = comparisons.index(name)
        output = 'group_comparison_' + str(index).zfill(3) + '.npz'
        structural = name in _STRUCTURAL
        members = (('subject_values', 'train_times', 'test_times') if structural else
                   ('subject_values', 't', 'cluster_masks', 'cluster_p', 'null_max', 'train_times', 'test_times'))
        requests.append(_request(parsed['files'][output], 'group_comparison_npz', comparison=name,
                                 npz_members=members))
        disposition = {'name': name, 'status': 'structural_identity_null' if structural else 'available',
                       'output': output}
        if structural:
            disposition['metadata'] = group['structural_controls'][name]
        comparison_dispositions.append(disposition)
    bayes_dispositions = []
    for name in _BAYES:
        if name not in bayes:
            bayes_dispositions.append({'name': name, **group['unavailable'][name]})
        else:
            output = 'group_BF10_' + str(bayes.index(name)) + '.npz'
            requests.append(_request(parsed['files'][output], 'BF10_npz', comparison=name,
                                     npz_members=('BF10', 'train_times', 'test_times')))
            bayes_dispositions.append({'name': name, 'status': 'available', 'output': output})
    requests.append(_request(parsed['files']['group_oof_confusion.npz'], 'averaged_confusion_npz',
                             npz_members=('value', 'train_times', 'test_times')))
    for figure in FIGURES:
        requests.append(_request(parsed['files'][figure + '.pdf'], 'figure_pdf', figure=figure))
    return {'capture_requests': requests, 'product_keys': keys,
            'comparison_dispositions': comparison_dispositions, 'BF10_dispositions': bayes_dispositions,
            'figures': [figure + '.pdf' for figure in FIGURES],
            'unavailable': expected_result_absent,
            'fixed_seed': group['policy']['fixed_seed'],
            'declared_total_bytes': parsed['declared_total_bytes']}
