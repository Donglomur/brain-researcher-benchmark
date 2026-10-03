"""PR200 draft: fixed private closure and exactly one source-bound decision.

All code pins stay unfrozen until parent review/qualification of the adapted
source I/O and artifact hardening. No original reads or fitting on import.
"""
from pathlib import Path

import code_guard as guard

MODULE_ORDER = ('artifact_reader', 'gradient_math', 'source_numerics',
                'source_reference', 'gradient_reporting', 'proof_of_work')
MODULE_PINS = {
    'artifact_reader': '05f19ca4b43636c135bce0a88ac59477e930804b362263f5c71a2e5129a42edf',
    'gradient_math': '1e2201af4c5ec235f32d9cd44169d3acf3d2384420d99a4b1b1c9914b001d8be',
    'source_numerics': 'e88835993a9bb5c52204901c7ca1487658ae7fdc78680d9885f62275faa48ba2',
    'source_reference': 'ebbfa8d8fa57f24a7f5ce9faa5b4faf63353489631487c038464fe7803c6c0b7',
    'gradient_reporting': '5415be4a45825796e4549b28a27e17dd4a78523ccddf81b920605fe374b5d897',
    'proof_of_work': '7fbc73f44b56e2122efea140bdb5bc1aa5fa4f715a50ccf83fcafe3c3e90fd2a',
}
DOCUMENT_PINS = {
    'manifest_path': ('source_manifest.json', '6afac2a68c4ca4847265ac5f890d56aa53a658e78f13b32e0f15f74007ed91c7'),
    'method_path': ('method_contract.json', 'c6575d9cc8a9f8d422dc3ec88c2a7aefa6ca971757180517948d2466fefce872'),
    'schema_path': ('output_schema.json', 'e9ceb1a15180ed086290c4c7f5eb079038302b4dd5feabc3e99c9acb688bcf16'),
}
PUBLIC_DOCUMENTS = {key: '/app/' + value[0] for key, value in DOCUMENT_PINS.items()}
DATA_DIR = '/app/data/gradient'
OUTPUT_DIR = '/app/output'
REQUIRED = ('cohort.csv', 'parcels.csv', 'gradient_arrays.npz', 'configurations.csv',
            'per_subject.csv', 'results.json', 'run_metadata.json', 'findings.md')


def load_private():
    guard.need(tuple(MODULE_PINS) == MODULE_ORDER, 'private_module_closure')
    context = guard.load_closure(Path(__file__).absolute().parent, MODULE_PINS,
                                 DOCUMENT_PINS, PUBLIC_DOCUMENTS)
    modules = context['modules']
    reference = modules['source_reference']
    guard.need((reference.SOURCE_SHA256, reference.METHOD_SHA256, reference.SCHEMA_SHA256)
               == tuple(DOCUMENT_PINS[key][1] for key in ('manifest_path', 'method_path', 'schema_path')),
               'private_source_authority_pins')
    reader = modules['artifact_reader']
    method = reader.parse_json(context['document_bytes']['method_path'])
    schema = reader.parse_json(context['document_bytes']['schema_path'])
    guard.need(method['task_id'] == schema['task_id'] == 'GRADIENT-001'
               and method['source']['manifest_sha256'] == reference.SOURCE_SHA256
               and tuple(schema['files']) == REQUIRED, 'fixed_contract_identity')
    return context


def grade():
    context = load_private()
    modules, paths = context['modules'], context['private_documents']
    output = guard.disjoint_output(OUTPUT_DIR, DATA_DIR, context['private_dir'],
                                   [*paths.values(), *PUBLIC_DOCUMENTS.values()])
    guard.output_inventory(output, require_files=REQUIRED)
    # Explicit paths suppress the historical GRADIENT_DIR environment fallback.
    # The source reader authenticates all 46 files; no persisted basis is reused.
    reference = modules['source_reference'].reconstruct(
        data_dir=DATA_DIR, method_path=paths['method_path'], schema_path=paths['schema_path'])
    result = modules['proof_of_work'].validate(output, reference)
    # This reauthentication is retained even before the reader's planned final
    # same-buffer/source recheck is integrated. No source-derived values stored.
    modules['source_reference'].authenticate_source(DATA_DIR)
    guard.recheck(context)
    guard.output_inventory(output, require_files=REQUIRED)
    guard.need(result['status'] == 'accepted', 'binary_source_bound_decision')
    return result
