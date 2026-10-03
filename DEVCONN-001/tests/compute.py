"""Offline reference solution using the independent Nilearn source route."""
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import types

CODE_PINS = {'run_source_route.py': 'e913700f12c3e3286e7a284753f0db811e2fcaf3329d2103bbc0b7f0477b2a4d',
             'output_writer.py': '99c33e0f796eeb818f6520886eba0086dbfc64c8867a8b1954b8426512ca1c5b',
             'reporting_kernel.py': '2b3abe5fe37d3ad68db57301afa68cf6b0f5409abaf81bc5b06494ae4bf88638'}


def load_helpers():
    directory = Path(__file__).absolute().parent
    payloads = {}
    for name, pin in CODE_PINS.items():
        if type(pin) is not str or re.fullmatch('[0-9a-f]{64}', pin) is None:
            raise ValueError('unfrozen_solution_pin')
        path = directory / name
        for part in (*reversed(path.parents), path):
            if part.is_symlink(): raise ValueError('solution_symlink')
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 1024**2:
            raise ValueError('solution_code_cap')
        raw = path.read_bytes()
        # Reading a freshly copied Harbor file can legitimately update atime.
        # Identity/content metadata must stay fixed; access time is not identity.
        signature = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size,
                               s.st_mtime_ns, s.st_ctime_ns)
        if signature(path.stat()) != signature(before) or hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError('solution_code_identity')
        payloads[name] = raw
    result = {}
    for name, raw in payloads.items():
        module = types.ModuleType('_devconn_solution_' + name[:-3])
        module.__file__ = str(directory / name)
        sys.modules[module.__name__] = module
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)
        result[name[:-3]] = module
    return result


def main():
    helpers = load_helpers()
    writer, route, kernel = (helpers[key] for key in
                            ('output_writer', 'run_source_route', 'reporting_kernel'))
    source = '/app/data/devconn'
    docs = ['/app/source_manifest.json', '/app/method_contract.json', '/app/output_schema.json']
    protected = [source, *docs, Path(__file__).absolute().parent]
    output = writer.fresh_output(os.environ.get('OUTPUT_DIR', '/app/output'), protected)
    try:
        adapter = route.load_adapter('oracle')
        reference = adapter(source, *docs)
        writer.write_artifacts(reference, str(output), kernel, protected=protected)
    except BaseException:
        marker = output / 'failure_report.json'
        if not os.path.lexists(marker):
            writer.json_write(marker, {'status': 'failed_precondition',
                                      'reason': 'oracle_source_or_output_failure'})
        raise
    print('DEVCONN-001: complete source-derived artifacts written')


if __name__ == '__main__':
    main()
