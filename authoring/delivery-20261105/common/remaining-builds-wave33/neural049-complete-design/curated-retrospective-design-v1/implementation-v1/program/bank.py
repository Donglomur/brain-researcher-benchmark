"""Concrete immutable per-day bank. Copy once, individually mount, retain on failure."""
import hashlib
import os
import stat
from pathlib import Path
from core import (need, integer, encoded, parse, pin, capture, publish, fresh, canonical, relative,
                  descriptor, parent_chain, stamp, close_preserving, sync_dir, Budget)
from verity import BACKEND, enable, verify


def inventory(packet):
    """Metadata only. Labels remain private; no content-based alias deduplication."""
    rows = {}
    for day in packet['days']:
        entries = list(day['arrays'].items()) + [('label_' + k, v) for k, v in day['labels'].items()]
        if day['disrupted_arrays'] is not None:
            entries += [('D_' + k, v) for k, v in day['disrupted_arrays'].items()]
        for kind, desc in entries:
            name = str(relative(desc['path'])); p = descriptor({k: desc[k] for k in ('bytes', 'sha256')})
            need(name not in rows, 'one complete bank artifact identity')
            private = kind.startswith('label_')
            rows[name] = {'original_path': name, 'pin': p, 'dtype': desc['dtype'], 'shape': desc['shape'],
                          'person': day['person'], 'day': day['day'], 'kind': kind,
                          'path': ('private/' if private else 'public/') + pin(encoded(name))['sha256'] + '.npy'}
    return rows


def copy_closed(source, expected, destination, budget):
    """Bounded streaming copy with no writable FD left open before verity enable."""
    source = parent_chain(source); destination = parent_chain(destination); descriptor(expected)
    budget.reserve_read(expected['bytes'] + 1); budget.reserve_write(expected['bytes']); budget.tick()
    inp = out = None; failure = None; later = []
    try:
        inp = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(inp)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes']
             and stamp(before) == stamp(os.lstat(source)), 'exact complete source bank inode')
        out = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        digest = hashlib.sha256(); count = 0
        while count < expected['bytes']:
            budget.tick(); block = os.read(inp, min(65536, expected['bytes']-count))
            need(block, 'short prepared bank'); digest.update(block); count += len(block)
            pending = memoryview(block)
            while pending:
                budget.tick(); n = os.write(out, pending); need(n > 0, 'short bank copy'); pending = pending[n:]
        need(not os.read(inp, 1) and digest.hexdigest() == expected['sha256']
             and stamp(before) == stamp(os.fstat(inp)) == stamp(os.lstat(source)), 'unchanged exact full bank copy')
        os.fsync(out); budget.tick()
    except BaseException as error:
        failure = error
    finally:
        for fd in (out, inp):
            if fd is not None:
                try: os.close(fd)
                except BaseException as error: later.append(error)
    if failure is not None or later:
        raise BaseExceptionGroup('bank copy/independent close failure', ([failure] if failure else []) + later)
    need(stamp(before) == stamp(os.lstat(source)), 'source name after all closes')
    sync_dir(destination.parent); budget.tick()


def build(authority_descriptor, source_pin, inherited_context):
    """Separate root-selected actual action; not called by source construction."""
    budget = Budget(**inherited_context); root = None; attempted = []; complete = []; a = None
    try:
        raw, _ = capture(authority_descriptor['path'], authority_descriptor['pin'], 1 << 20, budget, readonly=True)
        a = parse(raw)
        need(a.get('schema') == 'neural049_bank_build_authority_v1' and a.get('active') is True
             and a['source_manifest'] == source_pin and a['backend'] == BACKEND
             and a['context'] == inherited_context, 'actual exact independent bank build selection')
        proof, _ = capture(a['qualification']['path'], a['qualification']['pin'], 1 << 20, budget, readonly=True)
        q = parse(proof)
        need(q.get('qualified') is True and q.get('realm') == 'actual_external_evidence'
             and q.get('selection') == pin(encoded({k: v for k, v in a.items() if k != 'qualification'}))
             and q.get('source_manifest') == source_pin and q.get('issuer') == a['operator_identity'],
             'actual fs-verity/build/root/resource qualification before packet')
        for field in ('backend', 'exclusive_namespace', 'source_completion', 'full_resource_plan', 'external_observer'):
            need(q.get(field) is True, 'bank actual qualification ' + field)
        need(type(q['evidence']) is list and q['evidence'], 'bank independent evidence')
        for e in q['evidence']: capture(e['path'], e['pin'], a['evidence_cap'], budget, retain=False, readonly=True)
        from preparation import admit_packet
        need(a['preparation_context']['origin'] == budget.origin and a['preparation_context']['deadline'] == budget.deadline,
             'same separately selected original build helper clock')
        budget.reserve_read(a['preparation_context']['limits']['read_bytes'])
        budget.reserve_write(a['preparation_context']['limits']['write_bytes'])
        prepared = admit_packet(a['packet'], a['preparation_context'])
        packet = prepared['manifest']; rows = inventory(packet)
        need(sum(v['pin']['bytes'] for v in rows.values()) <= integer(a['copy_bytes'], 1), 'full bank prospective copy bytes')
        from core import disjoint
        paths = [canonical(a[k]) for k in ('root', 'packet_root', 'source_root', 'output_root', 'operator_root', 'secrets_root')]
        need(all(disjoint(x, y) for i, x in enumerate(paths) for y in paths[i+1:]), 'complete disjoint bank namespaces')
        need(canonical(a['packet']['root']) == canonical(a['packet_root']), 'same packet root')
        root = fresh(a['root'], budget); fresh(root/'public', budget); fresh(root/'private', budget)
        publish(root/'ATTEMPT.json', encoded({'authority': authority_descriptor, 'source': source_pin,
                'status': 'entered', 'no_retry': True}), budget, readonly=True)
        for name, row in rows.items():
            attempted.append(name); output = root/relative(row['path'])
            copy_closed(Path(a['packet_root'])/relative(name), row['pin'], output, budget)
            row['kernel'] = enable(output, row['pin'], budget, a['kernel_read_per_file'], a['kernel_write_per_file'])
            capture(output, row['pin'], a['array_cap'], budget, retain=False, readonly=True)
            verify(output, row['pin'], row['kernel'], budget); complete.append(name)
        manifest = {'schema': 'neural049_immutable_bank_v1', 'source': source_pin, 'packet': a['packet'],
                    'backend': BACKEND, 'files': rows, 'build_authority': authority_descriptor,
                    'copied_payload_bytes': sum(v['pin']['bytes'] for v in rows.values()), 'per_consumer_copy_bytes': 0}
        body = encoded(manifest); need(len(body) <= a['manifest_cap'], 'full bank manifest cap')
        desc = publish(root/'STORE.json', body, budget, readonly=False)
        kernel = enable(root/'STORE.json', desc, budget, a['kernel_read_manifest'], a['kernel_write_manifest'])
        result = {'schema': 'neural049_bank_build_result_v1', 'status': 'complete', 'manifest': {'path': 'STORE.json', 'pin': desc},
                  'manifest_kernel': kernel, 'source': source_pin, 'authority': authority_descriptor,
                  'logical_costs_before_publication': budget.record(), 'external_natural_closure_required': True,
                  'physical_kernel_io_unknown': True, 'retained': True, 'hard_ioctl_termination_claim': False}
        out = publish(root/'COMPLETE.json', encoded(result), budget, readonly=True); budget.tick()
        return {'path': str(root/'COMPLETE.json'), 'pin': out, 'costs_after_publication': budget.record()}
    except BaseException as error:
        record = {'status': 'failed', 'attempted': attempted, 'completed': complete, 'first_error': type(error).__name__,
                  'costs': {'reads': budget.read_bytes, 'writes': budget.write_bytes}, 'unknown_kernel_completion': True,
                  'early_namespace_unknown': root is None, 'no_retry_or_cleanup': True}
        if root is not None:
            try: publish(root/'FAILED.json', encoded(record), budget, readonly=True)
            except BaseException as later: record['publication_failure'] = type(later).__name__
        error.failure_record = record; raise


