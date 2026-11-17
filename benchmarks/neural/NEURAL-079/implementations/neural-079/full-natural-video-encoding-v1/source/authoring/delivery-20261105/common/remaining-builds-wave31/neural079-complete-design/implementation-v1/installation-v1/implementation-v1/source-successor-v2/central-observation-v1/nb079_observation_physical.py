"""Prospectively selected local resource estimands, never old scalar totals."""
from nb079_observation_common import require, integer, fields, check_pin, token, bounded_encode, body_pin

CLASSES = ('preexisting', 'imported', 'shared', 'new', 'failed', 'evidence')
SEMANTICS = {
    'storage': 'cgroup_device_charged_read_write_deltas',
    'memory': 'one_common_ancestor_cgroup_charged_peak',
    'retention': 'quiescent_unique_ordinary_file_logical_inventory',
    'transfers': 'owned_endpoint_positive_return_payload_by_direction',
    'remote': 'hardware_excluded_unknown_provider_usage_asserted',
    'terminal': 'independent_finalizer_reporting_is_trusted_terminal_boundary',
}


def device(value):
    require(type(value) is str and len(value) <= 64 and value.count(':') == 1,
            'device major:minor')
    major, minor = value.split(':')
    require(major.isdecimal() and minor.isdecimal() and
            str(int(major)) == major and str(int(minor)) == minor, 'canonical device identity')
    return value


def profile(value):
    fields(value, ('schema', 'scope_id', 'semantics', 'storage_limits', 'charged_memory_limit_bytes',
                   'memory_mode', 'supplemental_memory_limits', 'retention_limits',
                   'retention_class_precedence', 'endpoint_limits', 'endpoint_owners', 'endpoint_layers', 'encoding_limits',
                   'reader_limits', 'custody_admission_pin', 'source_environment_pin',
                   'authoring_history_pin', 'comparison_profile_id'), 'complete typed profile')
    require(value['schema'] == 'ach_local_resource_profile_v1' and value['semantics'] == SEMANTICS,
            'explicit prospective estimands; no legacy physical-total mapping')
    token(value['scope_id']); token(value['comparison_profile_id'])
    for name in ('custody_admission_pin', 'source_environment_pin', 'authoring_history_pin'):
        check_pin(value[name])
    require(type(value['storage_limits']) is dict, 'explicit complete admitted storage devices')
    for name, limits in value['storage_limits'].items():
        device(name)
        fields(limits, ('read_bytes', 'write_bytes'), 'per-device storage limits')
        for x in limits.values():
            integer(x)
    integer(value['charged_memory_limit_bytes'], 1)
    require(value['memory_mode'] in ('fresh_lifetime', 'verified_same_fd_reset'), 'explicit memory interval')
    require(type(value['supplemental_memory_limits']) is dict, 'explicit supplemental native counters')
    for name, limit in value['supplemental_memory_limits'].items():
        require(name in ('memory.swap.current', 'memory.swap.peak', 'memory.zswap.current') or
                name.startswith('hugetlb.') and name.endswith('.current') and
                all(c.isascii() and (c.isalnum() or c == '.') for c in name),
                'supported named scalar memory file; arbitrary device interface refuses')
        integer(limit)
    fields(value['retention_limits'], (*CLASSES, 'total_unique_bytes', 'files'), 'all retention class ceilings')
    for x in value['retention_limits'].values():
        integer(x)
    require(type(value['retention_class_precedence']) is list and
            len(value['retention_class_precedence']) == len(CLASSES) and
            set(value['retention_class_precedence']) == set(CLASSES), 'explicit cross-class backing deduplication')
    require(type(value['endpoint_limits']) is dict and value['endpoint_limits'], 'owned endpoint roster')
    for name, limits in value['endpoint_limits'].items():
        token(name)
        fields(limits, ('read_bytes', 'write_bytes', 'attempts'), 'separate endpoint layer ceilings')
        for x in limits.values():
            integer(x)
    require(set(value['endpoint_owners']) == set(value['endpoint_layers']) == set(value['endpoint_limits']),
            'one selected owner and explicit layer for every endpoint')
    for name in value['endpoint_limits']:
        require(value['endpoint_owners'][name] in ('collector', 'finalizer'), 'concrete independent endpoint owner')
        require(value['endpoint_layers'][name] in ('unix_framed_application_bytes',
            'http_request_body_and_decoded_response_body', 'process_pipe_return_bytes'), 'explicit payload layer')
    from nb079_observation_common import encoding_limits
    encoding_limits(value['encoding_limits'])
    fields(value['reader_limits'], ('file_bytes', 'directory_entries', 'path_chars', 'journal_bytes',
                                    'journal_records', 'stream_bytes', 'source_files'),
           'explicit collector/journal/complete-stream ceilings')
    for x in value['reader_limits'].values():
        integer(x, 1)
    return value


