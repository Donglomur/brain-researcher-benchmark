"""Pinned source loading; never opens a scientific input on import."""
import builtins
import hashlib
from pathlib import Path
import types

HERE = Path(__file__).absolute().parent
RUNTIME_SHA = 'c737e28d00613a71e9ba469a9082d77bb9ffa20abb3a7ed33d06355c1a3232aa'
BOOTSTRAP_SHA = 'cd2388db9872bff4e9bd60ca2c1e21c75de4a834a5d573266e3ce57f1c1e7075'
SCORER = 'benchmarks/neural/NEURAL-076/implementations/hierarchy-scorer-v2'
EXECUTION_FILES = ('support.py', 'run.py', 'score_closed.py', 'INSTRUCTIONS.md', 'DEPENDENCIES.json')
SCORE_READS = 2 * 650 * 24 * 2**20 + 32 * 2**20
SCORE_WRITES = 32 * 2**20
SCORE_MEMORY = 2**30


def runtime():
    path = HERE / 'runtime' / 'bootstrap.py'
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != BOOTSTRAP_SHA:
        raise ValueError('Fixed bootstrap source')
    module = types.ModuleType('_neural076_recovered_bootstrap')
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module.load(path.parent, RUNTIME_SHA)


def source_identity(common):
    return {name: common.capture(HERE / name, 262144)[1] for name in EXECUTION_FILES}


def current_scorer(repository, common):
    repository = common.path(repository)
    raw, _ = common.capture(HERE / 'DEPENDENCIES.json', 65536)
    manifest = common.decode(raw)
    common.need(manifest['schema'] == 'neural076_hierarchy_bridge_dependencies_v1'
                and manifest['accepted_commit'] == '31c05a9d2675c7d4235f7a8a0df88c88981b9395'
                and set(manifest['files']) == {SCORER + '/' + n + '.py' for n in ('core', 'io_utils', 'artifacts', 'score')},
                'Exact accepted scorer dependency closure')
    bodies = {name: common.capture(repository / name, 262144, pin)[0]
              for name, pin in manifest['files'].items()}
    modules = {}

    def load(name):
        if name in modules:
            return modules[name]
        common.need(name in ('core', 'io_utils', 'artifacts', 'score'), 'Fixed numerical module')
        filename = SCORER + '/' + name + '.py'
        module = types.ModuleType('_neural076_current_' + name)
        module.__file__ = str(repository / filename)
        scope = dict(vars(builtins))
        original = builtins.__import__

        def importer(target, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and target in ('core', 'io_utils', 'artifacts', 'score'):
                return load(target)
            return original(target, globals, locals, fromlist, level)

        scope['__import__'] = importer
        module.__dict__['__builtins__'] = scope
        modules[name] = module
        try:
            exec(compile(bodies[filename], module.__file__, 'exec'), module.__dict__)
        except BaseException:
            modules.pop(name, None)
            raise
        return module

    return load('score'), load('artifacts'), manifest


def score_budget(seconds):
    if type(seconds) is not int or not 1 <= seconds <= 7200:
        raise ValueError('Explicit prospective scoring duration, 1–7200 seconds')
    return {'seconds': seconds, 'memory_bytes': SCORE_MEMORY, 'managed_read_reservation': SCORE_READS,
            'write_and_retained_cap': SCORE_WRITES, 'runtime_qualified': False,
            'memory_enforcement': 'external supervisor required; this source does not qualify host memory'}
