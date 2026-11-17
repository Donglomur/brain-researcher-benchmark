"""Actual preparation composition, exact fold views and individual immutable mounts."""
from pathlib import Path
from core import need, encoded, pin, capture, parse, relative, canonical, publish, fresh
from contracts import roster, identity


def packet(a, budget):
    from preparation import admit_packet, Budget as PreparationBudget
    selected = a['preparation_context']
    need(selected['origin'] == budget.origin and selected['deadline'] == a['clock']['readback_end'],
         'original selected preparation context; role only narrows deadline')
    # One cumulative helper meter per role, prepaid in the host ledger. It is
    # shared by every materialized fold, not reset for each view/operand.
    budget.reserve_read(selected['limits']['read_bytes'])
    budget.reserve_write(selected['limits']['write_bytes'])
    nested = PreparationBudget({**selected,'deadline':budget.deadline})
    value = admit_packet(a['packet'], nested)
    value['_budget'] = nested
    m = value['manifest']; table = {}
    for row in m['days']:
        table.setdefault(row['person'], []).append({'day': row['day'], 'ids': row['ids'], 'axis': row['axis'],
            'source': row['source']['pin'], 'empty': row['rows'] == 0})
    roster(table)
    need(m['source_count'] == 55 and m['person_count'] == 12, 'complete prepared cohort')
    need('D' not in a['modules'] or m['assignment_status'] == 'complete', 'complete D feasibility, no singleton fallback')
    return value, table


def make(a, packet_value, bank, budget, operation, person, train, query, view, role, policy):
    """Root issues selected view proof before materialization. No caller success callback."""
    from preparation import materialize_view
    selection = {'schema': 'neural049_fold_selection_v1', 'person': person, 'train_days': train,
                 'query_days': query, 'view': view, 'role': role,
                 'case_id': identity(['visible-case', person, train, query])[:32],
                 'source_policy': policy, 'packet_pin': a['packet']['complete']['pin']}
    # This operator-private identity may differ across arms; it is never placed
    # in actor messages, files, argv-visible source or public VIEW content.
    path = Path(a['roots']['operator'])/'views'/ (operation+'.json')
    from authority import evidence, selection_pin
    from core import capture_new_protected
    raw, desc = capture_new_protected(path, a['resources']['qualification_bytes'], budget)
    proof = parse(raw)
    need(proof.get('schema') == 'neural049_view_authority_v1' and proof.get('status') == 'selected_qualified_view'
         and proof.get('selection') == pin(encoded(selection)) and proof.get('packet') == a['packet']
         and proof.get('execution_selection') == selection_pin(a) and proof.get('issuer') == a['operator_identity']
         and proof.get('realm') == 'actual_external_evidence', 'independently selected exact fold-view authority')
    evidence(a, proof['evidence'], budget)
    selection['selection_authority'] = {'root': str(path.parent), 'body': {'path': path.name, 'pin': desc}}
    out = Path(a['roots']['output'])/'views'/operation
    budget.tick()
    result = materialize_view(a['packet'], selection, str(out), packet_value['_budget'])
    budget.tick()
    raw, _ = capture(out/result['mounts']['path'], result['mounts']['pin'], a['resources']['view_bytes'], budget, readonly=True)
    plan = parse(raw)
    raw, _ = capture(out/result['view']['path'], result['view']['pin'], a['resources']['view_bytes'], budget, readonly=True)
    visible = parse(raw)
    need(plan['selection'] == selection and visible['view'] == ('NC' if view == 'NC_D' else view), 'actual materialized exact requested view')
    mounts = []
    for row in plan['mounts']:
        need(row['readonly'] is True and canonical(row['source_root']) == canonical(a['packet']['root']), 'exact original prepared source root')
        source = bank.source(row['source']['path'], row['source']['pin'])
        need(row['target'].startswith('/case/inputs/') and row['role'] in ('train', 'query'), 'individual opaque array aliases')
        need(not row['kind'].startswith('label_') or row['role'] == 'train', 'no query target mounts')
        destination = '/inputs' + row['target']
        mounts.append({'source': source, 'destination': destination, 'pin': row['source']['pin'], 'bytes_cap': row['source']['pin']['bytes']})
    mounts.append({'source': str(out/result['view']['path']), 'destination': '/inputs/case/VIEW.json',
                   'pin': result['view']['pin'], 'bytes_cap': result['view']['pin']['bytes']})
    return {'result': result, 'selection': selection, 'plan': plan, 'visible': visible, 'mounts': mounts,
            'descriptor': {'path': '/inputs/case/VIEW.json', 'pin': result['view']['pin']}}


def numeric_parts(view, role, endpoint=None):
    """Add private original-day membership only to trusted reference requests."""
    from reference_adapter import reference_input
    public = view['visible']['train_parts' if role == 'train' else 'query_parts']
    private = [x for x in view['plan']['parts'] if x['role'] == role]
    need(len(public) == len(private), 'complete private/public part join')
    parts = []
    for visible, actual in zip(public, private):
        need(visible['ids'] == actual['ids'] and visible['axis'] == actual['axis'], 'exact assigned original part')
        row = {'day': actual['day'], 'ids': visible['ids'], 'axis': visible['axis'],
               'arrays': {k: reference_input(d) for k, d in visible['arrays'].items()}}
        if role == 'train':
            need(endpoint in ('angle', 'magnitude', 'speed'), 'one selected scalar reference endpoint')
            row['labels'] = reference_input(visible['labels'][endpoint])
        else: need('labels' not in visible, 'no query labels')
        parts.append(row)
    # The caller filters the private typed mount plan by endpoint. Filenames
    # are opaque and are never used to infer label identity.
    mounts = list(view['mounts'])
    return {'schema': 'neural049_numeric_parts_v1', 'parts': parts}, mounts