def profile_pin(value):
    profile(value)
    return body_pin(bounded_encode(value, value['encoding_limits']))


def storage_delta(before, after, selected):
    """No vanished/new device, decrement or unselected layer is hidden."""
    profile(selected)
    names = set(selected['storage_limits'])
    require(type(before) is dict and type(after) is dict and set(before) <= names and set(after) <= names,
            'all observed storage devices admitted')
    require(set(before) <= set(after), 'previous device counter vanished')
    result = {}
    for name in sorted(names):
        # An admitted device absent from io.stat has no recorded entry yet;
        # represent its absence separately, rather than inventing a raw sample.
        old, new = before.get(name), after.get(name)
        if new is None:
            require(old is None, 'lost storage device')
            result[name] = {'read_bytes': 0, 'write_bytes': 0, 'entry_seen': False}
            continue
        for x in new.values():
            integer(x)
        fields(new, ('read_bytes', 'write_bytes'), 'storage native fields')
        old = {'read_bytes': 0, 'write_bytes': 0} if old is None else old
        fields(old, ('read_bytes', 'write_bytes'), 'storage native fields')
        item = {'entry_seen': True}
        for key in ('read_bytes', 'write_bytes'):
            integer(old[key]); require(new[key] >= old[key], 'storage reset/wrap/loss')
            item[key] = new[key] - old[key]
        result[name] = item
    return result


def validate_snapshot(value, selected, *, require_closed=False):
    profile(selected)
    fields(value, ('schema', 'scope_id', 'profile_pin', 'source_pin', 'origin_ns', 'observed_ns',
                   'state', 'scope_identity', 'storage', 'memory', 'retention', 'transfers',
                   'remote', 'selected_unknown', 'raw_evidence_pin', 'pending_endpoints'), 'exact typed resource snapshot')
    require(value['schema'] == 'ach_local_resource_snapshot_v1' and value['scope_id'] == selected['scope_id']
            and value['profile_pin'] == profile_pin(selected), 'same prospective resource profile')
    for key in ('source_pin', 'raw_evidence_pin'):
        check_pin(value[key])
    integer(value['origin_ns']); integer(value['observed_ns'])
    require(value['origin_ns'] <= value['observed_ns'], 'original observation interval')
    require(value['state'] in ('open_checkpoint', 'closed_scope') and
            (not require_closed or value['state'] == 'closed_scope'), 'exact scope closure requirement')
    fields(value['scope_identity'], ('device', 'inode', 'creation_receipt_pin'), 'owned common cgroup identity')
    integer(value['scope_identity']['device']); integer(value['scope_identity']['inode'], 1)
    check_pin(value['scope_identity']['creation_receipt_pin'])
    require(value['selected_unknown'] == [], 'required local selected dimension is unknown')
    fields(value['storage'], ('devices', 'baseline_pin', 'current_pin', 'attribution'), 'storage layer')
    require(value['storage']['attribution'] == 'kernel_cgroup_charge_not_unique_causal_media', 'storage attribution disclosed')
    for key in ('baseline_pin', 'current_pin'):
        check_pin(value['storage'][key])
    require(set(value['storage']['devices']) == set(selected['storage_limits']), 'full selected device roster')
    for name, row in value['storage']['devices'].items():
        fields(row, ('read_bytes', 'write_bytes', 'entry_seen'), 'device delta')
        require(type(row['entry_seen']) is bool, 'actual entry disposition')
        for key in ('read_bytes', 'write_bytes'):
            integer(row[key]); require(row[key] <= selected['storage_limits'][name][key], 'typed storage overrun')
        require(row['entry_seen'] or row['read_bytes'] == row['write_bytes'] == 0, 'unseen entry has no charges')
    fields(value['memory'], ('charged_peak_bytes', 'mode', 'supplemental', 'device_memory'), 'named memory quantities')
    integer(value['memory']['charged_peak_bytes'])
    require(value['memory']['mode'] == selected['memory_mode'] and
            value['memory']['charged_peak_bytes'] <= selected['charged_memory_limit_bytes'], 'common-scope charge peak limit')
    require(set(value['memory']['supplemental']) == set(selected['supplemental_memory_limits']), 'all supplemental counters')
    for name, amount in value['memory']['supplemental'].items():
        integer(amount); require(amount <= selected['supplemental_memory_limits'][name], 'supplemental memory limit')
    require(value['memory']['device_memory'] == {'status': 'unmeasured_not_in_selected_charge_estimand'},
            'universal device-memory total is not measured zero')
    fields(value['retention'], ('state', 'class_bytes', 'total_unique_bytes', 'files', 'inventory_pin'), 'retention state')
    retained = value['retention']
    if value['state'] == 'open_checkpoint':
        require(retained == {'state': 'pending_quiescence', 'class_bytes': None, 'total_unique_bytes': None,
                             'files': None, 'inventory_pin': None}, 'checkpoint cannot claim final retention')
    else:
        require(retained['state'] == 'closed_logical_inventory', 'actual final inventory required')
        check_pin(retained['inventory_pin']); fields(retained['class_bytes'], CLASSES, 'all retained classes')
        for name, amount in retained['class_bytes'].items():
            integer(amount); require(amount <= selected['retention_limits'][name], 'retention class limit')
        require(integer(retained['total_unique_bytes']) == sum(retained['class_bytes'].values()) and
                retained['total_unique_bytes'] <= selected['retention_limits']['total_unique_bytes'], 'one unique backing inventory')
        require(integer(retained['files']) <= selected['retention_limits']['files'], 'inventory file ceiling')
    require(type(value['transfers']) is dict and type(value['pending_endpoints']) is list and
        set(value['transfers']).isdisjoint(value['pending_endpoints']) and
        set(value['transfers']) | set(value['pending_endpoints']) == set(selected['endpoint_limits']) and
        len(value['pending_endpoints']) == len(set(value['pending_endpoints'])), 'complete explicit endpoint disposition')
    require(not require_closed or value['pending_endpoints'] == [], 'all endpoint owners observed at terminal close')
    require(value['state'] != 'closed_scope' or value['pending_endpoints'] == [], 'closed endpoint completeness')
    for endpoint, counters in value['transfers'].items():
        fields(counters, ('read_bytes', 'write_bytes', 'attempts', 'failed_attempts', 'coverage'), 'endpoint observation counters')
        for name in ('read_bytes', 'write_bytes', 'attempts', 'failed_attempts'):
            integer(counters[name])
        require(counters['failed_attempts'] <= counters['attempts'] and
                counters['coverage'] == 'owned_positive_return_prefixes', 'partial endpoint disposition')
        for name, limit in selected['endpoint_limits'][endpoint].items():
            require(counters[name] <= limit, 'endpoint layer limit')
    fields(value['remote'], ('hardware', 'usage_evidence_pins'), 'explicit remote boundary')
    require(value['remote']['hardware'] == 'excluded_unknown' and
            type(value['remote']['usage_evidence_pins']) is list, 'remote hardware never inferred')
    for evidence in value['remote']['usage_evidence_pins']:
        check_pin(evidence)
    return value


