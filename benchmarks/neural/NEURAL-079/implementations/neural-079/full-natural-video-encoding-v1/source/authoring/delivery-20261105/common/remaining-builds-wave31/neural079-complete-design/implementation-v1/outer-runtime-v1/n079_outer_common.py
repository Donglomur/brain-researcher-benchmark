"""Bounded outer audit primitives. Import performs no deployment effects."""
import hashlib
import os
import stat
from pathlib import PurePosixPath
from ach_resource_common import (require, fields, integer, check_pin, body_pin,
    bounded_encode, bounded_decode, read_fd, collect_errors, close_all)
from ach_resource_readers import LocalReaders, identity, key_values
from n079_budget import DIMENSIONS, allocation


def canonical_path(path):
    require(type(path) is str and path.startswith('/') and str(PurePosixPath(path)) == path and
            '..' not in PurePosixPath(path).parts and '\x00' not in path, 'canonical absolute selected path')
    return path


def open_directory(path):
    canonical_path(path); fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    first = None
    try:
        for name in PurePosixPath(path).parts[1:]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            old, fd = fd, child
            try: os.close(old)
            except BaseException as error:
                close_all([('acquired directory close', lambda: os.close(fd))], error); fd = None; raise
        result, fd = fd, None; return result
    except BaseException as error: first = error; raise
    finally:
        close_all([] if fd is None else [('directory traversal close', lambda: os.close(fd))], first)