class Bank:
    def __init__(self, a, budget, packet):
        self.a, self.budget = a, budget; self.root = canonical(a['roots']['store']); self.measurements = 0
        selected = a['bank']
        need(canonical(a['roots']['operator']) in canonical(selected['qualification']['path']).parents,
             'operator-only bank proof before any body access')
        qraw, _ = capture(selected['qualification']['path'], selected['qualification']['pin'],
                                               a['resources']['qualification_bytes'], budget, readonly=True)
        q = parse(qraw)
        from authority import selection_pin, evidence
        need(q.get('schema') == 'neural049_bank_qualification_v1' and q.get('qualified') is True
             and q.get('realm') == 'actual_external_evidence' and q.get('issuer') == a['operator_identity']
             and q.get('selection') == selection_pin(a) and q.get('bank') == {k: v for k, v in selected.items() if k != 'qualification'},
             'exact independently qualified immutable bank')
        for field in ('natural_build_closure', 'kernel_enforcement', 'physical_namespace', 'individual_mount_custody', 'complete_packet_join'):
            need(q.get(field) is True, 'bank qualification '+field)
        evidence(a, q['evidence'], budget)
        need(selected['manifest']['path'] == 'STORE.json', 'fixed operator-only bank manifest')
        verify(self.root/'STORE.json', selected['manifest']['pin'], selected['manifest_kernel'], budget)
        raw, _ = capture(self.root/'STORE.json', selected['manifest']['pin'], a['resources']['packet_bytes'], budget, readonly=True)
        self.manifest = parse(raw); m = self.manifest
        need(m['schema'] == 'neural049_immutable_bank_v1' and m['source'] == a['source_manifest']
             and m['packet'] == a['packet'] and m['backend'] == BACKEND, 'same complete packet and source bank')
        expected = inventory(packet); need(set(expected) == set(m['files']), 'all original/D/label bank files')
        self.by_path = {}
        for name, row in expected.items():
            actual = m['files'][name]
            need({k: actual[k] for k in row} == row, 'complete exact bank identity')
            self.by_path[str(self.root/relative(row['path']))] = actual
        budget.tick()

    def contains(self, path):
        return self.root in canonical(path).parents

    def verify(self, path, expected):
        name = str(canonical(path)); need(name in self.by_path, 'only admitted selected file, never store metadata')
        row = self.by_path[name]; need(expected == row['pin'], 'exact bank content descriptor')
        result = verify(name, expected, row['kernel'], self.budget); self.measurements += 1; return result

    def source(self, original, expected):
        row = self.manifest['files'][str(relative(original))]
        need(row['pin'] == expected, 'same exact original array identity')
        return str(self.root/relative(row['path']))

    def record(self, remeasure=False):
        if remeasure:
            for path, row in self.by_path.items(): self.verify(path, row['pin'])
        return {'manifest': self.a['bank']['manifest'], 'qualification': self.a['bank']['qualification'],
                'manifest_kernel': self.a['bank']['manifest_kernel'], 'backend': BACKEND,
                'selected_unique_blobs': len(self.by_path), 'successful_blob_measurements': self.measurements,
                'store_retained': True, 'shared_adaptive_state': False, 'per_consumer_copy_bytes': 0}
