"""Closed host source/input views, bounded artifact reads and complete custody joins."""
import failures
import os
from pathlib import Path
from core import encoded, identity, need
from safe_io import capture, child, pin, strict, sync_parent

def descriptor(path, d):
    return {'source_path': str(Path(path).absolute()), 'bytes': d['bytes'], 'sha256': d['sha256']}

class Workspace:

    def __init__(self, root, budget, metadata):
        self.root = Path(root)
        self.budget = budget
        self.metadata = metadata
        self.views = []
        need(self.root.is_absolute() and self.root.is_dir() and (not self.root.is_symlink()), 'Owned original workspace')

    def json(self, name, value):
        path = self.root / name
        path.parent.mkdir(mode=448, parents=True, exist_ok=True)
        raw = encoded(value)
        need(len(raw) <= self.metadata['json_bytes'], 'Full metadata cap before publication')
        d = self.budget.save(path, raw)
        return descriptor(path, d)

    def read(self, path, d):
        return strict(self.budget.read_file(path, {k: d[k] for k in ('bytes', 'sha256')}, self.metadata['json_bytes']))

    def from_capture(self, record, name):
        need(record['status'] == 'captured' and name in record['output_files'], 'Exact independently closed output member')
        d = record['output_files'][name]
        return descriptor(child(record['capture_root'], name), d)

    def result(self, record):
        d = self.from_capture(record, 'RESULT.json')
        return self.read(d['source_path'], d)

    def stage(self, name, bindings, purpose):
        """Concrete streamed owned copies, partial evidence retained on failure."""
        from transport.staging import stage_files
        root = self.root / name
        root.parent.mkdir(mode=448, parents=True, exist_ok=True)
        try:
            evidence = stage_files(root, {p: {'path': d['source_path'], 'bytes': d['bytes'], 'sha256': d['sha256']} for p, d in bindings.items()}, self.budget)
        except BaseException as exc:
            failures.hold(exc, 'caught')
            if failures.evidence(exc,'stage_evidence') is not None:
                self.views.append(failures.evidence(exc,'stage_evidence'))
            raise
        self.views.append(evidence)
        return {'path': str(root / 'files'), 'kind': 'directory', 'purpose': purpose, 'files': dict(evidence['files'])}

    def verify_mount(self, mount):
        root = Path(mount['path'])
        files = mount['files']
        need(not any((p.is_symlink() for p in root.rglob('*'))) and {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()} == set(files), 'Full unchanged closed mount membership')
        for name, d in files.items():
            self.budget.read_file(child(root, name), d, max(1, d['bytes']))
        return True

    def retire(self, mount, closed):
        from transport.staging import retire_stage
        need(closed is True, 'Independently closed all external consumers before retirement')
        evidence = next((v for v in self.views if str(Path(v['root']) / 'files') == mount['path']))
        result = retire_stage(evidence, self.budget)
        self.budget.retained -= result['payload_retained_credit_eligible_bytes']
        self.budget.tick()
        return result