def signature(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


class AuditCounters:
    """One predeclared finalizer partition, not an additional whole-study budget.

    Charged counts include prospective logical byte bounds for delegated reads.
    Positive observed returns are separately retained; they never erase charges.
    No physical syscall, allocator or media accounting is implied.
    """
    def __init__(self, selected, source_pin, encoding, clock, maximum_attempts):
        parsed = allocation(selected)
        require(selected['source_pin'] == source_pin, 'same source/allocation')
        self.limit = parsed['rows']['finalizer']; self.source_pin = source_pin
        self.allocation_pin = body_pin(bounded_encode(selected, encoding)); self.clock = clock
        self.maximum_attempts = integer(maximum_attempts, 1)
        self.counts = {k: 0 for k in DIMENSIONS}; self.attempts = []; self.observed = {}
        self.reservation = None

    def charge(self, delta, reason, phase='scientific'):
        require(type(delta) is dict and set(delta) <= set(DIMENSIONS), 'existing additive dimensions only')
        values = {k: integer(v) for k, v in delta.items()}
        require(len(self.attempts) < self.maximum_attempts, 'finite audit attempt roster')
        row = {'delta': values, 'reason': reason, 'status': 'attempted'}; self.attempts.append(row)
        for key, value in values.items(): self.counts[key] += value
        try:
            self.clock.tick(phase)
            require(all(self.counts[k] <= self.limit[k] for k in DIMENSIONS), 'selected finalizer partition exceeded')
        except BaseException as error:
            row['status'] = 'refused'; error.n079_audit_prefix = self.snapshot(); raise
        row['status'] = 'charged'

    def returned(self, category, count):
        self.observed[category] = self.observed.get(category, 0) + integer(count)

    def reservation_request(self, participant):
        require(self.reservation is None, 'single finalizer reservation')
        return {'schema': 'n079_additive_charge_v1', 'participant': participant, 'sequence': 1,
            'allocation_pin': self.allocation_pin, 'source_pin': self.source_pin, 'work_id': 'finalizer',
            'delta': dict(self.limit), 'reason': 'complete selected finalizer partition including pre-observer startup and post-observer audit',
            'phase': 'scientific'}

    def bind_reservation(self, request, reply, encoding):
        fields(reply, ('schema','request_pin','allocation_pin','sequence','participant','whole_attempted','local_attempted'), 'central reservation receipt')
        require(self.reservation is None and reply['schema'] == 'n079_additive_reservation_v1' and
            reply['request_pin'] == body_pin(bounded_encode(request, encoding)) and
            reply['allocation_pin'] == self.allocation_pin and reply['sequence'] == 1 and
            reply['participant'] == request['participant'] and reply['local_attempted'] == self.limit,
            'once-only central exact finalizer row; no prior duplicate startup charges')
        self.reservation = reply

    def snapshot(self):
        return {'selected_partition': dict(self.limit), 'charged_attempted': dict(self.counts),
            'positive_observed_returns': dict(self.observed), 'reservation': self.reservation,
            'allocation_pin': self.allocation_pin, 'source_pin': self.source_pin,
            'attempts': list(self.attempts), 'physical_total_claim': False}


class AuditIO:
    def __init__(self, audit, clock, encoding, limits):
        self.audit, self.clock, self.encoding, self.limits = audit, clock, encoding, limits

    def read(self, path, pin=None, phase='scientific', maximum=None):
        canonical_path(path); maximum = self.limits['file_bytes'] if maximum is None else integer(maximum)
        if pin is not None: check_pin(pin); require(pin['bytes'] <= maximum, 'selected file before read')
        parent = open_directory(str(PurePosixPath(path).parent)); fd = None; first = None
        try:
            fd = os.open(PurePosixPath(path).name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum, 'ordinary bounded single-link metadata')
            self.audit.charge({'source_read_bytes': before.st_size + 1}, 'full metadata read including EOF probe', phase)
            raw = read_fd(fd, before.st_size + 1, self.clock, phase)
            self.audit.returned('source_read_bytes', len(raw))
            require(signature(before) == signature(os.fstat(fd)) and len(raw) == before.st_size, 'stable exact file read')
            if pin is not None: require(body_pin(raw) == pin, 'exact admitted metadata pin')
            return raw
        except BaseException as error: first = error; raise
        finally:
            close_all(([] if fd is None else [('metadata file close', lambda: os.close(fd))]) +
                      [('metadata parent close', lambda: os.close(parent))], first)

    def write(self, root, name, raw, phase='scientific', log=False):
        require(type(raw) is bytes and '/' not in name and name not in ('','.','..'), 'one exact owned output leaf')
        require(len(raw) <= self.limits['artifact_bytes'], 'complete artifact ceiling')
        charge = {'write_bytes': len(raw)}
        if log: charge['log_bytes'] = len(raw)
        self.audit.charge(charge, 'prospective complete audit artifact', phase)
        fd = None; first = None; record = {'path': name, 'bytes': 0, 'sha256': None, 'durable': False}
        h = hashlib.sha256()
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=root)
            done = 0
            while done < len(raw):
                self.clock.tick(phase); n = os.write(fd, memoryview(raw)[done:])
                require(type(n) is int and 0 < n <= len(raw) - done, 'complete actual audit write')
                h.update(memoryview(raw)[done:done+n]); done += n; record['bytes'] = done
                self.audit.returned('write_bytes', n)
            os.fsync(fd); os.fsync(root); self.clock.tick(phase); record['durable'] = True
            return {'path': name, **body_pin(raw)}
        except BaseException as error:
            record['sha256'] = h.hexdigest(); error.n079_partial_artifact = record; first = error; raise
        finally: close_all([] if fd is None else [('audit artifact close', lambda: os.close(fd))], first)


class CountedReaders(LocalReaders):
    def __init__(self, admitted, selected, clock, audit, *, held_peak_fd=None):
        self.audit = audit
        # LocalReaders also reads mountinfo once; named reads below are charged individually.
        audit.charge({'source_read_bytes': selected['reader_limits']['file_bytes'] + 1}, 'common-reader mountinfo bound')
        super().__init__(admitted, selected, clock, held_peak_fd=held_peak_fd)

    def read_named(self, name, phase):
        self.audit.charge({'source_read_bytes': self.selected['reader_limits']['file_bytes'] + 1}, 'bounded named common kernel read: '+name, phase)
        raw = super().read_named(name, phase); self.audit.returned('source_read_bytes', len(raw)); return raw

    def read_peak_raw(self, phase):
        self.audit.charge({'source_read_bytes': self.selected['reader_limits']['file_bytes'] + 1}, 'bounded memory peak read', phase)
        raw = super().read_peak_raw(phase); self.audit.returned('source_read_bytes', len(raw)); return raw


