"""Use the accepted complete CBraMod source without changing its metric code."""
import hashlib
import importlib
from pathlib import Path
import types
import safe_io as safe
from engine import read_pinned, write_bytes

OPERATOR = {'bytes': 15272, 'sha256': '0233582a91e3e9d6b481d75bfdb165a378675b33666e18ed72d7f897f0bbcaea'}
TASK = 'PAPER-paper-method-024'
ARMS = {'A': 'paper_and_data', 'B': 'paper_data_official_code'}


def load(root):
    raw = read_pinned(Path(root)/'central_operator.py', OPERATOR, 65536)
    module = types.ModuleType('cbramod_selected_operator'); module.__file__ = str(Path(root)/'central_operator.py')
    exec(compile(raw, module.__file__, 'exec', dont_inherit=True), module.__dict__)
    return module.HostRuntime(root)


def freeze(root, output):
    host = load(root); freeze, bodies = host.verify_source()
    output.mkdir(mode=0o700)
    write_bytes(output/'central_operator.py', read_pinned(Path(root)/'central_operator.py', OPERATOR, 65536))
    write_bytes(output/'SOURCE_FREEZE.json', safe.read(Path(root)/'SOURCE_FREEZE.json', 65536))
    for name, raw in bodies.items():
        path = output/name; path.parent.mkdir(parents=True, exist_ok=True, mode=0o700); write_bytes(path, raw)
    result = load(output); result.verify_source()
    return result


def public(host):
    # Compile the already authenticated pure public contract under a private name.
    _, bodies = host.verify_source()
    panel = safe.strict(bodies['runtime/source/benchmark/public/PANEL.json'])
    module = types.ModuleType('cbramod_public_contract')
    exec(compile(bodies['runtime/source/benchmark/public/contract.py'], '<selected CBraMod public contract>', 'exec'), module.__dict__)
    return panel, module


def expectation(host, query, arm):
    panel, contract = public(host); contract.validate_query(query, panel)
    counts = {d['id']: len(d['rows']) for d in query['datasets']}
    return {'schema': 'cbramod_capture_expectation_v1', 'task_id': TASK,
            'query_sha256': contract.digest(query), 'information_arm': ARMS[arm],
            'cases': [{'case': c['id'], 'shape': [counts[c['dataset']], c['columns']]}
                      for c in contract.cases(panel, query['purpose'])]}


def scope(host):
    panel, c = public(host)
    return {'primary_datasets': [d['id'] for d in panel['primary_downstream_datasets']],
            'candidate_reproduction': len(c.cases(panel, 'reproduction')),
            'candidate_improvement': len(c.cases(panel, 'improvement')),
            'reference_improvement': len(c.cases(panel, 'improvement', True)),
            'reference_reproduction': len(c.cases(panel, 'reproduction', True)),
            'additional_required_paper_families': panel['additional_required_paper_families'],
            'appendix_qualification': False, 'historical_seed_values': panel['seed_values'],
            'full_paper_reproduced': False}
