"""Closed NEURAL-017 native rows with complete resident, immutable operands.

The legacy expanded runtime_layout API is unchanged. This module performs real
bounded preparation, preserves each completed original custody in Store, and
expands one original slot at a time. It never runs a worker or a model.
"""
import copy
import hashlib
import json
import os
import struct
import sys
from array import array
from bisect import bisect_right
from types import MappingProxyType
from .contracts import (Custody, Handles, Store, canonical, closed, descriptor,
                        digest, integer, need, parse, relative)
from .operator_roster import JobRoster
from .runtime_layout import PROFILE_KEYS, _profile, _pins
from .factored_leaf_builder import (GEOMETRY_KEYS, OPERAND_KEYS, _geometry,
                                    leaf_paths, leaf_static_manifest, build_leaf,
                                    validate_fixed_profile)

WIRE_KEYS = {'schema', 'phase', 'slots', 'geometry', 'profiles', 'process_census',
             'operands', 'admission', 'authoring_output_prefix'}
LEAF_KEYS = {'ordinal', 'token', 'paths_sha256', 'qualification',
             'storage_qualification', 'output_manifest', 'static_manifest',
             'config_pin', 'path_receipt', 'mount_receipt'}
LIMIT_KEYS = {'namespace_receipt_bytes', 'path_receipt_bytes',
              'mount_receipt_bytes', 'admission_bytes', 'selection_metadata_bytes'}
ADMISSION_KEYS = {'schema', 'phase', 'slots_sha256', 'geometry_sha256',
                  'profiles_sha256', 'process_census', 'slot_count',
                  'physical_count', 'operands_sha256', 'profile_input_sha256',
                  'qualification_input_sha256', 'gateway_input_sha256',
                  'namespace_receipt', 'path_receipt_chain_sha256',
                  'mount_receipt_chain_sha256', 'budget_before_admission',
                  'receipt_limits', 'complete', 'authoring_output_prefix', 'selected_inputs',
                  'selected_inputs_receipt'}
_ADMITTED = object()


def json_chunks(value, final_lf=False):
    encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'),
                               ensure_ascii=False, allow_nan=False)
    for chunk in encoder.iterencode(value):
        yield chunk.encode('utf-8')
    if final_lf:
        yield b'\n'


def json_identity(value):
    h = hashlib.sha256(); length = 0
    for chunk in json_chunks(value, True):
        h.update(chunk); length += len(chunk)
    return {'bytes': length, 'sha256': h.hexdigest()}


def _write_selected_inputs(store, name, value, maximum):
    """Actual exclusive streaming publication of complete selected metadata.

This is the original Store write protocol over bounded JSON chunks. It keeps
the full input artifact rather than retaining only an unresolvable digest.
"""
    identity = json_identity(value); need(identity['bytes'] <= maximum, 'explicit selected-input metadata ceiling')
    owner = store.custody; handles = Handles(owner)
    event = {'path': name, 'accepted_bytes': 0, 'created': False, 'durable': False}
    owner.events.append(event); observed = hashlib.sha256()
    try:
        store.budget.admit(); store.budget.reserve('write_bytes', identity['bytes'])
        store.budget.reserve('created_files', 1)
        parent, leaf = store.parent(name, handles)
        fd = handles.own(os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                0o600, dir_fd=parent), 'file', name)
        event['created'] = True; store.budget.charge('created_files', 1)
        for chunk in json_chunks(value, True):
            start = 0
            while start < len(chunk):
                store.budget.guard(); n = os.write(fd, chunk[start:]); need(n > 0, 'complete selected metadata write')
                observed.update(chunk[start:start + n]); start += n
                event['accepted_bytes'] += n; store.budget.charge('write_bytes', n)
        need(event['accepted_bytes'] == identity['bytes'] and observed.hexdigest() == identity['sha256'],
             'exact unchanged complete selected-input bytes')
        os.fsync(fd); os.fsync(parent); event['durable'] = True
    except BaseException as error:
        owner.fail(error, 'selected_input_stream_publication')
    finally:
        handles.finish()
    owner.raise_if_failed(); store.budget.guard()
    return {'path': name, **identity}


def _hex(value):
    need(type(value) is str and len(value) == 64 and
         all(x in '0123456789abcdef' for x in value), 'exact hexadecimal digest')
    return bytes.fromhex(value)


def _variant_rows(job):
    if job['role'] == 'participant_tool':
        return tuple(job['runtime_profile'].items())
    return (('', job['runtime_profile']),)


