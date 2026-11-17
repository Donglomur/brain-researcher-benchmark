"""Task paths and descriptors over immutable shared transport/ownership."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SHARED = ROOT / 'authoring/shared-program-runner-v2'
sys.path.insert(0, str(SHARED))
from qualified_core import BaseEngine, HostBudget, digest, DOCKER, ENV
from unit import run_unit
from engine_profile import ProfileEngine
import contract_profile
from profile import runtime
sys.path.insert(0, str(ROOT / 'authoring/shared-program-ownership-v3'))
import process_owner as owner


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# These reusable helpers do not invoke a task, touch data, or dispatch commands.
summary_common = load_module(ROOT / 'authoring/shared-summary-runner-v1/common.py', '_sleep_summary_common')
ordinary, save = summary_common.ordinary, summary_common.save
recovery_core = load_module(ROOT / 'authoring/paper-language-project/phase1-numerical-v1/recovery_guard.py', '_sleep_recovery_primitives')


def descriptor(path):
    body = ordinary(path, 262_144)
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def profile():
    value = json.loads(ordinary(HERE / 'profile.json', 32_768))
    need(value['candidate_id'] == 'NEURAL-007' and [x['unit_id'] for x in value['units']] ==
         ['development-001', 'development-002'] and len(value['training']) == 18 and len(value['helpers']) == 2,
         'Exact fixed feature task inventory')
    return value


def units():
    value = profile()
    common = [{k: x[k] for k in ('path', 'bytes', 'sha256', 'mount_destination', 'read_only')}
              for x in value['training'] + value['helpers']]
    common += [descriptor(HERE / 'public_validation.py') | {'mount_destination': '/input/public_validation.py', 'read_only': True}]
    result = []
    for unit in value['units']:
        active = [{k: x[k] for k in ('path', 'bytes', 'sha256', 'mount_destination', 'read_only')} for x in unit['active_inputs']]
        case = descriptor(HERE / (unit['unit_id'] + '.json')) | {'mount_destination': '/input/case.json', 'read_only': True}
        result.append({k: unit[k] for k in ('unit_id', 'output_filename', 'max_output_bytes')} |
                      {'public_inputs': common + active + [case]})
    return result


def opaque(body, unit):
    need(type(body) is bytes and 0 < len(body) <= unit['max_output_bytes'], 'Bounded opaque single-case bytes')
