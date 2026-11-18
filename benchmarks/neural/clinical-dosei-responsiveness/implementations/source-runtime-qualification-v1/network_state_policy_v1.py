"""Pure proposed state condition; no I/O, adoption, or runtime qualification.

The caller must authenticate TrustedBindings and the host attestation outside
participant control. Matching hashes and constructing this record do not create
authenticity. This module checks consistency and the stated proposed condition.
"""
from collections import namedtuple
import hashlib
import json
import math
import re

PROOF_CAP = 262144
ATTESTATION_CAP = 16384
RESULT_CAP = 8192
PROBE_SHA256 = 'f513ed96f8598d5693fa2dc4e2589d18bc5b92f14ea6d88be7f58311e76f3848'
PROFILE_SHA256 = 'c1830439a06254a982279604d645de5969c3444260e74262f7ad0efc7bc3129b'
IMAGE_ID = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
IFF_UP, IFF_LOOPBACK = 1, 8
IF_OPER_UNKNOWN, IF_OPER_DOWN, IF_OPER_UP = 0, 2, 6
SCHEDULE = ('links_before', 'addresses_ipv4', 'addresses_ipv6',
            'routes_ipv4', 'routes_ipv6', 'links_after')
STABLE_FIELDS = ('index', 'name', 'type', 'flags', 'operstate', 'MTU')
STATUS_KEYS = ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb', 'NoNewPrivs', 'Seccomp')
TrustedBindings = namedtuple('TrustedBindings', (
    'proof_sha256 custody_review_sha256 source_protocol_sha256 probe_sha256 '
    'profile_sha256 image_id host_attestation_sha256 context_id container_id'))
HOST_KEYS = {'schema', 'proof_sha256', 'custody_review_sha256', 'source_protocol_sha256',
             'probe_sha256', 'profile_sha256', 'image_id', 'context_id', 'container_id',
             'inspected_configuration', 'originals'}
ROLE_SUFFIXES = {
    'image_inspection': '-command_output_prefix.bin',
    'initial_container_inspection': '-command_output_prefix.bin',
    'final_container_inspection': '-command_output_prefix.bin',
    'remove_receipt': '-command_receipt.bin',
    'absence_receipt': '-command_receipt.bin',
    'context_close': '-code_close.bin',
}
LIMITS = (
    'Caller authentication of host bindings is required; hashes alone provide no authority.',
    'Six sequential dumps are not an atomic snapshot or a later-state guarantee.',
    'No policy-routing rules, firewall rules, other namespaces, or all communication mechanisms are proved.',
    'Seccomp mode is checked; filter contents and future hostile-code safety are not proved.',
    'Route priority, cache, and preference payload values are not decoded; only their descriptors are checked.',
    'Unknown link attributes remain opaque; only selected link-state fields determine this condition.',
    'Original process-status body and live timing are not independently remeasured.',
)


class Refusal(Exception):
    """Fixed bounded reason; no participant or host text is reflected."""


def require(ok, reason):
    if not ok:
        raise Refusal(reason)


def integer(value, low=0, high=2**32-1):
    require(type(value) is int and low <= value <= high, 'integer_type_or_range')
    return value


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
            'digest_encoding')
    return value


def text(value, maximum):
    require(type(value) is str and 0 < len(value.encode('utf-8')) <= maximum and
            '\x00' not in value, 'bounded_text_required')
    return value


def keys(value, expected, reason):
    require(type(value) is dict and set(value) == set(expected), reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def decode(raw, cap):
    require(type(raw) is bytes and 0 < len(raw) <= cap, 'input_byte_cap_or_type')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def nonfinite(_):
        raise Refusal('nonfinite_json')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=nonfinite)
    pending = [(value, 0)]; count = 0
    while pending:
        item, depth = pending.pop(); count += 1
        require(count <= 50000 and depth <= 32, 'json_structure_cap')
        if type(item) is dict:
            pending.extend((part, depth+1) for part in item.values())
        elif type(item) is list:
            pending.extend((part, depth+1) for part in item)
        elif type(item) is float:
            require(math.isfinite(item), 'nonfinite_json')
    require(type(value) is dict, 'json_object_required')
    return value


def binding(value, maximum=4*1024**2):
    keys(value, ('bytes', 'sha256'), 'binding_shape')
    integer(value['bytes'], 0, maximum); digest(value['sha256'])
    return value


