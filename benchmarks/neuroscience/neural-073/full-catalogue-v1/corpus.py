"""Exact catalogue source and future admitted canonical-corpus integration.

Import and load_catalogue perform no neural, numerical-runtime or key I/O.
The remaining entry points require the independently admitted OperatorContext.
The mapping never searches for data, infers geometry, or substitutes supplied C.
"""
from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, fields
import hashlib
import math
import os
from pathlib import Path
import stat
import struct
import time
from types import MappingProxyType
import weakref

from . import declaration as dec
from .runtime import admission
from .runtime.admission.catalogue import digest, strict_json, canonical_json
from .runtime.core.plan import PrivateRecord, StudyPlan


class CorpusError(ValueError):
    """Missing, changed or overbudget evidence is invalid, never downscoped."""


class CorpusFailure(CorpusError):
    """Original failure is chained; bounded trusted metadata remains inspectable."""
    def __init__(self, original, receipt):
        super().__init__('corpus admission failed: ' + type(original).__name__)
        self.receipt = receipt


def _need(test, message):
    if not test:
        raise CorpusError(message)


def _keys(value, expected, label):
    _need(type(value) is dict and set(value) == set(expected), 'closed fields: ' + label)
    return value


def _positive(value, label, *, zero=False):
    _need(type(value) is int and (0 if zero else 1) <= value <= 2**53-1,
          'finite integral bound: ' + label)
    return value


def _root(task_root, package):
    root = dec._absolute(str(task_root))
    _need(type(package) is dict and Path(package.get('root', '')) == root,
          'explicit package root mismatch')
    return root


def load_catalogue(task_root, package, *, ledger):
    """Read all 14 exact source metadata bodies; return the actual Catalogue.

    Packaged page filenames differ from historical logical PAGE_PINS keys.
    Their exact indexed bijection is checked, not guessed from row contents.
    A fresh ReadLedger records this read even if load_package read them earlier.
    """
    root = _root(task_root, package)
    _need(type(ledger) is dec.ReadLedger, 'actual metadata ReadLedger required')
    for path, pin in dec.CATALOGUE_METADATA.items():
        _need(package['B']['files'].get(path) == dict(pin, role='static'),
              'catalogue metadata absent from authenticated code closure')
    _need(ledger.reserved_bytes + sum(p['bytes'] for p in dec.CATALOGUE_METADATA.values()) <= ledger.cap,
          'all 14 source metadata reads must fit before first read')
    bodies = {}
    for path, pin in dec.CATALOGUE_METADATA.items():
        bodies[path] = dec.read_bytes_pinned(root/path, pin, limit=pin['bytes'], ledger=ledger)
    pin_document = bodies['static/catalogue/PAGE_PINS.json']
    document = strict_json(pin_document)
    entries = document['pages']
    _need(type(entries) is list and len(entries) == 12, 'exact twelve logical pages')
    logical = {}
    for index, entry in enumerate(entries):
        local = 'static/catalogue/page_%02d.json' % index
        _need(entry['path'].endswith('/census/page-%02d.compact.json' % index),
              'historical logical page identity/order')
        _need({k:entry[k] for k in ('bytes','sha256')} == dec.CATALOGUE_METADATA[local],
              'logical/packaged page pin mismatch')
        _need(entry['path'] not in logical, 'duplicate logical page')
        logical[entry['path']] = bodies[local]
    return admission.catalogue_from_pages(logical, pin_document,
                                           bodies['static/catalogue/SUPPORT.json'])


def build_study_plan(catalogue, *, assessment_digest, source_contract_digest, context_key):
    """Actual metadata StudyPlan; a digest argument alone grants no admission.

    Run uses actual assessment; grade uses its authenticated terminal commitment.
    The shared source contract is Hraw(TASK.json), supplied by the trusted caller.
    """
    _need(type(catalogue) is admission.Catalogue, 'actual issued Catalogue required')
    catalogue.require_valid()
    normalize = {'dir-ap':'AP', 'dir-pa':'PA', 'ffx':'FFX', 'AP':'AP', 'PA':'PA', 'FFX':'FFX'}
    try:
        records = [PrivateRecord(r.record_id,r.person,r.label,normalize[r.construction])
                   for r in catalogue.records]
    except KeyError as error:
        raise CorpusError('unrecognized declared acquisition construction') from error
    return StudyPlan(records, assessment_digest=assessment_digest,
                     source_contract_digest=source_contract_digest, context_key=context_key,
                     domain='authentic' if catalogue.domain == admission.SOURCE_DOMAIN else 'invented')


