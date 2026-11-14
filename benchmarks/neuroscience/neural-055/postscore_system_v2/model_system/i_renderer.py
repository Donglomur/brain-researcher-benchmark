"""Emit one fixed I.py with explicit prospective system selection.

This producer imports only the adjacent source-owned standard-library template.
It neither opens data/model assets nor manufactures source-method approval.
"""
import ast
import hashlib
import json
from pathlib import Path
import stat


def render_i_program(loop_spec, participant_interface, *, read_source=None):
    path = Path(__file__).absolute().parent / 'i-interpreter' / 'participant_template.py'
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_size > 131072 or any(x.is_symlink() for x in (path, *path.parents))):
        raise ValueError('ordinary finite source-owned participant template required')
    template = path.read_bytes() if read_source is None else read_source(path)
    if before != path.lstat():
        # Full stat comparison includes atime and is not used as custody: only
        # content/type/extent below binds the emitted immutable source.
        after = path.lstat()
        if (before.st_dev, before.st_ino, before.st_mode, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino,
                after.st_mode, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('template changed during capture')
    scope = {'__name__': '_n055_i_template_source', '__file__': str(path)}
    exec(compile(template, str(path), 'exec'), scope)
    scope['validate_spec'](loop_spec)
    scope['validate_interface'](participant_interface)
    text = template.decode('utf-8')
    for marker, name, value in [('SPEC = None  # RENDER_SPEC', 'SPEC', loop_spec),
                                ('PARTICIPANT_INTERFACE = None  # RENDER_INTERFACE', 'PARTICIPANT_INTERFACE', participant_interface)]:
        if text.count(marker) != 1:
            raise ValueError('one fixed renderer marker required')
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
        text = text.replace(marker, name + ' = json.loads(' + repr(raw) + ')')
    source = text.encode('utf-8')
    if not 0 < len(source) <= 131072:
        raise ValueError('emitted global source exceeds original programme cap')
    ast.parse(text, filename='I.py')
    digest = hashlib.sha256(source).hexdigest()
    services = [loop_spec['model_provider']]
    if loop_spec['tool_provider'] is not None:
        services.append(loop_spec['tool_provider'])
    policy = {'source_sha256': digest,
              'initializer': 'fresh_full_cell_and_phase_from_permitted_seal',
              'dependencies': loop_spec['dependencies'], 'services': services,
              'inference_restrictions': {
                  'query_fit': False, 'new_query_source': False,
                  'execution_actions': 'exact FIT-sealed source only',
                  'state_codec': 'neural055-i-typed-seal-v1',
                  'broker_actions': 'exact pairs in same-cell FIT selected_method',
                  'system_restriction_not_benchmark_permission_change': True,
                  'semantic_qualification': 'independent source and operation review required'}}
    return {'source_bytes': source, 'source_sha256': digest, 'I_policy_fragment': policy}
