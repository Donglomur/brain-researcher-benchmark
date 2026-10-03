"""Private DEVCONN code/document authentication; no source reads on import.

Adapted from the reviewed PR197 bootstrap. Authenticate all code and both copies
of all documents before executing any private module. Never add an agent-visible
directory to sys.path or reuse cached private modules. _load is an explicit
manufactured-test seam; production load_private has no path/pin arguments.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import types


MODULE_ORDER = ('inspect_structure', 'source_numerics', 'reporting_kernel',
                'coordinate_contract', 'source_reference', 'io_contract', 'validator')
PRIVATE_PINS = {
    'inspect_structure': 'b0474f9de46a4a76e9307928f0a7f1999f7e51c23c1b3dd3657860a9374f9a15',
    'source_numerics': 'cc39d43bfa3308433a71a0cdd5457d896625d33882c68bb6dfba0d44d4a19673',
    'reporting_kernel': '2b3abe5fe37d3ad68db57301afa68cf6b0f5409abaf81bc5b06494ae4bf88638',
    'coordinate_contract': '40991bfa9e2d78e14163b58a1f5f6ed30b9d14be6143c2671b5b87e5be8fc00e',
    'source_reference': '2ee516449dd0071018b5dec9cacf2ef00b80627cae487bb994f31a2abc86ed0f',
    'io_contract': '2f031453bc675ea33fb735ef10d1cc7aca6c957f1c9b69946be8deae645daa60',
    'validator': '335b956bd6bb498adf3c4c7f6d72b134898a9dd27fe6212d726a62f50ab529c3',
}
DOCUMENT_PINS = {
    'manifest_path': ('source_manifest.json', '0fb419ee0dbea59376f5b0dc1e91d26502e8203d6e7b02334b979e6a1d9f66e3'),
    'method_path': ('method_contract.json', 'e8ba3df50c7cc4bf8b83e2db559c0f1e515f10bf4c45498da84076306e883f6e'),
    'schema_path': ('output_schema.json', '3463740e8c55a9f549590fee013aa29d30480eb63e9984acafd2a41c1a1531b4'),
}
PUBLIC_DOCUMENTS = {key: '/app/' + value[0] for key, value in DOCUMENT_PINS.items()}
DATA_DIR = '/app/data/devconn'
OUTPUT_DIR = '/app/output'
MAX_CODE_BYTES = 1024**2
MAX_DOCUMENT_BYTES = 4 * 1024**2


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def guarded_path(value):
    raw = os.fspath(value)
    need(type(raw) is str and raw.startswith('/') and '\0' not in raw
         and not any(part in ('.', '..') for part in raw.split('/')), 'private_absolute_path')
    path = Path(raw)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'private_symlink')
            if part != path:
                need(stat.S_ISDIR(mode), 'private_parent_directory')
    return path


def identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _read(path, digest, cap):
    need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'unfrozen_private_pin')
    path = guarded_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'private_regular_size')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        need(identity(before) == identity(os.fstat(stream.fileno())), 'private_open_identity')
        raw = stream.read(cap + 1)
        need(identity(before) == identity(os.fstat(stream.fileno())), 'private_read_identity')
    need(identity(before) == identity(path.lstat()), 'private_path_identity')
    need(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == digest, 'private_sha256')
    return raw


def _documents(root, document_pins, public_paths):
    need(type(document_pins) is dict and set(document_pins) == set(DOCUMENT_PINS)
         and type(public_paths) is dict and set(public_paths) == set(document_pins), 'document_closure')
    paths, raw = {}, {}
    for key, item in document_pins.items():
        need(type(item) in (tuple, list) and len(item) == 2, 'document_pin_pair')
        filename, digest = item
        need(type(filename) is str and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*[.]json', filename), 'document_filename')
        private = root / filename
        private_raw = _read(private, digest, MAX_DOCUMENT_BYTES)
        public_raw = _read(public_paths[key], digest, MAX_DOCUMENT_BYTES)
        need(private_raw == public_raw, 'public_private_document_identity')
        paths[key], raw[key] = str(private), private_raw
    return paths, raw


def _load(directory, pins, document_pins, public_paths):
    root = guarded_path(directory)
    need(root.is_dir() and type(pins) is dict and pins, 'private_code_directory_or_pins')
    payloads = {}
    for name, digest in pins.items():
        need(type(name) is str and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', name), 'private_module_name')
        payloads[name] = _read(root / (name + '.py'), digest, MAX_CODE_BYTES)
    documents, document_bytes = _documents(root, document_pins, public_paths)
    # Compile the complete authenticated closure before the first module executes.
    compiled = {name: compile(raw, str(root / (name + '.py')), 'exec') for name, raw in payloads.items()}
    present = {name: name in sys.modules for name in pins}
    previous = {name: sys.modules.get(name) for name in pins}
    modules = {}
    try:
        for name in pins:
            sys.modules.pop(name, None)
        for name, code in compiled.items():
            module = types.ModuleType(name)
            module.__file__ = str(root / (name + '.py'))
            module.__package__ = ''
            sys.modules[name] = module  # Dataclasses resolve their defining module.
            exec(code, module.__dict__)
            modules[name] = module
    except BaseException:
        for name in pins:
            if present[name]: sys.modules[name] = previous[name]
            else: sys.modules.pop(name, None)
        raise
    return dict(modules=modules, payloads=payloads, documents=documents,
                document_bytes=document_bytes, private_dir=root,
                document_pins=dict(document_pins), public_paths=dict(public_paths))


def _authorize(context):
    modules = context['modules']
    need(tuple(modules) == MODULE_ORDER, 'private_module_closure')
    source, method, schema = (DOCUMENT_PINS[key][1] for key in ('manifest_path', 'method_path', 'schema_path'))
    kernel = PRIVATE_PINS['reporting_kernel']
    reference, validator = modules['source_reference'], modules['validator']
    need((reference.SOURCE_SHA, reference.METHOD_SHA, reference.SCHEMA_SHA, reference.REPORTING_SHA)
         == (source, method, schema, kernel), 'reference_authority_pins')
    need((validator.SOURCE_SHA, validator.METHOD_SHA, validator.SCHEMA_SHA, validator.KERNEL_SHA)
         == (source, method, schema, kernel), 'validator_authority_pins')
    expected_closure = {name + '.py': PRIVATE_PINS[name] for name in
                        ('inspect_structure', 'source_numerics', 'reporting_kernel', 'coordinate_contract')}
    need(reference.MODULE_PINS == expected_closure, 'reference_dependency_pins')
    io = modules['io_contract']
    method_doc = io.json_bytes(context['document_bytes']['method_path'], MAX_DOCUMENT_BYTES)
    schema_doc = io.json_bytes(context['document_bytes']['schema_path'], MAX_DOCUMENT_BYTES)
    need(method_doc['task_id'] == schema_doc['task_id'] == 'DEVCONN-001', 'document_task')
    need(method_doc['source']['source_manifest_sha256'] == source
         and schema_doc['source_manifest_sha256'] == source
         and schema_doc['method_sha256'] == method
         and schema_doc['reporting_kernel_sha256'] == kernel, 'document_authority_pins')
    validator.bind_reporting_kernel(context['payloads']['reporting_kernel'])


def load_private():
    """Production authority: adjacent private files, fixed public paths, no overrides."""
    need(tuple(PRIVATE_PINS) == MODULE_ORDER, 'private_module_closure')
    context = _load(Path(__file__).absolute().parent, PRIVATE_PINS, DOCUMENT_PINS, PUBLIC_DOCUMENTS)
    _authorize(context)
    return context


def recheck_documents(context):
    paths, raw = _documents(context['private_dir'], context['document_pins'], context['public_paths'])
    need(paths == context['documents'] and raw == context['document_bytes'], 'documents_changed')


def disjoint_output(output, data_dir, documents, private_dir):
    out = guarded_path(output)
    need(out.is_dir(), 'output_directory')
    for protected in (guarded_path(data_dir), guarded_path(private_dir)):
        need(out != protected and out not in protected.parents and protected not in out.parents,
             'output_overlaps_source_or_private')
    for value in documents:
        document = guarded_path(value)
        need(out != document and out not in document.parents and document not in out.parents,
             'output_overlaps_document')
    return out