class Deadline:
    """Cooperative monotonic deadline; the selected host also enforces wall time."""
    def __init__(self, absolute):
        _need(type(absolute) in (int,float) and math.isfinite(absolute), 'explicit finite deadline')
        self.absolute = float(absolute)
        self.check()

    def check(self):
        _need(time.monotonic() < self.absolute, 'whole invocation wall deadline exceeded')


class Workspace:
    """Logical live workspace accounting, not a claim about measured native RSS."""
    def __init__(self, cap, deadline):
        self.cap = _positive(cap,'workspace')
        self.deadline = deadline
        self.live = self.peak = self.cumulative = 0
        self.by_kind = {}

    def acquire(self, size, kind):
        self.deadline.check()
        _positive(size,'workspace reservation',zero=True)
        _need(self.live + size <= self.cap, 'complete workspace exceeds selected capacity: ' + kind)
        self.live += size
        self.peak = max(self.peak,self.live)
        self.cumulative += size
        self.by_kind[kind] = self.by_kind.get(kind,0) + size

    def release(self, size):
        _need(type(size) is int and 0 <= size <= self.live, 'invalid workspace release')
        self.live -= size

    @contextmanager
    def reservation(self, size, kind):
        self.acquire(size,kind)
        try:
            yield
        finally:
            self.release(size)

    def receipt(self):
        return {'limit_bytes':self.cap,'live_reserved_bytes':self.live,
                'peak_reserved_bytes':self.peak,'cumulative_materialization_reserved_bytes':self.cumulative,
                'reservations_by_kind':dict(sorted(self.by_kind.items())),
                'physical_rss_measurement':False}


class _CanonicalValues(Sequence):
    """Immutable, finite, little-endian byte-backed values; no tuple materialization."""
    __slots__ = ('_raw','_deadline','__weakref__')

    def __init__(self, raw, deadline):
        object.__setattr__(self,'_raw',raw)
        object.__setattr__(self,'_deadline',deadline)

    def __setattr__(self, name, value):
        raise CorpusError('canonical values are immutable')

    def __len__(self):
        return len(self._raw)//8

    def __getitem__(self, index):
        self._deadline.check()
        if type(index) is not int:
            raise TypeError('scalar canonical indexing only; no implicit slice materialization')
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        return struct.unpack_from('<d', self._raw, 8*index)[0]


