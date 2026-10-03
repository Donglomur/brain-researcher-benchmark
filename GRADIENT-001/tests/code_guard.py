"""Draft non-scientific entrypoint guard, adapted from qualified PR198 bootstrap.

No filesystem access on import. Read/hash all declared code and private/public
documents before compiling or executing any module; compile the exact bytes
read, without sys.path additions, loaders, pyc files or cached private modules.
Production wrappers supply fixed closures. The explicit generic API also permits
tiny manufactured fixtures; it is not an alternative scientific authority.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import types

CODE_CAP = 1024**2
DOCUMENT_CAP = 4 * 1024**2


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def safe_path(value):
    raw = os.fspath(value)
    need(type(raw) is str and raw.startswith('/') and '\0' not in raw
         and not any(part in ('.', '..') for part in raw.split('/')), 'absolute_lexical_path')
    path = Path(raw)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'symlink_path')
            if part != path:
                need(stat.S_ISDIR(mode), 'nondirectory_ancestor')
    return path


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def pinned_bytes(path, digest, cap):
    need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'unfrozen_sha256_pin')
    need(type(cap) is int and 0 < cap <= 4 * 1024**2, 'read_cap')
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'bounded_regular_file')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        need(identity(os.fstat(stream.fileno())) == identity(before), 'open_identity')
        raw = stream.read(cap + 1)
        need(identity(os.fstat(stream.fileno())) == identity(before), 'read_identity')
    need(identity(path.lstat()) == identity(before), 'path_identity')
    need(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == digest, 'sha256_mismatch')
    return raw


def documents(directory, pins, public_paths):
    root = safe_path(directory)
    need(type(pins) is dict and pins and type(public_paths) is dict
         and set(public_paths) == set(pins), 'document_closure')
    paths, payloads = {}, {}
    for name, spec in pins.items():
        need(type(name) is str and type(spec) in (tuple, list) and len(spec) == 2, 'document_spec')
        filename, digest = spec
        need(type(filename) is str and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*[.]json', filename),
             'document_filename')
        private = root / filename
        raw = pinned_bytes(private, digest, DOCUMENT_CAP)
        need(pinned_bytes(public_paths[name], digest, DOCUMENT_CAP) == raw, 'public_private_document_identity')
        paths[name], payloads[name] = str(private), raw
    return paths, payloads


def load_closure(directory, module_pins, document_pins, public_paths):
    """Explicit ordered DAG; production caller must supply its exact fixed list."""
    root = safe_path(directory)
    need(root.is_dir() and type(module_pins) is dict and module_pins, 'code_closure')
    payloads = {}
    for name, digest in module_pins.items():
        need(type(name) is str and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', name), 'module_name')
        payloads[name] = pinned_bytes(root / (name + '.py'), digest, CODE_CAP)
    paths, doc_bytes = documents(root, document_pins, public_paths)
    compiled = {name: compile(raw, str(root / (name + '.py')), 'exec') for name, raw in payloads.items()}
    previous = {name: sys.modules.get(name) for name in module_pins}
    present = {name: name in sys.modules for name in module_pins}
    modules = {}
    try:
        # Placeholders prevent falling through to public/cwd files if a declared
        # dependency is incorrectly ordered. Such a closure must fail, not load
        # a mutable file in its place. The reviewed closure is dependency-first.
        for name in module_pins:
            module = types.ModuleType(name)
            module.__file__, module.__package__ = str(root / (name + '.py')), ''
            modules[name] = module
            sys.modules[name] = module
        for name, code in compiled.items():
            exec(code, modules[name].__dict__)
    except BaseException:
        for name in module_pins:
            if present[name]:
                sys.modules[name] = previous[name]
            else:
                sys.modules.pop(name, None)
        raise
    return dict(modules=modules, module_bytes=payloads, module_pins=dict(module_pins),
                private_dir=root, private_documents=paths, document_bytes=doc_bytes,
                document_pins=dict(document_pins), public_paths=dict(public_paths))


def recheck(context):
    """Check unchanged authority after a call, not a cached output acceptance."""
    for name, digest in context['module_pins'].items():
        need(pinned_bytes(context['private_dir'] / (name + '.py'), digest, CODE_CAP)
             == context['module_bytes'][name], 'private_code_changed')
    paths, payloads = documents(context['private_dir'], context['document_pins'], context['public_paths'])
    need(paths == context['private_documents'] and payloads == context['document_bytes'], 'documents_changed')


def disjoint_output(output, source_root, code_root, document_paths):
    out = safe_path(output)
    for protected in (safe_path(source_root), safe_path(code_root)):
        need(out != protected and out not in protected.parents and protected not in out.parents,
             'output_overlaps_source_or_code')
    for value in document_paths:
        protected = safe_path(value)
        need(out != protected and out not in protected.parents and protected not in out.parents,
             'output_overlaps_document')
    return out


def output_inventory(output, *, require_files):
    """Original PR190 public inventory envelope; regular harmless extras allowed."""
    root = safe_path(output)
    need(root.is_dir(), 'output_directory')
    need(not os.path.lexists(root / 'failure_report.json'), 'authoritative_failure_marker')
    total, count, files = 0, 0, set()
    for path in root.rglob('*'):
        count += 1
        need(count <= 1000, 'output_entry_cap')
        info = path.lstat()
        need(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), 'nonregular_output')
        if stat.S_ISREG(info.st_mode):
            files.add(path.relative_to(root).as_posix())
            total += info.st_size
        need(total <= 256 * 2**20, 'output_total_cap')
    need(set(require_files) <= files, 'missing_required_output')
    return root