def _authoring_prefix(phase, value):
    if phase == 'authoring':
        relative(value)
    else:
        need(phase == 'campaign' and value is None, 'campaign has no authoring output prefix')
    return value


def _checker_projection(native, job, profile, prefix):
    if job['role'] == 'source_syntax':
        relative(prefix)
        gid, suffix = job['job'].rsplit('/', 1)
        need(suffix.startswith('author-check-'), 'source-owned checker ordinal')
        number = int(suffix[len('author-check-'):])
        need(suffix == 'author-check-%04d' % number, 'exact original checker spelling')
        native['dynamic_input_policy'] = {'schema': 'NLB017_F_checker_dynamic_input_v1',
            'manifest_path': prefix + '/' + digest(gid.encode()) + '/checker-input-%04d.json' % number,
            'authority': copy.deepcopy(profile['authority'])}
    return native


def _receipt_path(entry, phase):
    return entry['static_manifest_path'].removesuffix('.static.json') + '.' + phase + '-receipt.json'


def _pack_pin(pin, known_path=None):
    descriptor(pin)
    out = bytearray()
    if known_path is None:
        path = pin['path'].encode('utf-8'); need(len(path) <= 65535, 'packed descriptor path')
        out.extend(struct.pack('>H', len(path))); out.extend(path)
    else:
        need(pin['path'] == known_path, 'exact source-derived original descriptor path')
    out.extend(struct.pack('>Q', pin['bytes'])); out.extend(_hex(pin['sha256']))
    return bytes(out)


def _unpack_pin(raw, offset, known_path=None):
    if known_path is None:
        size = struct.unpack_from('>H', raw, offset)[0]; offset += 2
        path = raw[offset:offset + size].decode('utf-8'); offset += size
    else:
        path = known_path
    size = struct.unpack_from('>Q', raw, offset)[0]; offset += 8
    checksum = raw[offset:offset + 32].hex(); offset += 32
    pin = {'path': path, 'bytes': size, 'sha256': checksum}; descriptor(pin)
    return pin, offset


class OperandTable:
    """Complete ordered operands, packed per record; no descriptor is omitted.

Known generated paths are losslessly reconstructed. Actual lengths and hashes
remain stored. Records are immutable bytes, and seal replaces only the small
record-pointer list with a tuple. No whole-table byte copy is required.
"""
    def __init__(self):
        self._records = []; self._sealed = False

    def __len__(self):
        return len(self._records)

    def append(self, record, entry):
        need(not self._sealed, 'unsealed original operand table')
        closed(record, LEAF_KEYS)
        need(record['ordinal'] == len(self) and record['token'] == entry['token'] and
             record['paths_sha256'] == digest(canonical(entry['paths'])),
             'exact ordered physical operand and prepared paths')
        raw = bytearray(_hex(record['token']) + _hex(record['paths_sha256']))
        for key in ('qualification', 'storage_qualification'):
            raw.extend(_pack_pin(record[key]))
        for key, path in (('output_manifest', entry['output_manifest']['path']),
                          ('static_manifest', entry['static_manifest_path'])):
            raw.extend(_pack_pin(record[key], path))
        config = record['config_pin']; raw.append(0 if config is None else 1)
        if config is not None:
            raw.extend(_pack_pin(config))
        for key, phase in (('path_receipt', 'paths'), ('mount_receipt', 'mounts')):
            raw.extend(_pack_pin(record[key], _receipt_path(entry, phase)))
        self._records.append(bytes(raw))

    def seal(self, expected):
        need(not self._sealed and len(self) == expected, 'complete original physical operand census')
        self._records = tuple(self._records); self._sealed = True
        return self

    def row(self, ordinal, entry):
        integer(ordinal, 0, len(self) - 1)
        raw = self._records[ordinal]; offset = 64
        need(raw[:32].hex() == entry['token'] and raw[32:64].hex() == digest(canonical(entry['paths'])),
             'same original packed operand geometry')
        out = {'ordinal': ordinal, 'token': raw[:32].hex(), 'paths_sha256': raw[32:64].hex()}
        for key in ('qualification', 'storage_qualification'):
            out[key], offset = _unpack_pin(raw, offset)
        for key, path in (('output_manifest', entry['output_manifest']['path']),
                          ('static_manifest', entry['static_manifest_path'])):
            out[key], offset = _unpack_pin(raw, offset, path)
        present = raw[offset]; offset += 1; need(present in (0, 1), 'packed config presence')
        out['config_pin'] = None
        if present:
            out['config_pin'], offset = _unpack_pin(raw, offset)
        for key, phase in (('path_receipt', 'paths'), ('mount_receipt', 'mounts')):
            out[key], offset = _unpack_pin(raw, offset, _receipt_path(entry, phase))
        need(offset == len(raw), 'exact complete packed operand extent')
        return out

    def footprint(self):
        return {'records': len(self), 'packed_payload_bytes': sum(map(len, self._records)),
                'resident_record_bytes': sum(sys.getsizeof(x) for x in self._records),
                'resident_pointer_container_bytes': sys.getsizeof(self._records),
                'largest_packed_record_bytes': max(map(len, self._records), default=0),
                'sealed': self._sealed}