def authority(proof_raw, host_raw, trusted):
    require(type(trusted) is TrustedBindings, 'trusted_binding_record_required')
    for name in ('proof_sha256', 'custody_review_sha256', 'source_protocol_sha256',
                 'probe_sha256', 'profile_sha256', 'host_attestation_sha256',
                 'context_id', 'container_id'):
        digest(getattr(trusted, name))
    require(type(trusted.image_id) is str and trusted.image_id == IMAGE_ID and
            trusted.probe_sha256 == PROBE_SHA256 and trusted.profile_sha256 == PROFILE_SHA256,
            'unsupported_source_profile_or_image')
    require(type(proof_raw) is bytes and 0 < len(proof_raw) <= PROOF_CAP and
            type(host_raw) is bytes and 0 < len(host_raw) <= ATTESTATION_CAP,
            'input_byte_cap_or_type')
    require(hashlib.sha256(proof_raw).hexdigest() == trusted.proof_sha256 and
            hashlib.sha256(host_raw).hexdigest() == trusted.host_attestation_sha256,
            'stale_or_unbound_input')
    proof = decode(proof_raw, PROOF_CAP); host = decode(host_raw, ATTESTATION_CAP)
    keys(host, HOST_KEYS, 'host_attestation_shape')
    require(host['schema'] == 'dosei_proposed_network_host_attestation_v1', 'host_schema')
    for name in HOST_KEYS-{'schema', 'inspected_configuration', 'originals'}:
        require(type(host[name]) is str and host[name] == getattr(trusted, name),
                'host_binding_mismatch')
    configuration = host['inspected_configuration']
    keys(configuration, ('network_mode', 'cap_drop', 'no_new_privileges', 'image_id'),
         'inspected_configuration_shape')
    require(configuration['network_mode'] == 'none' and
            configuration['cap_drop'] == ['ALL'] and configuration['no_new_privileges'] is True and
            configuration['image_id'] == trusted.image_id, 'host_configuration_mismatch')
    require(proof['schema'] == 'dosei_saved_network_diagnostic_review_v1' and
            proof['status'] == 'verified_diagnostic_collection' and proof['failure'] is None and
            proof['native_status'] == 'succeeded' and proof['network_qualified'] is False and
            proof['historical_qualification_status'] == 'failed', 'incomplete_or_incompatible_proof')
    for name, expected in (('qualified_runtime_controls', 0), ('required_runtime_controls', 6),
                           ('executed_candidate_calls', 1), ('verified_owned_container_lifecycles', 1),
                           ('verified_CLI_commands', 8), ('context_close_originals', 1)):
        require(integer(proof[name], 0, 8) == expected, 'proof_population_or_closure')
    require(proof['protocol_sha256'] == trusted.source_protocol_sha256 and
            proof['prior_failed_qualification_results_preserved'] is True and
            proof['network_semantics_reinterpreted'] is False, 'proof_source_or_scope')
    native = proof['native_record']
    require(type(native) is dict and native['status'] == 'succeeded' and
            type(native['exit_code']) is int and native['exit_code'] == 0 and
            native['protocol']['sha256'] == trusted.source_protocol_sha256,
            'native_protocol_or_exit')
    binding(proof['candidate_output_original'], 262144)
    files = proof['saved_file_bindings']
    require(type(files) is dict and 1 <= len(files) <= 256, 'saved_bindings_shape')
    for name, item in files.items():
        text(name, 256); binding(item)
    originals = host['originals']; keys(originals, ROLE_SUFFIXES, 'host_original_roles')
    used = set()
    for role, suffix in ROLE_SUFFIXES.items():
        item = originals[role]; keys(item, ('name', 'bytes', 'sha256'), 'host_original_shape')
        name = item['name']; text(name, 256)
        require(re.fullmatch('evidence/[0-9]{4}'+re.escape(suffix), name) is not None and
                name not in used and name in files, 'original_role_or_reference')
        b = binding({key: item[key] for key in ('bytes', 'sha256')})
        require(canonical(files[name]) == canonical(b), 'original_binding_mismatch')
        used.add(name)
    return proof