def _read_canonical(path, pin, ledger, deadline, workspace):
    """Descriptor-relative, non-following read with exact full extent/hash checks."""
    path = dec._absolute(str(path))
    size = pin['bytes']
    _need(hasattr(os,'O_NOFOLLOW') and hasattr(os,'O_DIRECTORY'),'safe reads unavailable')
    workspace.acquire(8192,'canonical_read_receipt_metadata')
    row = ledger.reserve(path,size)
    held, chain = [], []
    original = None
    try:
        deadline.check()
        fd = os.open('/',os.O_RDONLY|os.O_DIRECTORY)
        held.append(fd)
        for part in path.parts[1:-1]:
            child = os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            held.append(child)
            chain.append((fd,part,child,dec._stamp(os.fstat(child))))
            fd = child
        body = os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        held.append(body)
        before = os.fstat(body)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size,
              'canonical original must be exact regular single-link extent')
        # Raw pieces plus joined bytes coexist briefly. The returned immutable
        # backing has its own live reservation, transferred to its finalizer.
        with workspace.reservation(size,'canonical_read_pieces'):
            pieces, left = [], size
            while left:
                deadline.check()
                block = os.read(body,min(left,65536))
                _need(bool(block),'short canonical source read')
                pieces.append(block)
                left -= len(block)
                row['read_bytes'] += len(block)
                ledger.actual_bytes += len(block)
            raw = b''.join(pieces)
            del pieces,block
        after = os.fstat(body)
        _need(dec._stamp(before) == dec._stamp(after) == dec._stamp(os.stat(path.name,dir_fd=fd,follow_symlinks=False)),
              'canonical original changed or replaced during read')
        for parent,name,child,stamp in chain:
            _need(dec._stamp(os.fstat(child)) == stamp == dec._stamp(os.stat(name,dir_fd=parent,follow_symlinks=False)),
                  'canonical original ancestor changed during read')
        _need(hashlib.sha256(raw).hexdigest() == pin['sha256'],'canonical original SHA mismatch')
        for index,(value,) in enumerate(struct.iter_unpack('<d',raw)):
            if index % 8192 == 0:
                deadline.check()
            _need(math.isfinite(value),'nonfinite canonical original value')
        deadline.check()
        row['status'] = 'read_verified'
        return raw
    except BaseException as error:
        original = error
        row['status'],row['error_type'] = 'failed',type(error).__name__
        raise
    finally:
        errors = []
        for fd in reversed(held):
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
        if errors:
            if original is not None:
                raise BaseExceptionGroup('canonical read and close failures',[original,*errors]) from None
            raise ExceptionGroup('canonical descriptor close failed',errors)


class CanonicalMapping(Mapping):
    """Bounded LRU over the complete explicit inventory, including every reread.

    Only load_corpus constructs this after real independent operator admission.
    No original file is altered or removed; close releases owned cache references.
    Live escaped value references remain accounted until actually released.
    """
    def __init__(self, root, entries, geometry, limits, deadline, *, seal, workspace=None):
        _need(seal is _BUNDLE_SEAL,'canonical mapping requires admitted corpus factory')
        self.root,self.geometry = root,geometry
        self.entries = MappingProxyType({rid:MappingProxyType(dict(pin)) for rid,pin in entries.items()})
        self.limits = MappingProxyType(dict(limits))
        self.deadline = deadline
        self.ledger = dec.ReadLedger(limits['total_read_bytes'])
        self.workspace = Workspace(limits['max_workspace_bytes'],deadline) if workspace is None else workspace
        _need(type(self.workspace) is Workspace and self.workspace.cap == limits['max_workspace_bytes'] and
              self.workspace.deadline is deadline,'exact shared corpus workspace required')
        self._cache = OrderedDict()
        self._cache_bytes = self._cache_peak = self._cache_hits = self._misses = 0
        self._closed = False
        self._last_request = None

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def __getitem__(self,rid):
        self.deadline.check()
        _need(not self._closed,'canonical mapping closed')
        if rid not in self.entries:
            raise KeyError(rid)
        self._last_request = rid
        if rid in self._cache:
            self._cache_hits += 1
            self._cache.move_to_end(rid)
            return self._cache[rid]
        pin = self.entries[rid]
        size = pin['bytes']
        while self._cache and (self._cache_bytes+size > self.limits['cache_bytes'] or
                               self.workspace.live+2*size > self.workspace.cap):
            _,old = self._cache.popitem(last=False)
            self._cache_bytes -= len(old)*8
            del old
        self._misses += 1
        self.workspace.acquire(size,'canonical_backing')
        try:
            raw = _read_canonical(self.root/pin['path'],pin,self.ledger,self.deadline,self.workspace)
            values = _CanonicalValues(raw,self.deadline)
            weakref.finalize(values,self.workspace.release,size)
        except BaseException:
            self.workspace.release(size)
            raise
        if size <= self.limits['cache_bytes']:
            self._cache[rid] = values
            self._cache_bytes += size
            self._cache_peak = max(self._cache_peak,self._cache_bytes)
        return values

    def receipt(self):
        return {'canonical_read_reserved_bytes':self.ledger.reserved_bytes,
                'canonical_read_actual_bytes':self.ledger.actual_bytes,
                'canonical_read_limit_bytes':self.ledger.cap,
                'canonical_read_attempts':[dict(row) for row in self.ledger.attempts],
                'cache_hits':self._cache_hits,'cache_misses':self._misses,
                'cache_bytes':self._cache_bytes,'cache_peak_bytes':self._cache_peak,
                'workspace':self.workspace.receipt(),'closed':self._closed,
                'last_requested_record_id':self._last_request}

    def close(self):
        self._closed = True
        self._cache.clear()
        self._cache_bytes = 0