class FactoredRuntime:
    """Immutable selected profiles/operands; expansion owns fresh job values."""
    def __init__(self, geometry, slots, phase, profiles, operands, admission, *,
                 authoring_output_prefix=None, _token=None):
        need(_token is _ADMITTED and type(operands) is OperandTable and operands._sealed,
             'source-owned complete admitted runtime construction')
        _geometry(geometry); closed(geometry, GEOMETRY_KEYS); descriptor(admission)
        self._roster = JobRoster.from_selection(slots, phase)
        self._authoring_output_prefix = _authoring_prefix(phase, authoring_output_prefix)
        need(len(operands) == self.roster.physical_count, 'complete resident physical operands')
        self._geometry_raw = canonical(geometry)
        self._slots_raw = canonical(slots)
        self._census_raw = canonical(self.roster.census())
        self._profile_raw = MappingProxyType({name: canonical(value) for name, value in profiles.items()})
        self._admission_raw = canonical(admission)
        self._table = operands
        self._wire_identity_cache = None
        self._slot_offsets = array('Q', [0]); used = set(); physical = 0
        for job in self.roster.rows():
            variants = _variant_rows(job); physical += len(variants)
            used.update(p for _, p in variants); self._slot_offsets.append(physical)
        need(physical == len(operands) and used == set(profiles), 'exact selected profile/physical census')
        for name, profile in profiles.items():
            validate_fixed_profile(name, profile)

    @property
    def census(self):
        return parse(self._census_raw)

    @property
    def roster(self):
        return self._roster

    @property
    def authoring_output_prefix(self):
        return self._authoring_output_prefix

    @property
    def admission(self):
        return parse(self._admission_raw)

    def _geometry(self):
        return parse(self._geometry_raw)

    def _profiles(self):
        return {name: parse(raw) for name, raw in self._profile_raw.items()}

    def _entries(self):
        geometry = self._geometry(); profiles = self._profiles(); physical = 0
        for slot in range(len(self.roster)):
            job = self.roster.row(slot)
            for variant, name in _variant_rows(job):
                yield physical, slot, job, variant, name, leaf_paths(geometry, job, variant, name, profiles[name])
                physical += 1

    def iter_operands(self):
        for physical, _, _, _, _, entry in self._entries():
            yield self._table.row(physical, entry)

    def entry(self, physical_ordinal):
        integer(physical_ordinal, 0, self.roster.physical_count - 1)
        slot = bisect_right(self._slot_offsets, physical_ordinal) - 1
        job = self.roster.row(slot)
        variant, name = _variant_rows(job)[physical_ordinal - self._slot_offsets[slot]]
        entry = leaf_paths(self._geometry(), job, variant, name, parse(self._profile_raw[name]))
        return {**entry, 'physical_ordinal': physical_ordinal, 'slot_ordinal': slot,
                'stage': job['stage'], 'parent_group': job['parent_group']}

    def iter_physical_entries(self):
        for ordinal in range(self.roster.physical_count):
            yield self.entry(ordinal)

    def slot(self, ordinal):
        job = self.roster.row(ordinal); geometry = self._geometry()
        geometry['process_census'] = self.census
        row = None; context = None
        for n, (variant, name) in enumerate(_variant_rows(job)):
            profile = parse(self._profile_raw[name]); entry = leaf_paths(geometry, job, variant, name, profile)
            record = self._table.row(self._slot_offsets[ordinal] + n, entry)
            native, current = build_leaf(geometry, job, variant, name, profile, entry,
                                         {key: record[key] for key in OPERAND_KEYS})
            native = _checker_projection(native, job, profile, self.authoring_output_prefix)
            if variant:
                if row is None:
                    row = {key: native[key] for key in ('stage', 'role', 'parent_group', 'process_limit')}
                    row['tool_variants'] = {}
                row['tool_variants'][variant] = native
                need(context is None or context == current, 'one exact tool-slot worker context')
            else:
                row = native
            context = current
        return {'job': job['job'], 'native_job': row, 'worker_context': context}

    def lookup(self, job):
        return self.slot(self.roster.ordinal(job))

    def _fields(self):
        return {'schema': 'NLB017_factored_native_jobs_v1', 'phase': self.roster.phase,
                'slots': parse(self._slots_raw), 'geometry': self._geometry(),
                'profiles': self._profiles(), 'process_census': self.census,
                'admission': self.admission, 'authoring_output_prefix': self.authoring_output_prefix}

    def canonical_chunks(self, final_lf=False):
        fields = self._fields(); yield b'{'
        for i, key in enumerate(sorted(WIRE_KEYS)):
            if i:
                yield b','
            yield canonical(key)[:-1]; yield b':'
            if key != 'operands':
                yield from json_chunks(fields[key])
            else:
                yield b'['
                for n, row in enumerate(self.iter_operands()):
                    if n:
                        yield b','
                    yield from json_chunks(row)
                yield b']'
        yield b'}'
        if final_lf:
            yield b'\n'

    @property
    def wire_identity(self):
        if self._wire_identity_cache is None:
            h = hashlib.sha256(); size = 0
            for chunk in self.canonical_chunks(True):
                h.update(chunk); size += len(chunk)
            self._wire_identity_cache = (size, h.hexdigest())
        return {'bytes': self._wire_identity_cache[0], 'sha256': self._wire_identity_cache[1]}

    def to_wire(self, maximum_bytes):
        integer(maximum_bytes, 1); raw = bytearray()
        for chunk in self.canonical_chunks(True):
            need(len(raw) + len(chunk) <= maximum_bytes, 'explicit materialization byte ceiling')
            raw.extend(chunk)
        return parse(bytes(raw))

    def footprint(self):
        table = self._table.footprint()
        fixed = sum(sys.getsizeof(x) for x in (self._geometry_raw, self._slots_raw,
                    self._census_raw, self._admission_raw, self._slot_offsets))
        fixed += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self._profile_raw.items())
        if self._wire_identity_cache is not None:
            fixed += sys.getsizeof(self._wire_identity_cache)
            fixed += sum(sys.getsizeof(x) for x in self._wire_identity_cache)
        return {'operand_table': table, 'fixed_profile_geometry_index_bytes': fixed,
                'source_owned_resident_bytes_lower_bound': fixed + table['resident_record_bytes'] +
                    table['resident_pointer_container_bytes'],
                'mutable_native_cache_entries': 0,
                'exclusions': 'interpreter/modules, caller raw wire/admission inputs, active row, parent Executor cache, transient serialization'}

    @classmethod
    def from_selected(cls, store, wire):
        need(type(store) is Store, 'actual bounded source Store')
        closed(wire, WIRE_KEYS)
        need(wire['schema'] == 'NLB017_factored_native_jobs_v1', 'closed factored native schema')
        roster = JobRoster.from_selection(wire['slots'], wire['phase'])
        need(wire['process_census'] == roster.census(), 'exact source-owned parent census')
        _geometry(wire['geometry']); closed(wire['geometry'], GEOMETRY_KEYS)
        need(str(store.root) == wire['geometry']['store_root'], 'exact selected artifact store')
        descriptor(wire['admission'])
        report = store.json(wire['admission'], wire['admission']['bytes'])
        closed(report, ADMISSION_KEYS)
        need(report['schema'] == 'NLB017_factored_runtime_admission_v1' and report['complete'] is True,
             'actual selected completed source preparation record')
        need(type(wire['operands']) is list and len(wire['operands']) == roster.physical_count,
             'complete actual ordered physical operand wire')
        profiles = wire['profiles']; used = set(); table = OperandTable(); index = 0
        need(type(profiles) is dict, 'closed fixed runtime profiles')
        for name, profile in profiles.items():
            validate_fixed_profile(name, profile)
        for job in roster.rows():
            for variant, name in _variant_rows(job):
                used.add(name); need(name in profiles, 'actual selected profile')
                entry = leaf_paths(wire['geometry'], job, variant, name, profiles[name])
                record = wire['operands'][index]
                # This checks original protocol/manifest/gateway metadata for one
                # row only; no model/native effects occur in the pure builder.
                build_leaf({**wire['geometry'], 'process_census': roster.census()}, job,
                           variant, name, profiles[name], entry,
                           {key: record[key] for key in OPERAND_KEYS})
                table.append(record, entry); index += 1
        need(used == set(profiles), 'no unused selected profiles')
        table.seal(roster.physical_count)
        out = cls(wire['geometry'], wire['slots'], wire['phase'], profiles, table, wire['admission'],
                  authoring_output_prefix=wire['authoring_output_prefix'], _token=_ADMITTED)
        out._check_report(report)
        return out

    def _check_report(self, report):
        closed(report, ADMISSION_KEYS)
        for key in ('slots_sha256', 'geometry_sha256', 'profiles_sha256', 'operands_sha256',
                    'profile_input_sha256', 'qualification_input_sha256', 'gateway_input_sha256',
                    'path_receipt_chain_sha256', 'mount_receipt_chain_sha256'):
            _hex(report[key])
        descriptor(report['namespace_receipt']); descriptor(report['selected_inputs'])
        descriptor(report['selected_inputs_receipt'])
        closed(report['receipt_limits'], LIMIT_KEYS)
        for value in report['receipt_limits'].values():
            integer(value, 1)
        need(report['schema'] == 'NLB017_factored_runtime_admission_v1' and report['complete'] is True,
             'actual selected completed admission record')
        need(report['phase'] == self.roster.phase and
             report['authoring_output_prefix'] == self.authoring_output_prefix and
             report['slots_sha256'] == digest(self._slots_raw) and
             report['geometry_sha256'] == digest(self._geometry_raw) and
             report['profiles_sha256'] == json_identity(self._profiles())['sha256'] and
             report['process_census'] == self.census and
             report['slot_count'] == len(self.roster) and
             report['physical_count'] == self.roster.physical_count,
             'actual admission binds original full selection and census')
        h = hashlib.sha256(); h.update(b'[')
        path_chain = '0' * 64; mount_chain = '0' * 64
        for i, row in enumerate(self.iter_operands()):
            if i:
                h.update(b',')
            for chunk in json_chunks(row):
                h.update(chunk)
            path_chain = digest(canonical({'previous': path_chain, 'pin': row['path_receipt']}))
            mount_chain = digest(canonical({'previous': mount_chain, 'pin': row['mount_receipt']}))
        h.update(b']\n')
        need(report['operands_sha256'] == h.hexdigest() and
             report['path_receipt_chain_sha256'] == path_chain and
             report['mount_receipt_chain_sha256'] == mount_chain,
             'complete actual admitted operands and original custody chains')


