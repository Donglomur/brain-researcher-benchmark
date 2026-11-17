"""Concrete future deployment contract, with no supplied qualification booleans."""
from pathlib import Path
from .core import keys, need, integer, positive, CONDITIONS, capture, parse, pin

BUDGET_KEYS = ('wall_seconds','cpu_seconds','read_bytes','write_bytes','live_bytes',
               'files','model_calls','stream_bytes')


def budget(value):
    keys(value, BUDGET_KEYS)
    for k, v in value.items():
        positive(v) if k.endswith('_seconds') else integer(v)
    return value


def role(value):
    keys(value, ('image','python','memory_bytes','pids','tmpfs_bytes','request_bytes',
                 'response_bytes','stream_bytes','wall_seconds','cpu_seconds',
                 'journal_bytes','artifact_bytes','channel_bytes','channel_files','work_files'))
    need(type(value['image']) is str and value['image'].startswith('sha256:') and
         len(value['image']) == 71, 'immutable full OCI image ID')
    need(type(value['python']) is str and value['python'].startswith('/'), 'selected container interpreter')
    for k, v in value.items():
        if k in ('image','python'): continue
        positive(v) if k.endswith('_seconds') else integer(v)
    need(value['channel_bytes']>=4096 and value['channel_bytes']%4096==0 and value['channel_files']>=4,
         'explicit page-aligned channel tmpfs and inode ceiling')
    need(value['work_files']>=4,'explicit native work inode ceiling')
    return value


def validate(value):
    keys(value, ('schema','study_id','source_sha256','members','raw_inputs','preparation_limits',
        'output_root','stage_caps','paired_cost_limits','global_cost_limits','measured_global_F',
        'global_F_evidence','actors','model','native_profile','deployment','budget',
        'diagnostic_output_bytes','closure_reserve_seconds'))
    need(value['schema'] == 'n059_complete_process_selection_v1', 'complete N059 selection')
    need(type(value['study_id']) is str and len(value['study_id']) == 32 and
         all(c in '0123456789abcdef' for c in value['study_id']), 'fresh prospective study identity')
    budget(value['budget']); positive(value['closure_reserve_seconds'])
    need(value['closure_reserve_seconds'] < value['budget']['wall_seconds'], 'whole close reserve')
    integer(value['diagnostic_output_bytes'])
    keys(value['actors'], CONDITIONS)
    for condition, arms in value['actors'].items():
        keys(arms, ('F','I'))
        for arm, spec in arms.items():
            keys(spec, ('policy','role','model_limits'))
            role(spec['role']); keys(spec['model_limits'], ('calls','input_tokens','output_tokens'))
            for n in spec['model_limits'].values(): integer(n)
        need(arms['F']['role'] == arms['I']['role'] and
             arms['F']['model_limits'] == arms['I']['model_limits'], 'equal paired physical/model capability')
    first = value['actors']['SH']['F']
    need(all(v[a]['role'] == first['role'] and v[a]['model_limits'] == first['model_limits']
             for v in value['actors'].values() for a in ('F','I')), 'equal C/CN and F/I ceilings')
    keys(value['model'], ('kind','role','configuration','checkpoint_root','checkpoint_files'))
    need(value['model']['kind'] == 'local_transformers_text_v1', 'supported actual local model backend')
    role(value['model']['role'])
    d = value['deployment']
    keys(d, ('docker','dockerd','docker_host','docker_config','daemon_id','daemon_root','whole_cgroup',
             'controller_leaf','daemon_leaf','whole_memory_bytes','whole_pids',
             'reference_role','grade_role','code_root'))
    role(d['reference_role']); role(d['grade_role'])
    integer(d['whole_memory_bytes']); integer(d['whole_pids'])
    # Each of232 fitted actors is captured and closed; inference uses one fresh
    # container at a time.29 reference workers and2 arm-owned model services coexist.
    live_roles = [(1,first['role']), (29,d['reference_role']), (2,value['model']['role'])]
    need(sum(n*r['memory_bytes'] for n,r in live_roles) < d['whole_memory_bytes'],
         'complete concurrent worker memory plus externally enforced controller/daemon headroom')
    need(sum(n*r['pids'] for n,r in live_roles) < d['whole_pids'], 'complete concurrent PID envelope')
    need(d['grade_role']['memory_bytes'] < d['whole_memory_bytes'], 'protected grader whole memory')
    need(type(d['docker_host']) is str and d['docker_host'].startswith('unix:///'),
         'explicit dedicated local Docker endpoint')
    need(type(d['daemon_id']) is str and d['daemon_id'], 'original selected daemon identity')
    return value


def capture_policies(value, managed):
    """Every F procedure and I policy is captured before any authentic input opening."""
    rows = {}
    for c in CONDITIONS:
        for a in ('F','I'):
            rows[(c,a)] = capture(value['actors'][c][a]['policy'], managed)
    return rows