_BUNDLE_SEAL = object()


def _validate_sections(corpus, capacity):
    _keys(corpus,('schema','inventory_pin','canonical_root','geometry','identity_conflicts','adjudications'),'corpus')
    _need(corpus['schema'] == 'n073_corpus_section_v1','corpus schema')
    dec._absolute(corpus['canonical_root'])
    _keys(corpus['geometry'],('shape','affine','orientation'),'geometry')
    geometry = admission.Geometry(**corpus['geometry'])
    geometry.validate(full=True)
    _keys(capacity,('schema','metadata_limits','canonical_limits','reference_capacity','preparation_numeric_limits','storage','whole_wall_seconds'),'capacity')
    _need(capacity['schema'] == 'n073_capacity_section_v1','capacity schema')
    limits = _keys(capacity['canonical_limits'],('total_read_bytes','per_file_bytes','cache_bytes','max_array_elements','max_workspace_bytes'),'canonical limits')
    for key,value in limits.items():
        _positive(value,key,zero=key=='cache_bytes')
    _need(geometry.voxels <= limits['max_array_elements'],'full geometry exceeds array element cap')
    _need(8*geometry.voxels <= limits['per_file_bytes'],'full geometry exceeds per-file byte cap')
    metadata = _keys(capacity['metadata_limits'],('file_bytes','total_bytes'),'metadata limits')
    for key,value in metadata.items():
        _positive(value,key)
    dec._pin(corpus['inventory_pin'],max_bytes=metadata['file_bytes'])
    _need('path' in corpus['inventory_pin'],'explicit inventory path required')
    _need(type(corpus['identity_conflicts']) is list and type(corpus['adjudications']) is list,
          'explicit identity conflict and adjudication lists required')
    return geometry,dict(limits)


def corpus_bindings(catalogue, corpus_section, capacity_section, source_contract_digest):
    geometry,limits = _validate_sections(corpus_section,capacity_section)
    return {'catalogue_digest':catalogue.fingerprint,'geometry_digest':geometry.fingerprint,
            'inventory_pin_digest':digest(corpus_section['inventory_pin']),
            'canonical_root_digest':digest(corpus_section['canonical_root']),
            'canonical_limits_digest':digest(limits),'source_contract_digest':dec._sha(source_contract_digest)}


def _parse_inventory(document, catalogue, geometry, limits):
    _keys(document,('schema','records'),'canonical inventory')
    _need(document['schema'] == 'n073_canonical_inventory_v1','inventory schema')
    rows = document['records']
    _need(type(rows) is list and len(rows) == len(catalogue.records),'all original records required')
    expected = set(catalogue.by_id)
    entries,receipts,paths = {},{},{}
    receipt_fields = tuple(f.name for f in fields(admission.OriginalReceipt))
    for row in rows:
        _keys(row,('record_id','canonical','original_receipt'),'inventory record')
        rid = row['record_id']
        _need(type(rid) is str and rid in expected and rid not in entries,'unknown or duplicate inventory record')
        pin = _keys(row['canonical'],('path','bytes','sha256'),'canonical pin')
        dec.relative_path(pin['path'])
        dec._pin(pin,max_bytes=limits['per_file_bytes'])
        _need(pin['bytes'] == geometry.voxels*8,'exact full canonical geometry extent required')
        _need(pin['path'] not in paths or paths[pin['path']] == pin,
              'one explicit canonical path has conflicting declared pins')
        paths[pin['path']] = dict(pin)
        receipt = admission.OriginalReceipt(**_keys(row['original_receipt'],receipt_fields,'original receipt'))
        receipt.validate()
        _need(receipt.record_id == rid and receipt.domain == catalogue.domain,'original receipt record/domain join')
        entries[rid],receipts[rid] = dict(pin),receipt
    _need(set(entries) == expected,'full canonical inventory identity set required')
    # At least the first full pass must fit. Every subsequent reread is charged
    # dynamically; exhausting the selected cumulative cap invalidates the run.
    _need(sum(p['bytes'] for p in entries.values()) <= limits['total_read_bytes'],
          'first full canonical pass exceeds cumulative read cap')
    return entries,receipts