class FactoredPreparation:
    """Caller-owned original preparation, with bounded per-leaf custody files."""
    def __init__(self, geometry, slots, phase, profile_roots, receipt_limits, *, authoring_output_prefix=None):
        _geometry(geometry); closed(geometry, GEOMETRY_KEYS)
        self.geometry = copy.deepcopy(geometry); self.roster = JobRoster.from_selection(slots, phase)
        self.authoring_output_prefix = _authoring_prefix(phase, authoring_output_prefix)
        closed(receipt_limits, LIMIT_KEYS)
        for value in receipt_limits.values():
            integer(value, 1)
        self.receipt_limits = copy.deepcopy(receipt_limits)
        self.profile_roots = copy.deepcopy(profile_roots)
        self._slot_offsets = array('Q', [0])
        used = set()
        for job in self.roster.rows():
            for variant, name in _variant_rows(job):
                used.add(name); need(name in profile_roots, 'complete phase profile roots')
                closed(profile_roots[name], {'cgroup_parent', 'scratch_parent'})
                leaf_paths(geometry, job, variant, name, profile_roots[name])
            self._slot_offsets.append(self._slot_offsets[-1] + len(_variant_rows(job)))
        need(used == set(profile_roots), 'exact phase profile roots')
        self.custody = Custody('factored_runtime_preparation')
        self.current_owner = None; self.paths_started = False; self.paths_complete = False
        self.mounts_started = False; self.mounts_complete = False; self.finish_started = False
        self._path_records = []; self._table = OperandTable(); self._profiles = None
        self.path_chain = '0' * 64; self.mount_chain = '0' * 64
        self.namespace_receipt = None; self.input_hashes = None
        self.selected_inputs = None
        self.selected_inputs_receipt = None

    def entry(self, physical_ordinal):
        integer(physical_ordinal, 0, self.roster.physical_count - 1)
        slot = bisect_right(self._slot_offsets, physical_ordinal) - 1
        job = self.roster.row(slot)
        variant, name = _variant_rows(job)[physical_ordinal - self._slot_offsets[slot]]
        entry = leaf_paths(self.geometry, job, variant, name, self.profile_roots[name])
        return {**entry, 'physical_ordinal': physical_ordinal, 'slot_ordinal': slot,
                'stage': job['stage'], 'parent_group': job['parent_group']}

    def iter_physical_entries(self):
        for ordinal in range(self.roster.physical_count):
            yield self.entry(ordinal)

    def _entries(self, profiles=None):
        source = self.profile_roots if profiles is None else profiles
        index = 0
        for job in self.roster.rows():
            for variant, name in _variant_rows(job):
                yield index, job, variant, name, leaf_paths(self.geometry, job, variant, name, source[name])
                index += 1

    def _store(self, store, owner):
        need(type(store) is Store and str(store.root) == self.geometry['store_root'], 'actual selected bounded Store')
        return Store(store.root, store.budget, owner)

    def _mkdir(self, store, name, owner):
        relative(name); store.budget.admit(); handles = Handles(owner)
        event = {'path': str(store.root) + '/' + name, 'effect': 'not_attempted', 'created': False}
        owner.events.append(event)
        try:
            store.budget.reserve('created_files', 1)
            parent, leaf = store.parent(name, handles)
            event['effect'] = 'attempted_unknown'; os.mkdir(leaf, mode=0o700, dir_fd=parent)
            event['created'] = True; event['effect'] = 'created'
            store.budget.charge('created_files', 1); os.fsync(parent)
        except BaseException as error:
            owner.fail(error, 'exclusive_factored_directory')
            store.budget.stop('incomplete original factored preparation')
        finally:
            handles.finish()
        owner.raise_if_failed()

    def _retain(self, store, owner, name, body, maximum):
        raw = canonical(body); need(len(raw) <= maximum, 'selected original preparation receipt cap')
        publication = Custody('factored_preparation_receipt')
        try:
            pin = Store(store.root, store.budget, publication).write(name, raw, maximum)
        except BaseException as error:
            owner.fail(error, 'original_receipt_publication'); raise
        finally:
            owner.fail(None, 'original_receipt_writer', publication)
        owner.raise_if_failed()
        return pin

    def _leaf_receipt(self, store, owner, entry, ordinal, phase, manifest):
        owner.complete = owner.first_error is None
        body = {'schema': 'NLB017_factored_original_preparation_receipt_v1',
                'phase': phase, 'ordinal': ordinal, 'token': entry['token'],
                'paths': entry['paths'], 'manifest': manifest, 'original': owner.snapshot(),
                'budget_before_receipt': store.budget.snapshot()}
        limit = self.receipt_limits['path_receipt_bytes' if phase == 'paths' else 'mount_receipt_bytes']
        return self._retain(store, owner, _receipt_path(entry, phase), body, limit)

    def _fail(self, error, phase):
        if self.current_owner is not None:
            self.custody.fail(error, phase, self.current_owner)
        else:
            self.custody.fail(error, phase)
        self.custody.raise_if_failed()

    def prepare_paths(self, store):
        need(not self.paths_started, 'one original factored path preparation')
        self.paths_started = True
        try:
            owner = Custody('factored_run_namespaces'); self.current_owner = owner
            scoped = self._store(store, owner)
            namespace = 'nlb017-' + digest(canonical({'programme': self.geometry['programme'], 'run_id': self.geometry['run_id']}))
            output = self.geometry['output_parent'] + '/' + namespace + '-outputs'
            metadata = self.geometry['metadata_parent'] + '/' + namespace + '-metadata'
            self._mkdir(scoped, output, owner); self._mkdir(scoped, metadata, owner)
            for root in dict.fromkeys(p['scratch_parent'] for p in self.profile_roots.values()):
                self._mkdir(Store(root, store.budget, owner), namespace, owner)
            owner.complete = True
            self.namespace_receipt = self._retain(store, owner, metadata + '/NAMESPACE_RECEIPT.json',
                {'schema': 'NLB017_factored_namespace_receipt_v1', 'geometry': self.geometry,
                 'profile_roots': self.profile_roots, 'original': owner.snapshot(),
                 'budget_before_receipt': store.budget.snapshot()}, self.receipt_limits['namespace_receipt_bytes'])
            self.current_owner = None
            for index, _, _, name, entry in self._entries():
                owner = Custody('factored_paths:' + entry['token']); self.current_owner = owner
                scoped = self._store(store, owner)
                self._mkdir(scoped, entry['paths']['output_prefix'], owner)
                scratch = Store(self.profile_roots[name]['scratch_parent'], store.budget, owner)
                self._mkdir(scratch, namespace + '/' + entry['token'], owner)
                raw = canonical({'schema': 'NLB017_mount_tree_v1', 'role': 'output', 'files': []})
                expected = entry['output_manifest']; actual = scoped.write(expected['path'], raw, expected['bytes'])
                need(actual == expected, 'actual original empty output manifest')
                receipt = self._leaf_receipt(store, owner, entry, index, 'paths', actual)
                record = _hex(entry['token']) + _hex(digest(canonical(entry['paths'])))
                record += _pack_pin(actual, expected['path']) + _pack_pin(receipt, _receipt_path(entry, 'paths'))
                self._path_records.append(record)
                self.path_chain = digest(canonical({'previous': self.path_chain, 'pin': receipt}))
                self.current_owner = None
            need(len(self._path_records) == self.roster.physical_count, 'complete original path census')
            self._path_records = tuple(self._path_records); self.paths_complete = True
        except BaseException as error:
            self._fail(error, 'factored_paths')
        return self

    def prepare_mounts(self, store, profiles, qualifications, gateway_jobs):
        need(self.paths_complete and not self.mounts_started and self.custody.first_error is None,
             'one original mount preparation after genuine paths')
        self.mounts_started = True
        try:
            need(type(profiles) is dict and set(profiles) == set(self.profile_roots), 'exact full selected profiles')
            selected = {}
            for name, profile in profiles.items():
                _profile(name, profile)
                need({key: profile[key] for key in ('cgroup_parent', 'scratch_parent')} == self.profile_roots[name],
                     'same original prepared profile roots')
                selected[name] = _pins(profile['selected_pins'])
            need(type(qualifications) is dict and len(qualifications) == self.roster.physical_count,
                 'finite complete selected per-path qualifications')
            need(type(gateway_jobs) is dict, 'finite selected actual gateway config census')
            expected_models = sum(job['role'] == 'model_exchange' for job in self.roster.rows())
            need(len(gateway_jobs) == expected_models, 'exact selected gateway configuration count')
            self.input_hashes = {'profiles': json_identity(profiles)['sha256'],
                                 'qualifications': json_identity(qualifications)['sha256'],
                                 'gateway_jobs': json_identity(gateway_jobs)['sha256']}
            owner = Custody('factored_selected_inputs'); self.current_owner = owner
            scoped = self._store(store, owner)
            selected_name = self.namespace_receipt['path'].rsplit('/', 1)[0] + '/SELECTED_INPUTS.json'
            self.selected_inputs = _write_selected_inputs(scoped, selected_name,
                {'profiles': profiles, 'qualifications': qualifications, 'gateway_jobs': gateway_jobs},
                self.receipt_limits['selection_metadata_bytes'])
            # Preserve this original writer's complete custody before releasing
            # it, using the existing namespace-receipt cap explicitly selected.
            owner.complete = True
            self.selected_inputs_receipt = self._retain(store, owner, selected_name.removesuffix('.json') + '_RECEIPT.json',
                {'schema': 'NLB017_factored_selected_inputs_receipt_v1', 'selected_inputs': self.selected_inputs,
                 'original': owner.snapshot(), 'budget_before_receipt': store.budget.snapshot()},
                self.receipt_limits['namespace_receipt_bytes'])
            self.current_owner = None
            fixed = {name: {key: copy.deepcopy(value) for key, value in profile.items() if key != 'selected_pins'}
                     for name, profile in profiles.items()}
            for index, job, variant, name, entry in self._entries(fixed):
                owner = Custody('factored_mounts:' + entry['token']); self.current_owner = owner
                scoped = self._store(store, owner); token = entry['token']
                need(token in qualifications, 'exact selected original physical token')
                q = qualifications[token]; closed(q, {'paths', 'qualification', 'storage_qualification'})
                need(q['paths'] == entry['paths'], 'actual qualifications bind exact current prepared paths')
                for key in ('qualification', 'storage_qualification'):
                    descriptor(q[key]); need(selected[name].get(q[key]['path']) == q[key],
                                             'actual original selected qualification membership')
                config = None
                if job['role'] == 'model_exchange':
                    need(job['job'] in gateway_jobs, 'exact actual gateway job config')
                    closed(gateway_jobs[job['job']], {'config_pin'})
                    config = gateway_jobs[job['job']]['config_pin']; descriptor(config)
                path_record = self._path_records[index]
                need(path_record[:32].hex() == token and path_record[32:64].hex() == digest(canonical(entry['paths'])),
                     'same original successful path preparation')
                output, offset = _unpack_pin(path_record, 64, entry['output_manifest']['path'])
                path_receipt, offset = _unpack_pin(path_record, offset, _receipt_path(entry, 'paths'))
                need(offset == len(path_record), 'complete original path receipt')
                raw, expected, _ = leaf_static_manifest(self.geometry, job, fixed[name], entry, config)
                actual = scoped.write(expected['path'], raw, expected['bytes'])
                need(actual == expected, 'actual original static input manifest')
                operand = {'qualification': q['qualification'], 'storage_qualification': q['storage_qualification'],
                           'output_manifest': output, 'static_manifest': actual, 'config_pin': config}
                # Consume the exact same pure builder used by subsequent lookup,
                # including real gateway constructor and physical capability checks.
                build_leaf({**self.geometry, 'process_census': self.roster.census()}, job, variant,
                           name, fixed[name], entry, operand)
                receipt = self._leaf_receipt(store, owner, entry, index, 'mounts', actual)
                record = {'ordinal': index, 'token': token, 'paths_sha256': digest(canonical(entry['paths'])),
                          **operand, 'path_receipt': path_receipt, 'mount_receipt': receipt}
                self._table.append(record, entry)
                self.mount_chain = digest(canonical({'previous': self.mount_chain, 'pin': receipt}))
                self.current_owner = None
            need(self.input_hashes == {'profiles': json_identity(profiles)['sha256'],
                                      'qualifications': json_identity(qualifications)['sha256'],
                                      'gateway_jobs': json_identity(gateway_jobs)['sha256']},
                 'actual selected metadata unchanged through preparation')
            self._table.seal(self.roster.physical_count)
            self._profiles = fixed; self._path_records = (); self.mounts_complete = True
        except BaseException as error:
            self._fail(error, 'factored_mounts')
        return self

    def finish(self, store):
        need(self.mounts_complete and not self.finish_started and self.custody.first_error is None,
             'one actual complete source admission publication')
        self.finish_started = True
        try:
            owner = Custody('factored_final_admission'); self.current_owner = owner
            scoped = self._store(store, owner); h = hashlib.sha256(); h.update(b'[')
            for index, _, _, _, entry in self._entries(self._profiles):
                if index:
                    h.update(b',')
                for chunk in json_chunks(self._table.row(index, entry)):
                    h.update(chunk)
            h.update(b']\n')
            specification = self.roster.specification()
            report = {'schema': 'NLB017_factored_runtime_admission_v1', 'phase': self.roster.phase,
                      'authoring_output_prefix': self.authoring_output_prefix,
                      'slots_sha256': digest(canonical(specification['slots'])),
                      'geometry_sha256': digest(canonical(self.geometry)),
                      'profiles_sha256': json_identity(self._profiles)['sha256'],
                      'process_census': self.roster.census(), 'slot_count': len(self.roster),
                      'physical_count': self.roster.physical_count, 'operands_sha256': h.hexdigest(),
                      'profile_input_sha256': self.input_hashes['profiles'],
                      'qualification_input_sha256': self.input_hashes['qualifications'],
                      'gateway_input_sha256': self.input_hashes['gateway_jobs'],
                      'namespace_receipt': self.namespace_receipt,
                      'selected_inputs': self.selected_inputs,
                      'selected_inputs_receipt': self.selected_inputs_receipt,
                      'path_receipt_chain_sha256': self.path_chain,
                      'mount_receipt_chain_sha256': self.mount_chain,
                      'budget_before_admission': store.budget.snapshot(),
                      'receipt_limits': self.receipt_limits, 'complete': True}
            name = self.namespace_receipt['path'].rsplit('/', 1)[0] + '/ADMISSION.json'
            encoded = canonical(report)
            expected = {'path': name, 'bytes': len(encoded), 'sha256': digest(encoded)}
            out = FactoredRuntime(self.geometry, specification['slots'], self.roster.phase,
                                  self._profiles, self._table, expected,
                                  authoring_output_prefix=self.authoring_output_prefix, _token=_ADMITTED)
            out._check_report(report)
            # The expected descriptor is only a recipe until this exact real
            # Store publication returns. No runtime escapes before it succeeds.
            pin = self._retain(scoped, owner, name, report, self.receipt_limits['admission_bytes'])
            need(pin == expected, 'actual final admission publication identity')
            self.current_owner = None; self.custody.receipt = pin; self.custody.complete = True
            return out
        except BaseException as error:
            self._fail(error, 'factored_admission')

