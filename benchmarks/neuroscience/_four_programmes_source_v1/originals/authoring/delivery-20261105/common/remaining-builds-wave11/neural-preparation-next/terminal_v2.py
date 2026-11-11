"""Explicit optional unknown-next representation; no synthetic event times.

This produces a reviewed source adaptation, not an installed preparation route.
Only the pure binding validator is executable independently in controls.
"""
import ast
import hashlib
import math

SOURCE_PIN=(10785,'ca9c3439316576986b3e78e74a3805cf032ac53014d65e321e88295784e07cc3')
CHANGES=(
 ("for key in ('selection_index','run','event_sample','epoch_event_sample','offset_sample','next_onset_sample','stim_trigger'):",
  "for key in ('selection_index','run','event_sample','epoch_event_sample','offset_sample','stim_trigger'):"),
 ("    if binding['run']<1 or binding['next_onset_sample']<=binding['offset_sample'] or binding['offset_sample']<=binding['event_sample']:raise ValueError('ordered actual events')",
  "    if binding['next_onset_sample'] is not None and (type(binding['next_onset_sample']) is not int or not 0<=binding['next_onset_sample']<=10**12):raise ValueError('observed next onset or explicit unknown')\n    if binding['run']<1 or (binding['next_onset_sample'] is not None and binding['next_onset_sample']<=binding['offset_sample']) or binding['offset_sample']<=binding['event_sample']:raise ValueError('ordered actual events')"),
 ("complete=(binding['next_onset_sample']-binding['event_sample'])/sfreq>=end",
  "complete=(binding['next_onset_sample'] is not None and (binding['next_onset_sample']-binding['event_sample'])/sfreq>=end)"),
 ("bindings['schema']!='neural098-event-bindings-v1'", "bindings['schema']!='neural098-event-bindings-v2'"),
)

def adapt_preparer_source(raw):
    if type(raw) is not bytes or (len(raw),hashlib.sha256(raw).hexdigest())!=SOURCE_PIN:
        raise ValueError('exact frozen original preparation source')
    text=raw.decode('utf-8')
    for old,new in CHANGES:
        if text.count(old)!=1:raise ValueError('exact nullable-next adaptation occurrence')
        text=text.replace(old,new)
    ast.parse(text)
    return text.encode('utf-8')

def binding_validator(raw,*,profile):
    """Compile only this source's pure guard; no preparation/reference imports."""
    if profile=='nullable_next_v2':body=adapt_preparer_source(raw)
    elif profile=='strict_existing_v1':
        if type(raw) is not bytes or (len(raw),hashlib.sha256(raw).hexdigest())!=SOURCE_PIN:raise ValueError('frozen source pin')
        body=raw
    else:raise ValueError('explicit ABI profile')
    tree=ast.parse(body)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_binding']
    if len(nodes)!=1:raise ValueError('exact binding function')
    namespace={'math':math}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pinned binding guard>','exec'),namespace)
    return namespace['validate_binding']

def adaptation_receipt(raw):
    changed=adapt_preparer_source(raw)
    return {'schema':'neural098-nullable-next-source-adaptation-v1',
      'original':{'bytes':SOURCE_PIN[0],'sha256':SOURCE_PIN[1]},
      'adapted':{'bytes':len(changed),'sha256':hashlib.sha256(changed).hexdigest()},
      'literal_changes':len(CHANGES),'original_file_modified':False,'installed_or_executed_preparation':False,
      'unknown_next_policy':'Keep full binding; unknown is None and ineligible. Never infer a physical successor from97, run end, next run or nominal duration.',
      'future_execution_context':'Enclosing trusted preparation runner must authenticate dependencies and retain original neural098/private/prepare.py __file__/import context. This generator does not provide native loading, file custody or a process controller.',
      'known_next_eligibility_changed':False,'analysis_metric_or_cohort_changed':False}