def parse_cpu(raw):
    require(type(raw) is bytes, 'actual cpu.stat bytes')
    values = key_values(raw)
    require('usage_usec' in values, 'cpu.stat usage_usec is required, unknown is never zero')
    return integer(values['usage_usec'])


class CPUInterval:
    def __init__(self, readers, selected, audit, clock):
        fields(selected, ('usage_usec_limit','admission_pin','cpu_only_runtime_pin','cpu_only_native_pin'), 'independent CPU and no-GPU admissions')
        integer(selected['usage_usec_limit'], 1)
        for k in ('admission_pin','cpu_only_runtime_pin','cpu_only_native_pin'): check_pin(selected[k])
        self.readers, self.selected, self.audit, self.clock = readers, selected, audit, clock
        self.baseline = self.read('scientific'); self.final = None

    def read(self, phase):
        require(identity(self.readers.scope) == self.readers.admitted['scope_identity'], 'same common CPU scope')
        self.audit.charge({'source_read_bytes': self.readers.selected['reader_limits']['file_bytes'] + 1}, 'bounded common cpu.stat read', phase)
        fd = os.open('cpu.stat', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.readers.scope); first = None
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode), 'ordinary cpu.stat virtual file')
            raw = read_fd(fd, self.readers.selected['reader_limits']['file_bytes'], self.clock, phase)
            self.audit.returned('source_read_bytes', len(raw))
            return {'usage_usec': parse_cpu(raw), 'raw_ascii': raw.decode('ascii'), 'pin': body_pin(raw), 'observed_ns': self.clock.tick(phase)}
        except BaseException as error: first = error; raise
        finally: close_all([('cpu.stat descriptor close', lambda: os.close(fd))], first)

    def finish(self):
        require(self.final is None, 'one closed CPU interval'); self.final = self.read('outer')
        delta = self.final['usage_usec'] - self.baseline['usage_usec']
        require(delta >= 0, 'same monotone CPU counter interval')
        record = {'schema': 'n079_common_cpu_interval_v1', 'baseline': self.baseline, 'final': self.final,
            'usage_usec': delta, 'selected_limit_usec': self.selected['usage_usec_limit'],
            'within_limit': delta <= self.selected['usage_usec_limit'], 'admissions': self.selected,
            'scope_identity': self.readers.admitted['scope_identity'], 'gpu_execution_time': 'unmeasured_unadmitted',
            'interpretation': 'cgroup charged CPU time interval; not wall time or GPU time'}
        self.record = record
        if not record['within_limit']:
            error=ValueError('selected common CPU-time ceiling exceeded');error.n079_cpu_prefix=record;raise error
        return record


def merge_endpoint_records(records, selection, selected):
    require(set(records) == set(selection['roles'].values()), 'every actual endpoint owner required')
    merged = {}
    for role, row in records.items():
        fields(row, ('role','selection_pin','counters','scope'), 'exact role endpoint terminal record')
        require(row['role'] == role and row['selection_pin'] == selection['selection_pin'], 'same endpoint selection and actual role')
        expected = {k for k, owner in selection['roles'].items() if owner == role}
        require(set(row['counters']) == expected and not set(merged).intersection(expected), 'exact disjoint owner coverage')
        for endpoint, counter in row['counters'].items():
            fields(counter, ('read_bytes','write_bytes','attempts','failed_attempts','coverage'), 'complete observed endpoint counter')
            require(counter['coverage'] == 'owned_positive_return_prefixes', 'actual owned prefix estimand')
            for key in ('read_bytes','write_bytes','attempts','failed_attempts'): integer(counter[key])
            require(counter['failed_attempts'] <= counter['attempts'], 'actual failed attempt subset')
            for key, maximum in selected['endpoint_limits'][endpoint].items():
                require(counter[key] <= maximum, 'closed endpoint ceiling')
            merged[endpoint] = dict(counter)
    require(set(merged) == set(selected['endpoint_limits']), 'complete endpoint roster; no unknown-to-zero replacement')
    return merged


