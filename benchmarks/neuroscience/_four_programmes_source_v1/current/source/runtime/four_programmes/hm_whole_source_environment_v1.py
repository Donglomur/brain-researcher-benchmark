"""Concrete fixed environment/import admission for an actual whole-job HM W.

The independently accepted qualification and nonempty Context admission remain
required. A configuration dictionary or an import allowlist cannot create either.
"""
import os
import sys
import types
from . import dependencies
from .common import need, closed, descriptor, encode, pin, integer, bounded_size
from .hm_whole_worker_contract_v1 import FD_ENVIRONMENT, absolute, pinlike

_ENVIRONMENT = object()
ENV_FIELDS = ('schema', 'qualification', 'interpreter', 'interpreter_absolute',
              'platform', 'machine', 'version', 'environment', 'imports', 'loaded_sources')


def validate_environment_record_v1(body):
    closed(body, ENV_FIELDS)
    need(body['schema'] == 'hm_whole_source_environment_v1', 'distinct fixed HM environment record')
    descriptor(body['qualification']); descriptor(body['interpreter'])
    absolute(body['interpreter_absolute'])
    need(body['platform'] == 'linux' and type(body['machine']) is str and body['machine'] and
         type(body['version']) is str and body['version'], 'selected qualified Linux interpreter domain')
    need(type(body['environment']) is dict and
         all(type(k) is str and type(v) is str for k, v in body['environment'].items()) and
         not any(k in body['environment'] for k in FD_ENVIRONMENT),
         'complete fixed non-carrier environment; only three inherited FD values vary')
    imports = body['imports']
    need(type(imports) is list and imports and len(imports) == len(set(imports)) and
         all(type(name) is str and name and all(x.isidentifier() for x in name.split('.')) for name in imports),
         'complete prospective explicit import roots')
    rows = body['loaded_sources']
    need(type(rows) is list and rows and len(rows) <= 8192, 'full installed runtime source selection')
    seen = set()
    for row in rows:
        closed(row, ('module', 'absolute_path', 'descriptor', 'loaded_code_sha256'))
        need(type(row['module']) is str and row['module'] not in seen, 'unique installed source module')
        seen.add(row['module']); absolute(row['absolute_path']); descriptor(row['descriptor'])
        need(type(row['loaded_code_sha256']) is str and len(row['loaded_code_sha256']) == 64 and
             all(c in '0123456789abcdef' for c in row['loaded_code_sha256']), 'exact installed code identity')
    required = {'four_programmes.hm_whole_worker_runtime_v1', 'four_programmes.hm_whole_worker_contract_v1',
                'four_programmes.hm_whole_source_environment_v1', 'four_programmes.hm_whole_job_profile_v1',
                'four_programmes.source_session', 'four_programmes.channel', 'four_programmes.common',
                'four_programmes.roots', 'four_programmes.identity', 'four_programmes.resources',
                'four_programmes.dependencies', 'four_programmes.context_boundary',
                'four_programmes.operator_entry', '__main__'}
    need(required <= seen, 'whole operative worker/runtime/source/session/channel closure is selected')
    return body


class HMWholeSourceEnvironmentV1:
    def __init__(self, token, runtime, body, selected_pin):
        need(token is _ENVIRONMENT, 'only actual owned worker environment observation')
        self.runtime = runtime;self._raw = encode(body);self.body = body
        self.pin = dict(selected_pin);self.imports = tuple(body['imports'])
        self.observed_sources = [];self.complete = False

    def require_original_import(self, name, fromlist):
        self.runtime.require_current()
        need(self.complete and self.runtime.environment is self and
             encode(self.body) == self._raw and pin(self._raw) ==
             {k: self.pin[k] for k in ('bytes', 'sha256')}, 'same actual unchanged environment admission')
        # Python's ordinary ``import x`` calls __import__ with fromlist=None.
        selected_fromlist = () if fromlist is None else fromlist
        need(type(name) is str and name and type(selected_fromlist) in (tuple, list) and
             all(type(item) is str for item in selected_fromlist), 'literal captured original import')
        need(any(name == root or name.startswith(root + '.') for root in self.imports),
             'original external import in prospective qualified closure')
        self.runtime.bootstrap_meter.charge('work_units', len(name) + sum(len(x) for x in selected_fromlist) + 128)


def create_original_hm_source_environment_v1(runtime, body, selected_pin):
    from .hm_whole_worker_runtime_v1 import HMWholeWorkerRuntimeV1
    from .operator_entry import _code_identity
    from . import context_boundary
    need(type(runtime) is HMWholeWorkerRuntimeV1, 'actual registered whole-job worker runtime')
    runtime.require_current()
    need(runtime.start_event is not None and runtime.channel.owns_completed_event(runtime.start_event) and
         runtime.environment is None and not runtime.environment_attempted, 'one actual owned start/environment admission')
    runtime.environment_attempted = True
    validate_environment_record_v1(body)
    need(selected_pin == runtime.plan.body['environment'] and
         pin(encode(body)) == {k: selected_pin[k] for k in ('bytes', 'sha256')},
         'same complete earlier profile environment identity')
    need(body['environment'] == runtime.configuration['environment_values'] and
         body['interpreter_absolute'] == runtime.configuration['python_executable'],
         'same source-selected actual H launch environment and interpreter')
    # This is an accepted source/runtime dependency, not a supplied qualified:true.
    dependencies.require('root_observer_host_clock_environment', body['qualification'])
    environment = HMWholeSourceEnvironmentV1(_ENVIRONMENT, runtime, body, selected_pin)
    runtime.environment = environment
    meter = runtime.bootstrap_meter
    meter.charge('work_units', bounded_size(body));meter.charge('retained_bytes', bounded_size(body))
    actual_env = {k: v for k, v in os.environ.items() if k not in FD_ENVIRONMENT}
    need(sys.platform == body['platform'] and os.uname().machine == body['machine'] and
         sys.version == body['version'] and actual_env == body['environment'] and sys.flags.isolated == 1,
         'actual original interpreter/platform/environment; no ambient path selection')
    interpreter = body['interpreter']
    raw = runtime.roots.read({**interpreter, 'path': body['interpreter_absolute']}, interpreter['bytes'])
    need(pin(raw) == {k: interpreter[k] for k in ('bytes', 'sha256')}, 'exact selected interpreter bytes')
    actual = os.stat('/proc/self/exe');named = os.stat(body['interpreter_absolute'], follow_symlinks=False)
    need((actual.st_dev, actual.st_ino, actual.st_mode) == (named.st_dev, named.st_ino, named.st_mode),
         'selected interpreter is the actual running executable')
    for row in body['loaded_sources']:
        module = sys.modules.get(row['module'])
        need(type(module) is types.ModuleType and module.__file__ == row['absolute_path'] and
             module.__spec__ is not None and module.__spec__.origin == row['absolute_path'],
             'actual loaded selected module origin; no dynamic alternate import')
        if row['module'] == '__main__':
            need(module.__spec__.name == 'four_programmes.hm_whole_worker_entry_v1',
                 'actual fixed installed HM entry module, not an arbitrary main script')
        raw = runtime.roots.read({**row['descriptor'], 'path': row['absolute_path']}, row['descriptor']['bytes'])
        need(pin(raw) == {k: row['descriptor'][k] for k in ('bytes', 'sha256')} and
             _code_identity(module) == row['loaded_code_sha256'], 'actual full loaded source and code identity')
        environment.observed_sources.append(dict(row))
    runtime.require_current();environment.complete = True
    return environment
