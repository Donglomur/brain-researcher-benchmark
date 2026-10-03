"""Draft fixed-input oracle entrypoint; scientific core is the exact PR190 port.

The same non-scientific code_guard utility is copied into /solution. No private
grader/source reconstruction module is imported. Original execution is disabled
by unset closure pins until parent review and the separate PR200 source gate.
"""
import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace

import code_guard as guard

MODULE_ORDER = ('core', 'source_reader', 'compute')
MODULE_PINS = {
    'core': '456ce2f70b64730fe65cbd3a9c74eb4174eb5febc87df76fa06818848f886632',
    'source_reader': 'e3e5cbee2cc2012fa61403c7b0686cf880d9e14c5d7957f5e44f8ff4c42d68d7',
    'compute': '8344e0a4cbbdcef73450b1eee184057ad8a5b6bf3e59ae2763717d423067de52',
}
DOCUMENT_PINS = {
    'manifest_path': ('source_manifest.json', '6afac2a68c4ca4847265ac5f890d56aa53a658e78f13b32e0f15f74007ed91c7'),
    'method_path': ('method_contract.json', 'c6575d9cc8a9f8d422dc3ec88c2a7aefa6ca971757180517948d2466fefce872'),
    'schema_path': ('output_schema.json', 'e9ceb1a15180ed086290c4c7f5eb079038302b4dd5feabc3e99c9acb688bcf16'),
}
PUBLIC_DOCUMENTS = {key: '/app/' + value[0] for key, value in DOCUMENT_PINS.items()}
DATA_DIR = '/app/data/gradient'
REQUIRED = ('cohort.csv', 'parcels.csv', 'gradient_arrays.npz', 'configurations.csv',
            'per_subject.csv', 'results.json', 'run_metadata.json', 'findings.md')


def run(output_dir='/app/output', private_dir=None, report=None):
    guard.need(tuple(MODULE_PINS) == MODULE_ORDER, 'oracle_module_closure')
    context = guard.load_closure(Path(__file__).absolute().parent, MODULE_PINS,
                                 DOCUMENT_PINS, PUBLIC_DOCUMENTS)
    paths = context['private_documents']
    out = guard.disjoint_output(output_dir, DATA_DIR, context['private_dir'],
                               [*paths.values(), *PUBLIC_DOCUMENTS.values()])
    existed = os.path.lexists(out)
    # The I/O-only compute amendment also accepts an existing empty real output
    # directory. Private/report destinations remain absent and all are disjoint.
    args = SimpleNamespace(data_dir=DATA_DIR, contract_path=paths['method_path'],
                           schema_path=paths['schema_path'], output_dir=output_dir,
                           private_dir=private_dir, report=report)
    completed_write = False
    try:
        receipt = context['modules']['compute'].run(args)
        completed_write = True
        # Reauthenticate opaque source identities after consumption; no second fit.
        context['modules']['source_reader'].authenticate(DATA_DIR, paths['method_path'], paths['schema_path'])
        guard.recheck(context)
        guard.output_inventory(output_dir, require_files=REQUIRED)
        return receipt
    except Exception as exc:
        # Do not modify a protected or pre-existing destination. Preserve any
        # earlier writer failure marker; never turn a late failure into success.
        if (not existed or completed_write) and out.is_dir() and not out.is_symlink():
            guard.safe_path(out)
            marker = out / 'failure_report.json'
            if not os.path.lexists(marker):
                with marker.open('x', encoding='utf-8') as stream:
                    json.dump({'status': 'failed_precondition',
                               'reason': type(exc).__name__ + ': ' + str(exc)}, stream, allow_nan=False)
                    stream.write('\n')
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='/app/output')
    parser.add_argument('--private-dir')
    parser.add_argument('--report')
    args = parser.parse_args()
    return run(args.output_dir, args.private_dir, args.report)


if __name__ == '__main__':
    main()
