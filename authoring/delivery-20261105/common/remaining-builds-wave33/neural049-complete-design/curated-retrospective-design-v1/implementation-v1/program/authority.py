"""Independent actual proof admission and protected dynamic method/grade receipts."""
from pathlib import Path
import time
from core import need, encoded, pin, parse, capture, capture_new_protected, relative, canonical, integer
from configuration import validate
from contracts import GATES, TASK, PROFILE


def selection_pin(a):
    return pin(encoded({k: v for k, v in a.items() if k != 'qualifications'}))


def evidence(a, rows, budget):
    need(type(rows) is list and rows, 'nonempty independent actual evidence')
    for row in rows:
        capture(Path(a['roots']['operator']) / relative(row['path']), row['pin'],
                a['resources']['qualification_bytes'], budget, retain=False, readonly=True)


def qualify(a, source_pin, budget):
    validate(a, source_pin)
    need(budget.origin == a['clock']['origin'] and budget.deadline <= a['clock']['readback_end'],
         'unchanged original authority clock')
    selected = selection_pin(a); result = {}
    for name in GATES:
        row = a['qualifications'][name]
        optional_off = (name == 'tool_custody' and 'T1' not in a['modules']) or (
            name == 'assignment_feasibility' and 'D' not in a['modules']) or (
            name == 'reference_cache_custody' and not a['cache'])
        if optional_off:
            need(row == {'status': 'not_selected'}, 'explicit unselected module/cache disposition')
            result[name] = row; continue
        need(type(row) is dict and set(row) == {'path', 'pin'}, 'actual proof descriptor')
        raw, _ = capture(Path(a['roots']['operator']) / relative(row['path']), row['pin'],
                         a['resources']['qualification_bytes'], budget, readonly=True)
        q = parse(raw)
        need(q.get('schema') == 'neural049_actual_qualification_v1' and q.get('qualified') is True
             and q.get('realm') == 'actual_external_evidence' and q.get('issuer') == a['operator_identity']
             and q.get('kind') == name and q.get('task_id') == TASK and q.get('profile') == PROFILE
             and q.get('selection') == selected and q.get('source_manifest') == source_pin,
             'exact independent actual qualification: ' + name)
        evidence(a, q['evidence'], budget); result[name] = {'proof': row, 'body': q}
    budget.tick(); return result


def method(a, identity, source, recipe, claim, mode, budget, cutoff, context_pin):
    """Bounded wait for separately issued exact protected method review, never self-certification."""
    key = identity
    need(key in a['method_admissions'], 'predeclared protected method-review slot')
    path = Path(a['roots']['operator']) / relative(a['method_admissions'][key])
    while not path.exists():
        now = budget.tick(cutoff); time.sleep(min(.1, max(0., cutoff-now)))
    raw, desc = capture_new_protected(path, a['resources']['qualification_bytes'], budget)
    q = parse(raw)
    need(q.get('schema') == 'neural049_method_admission_v1' and q.get('qualified') is True
         and q.get('realm') == 'actual_external_evidence' and q.get('issuer') == a['operator_identity']
         and q.get('selection') == selection_pin(a) and q.get('source_manifest') == a['source_manifest']
         and q.get('identity') == key and q.get('source') == source and q.get('recipe') == recipe
         and q.get('claim') == claim and q.get('mode') == mode and q.get('source_context') == context_pin,
         'actual exact source/recipe/mode/disclosed-context review')
    for field in ('input_scope', 'state_isolation', 'no_hidden_labels', 'fixed_provider_grammar',
                  'full_output_support', 'query_batch_parity', 'source_only_global_authorship'):
        need(q.get(field) is True, 'independent method semantic finding: ' + field)
    evidence(a, q['evidence'], budget); budget.tick(cutoff)
    return {'path': str(path), 'pin': desc}


def grading_selection(a, declaration, budget):
    raw, _ = capture(declaration['path'], declaration['pin'], a['resources']['authority_bytes'], budget, readonly=True)
    q = parse(raw)
    need(q.get('schema') == 'neural049_late_grading_authority_v1' and q.get('active') is True
         and q.get('issuer') == a['operator_identity'] and q.get('selection') == selection_pin(a)
         and q.get('source_manifest') == a['source_manifest'] and q.get('original_origin') == budget.origin,
         'separately selected late protected grading')
    closure = q['external_completion']
    raw, _ = capture(Path(a['roots']['operator']) / relative(closure['path']), closure['pin'],
                     a['resources']['qualification_bytes'], budget, readonly=True)
    end = parse(raw)
    need(end.get('schema') == 'neural049_external_outer_completion_v1' and end.get('natural') is True
         and type(end.get('exit_code')) is int and end['exit_code'] == 0
         and end.get('source_manifest') == a['source_manifest'] and end.get('observation') == q['observation']
         and end.get('original_origin') == budget.origin and end.get('issuer') == a['operator_identity']
         and end.get('streams_closed') is True and end.get('capture_completed') is True
         and end.get('provisional') is False, 'independently observed outer completion before grading')
    evidence(a, end['evidence'], budget)
    need(canonical(q['output']).parent == canonical(a['roots']['observation']), 'fixed protected score output root')
    budget.tick(); return q