def _operator(operator,package,corpus_section,capacity_section):
    from .authority import OperatorContext
    _need(type(operator) is OperatorContext,'independently admitted concrete operator required')
    operator.require(action='run')
    selected_package = operator.package
    _need(selected_package['pins'] == package['pins'] and
          all(selected_package[k] == package[k] for k in ('A','B','T','D','F')) and
          Path(selected_package['root']) == Path(package['root']),
          'operator package source identity/document mismatch')
    _need(operator.sections['corpus'] == corpus_section and operator.sections['capacity'] == capacity_section,
          'caller corpus/capacity differs from independently selected sections')
    return operator


@dataclass(frozen=True)
class CorpusBundle:
    catalogue: object
    geometry: object
    values_by_id: object
    original_receipts: object
    observations: object
    screen: object
    assessment: object
    work: object
    package: object
    operator: object
    metadata_read_receipt: object
    admission_bindings: object
    admission_authority_digest: str
    persistent_workspace_bytes: int
    _production: object
    _seal: object

    def close(self):
        before = self.values_by_id._cache_bytes
        self.values_by_id.close()
        result = {'schema':'n073_corpus_cache_cleanup_v1','cache_bytes_before':before,
                  'cache_bytes_after':self.values_by_id._cache_bytes,'closed':self.values_by_id._closed,
                  'live_workspace_reserved_bytes':self.values_by_id.workspace.live,
                  'original_files_modified_or_removed':0,
                  'escaped_value_and_metadata_references':'remain reserved until released'}
        return result

    @property
    def producer_receipt(self):
        return strict_json(canonical_json(dict(self._production)))

    def receipt(self):
        _need(self._seal is _BUNDLE_SEAL,'actual corpus bundle required')
        return {'schema':'n073_actual_corpus_receipt_v1','catalogue_digest':self.catalogue.fingerprint,
                'geometry':self.geometry.public_descriptor(),'geometry_digest':self.geometry.fingerprint,
                'assessment_digest':self.assessment.fingerprint,'screening_digest':self.screen.fingerprint,
                'observations_digest':self.assessment.observations_digest,
                'original_receipts_digest':self.assessment.original_receipts_digest,
                'identity_conflicts_digest':self.assessment.identity_conflicts_digest,
                'adjudications_digest':self.assessment.adjudications_digest,
                'numeric_checks_passed':self.assessment.numeric_checks_passed,'issues':list(self.assessment.issues),
                'external_gates':list(self.assessment.external_gates),'records':len(self.catalogue.records),
                'observation_records':len(self.observations),'receipt_records':len(self.original_receipts),
                'duplicate_screen_counts':dict(self.screen.counts),'numeric_work':self.work.as_dict(),
                'metadata_reads':dict(self.metadata_read_receipt),'canonical_reads':self.values_by_id.receipt(),
                'admission_bindings':dict(self.admission_bindings),
                'admission_authority_digest':self.admission_authority_digest,
                'C105_production':self.producer_receipt,
                'scientific_outcome_or_submission_readiness':False}


