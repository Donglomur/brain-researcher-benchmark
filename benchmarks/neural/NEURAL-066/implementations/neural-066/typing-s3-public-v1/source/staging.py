"""Immutable role views from exact file inventories; no directory-wide mounts."""
import hashlib
import os
import re
from pathlib import Path
from core import encoded, need
from safe_io import capture, child, durable_new, pin, strict, sync_parent

def validate_files(files):
    need(type(files) is dict and files, 'Complete nonempty closed file inventory')
    for name, d in files.items():
        need(type(name) is str and all((re.fullmatch('[A-Za-z0-9_](?:[A-Za-z0-9._ -]*[A-Za-z0-9_.-])?', part) for part in name.split('/'))) and ('..' not in Path(name).parts), 'Safe immutable relative member')
        need(type(d) is dict and set(d) == {'bytes', 'sha256'} and (type(d['bytes']) is int) and (d['bytes'] >= 0) and (type(d['sha256']) is str) and re.fullmatch('[a-f0-9]{64}', d['sha256']), 'Exact member identity')
    return files

def materialize(root, source_root, files, budget):
    """Fresh private exact-file copy, hardened/fsynced before readonly mount."""
    validate_files(files)
    root = Path(root)
    need(not root.exists() and (not root.is_symlink()), 'Fresh owned immutable view')
    root.mkdir(mode=448, parents=True)
    for name, d in sorted(files.items()):
        source = child(source_root, name)
        body = budget.read_file(source, d, max(1, d['bytes']))
        target = root / name
        target.parent.mkdir(mode=448, parents=True, exist_ok=True)
        need(budget.save(target, body) == d, 'Exact complete role-view bytes')
        os.chmod(target, 292)
    manifest = {'schema': 'neural066_closed_role_view_v1', 'files': files}
    raw_manifest = encoded(manifest)
    need(len(raw_manifest) <= getattr(budget, 'max_view_manifest_bytes', len(raw_manifest)), 'Bounded complete view manifest; no membership truncation')
    descriptor = budget.save(root / 'MOUNT_MANIFEST.json', raw_manifest)
    os.chmod(root / 'MOUNT_MANIFEST.json', 292)
    for directory in [root, *[p for p in root.rglob('*') if p.is_dir()]]:
        os.chmod(directory, 365)
    return {'root': str(root.absolute()), 'manifest': descriptor, 'files': files, 'bytes': sum((d['bytes'] for d in files.values())) + descriptor['bytes']}

def verify(view, budget):
    root = Path(view['root'])
    need(not any((p.is_symlink() for p in root.rglob('*'))), 'No unbound links in immutable view')
    body = budget.read_file(child(root, 'MOUNT_MANIFEST.json'), view['manifest'], view['manifest']['bytes'])
    need(strict(body) == {'schema': 'neural066_closed_role_view_v1', 'files': view['files']}, 'Unchanged full view manifest')
    observed = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    need(observed == set(view['files']) | {'MOUNT_MANIFEST.json'}, 'No extra or omitted mounted source/input files')
    for name, d in view['files'].items():
        budget.read_file(child(root, name), d, max(1, d['bytes']))
    return True

def retire(view, externally_closed, budget):
    need(externally_closed is True, 'No input retirement while any owned producer may still exist')
    verify(view, budget)
    root = Path(view['root'])
    for directory in [root, *[p for p in root.rglob('*') if p.is_dir()]]:
        os.chmod(directory, 448)
    for name in [*view['files'], 'MOUNT_MANIFEST.json']:
        child(root, name).unlink()
    for directory in sorted((p for p in root.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        directory.rmdir()
    root.rmdir()
    sync_parent(root)
    budget.retained -= view['bytes']
    budget.tick()
    return {'retired': True, 'verified_complete_bytes': view['bytes']}