def configuration_projection(configuration, encoding):
    """Only detached admission records may differ from the actual proposal.

    No operator-provided list can expand these two admission-only exceptions.
    Scientific role payload/catalog, clocks, allocation, module source and caps
    remain byte-equivalent under the common canonical JSON serialization.
    """
    copy=bounded_decode(bounded_encode(configuration,encoding),encoding)
    require(type(copy) is dict and type(copy.get('context')) is dict,'full proposed role configuration')
    context=copy['context']
    require('source_admission' in context and type(context.get('effect_admission')) is dict and
            'issuer_evidence' in context['effect_admission'],'fixed detached role admission fields')
    del context['source_admission'];del context['effect_admission']['issuer_evidence']
    return copy


def validate_initial_receipt(receipt, configuration_pin, admission, selected, clock, encoding):
    fields(receipt,('schema','configuration_pin','source_pin','profile_pin','base_source_admission_pin',
        'custody_receipt_pin','issuer_receipt_pin','clock','decision'),'exact detached initial outer admission B')
    require(receipt['schema']=='n079_detached_outer_configuration_admission_v1' and
        receipt['decision']=='independently_selected_outer_configuration' and
        receipt['configuration_pin']==configuration_pin and receipt['source_pin']==admission['source_pin'] and
        receipt['base_source_admission_pin']==body_pin(bounded_encode(admission['selection'],encoding)) and
        receipt['custody_receipt_pin']==admission['selection']['custody_receipt']['pin'] and
        receipt['issuer_receipt_pin']==admission['selection']['issuer_receipt']['pin'] and
        receipt['clock']=={k:getattr(clock,k) for k in ('origin','scientific','closeout','outer')},
        'same independently selected K/base source/custody/issuer/original clocks')
    from ach_resource_model import profile_pin
    require(receipt['profile_pin']==profile_pin(selected),'same detached selected resource profile')
    return receipt


def fresh_grade_input(configuration, source_pin, io):
    """Read the newly assembled actual protected grade index before release.

    The deterministic declared observation identity contains no timestamp or
    self-reference. It is accepted only after this concrete full ordinary read.
    Actual read clocks/bytes are retained in a separate outer observation.
    """
    payload=configuration['role_payload'];item=payload['input_index'];selection=payload['selection']
    fields(item,('path','bytes','sha256'),'exact protected grade input descriptor')
    expected={k:item[k] for k in ('bytes','sha256')};check_pin(expected)
    repository=configuration['repository']
    fields(repository,('root','catalog','logical_limits'),'exact admitted material repository')
    root=canonical_path(repository['root']);key=item['path']
    require(type(key) is str and key in repository['catalog'],'selected index logical catalog entry')
    catalog=repository['catalog'][key]
    fields(catalog,('relative_path','pin','immutable_admission'),'complete selected immutable material record')
    check_pin(catalog['immutable_admission']);require(catalog['pin']==expected,'descriptor and catalog exact pin join')
    relative=catalog['relative_path'];path=PurePosixPath(relative)
    require(type(relative) is str and relative and not path.is_absolute() and str(path)==relative and
            '..' not in path.parts and '\x00' not in relative,'safe canonical nested material path')
    graph=selection['observation_pin'];check_pin(graph)
    declared={'schema':'n079_fresh_grade_input_observation_v1','index':item,'source_pin':source_pin,'input_graph_pin':graph}
    declared_pin=body_pin(bounded_encode(declared,io.encoding))
    require(selection['index_observation_pin']==declared_pin,'same deterministic fresh-index observation identity')
    started=io.clock.tick('scientific')
    # AuditIO traverses every ancestor O_NOFOLLOW, checks single-link ordinary
    # extent, reads every byte plus EOF, and verifies before/after stability.
    raw=io.read(root.rstrip('/')+'/'+relative,expected,'scientific')
    require(body_pin(raw)==expected,'actual complete fresh protected index body')
    return {'schema':'n079_actual_fresh_grade_input_read_v1','declared':declared,'declared_pin':declared_pin,
        'root':root,'catalog_record':catalog,'actual_read_pin':body_pin(raw),
        'started_ns':started,'finished_ns':io.clock.tick('scientific')}