def attributes(record, first_offset, *, allowed=None):
    keys(record, ('parsed', 'attributes', 'raw_frame', 'datagram', 'offset'), 'record_shape')
    size = binding(record['raw_frame'], 65536)['bytes']
    require(size >= first_offset and size % 4 == 0, 'frame_extent')
    integer(record['datagram'], 0, 127); integer(record['offset'], 0, 65536)
    require(record['offset'] % 4 == 0 and record['offset']+size <= 65536, 'datagram_extent')
    values = record['attributes']
    require(type(values) is list and len(values) <= 128, 'attribute_count')
    result = {}; cursor = first_offset
    for item in values:
        keys(item, ('offset', 'length', 'type_raw', 'type', 'nested', 'network_byteorder'),
             'attribute_shape')
        offset = integer(item['offset'], first_offset, 65536)
        length = integer(item['length'], 4, 65535)
        kind = integer(item['type'], 0, 16383); raw_kind = integer(item['type_raw'], 0, 65535)
        require(type(item['nested']) is bool and type(item['network_byteorder']) is bool and
                kind == raw_kind & 0x3fff and item['nested'] == bool(raw_kind & 0x8000) and
                item['network_byteorder'] == bool(raw_kind & 0x4000), 'attribute_flag_encoding')
        require(offset == cursor and offset+(length+3)//4*4 <= size, 'attribute_extent')
        cursor += (length+3)//4*4
        require(kind not in result, 'duplicate_attribute')
        if allowed is not None:
            require(kind in allowed and item['nested'] is False and
                    item['network_byteorder'] is False, 'unsupported_attribute_or_flags')
        result[kind] = item
    require(cursor == size, 'attribute_coverage')
    return result


def width(attrs, kind, length, *, required=True):
    if kind not in attrs:
        require(not required, 'missing_selected_attribute'); return
    require(attrs[kind]['length'] == length and attrs[kind]['nested'] is False and
            attrs[kind]['network_byteorder'] is False, 'selected_attribute_shape')


def links(rows):
    require(type(rows) is list and 1 <= len(rows) <= 64, 'link_count')
    result = {}; names = set()
    for row in rows:
        attrs = attributes(row, 32); p = row['parsed']
        keys(p, ('family', 'pad', 'type', 'index', 'flags', 'change', 'name', 'operstate', 'MTU'),
             'link_parsed_shape')
        require(integer(p['family'], 0, 255) == 0 and integer(p['pad'], 0, 255) == 0,
                'link_header')
        index = integer(p['index'], 1, 2**31-1); name = text(p['name'], 15)
        require(index not in result and name not in names, 'duplicate_link_identity')
        integer(p['type'], 0, 65535); integer(p['flags']); integer(p['change'])
        integer(p['operstate'], 0, 6); integer(p['MTU'], 1)
        width(attrs, 3, 5+len(name.encode('utf-8'))); width(attrs, 4, 8); width(attrs, 16, 5)
        result[index] = p; names.add(name)
    return result


def address_value(raw, family):
    width_bytes = 4 if family == 2 else 16
    require(type(raw) is str and re.fullmatch('[0-9a-f]{'+str(width_bytes*2)+'}', raw) is not None,
            'address_encoding')
    return int(raw, 16)


def loopback_address(raw, family, prefix):
    value = address_value(raw, family)
    integer(prefix, 0, 32 if family == 2 else 128)
    if family == 2:
        require(value >> 24 == 127 and prefix >= 8, 'nonloopback_address_or_prefix')
    else:
        require(value == 1 and prefix == 128, 'nonloopback_address_or_prefix')
    return value


def addresses(rows, family, loop_index):
    require(type(rows) is list and len(rows) <= 256, 'address_count')
    for row in rows:
        attrs = attributes(row, 24, allowed={1, 2, 3, 6, 8, 11}); p = row['parsed']
        keys(p, ('family', 'index', 'prefix_length', 'flags_header', 'scope', 'flags_attribute',
                 'address_hex', 'local_hex'), 'address_parsed_shape')
        require(integer(p['family'], 0, 255) == family and integer(p['index'], 1) == loop_index,
                'nonloopback_address_interface')
        require(integer(p['scope'], 0, 255) == 254, 'unsupported_address_scope')
        integer(p['flags_header'], 0, 255)
        loopback_address(p['address_hex'], family, p['prefix_length'])
        width(attrs, 1, 8 if family == 2 else 20)
        require((2 in attrs) == (p['local_hex'] is not None), 'local_address_attribute_parity')
        if p['local_hex'] is not None:
            loopback_address(p['local_hex'], family, p['prefix_length'])
            require(p['local_hex'] == p['address_hex'], 'peer_address_not_supported')
            width(attrs, 2, 8 if family == 2 else 20)
        if 3 in attrs:
            require(6 <= attrs[3]['length'] <= 20, 'address_label_descriptor')
        for kind, length in ((6, 20), (8, 8), (11, 5)):
            width(attrs, kind, length, required=False)
        require((8 in attrs) == (p['flags_attribute'] is not None), 'address_flags_attribute_parity')
        if p['flags_attribute'] is not None:
            require(integer(p['flags_attribute']) & 255 == p['flags_header'], 'address_flag_parity')


def routes(rows, family, loop_index):
    require(type(rows) is list and len(rows) <= 256, 'route_count')
    allowed = {15, 1, 7, 4} if family == 2 else {15, 1, 6, 4, 12, 20}
    for row in rows:
        attrs = attributes(row, 28, allowed=allowed); p = row['parsed']
        keys(p, ('family', 'destination_prefix_length', 'source_prefix_length', 'tos', 'table_header',
                 'table_attribute', 'table_effective', 'protocol', 'scope', 'type', 'flags',
                 'output_interface_index', 'input_interface_index', 'destination_hex', 'source_hex',
                 'gateway_hex', 'preferred_source_hex'), 'route_parsed_shape')
        require(integer(p['family'], 0, 255) == family, 'route_family')
        require(integer(p['output_interface_index'], 1) == loop_index, 'nonloopback_route_interface')
        require(integer(p['table_effective']) == 255 and integer(p['table_attribute']) == 255 and
                integer(p['table_header'], 0, 255) in (0, 255), 'nonlocal_route_table')
        require(integer(p['source_prefix_length'], 0, 128) == 0 and integer(p['tos'], 0, 255) == 0 and
                integer(p['flags']) == 0 and p['input_interface_index'] is None and p['source_hex'] is None and
                p['gateway_hex'] is None, 'source_input_gateway_or_flag_dependent_route')
        integer(p['protocol'], 0, 255)
        destination = loopback_address(p['destination_hex'], family, p['destination_prefix_length'])
        prefix = p['destination_prefix_length']; bits = 32 if family == 2 else 128
        require(destination & ((1 << (bits-prefix))-1) == 0, 'noncanonical_route_network')
        kind = integer(p['type'], 0, 255); scope = integer(p['scope'], 0, 255)
        require(kind == 2 or (family == 2 and kind == 3 and prefix == 32), 'unsupported_route_type')
        require(scope in ((254,) if family == 2 and kind == 2 else
                          (253,) if family == 2 else (0, 254)), 'unsupported_route_scope')
        width(attrs, 15, 8); width(attrs, 4, 8); width(attrs, 1, 8 if family == 2 else 20)
        require((7 in attrs) == (p['preferred_source_hex'] is not None), 'preferred_source_attribute_parity')
        if p['preferred_source_hex'] is not None:
            loopback_address(p['preferred_source_hex'], family, 32 if family == 2 else 128)
            width(attrs, 7, 8 if family == 2 else 20)
        # These known observational metadata payloads are not in the parsed view.
        # Validate their complete descriptors, without claiming value decoding.
        for attr, length in ((6, 8), (12, 36), (20, 5)):
            width(attrs, attr, length, required=False)


def process_status(value):
    keys(value, ('selected_raw_lines', 'selected_values', 'source_bytes', 'source_sha256',
                 'EOF_observed', 'capability_policy_inferred'), 'process_status_shape')
    require(value['EOF_observed'] is True and value['capability_policy_inferred'] is False,
            'incomplete_process_status')
    integer(value['source_bytes'], 1, 16384); digest(value['source_sha256'])
    lines, values = value['selected_raw_lines'], value['selected_values']
    keys(lines, STATUS_KEYS, 'process_status_fields'); keys(values, STATUS_KEYS, 'process_status_fields')
    for key in STATUS_KEYS:
        line, number = text(lines[key], 128), text(values[key], 64)
        require(line.isascii() and '\n' not in line and '\r' not in line and
                line.partition(':')[0] == key and line.partition(':')[2].strip() == number,
                'process_status_line_parity')
        pattern = '[0-9a-fA-F]{1,64}' if key.startswith('Cap') else '[0-9]{1,10}'
        require(re.fullmatch(pattern, number) is not None, 'process_status_encoding')
        expected = 0 if key.startswith('Cap') else 1 if key == 'NoNewPrivs' else 2
        require(int(number, 16 if key.startswith('Cap') else 10) == expected, 'process_security_condition')


def state_condition(proof):
    state = proof['state_view']
    require(type(state) is dict, 'state_shape')
    for key, expected in (('raw_netlink_frames_reparsed', True), ('reparse_uses_live_adapters', False),
                          ('original_full_proc_status_rehashed', False), ('probe_timing_not_independently_remeasured', True),
                          ('network_qualified', False), ('atomic_snapshot', False), ('routing_rules_collected', False),
                          ('firewall_rules_collected', False), ('unknown_attribute_descriptors_preserved', True),
                          ('no_network_safety_predicate_applied', True)):
        require(state[key] is expected, 'incomplete_or_unsupported_state_scope')
    integer(state['saved_datagram_bytes'], 1, 1048576)
    require(state['link_stability_fields'] == list(STABLE_FIELDS), 'stability_field_scope')
    rows = state['state_records']
    require(type(rows) is list and len(rows) == 6, 'six_complete_dump_views_required')
    for row, name in zip(rows, SCHEDULE):
        keys(row, ('name', 'records'), 'dump_view_shape')
        require(row['name'] == name, 'dump_view_order')
    before = links(rows[0]['records']); after = links(rows[5]['records'])
    project = lambda values: [[values[i][key] for key in STABLE_FIELDS] for i in sorted(values)]
    require(canonical(project(before)) == canonical(project(after)), 'unstable_link_state')
    expected_names = [[i, before[i]['name']] for i in sorted(before)]
    for name in ('if_nameindex_before', 'if_nameindex_after'):
        value = state[name]
        require(type(value) is list and len(value) == len(before), 'nameindex_shape')
        for item in value:
            require(type(item) is list and len(item) == 2, 'nameindex_shape')
            integer(item[0], 1); text(item[1], 15)
        require(canonical(sorted(value)) == canonical(expected_names), 'nameindex_parity')
    loopbacks = [p for p in before.values() if p['flags'] & IFF_LOOPBACK]
    require(len(loopbacks) == 1, 'exactly_one_flagged_loopback_required')
    loop = loopbacks[0]
    require(loop['flags'] & IFF_UP and loop['operstate'] in (IF_OPER_UNKNOWN, IF_OPER_UP),
            'loopback_not_operational')
    for p in before.values():
        if p['index'] != loop['index']:
            require(not p['flags'] & IFF_UP and p['operstate'] == IF_OPER_DOWN,
                    'nonloopback_not_down')
    addresses(rows[1]['records'], 2, loop['index']); addresses(rows[2]['records'], 10, loop['index'])
    routes(rows[3]['records'], 2, loop['index']); routes(rows[4]['records'], 10, loop['index'])
    process_status(state['process_status'])
    kernel = state['uname']; keys(kernel, ('sysname', 'nodename', 'release', 'version', 'machine'), 'kernel_shape')
    require(kernel['sysname'] == 'Linux', 'unsupported_kernel_family')
    for item in kernel.values():
        text(item, 1024)
    return {'links': len(before), 'nonloopback_links': len(before)-1,
            'addresses_ipv4': len(rows[1]['records']), 'addresses_ipv6': len(rows[2]['records']),
            'routes_ipv4': len(rows[3]['records']), 'routes_ipv6': len(rows[4]['records'])}


def evaluate(proof_bytes, *, host_attestation_bytes, trusted_bindings):
    """Return a proposed match/refusal; authenticate caller authority elsewhere.

    No input is modified. The first refusal is a fixed reason, not a complete
    diagnosis. Malformed/unsupported data never upgrades historical controls.
    """
    result = {'schema': 'dosei_proposed_network_state_policy_result_v1',
              'status': 'proposed_condition_refused', 'proposed_condition_matches': False,
              'adopted': False, 'network_qualified': False, 'historical_runtime_controls_changed': False,
              'caller_authentication_required': True, 'input_bindings_consistent': False,
              'reason': None, 'counts': None, 'limits': list(LIMITS)}
    try:
        proof = authority(proof_bytes, host_attestation_bytes, trusted_bindings)
        result['input_bindings_consistent'] = True
        result['counts'] = state_condition(proof)
        result.update(status='proposed_condition_matched', proposed_condition_matches=True)
    except Refusal as error:
        result['reason'] = str(error)
    except (KeyError, ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        result['reason'] = 'malformed_or_unsupported_input'
    require(len(canonical(result)) <= RESULT_CAP, 'internal_result_cap')
    return result