def load_corpus(task_root, package, corpus_section, capacity_section, *, catalogue, ledger, operator, deadline):
    """Future full production admission, never a supplied-assessment hydration.

    Requires exact independently authenticated run selection before any inventory
    or canonical-body read. Numerical runtime activation is a prior owner action.
    """
    root = _root(task_root,package)
    _operator(operator,package,corpus_section,capacity_section)
    from .runtime.runner.runtime_api import require_domain
    require_domain('authentic')
    _need(type(catalogue) is admission.Catalogue and catalogue.domain == admission.SOURCE_DOMAIN,
          'full authentic source Catalogue required')
    catalogue.require_valid()
    _need(type(ledger) is dec.ReadLedger,'actual metadata ReadLedger required')
    geometry,limits = _validate_sections(corpus_section,capacity_section)
    clock = Deadline(deadline)
    wall = capacity_section['whole_wall_seconds']
    _need(type(wall) in (int,float) and math.isfinite(wall) and wall > 0 and
          clock.absolute-time.monotonic() <= wall,'deadline exceeds selected whole wall limit')
    bindings = corpus_bindings(catalogue,corpus_section,capacity_section,package['pins']['T']['sha256'])
    capability = operator.issuer.capability('admission','complete-corpus',bindings)
    authority_digest = capability.require(role='admission',domain='authentic',bindings=bindings)
    pin = corpus_section['inventory_pin']
    inventory_path = dec._absolute(pin['path']) if pin['path'].startswith('/') else root/dec.relative_path(pin['path'])
    metadata = capacity_section['metadata_limits']
    _need(ledger.cap <= metadata['total_bytes'],'metadata ledger exceeds selected total cap')
    workspace = Workspace(limits['max_workspace_bytes'],clock)
    # Bound both the persistent original metadata and transient JSON decoding
    # before reading. These are explicit conservative logical reservations, not
    # an empirical claim about interpreter RSS. No file-size guesses are used.
    persistent = len(catalogue.records)*(4096+(geometry.voxels+7)//8)+32*pin['bytes']
    workspace.acquire(persistent,'full_observation_and_inventory_metadata')
    try:
        with workspace.reservation(32*pin['bytes'],'inventory_parse_and_join'):
            inventory,raw = dec.read_json_pinned(inventory_path,pin,limit=metadata['file_bytes'],ledger=ledger)
            entries,receipts = _parse_inventory(inventory,catalogue,geometry,limits)
            del inventory,raw
    except BaseException as error:
        receipt = {'schema':'n073_corpus_inventory_original_failure_v1',
                   'original_error_type':type(error).__name__,'workspace':workspace.receipt(),
                   'metadata_reads':{'actual_bytes':ledger.actual_bytes,'reserved_bytes':ledger.reserved_bytes,
                                     'attempts':[dict(row) for row in ledger.attempts]},
                   'canonical_body_reads':0}
        raise CorpusFailure(error,receipt) from error
    conflicts = tuple(admission.IdentityConflict(**_keys(x,('record_ids','source_evidence_digest'),'identity conflict'))
                      for x in corpus_section['identity_conflicts'])
    adjudications = tuple(admission.Adjudication(**_keys(x,('flag_id','disposition','evidence_digest','decision_receipt_digest'),'adjudication'))
                         for x in corpus_section['adjudications'])
    values = CanonicalMapping(dec._absolute(corpus_section['canonical_root']),entries,geometry,limits,clock,
                              seal=_BUNDLE_SEAL,workspace=workspace)
    work = admission.WorkCounter()
    try:
        # Full original inventory and support observations stay reserved.
        observations = {}
        for rid in entries:
            clock.check()
            observations[rid] = admission.inspect_array(rid,values[rid],geometry,receipts[rid],work)
            _need(observations[rid].decoded_sha256 == entries[rid]['sha256'],
                  'observation differs from exact canonical pin')
        # Exact/equal-support predicates are taken from the unchanged source
        # screen. Derive a conservative output bound from ACTUAL observations:
        # every equal-support cross-person pair may yield a near-content flag,
        # and at most floor(N/2) disjoint exact groups can add flags. A SHA match
        # is not subtracted: the original screen still verifies actual bytes.
        support_people = defaultdict(Counter)
        record_map = catalogue.by_id
        for rid,observation in observations.items():
            support_people[observation.support_bits][record_map[rid].person] += 1
        equal_pairs = sum((sum(c.values())**2-sum(n*n for n in c.values()))//2
                          for c in support_people.values())
        max_flags = equal_pairs + len(entries)//2
        screen_workspace = (4096*max_flags + 8*geometry.voxels*8 +
                            8192*len(entries) + 4096*len(conflicts))
        del support_people,record_map
        with values.workspace.reservation(screen_workspace,'complete_duplicate_screen_worst_case'):
            screen = admission.screen_duplicates(catalogue,observations,values,work)
            clock.check()
        # The report's actual metadata stays live; do not release its reservation.
        report_bytes = 4096*len(screen.flags)+8192*len(entries)
        values.workspace.acquire(report_bytes,'retained_screen_report')
        persistent += report_bytes
        assessment = admission.assess_corpus(catalogue,observations,receipts,screen,adjudications,
                                             identity_conflicts=conflicts)
        clock.check()
        _need(assessment.numeric_checks_passed and not assessment.issues,
              'complete source assessment invalid; unresolved adjudications remain')
        expected = operator.selection_constraints.get('assessment_digest')
        _need(expected is None or assessment.fingerprint == expected,'actual assessment differs from optional root constraint')
        bundle = CorpusBundle(catalogue,geometry,values,MappingProxyType(receipts),MappingProxyType(observations),
                            screen,assessment,work,package,operator,
                            MappingProxyType({'reserved_bytes':ledger.reserved_bytes,'actual_bytes':ledger.actual_bytes,
                                              'cap':ledger.cap}),MappingProxyType(bindings),authority_digest,persistent,{},_BUNDLE_SEAL)
        weakref.finalize(bundle,values.workspace.release,persistent)
        return bundle
    except BaseException as error:
        values.close()
        receipt = {'schema':'n073_corpus_original_failure_v1','original_error_type':type(error).__name__,
                   'canonical_reads':values.receipt(),'numeric_work':work.as_dict(),
                   'completed_observation_records':len(locals().get('observations',{})),
                   'assessment_issues':list(assessment.issues) if 'assessment' in locals() else [],
                   'metadata_read_actual_bytes':ledger.actual_bytes,
                   'metadata_read_reserved_bytes':ledger.reserved_bytes}
        raise CorpusFailure(error,receipt) from error


def generate_reference_data(bundle, *, context_key, permutation_key, source_contract_digest, numeric_limits):
    """Produce actual original C105 for every record, then actual ReferenceData.

    Returns ReferenceData; bundle.producer_receipt records its actual C production.
    No supplied C, array subsampling,
    numerical activation, fitted model or partial source profile is accepted.
    """
    _need(type(bundle) is CorpusBundle and bundle._seal is _BUNDLE_SEAL,'factory-issued corpus bundle required')
    _need(not bundle._production,'original C105 producer is single-use per admitted corpus')
    operator = bundle.operator
    operator.require(action='run')
    from .runtime.runner.runtime_api import require_domain, numpy_api
    require_domain('authentic')
    from .runtime.transforms.numeric import NumericLimits, c_descriptor
    from .runtime.admission.export import OriginalDescriptor, descriptors_digest
    from .constructors import construct_trusted
    _need(type(numeric_limits) is NumericLimits,'actual selected NumericLimits required')
    _need(vars(numeric_limits) == operator.sections['capacity']['preparation_numeric_limits'],
          'C preparation numeric limits differ from selected capacity')
    _need(source_contract_digest == bundle.package['pins']['T']['sha256'],'source contract must be Hraw(TASK.json)')
    _need(context_key == operator.keys['context'] and permutation_key == operator.keys['permutation'],
          'reference keys differ from independently admitted operator')
    D,N = bundle.geometry.voxels,len(bundle.catalogue.records)
    numeric_limits.require(32*D+2048,256*D+16384,'full_original_C105')
    source_pin = bundle.package['B']['files']['runtime/transforms/numeric.py']
    producer = digest({'schema':'n073_original_C105_producer_v1','source':dict(source_pin),
                       'call':'c_descriptor','dtype':'<f8','order':'C','feature_count':105,
                       'geometry_digest':bundle.geometry.fingerprint,'task_digest':source_contract_digest})
    workspace = bundle.values_by_id.workspace
    np = numpy_api()
    descriptors = {}
    descriptor_reservation = N*(105*32+1024)
    workspace.acquire(descriptor_reservation,'complete_original_C105_descriptors')
    # The closed constructor requires an actual observations dict. Its own
    # ReferenceData producer then copies both full observations and C mappings.
    # Reserve all N metadata entries explicitly; these are shallow metadata
    # copies with shared immutable objects, never invented or copied neural data.
    argument_copy_reservation = 256*N + 4096
    reference_copy_reservation = 512*N + 8192
    reference_copy_acquired = False
    try:
        for rid in bundle.values_by_id:
            bundle.values_by_id.deadline.check()
            with workspace.reservation(264*D+16384,'C105_original_full_volume_and_numeric_workspace'):
                original = bundle.values_by_id[rid]
                # Immutable canonical bytes are already authenticated on each miss.
                # Revalidate their original observation before every descriptor.
                observation = admission.inspect_array(rid,original,bundle.geometry,bundle.original_receipts[rid],bundle.work)
                _need(observation.private_descriptor() == bundle.observations[rid].private_descriptor(),
                      'original array differs since admission')
                volume = np.frombuffer(original._raw,dtype='<f8').astype(np.float64,copy=True).reshape(bundle.geometry.shape,order='C')
                values = c_descriptor(volume,limits=numeric_limits)
                descriptors[rid] = OriginalDescriptor(rid,observation.decoded_sha256,producer,tuple(float(v) for v in values))
                del values,volume,original
        bundle.values_by_id.deadline.check()
        workspace.acquire(reference_copy_reservation,'ReferenceData_retained_full_metadata_copies')
        reference_copy_acquired = True
        with workspace.reservation(argument_copy_reservation,'ReferenceData_full_observation_argument_copy'):
            data = construct_trusted('ReferenceData', {
                'catalogue':bundle.catalogue, 'assessment':bundle.assessment,
                'observations':dict(bundle.observations), 'values_by_id':bundle.values_by_id,
                'original_descriptors':descriptors, 'context_key':context_key,
                'permutation_key':permutation_key, 'source_contract_digest':source_contract_digest})
        expected = operator.selection_constraints.get('plan_digest')
        _need(expected is None or data.plan.binding_digest == expected,'actual plan differs from optional root constraint')
        receipt = {'schema':'n073_actual_C105_production_v1','producer_contract_digest':producer,
                   'transform_source_digest':source_pin['sha256'],'source_contract_digest':source_contract_digest,
                   'catalogue_digest':bundle.catalogue.fingerprint,'assessment_digest':bundle.assessment.fingerprint,
                   'plan_digest':data.plan.binding_digest,'descriptors_digest':descriptors_digest(descriptors),
                   'descriptor_records':len(descriptors),'descriptor_features':105,'calls':N,
                   'reference_constructor':'construct_trusted:ReferenceData',
                   'metadata_copy_records_per_mapping':N,
                   'constructor_metadata_copy_reservations':{
                       'temporary_full_mappings':1,'temporary_bytes':argument_copy_reservation,
                       'retained_full_mappings':2,'retained_bytes':reference_copy_reservation,
                       'array_bytes_copied_by_metadata_join':0},
                   'original_volume_elements_processed':N*D,'descriptor_source':'actual_c_descriptor_on_originals',
                   'supplied_C_hydration':False,
                   'canonical_read_reserved_bytes_at_production':bundle.values_by_id.ledger.reserved_bytes}
        # This reservation remains live with the returned ReferenceData. Bundle
        # close clears canonical cache only, never lies that escaped data vanished.
        data._corpus_owner = bundle  # Keep original metadata reservations live with all consumers.
        weakref.finalize(data,workspace.release,descriptor_reservation+reference_copy_reservation)
        bundle._production.update(receipt)
        return data
    except BaseException as error:
        workspace.release(descriptor_reservation + (reference_copy_reservation if reference_copy_acquired else 0))
        receipt = {'schema':'n073_C105_original_failure_v1','original_error_type':type(error).__name__,
                   'completed_descriptor_records':len(descriptors),'corpus':bundle.receipt()}
        raise CorpusFailure(error,receipt) from error