class SnapshotLedger:
    """Retain monotonic scope checkpoints. Never add them as per-job charges."""
    def __init__(self, selected):
        self.selected = profile(selected)
        self.records = []
        self.closed = False
        self.fixed_profile_pin=profile_pin(selected)
        self.previous = None

    def record(self, snapshot, phase):
        token(phase)
        require(profile_pin(self.selected)==self.fixed_profile_pin,'selected profile changed after admission')
        # Preserve an attempted body identity even if limits reject it later.
        raw = bounded_encode(snapshot, self.selected['encoding_limits'])
        record = {'phase': phase, 'snapshot_pin': body_pin(raw), 'accepted': False}
        self.records.append(record)
        require(not self.closed, 'scope already closed')
        validate_snapshot(snapshot, self.selected)
        if len(self.records) > 1:
            previous = self.records[-2]
            require(previous['accepted'], 'prior incomplete observation permanently closes completion')
            require(snapshot['observed_ns'] >= previous['observed_ns'], 'no backwards checkpoint time')
            old = self.previous
            for key in ('source_pin', 'origin_ns', 'scope_identity'):
                require(snapshot[key] == old[key], 'same independently selected operation identity')
            require(snapshot['storage']['baseline_pin'] == old['storage']['baseline_pin'], 'no storage rebaseline')
            require(snapshot['memory']['charged_peak_bytes'] >= old['memory']['charged_peak_bytes'], 'no memory peak reset')
            for name, row in snapshot['storage']['devices'].items():
                prior = old['storage']['devices'][name]
                require(not prior['entry_seen'] or row['entry_seen'], 'storage entry disappeared')
                for key in ('read_bytes', 'write_bytes'):
                    require(row[key] >= prior[key], 'storage checkpoint counter reset')
            require(set(old['transfers'])<=set(snapshot['transfers']),'previously observed endpoint owner disappeared')
            for name, row in snapshot['transfers'].items():
                if name not in old['transfers']: continue
                for key in ('read_bytes', 'write_bytes', 'attempts', 'failed_attempts'):
                    require(row[key] >= old['transfers'][name][key], 'endpoint checkpoint counter reset')
        record.update(accepted=True, observed_ns=snapshot['observed_ns'], state=snapshot['state'])
        # Own an immutable decoded copy rather than a caller-mutable reference.
        from nb079_observation_common import bounded_decode
        self.previous = bounded_decode(raw, self.selected['encoding_limits'])
        self.closed = snapshot['state'] == 'closed_scope'
        return record
