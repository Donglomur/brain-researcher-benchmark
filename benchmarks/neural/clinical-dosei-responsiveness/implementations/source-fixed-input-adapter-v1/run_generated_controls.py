"""Portable, pinned DoSEI generated controls; no authentic data application."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time
import types
import unittest

BASE = Path(__file__).resolve().parent
PINS = {
    'input_adapter.py': (15173, '618b3a5e358682e5d5b545a47f09443ee75fe7e876cb800789097d96d22d7bab'),
    'test_input_adapter03.py': (11238, 'd227110ed6f1c2d34390823a963100e40250f7d96027030a7a950fdcd4314340'),
    'test_independent_inputs.py': (5890, 'b06687d5fb7efb6776f4d8a27964ec56868bccfe7e7adf0c7b6838d37a61de73'),
    'vendor/verify_saved_eeg_projections.py.txt': (26700, 'bc2891b56bf4640586949137f95d80050d255e70c1314ac08aa2eca28503b228'),
}
MODULE_NAMES = ('input_adapter_reviewed', 'frozen_input_reader_source',
                'input_test_bundle', 'input_independent_bundle')
RAM_BYTES = 134217728
_started = None


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _signature(value):
    return tuple(getattr(value, key) for key in
                 ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def _read_fixed(relative, size):
    path = BASE / relative
    _require(path.parent.resolve() == path.parent, 'real package directory required')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode) and before.st_size == size,
                 'fixed source extent: ' + relative)
        chunks, count = [], 0
        while count < size:
            part = os.read(fd, size - count)
            _require(bool(part), 'short source: ' + relative)
            chunks.append(part)
            count += len(part)
        _require(os.read(fd, 1) == b'', 'source has trailing bytes: ' + relative)
        _require(_signature(before) == _signature(os.fstat(fd)) == _signature(path.lstat()),
                 'source identity changed: ' + relative)
        return b''.join(chunks)
    finally:
        os.close(fd)


def read_sources():
    return {name: _read_fixed(name, size) for name, (size, _) in PINS.items()}


def authenticate_sources(raws):
    _require(type(raws) is dict and set(raws) == set(PINS), 'exact four dependencies required')
    for name, (size, sha) in PINS.items():
        raw = raws[name]
        _require(type(raw) is bytes and len(raw) == size and
                 hashlib.sha256(raw).hexdigest() == sha, 'source authentication failed: ' + name)


def _exec_module(name, relative, raw):
    value = types.ModuleType(name)
    value.__file__ = str(BASE / relative)
    code = compile(raw, value.__file__, 'exec')
    sys.modules[name] = value
    exec(code, value.__dict__)
    return value


def load_modules(raws):
    # This complete check precedes every compile, exec and module injection.
    authenticate_sources(raws)
    _require(not any(name in sys.modules for name in MODULE_NAMES), 'reserved module already loaded')
    try:
        _exec_module(MODULE_NAMES[0], 'input_adapter.py', raws['input_adapter.py'])
        reader = types.ModuleType(MODULE_NAMES[1])
        reader.raw = raws['vendor/verify_saved_eeg_projections.py.txt']
        sys.modules[reader.__name__] = reader
        authored = _exec_module(MODULE_NAMES[2], 'test_input_adapter03.py', raws['test_input_adapter03.py'])
        independent = _exec_module(MODULE_NAMES[3], 'test_independent_inputs.py', raws['test_independent_inputs.py'])
        return authored, independent
    except BaseException:
        for name in MODULE_NAMES:
            sys.modules.pop(name, None)
        raise


def _limits():
    global _started
    if _started is not None:
        return
    _started = time.monotonic()
    # Exit directly at the worker deadline; unittest must not catch and extend it.
    signal.signal(signal.SIGALRM, lambda _signum, _frame: os._exit(124))
    signal.setitimer(signal.ITIMER_REAL, 15)
    resource.setrlimit(resource.RLIMIT_CPU, (10, 11))


class BoundedText(io.StringIO):
    def write(self, value):
        _require(self.tell() + len(value) <= 8192, 'diagnostic character ceiling')
        return super().write(value)


def run_suite(suite, *, expected_count, scope, mutation_cases=0):
    _limits()
    output = BoundedText()
    summary = {'schema': 'dosei_public_generated_controls_v1', 'scope': scope,
               'passed': False, 'expected_methods': expected_count,
               'mutation_cases_planned': mutation_cases, 'mutation_cases_passed': 0,
               'authentic_inputs_opened': False, 'native_context_invoked': False,
               'arrays_models_network_invoked': False, 'generated_payload_writes': 0}
    try:
        summary['test_ids'] = [test.id() for test in suite]
        _require(suite.countTestCases() == expected_count, 'exact selected method count required')
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
        summary.update(tests_run=result.testsRun, failures=len(result.failures),
                       errors=len(result.errors), skipped=len(result.skipped),
                       expected_failures=len(result.expectedFailures),
                       unexpected_successes=len(result.unexpectedSuccesses))
        summary['passed'] = (result.wasSuccessful() and result.testsRun == expected_count and
                             not result.skipped and not result.expectedFailures)
        if summary['passed']:
            summary['mutation_cases_passed'] = mutation_cases
    except BaseException as error:
        summary['error'] = type(error).__name__ + ': ' + str(error)[:256]
    usage = resource.getrusage(resource.RUSAGE_SELF)
    peak = int(usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024))
    summary.update(observed_peak_rss_bytes=peak, declared_ram_bytes=RAM_BYTES,
                   memory_enforcement='declared and observed; no OS hard memory cap',
                   wall_seconds=round(time.monotonic() - _started, 6),
                   cpu_seconds=round(usage.ru_utime + usage.ru_stime, 6),
                   source_body_bytes=59001, source_EOF_probes=4)
    summary['passed'] = summary['passed'] and peak <= RAM_BYTES
    raw = json.dumps(summary, sort_keys=True, ensure_ascii=True)
    log = output.getvalue()
    _require(len(log.encode('utf-8')) + len(raw.encode('ascii')) + 1 <= 16384, 'console byte ceiling')
    # Preserve the standard summary consumed by the existing public CI runner.
    sys.stdout.write(log)
    print(raw, flush=True)
    return 0 if summary['passed'] else 1


def main():
    _limits()
    authored, independent = load_modules(read_sources())
    suite = unittest.TestSuite([
        authored.InputAdapterTests('test_complete180_roles_use_real_reader_finish_and_one_shared_meter'),
        authored.InputAdapterTests('test_read_failure_preserves_unknown_grant_and_prevents_retry'),
        independent.IndependentInputBoundaries('test_coherent_member_substitution_and_open_descriptor_link_refusal'),
        independent.IndependentInputBoundaries('test_finish_and_close_failures_are_terminal_and_preserve_interruption'),
    ])
    return run_suite(suite, expected_count=4, scope='generated_adapter')


if __name__ == '__main__':
    raise SystemExit(main())
