"""Private same-buffer code authentication; no original reads on import.

The production entrypoint uses load_private(), with no environment-configurable
code paths or hash overrides. _load is factored only for manufactured I/O tests.
Every file is checked and compiled before any private module executes. Scientific
source authentication remains inside source_reference, never this bootstrap.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import types


# Dependency order is explicit; these are the reviewed private bytes, not /app.
PRIVATE_PINS = {
    'io_contract': 'afe9f4daf4a4ac8829e735094af4abfc6ed7f98dd1be35a03bf6a2385a4ac082',
    'measurement_kernel': 'bc12162f1496b3f4b83419748ee33905a050331cc815ea7d7a9788e6a6fbba9e',
    'wave_contract': 'a8f6a43dd620bd271b1c8841f7f7fe6939c4c55913a490426967968aa587236c',
    'mat_metadata': '66fb278c78255e382b85359d26e76df2059c3f9c9dfb2b3ca73ec138148623f7',
    'independent_fir': '86e0886c018517ab37b887677de140cf477cfc3d1a5d08f82f3b1d5d91de143f',
    'source_reference': '6e8d1c8cae9262e55a4da2598edf29dc4bd58c1ffae173fccd8dee723bb2a097',
    'proof_of_work': '6bc6cc17943c511f0cc1f8409bb9c55d253f0a7703678e5ae9c8e5457578d198',
}
MAX_CODE_BYTES = 1024 * 1024
DOCUMENT_PINS = {
    'manifest_path': ('source_manifest.json', '3970137c64990f680468baf1d51b89a73a61a748639795541e2c2734777b54cd'),
    'method_path': ('method_contract.json', '549cf315f0175ab13c3007703cec298a6cc5080d695aecd9f93f49e98a08ce92'),
    'schema_path': ('output_schema.json', 'fab0dbf2ff1fb60f0596b065ff5f148d9d46da8c89c6e81203dbc346a2070814'),
}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def guarded_path(value):
    text = os.fspath(value)
    need(isinstance(text, str) and text.startswith('/') and '\0' not in text,
         'private_absolute_path')
    need(not any(part in ('.', '..') for part in text.split('/')), 'private_path_traversal')
    path = Path(text)
    for parent in (*reversed(path.parents), path):
        if os.path.lexists(parent):
            mode = parent.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'private_symlink')
            if parent != path:
                need(stat.S_ISDIR(mode), 'private_parent_directory')
    return path


def identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _read(path, digest):
    path = guarded_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= MAX_CODE_BYTES,
         'private_code_regular_size')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        need(identity(before) == identity(os.fstat(stream.fileno())), 'private_code_open_identity')
        raw = stream.read(MAX_CODE_BYTES + 1)
        need(identity(before) == identity(os.fstat(stream.fileno())), 'private_code_read_identity')
    need(identity(before) == identity(path.lstat()), 'private_code_path_identity')
    need(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == digest,
         'private_code_sha256')
    return raw


def _load(directory, pins):
    root = guarded_path(directory)
    need(root.is_dir(), 'private_code_directory')
    need(isinstance(pins, dict) and bool(pins), 'private_pin_mapping')
    compiled = {}
    for name, digest in pins.items():
        need(type(name) is str and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', name), 'private_module_name')
        need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'private_sha_format')
        path = root / (name + '.py')
        compiled[name] = compile(_read(path, digest), str(path), 'exec')
    previous = {name: sys.modules.get(name) for name in pins}
    present = {name: name in sys.modules for name in pins}
    modules = {}
    try:
        # Remove stale/public module objects before executing dependencies.
        for name in pins:
            sys.modules.pop(name, None)
        for name, code in compiled.items():
            module = types.ModuleType(name)
            module.__file__ = str(root / (name + '.py'))
            module.__package__ = ''
            sys.modules[name] = module
            exec(code, module.__dict__)
            modules[name] = module
    except BaseException:
        for name in pins:
            if present[name]:
                sys.modules[name] = previous[name]
            else:
                sys.modules.pop(name, None)
        raise
    return modules


def load_private():
    """Reload held code, never cached output acceptance or agent-visible modules."""
    return _load(Path(__file__).absolute().parent, PRIVATE_PINS)


def authenticated_documents(public_paths, io_module):
    """Check public copies, but return only fixed private document paths."""
    root = Path(__file__).absolute().parent
    private = {}
    for key, (filename, digest) in DOCUMENT_PINS.items():
        path = root / filename
        expected = io_module.read_bytes(path, limit=MAX_CODE_BYTES, sha256=digest)
        observed = io_module.read_bytes(public_paths[key], limit=MAX_CODE_BYTES, sha256=digest)
        need(observed == expected, 'public_private_document_identity')
        private[key] = str(path)
    return private


def disjoint_output(output, data_dir, documents, private_dir):
    out = guarded_path(output)
    need(out.is_dir(), 'output_directory')
    for protected in (guarded_path(data_dir), guarded_path(private_dir)):
        need(out != protected and out not in protected.parents and protected not in out.parents,
             'output_overlaps_source_or_private')
    for value in documents:
        document = guarded_path(value)
        need(out != document and out not in document.parents, 'output_contains_public_input')
    return out
