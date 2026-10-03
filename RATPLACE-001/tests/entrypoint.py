"""Inert, SHA-bound RATPLACE v2 entrypoint; no source reads or numerical imports.

The shell authenticates this file before executing its retained bytes. This
loader then authenticates the complete fixed entrypoint closure before any exec.
Private scientific modules/documents are separately bound by the bootstraps.
Generic load_entries is an explicit manufactured-fixture seam, never a CLI
override. Production has only fixed /tests and /solution roots.
"""
import hashlib
import importlib.metadata
import os
from pathlib import Path
import re
import stat
import sys
import types


CODE_CAP = 1024**2
ENTRY_PINS = {
    'code_guard': 'ef716b45ce2204e96f11f1da81e677d7d99cf5b0e714338be131f8bf7581be0c',
    'grader_bootstrap': 'a0bedcf44a5f40e33122b95d0b29e0583e8c4e35b4b4719d18cbb31d2dcc54ee',
    'test_outputs': 'c7dbc3f922c60078a2404912c1953109efab7645086e98a91b04e2dcc2549c53',
    'oracle_bootstrap': 'b0444a0ba7b548901cdc6d5f93b5be49585878ff8bc20cd1861f75d431617e19',
}
GRADER_ORDER = ('code_guard', 'grader_bootstrap', 'test_outputs')
ORACLE_ORDER = ('code_guard', 'oracle_bootstrap')
TEST_NAME = 'test_source_bound_ratplace'


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def pinned_bytes(value, digest):
    need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'unfrozen_entrypoint_pin')
    raw_path = os.fspath(value)
    need(type(raw_path) is str and raw_path.startswith('/') and '\0' not in raw_path
         and not any(p in ('.', '..') for p in raw_path.split('/')), 'entrypoint_absolute_path')
    path = Path(raw_path)
    for part in (*reversed(path.parents), path):
        mode = part.lstat().st_mode
        need(not stat.S_ISLNK(mode) and (part == path or stat.S_ISDIR(mode)), 'entrypoint_path')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= CODE_CAP, 'entrypoint_regular_size')
    def signature(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        need(signature(os.fstat(stream.fileno())) == signature(before), 'entrypoint_open_identity')
        raw = stream.read(before.st_size + 1)
        need(signature(os.fstat(stream.fileno())) == signature(before), 'entrypoint_read_identity')
    need(signature(path.lstat()) == signature(before), 'entrypoint_path_identity')
    need(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == digest, 'entrypoint_sha256')
    return raw


def restore_entries(context):
    for name in context['pins']:
        if context['present'][name]: sys.modules[name] = context['previous'][name]
        else: sys.modules.pop(name, None)


def load_entries(directory, pins):
    need(type(pins) is dict and pins, 'entrypoint_closure')
    root = Path(directory)
    payloads = {}
    for name, digest in pins.items():
        need(type(name) is str and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', name), 'entrypoint_module_name')
        payloads[name] = pinned_bytes(root / (name + '.py'), digest)
    compiled = {name: compile(raw, str(root / (name + '.py')), 'exec') for name, raw in payloads.items()}
    context = dict(root=root, pins=dict(pins), payloads=payloads, modules={},
                   present={name: name in sys.modules for name in pins},
                   previous={name: sys.modules.get(name) for name in pins})
    try:
        # Every declared name exists before exec, including dependencies. No
        # missing entry may fall through to a public file or a stale pyc module.
        for name in pins:
            module = types.ModuleType(name)
            module.__file__, module.__package__ = str(root / (name + '.py')), ''
            context['modules'][name] = sys.modules[name] = module
        for name, code in compiled.items(): exec(code, context['modules'][name].__dict__)
    except BaseException:
        restore_entries(context)
        raise
    return context


def recheck_entries(context):
    for name, digest in context['pins'].items():
        need(pinned_bytes(context['root'] / (name + '.py'), digest) == context['payloads'][name],
             'entrypoint_changed')


def production_pytest(pytest, test_module, ctrf_plugin, *, logs=Path('/logs/verifier')):
    """Collect the retained module, not a filesystem import/rewrite of it."""
    path = Path(test_module.__file__)
    function = getattr(test_module, TEST_NAME, None)
    need(callable(function), 'production_test_missing')

    class RetainedModule(pytest.Module):
        def _getobj(self):
            return test_module

    class FixedCollection:
        passed_calls = 0
        invalid_report = False

        @pytest.hookimpl(tryfirst=True)
        def pytest_ignore_collect(self, collection_path, config):
            # Pytest enumerates siblings before selecting the explicit node.
            # Keep only its ancestor path and retained file, never a fallback import.
            return collection_path != path and collection_path not in path.parents

        @pytest.hookimpl(tryfirst=True)
        def pytest_pycollect_makemodule(self, module_path, parent):
            if module_path != path:
                raise pytest.UsageError('unexpected production module')
            return RetainedModule.from_parent(parent, path=module_path)

        def pytest_collection_modifyitems(self, items):
            if (len(items) != 1 or items[0].name != TEST_NAME
                    or items[0].obj is not function or items[0].path != path):
                raise pytest.UsageError('exactly one authenticated production test required')

        def pytest_runtest_logreport(self, report):
            if report.failed or report.skipped:
                self.invalid_report = True
            if report.when == 'call' and report.passed:
                self.passed_calls += 1

    fixed = FixedCollection()
    status = int(pytest.main(['-c', '/dev/null', '--rootdir=' + str(path.parent),
        '--noconftest', '--confcutdir=' + str(path.parent),
        '--import-mode=importlib', '-p', 'no:cacheprovider', '--ctrf', str(logs / 'ctrf.json'),
        '--junitxml=' + str(logs / 'junit.xml'), str(path) + '::' + TEST_NAME, '-rA'],
        plugins=[ctrf_plugin, fixed]))
    if status == 0:
        need(fixed.passed_calls == 1 and not fixed.invalid_report, 'one_passed_production_call_required')
    return status


def main(role, argv=()):
    need(role in ('grader', 'oracle') and type(argv) in (tuple, list), 'entrypoint_role')
    need(all(type(value) is str for value in argv), 'entrypoint_arguments')
    need(role == 'oracle' or not argv, 'grader_arguments_forbidden')
    order = GRADER_ORDER if role == 'grader' else ORACLE_ORDER
    root = Path('/tests' if role == 'grader' else '/solution')
    context = load_entries(root, {name: ENTRY_PINS[name] for name in order})
    previous_argv = sys.argv
    try:
        if role == 'grader':
            os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
            os.environ.pop('PYTEST_ADDOPTS', None)
            os.environ.pop('PYTEST_PLUGINS', None)
            import pytest
            distribution = importlib.metadata.distribution('pytest-json-ctrf')
            entries = [ep for ep in distribution.entry_points if ep.group == 'pytest11']
            need(len(entries) == 1, 'exactly_one_baked_ctrf_plugin_required')
            status = production_pytest(pytest, context['modules']['test_outputs'], entries[0].load())
        else:
            sys.argv = [str(root / 'oracle_bootstrap.py'), *argv]
            context['modules']['oracle_bootstrap'].main()
            status = 0
        recheck_entries(context)
        return status
    finally:
        sys.argv = previous_argv
        restore_entries(context)
