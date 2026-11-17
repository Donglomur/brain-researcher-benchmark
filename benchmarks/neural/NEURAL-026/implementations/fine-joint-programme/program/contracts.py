"""Full original NEURAL026 case/design validation, without scientific imports."""
MICE=('cfa17','cfa19','cfa20','cfa22','cfa24')
AREAS=('M1','S1')
N_FOLDS=5
PANELS=('specification_only','reference_code_control','trusted_reference')
ARMS=('nuisance','neural','shifted')
FILE_CAP=134217728
PANEL_CAP=2147483648
INPUT_CAP=2147483648
CATALOGUE_CAP=16777216
CASE_RECEIPT_CAP=16384
COMPLETE_CAP=131072
EXTERNAL_CAP=65536
OBSERVER_STARTUP_READ_CAP=2097152
OBSERVER_STREAM_CAP=65536
# Two opaque copies of each complete panel, plus bounded source/metadata/EOF work.
OBSERVER_READ_FLOOR=6*PANEL_CAP+134217728
COMMON_DOCS=('RECONSTRUCTION.md','contract.json','ARRAY_SCHEMA.json','PREDICTION_SCHEMA.json')
CONTROL_DOCS=('protocol.py','reference_program.py')
def need(ok,message):
    if not ok:raise ValueError(message)

def case_ids():
    return [f'{mouse}_{area}_fold{fold}' for mouse in MICE for area in AREAS
            for fold in range(N_FOLDS)]

def validate_design(design):
    """Enforce the full pooled-once estimand before any private-reference read."""
    need(type(design) is dict and design.get('schema') == 'neural026_design_v1'
         and type(design.get('cases')) is list and len(design['cases']) == 50,
         'Exact fifty-case operator design')
    need([c.get('case_id') for c in design['cases']] == case_ids(), 'Fixed case order')
    for row in design['cases']:
        cid = row['case_id']
        mouse, area, foldtext = cid.split('_')
        fold = int(foldtext[4:])
        need(row.get('mouse') == mouse and row.get('area') == area
             and type(row.get('fold')) is int and row['fold'] == fold, 'Case identity matches biological unit/fold')
        for side in ('train_id', 'query_id'):
            ids = row.get(side)
            need(type(ids) is list and 4 <= len(ids) <= 4096
                 and all(type(i) is int and 0 < i < 2**63 for i in ids)
                 and ids == sorted(set(ids)), 'Positive sorted unique bounded trial IDs')
        need(not set(row['train_id']) & set(row['query_id']), 'Whole-trial separation')
        counts = row.get('matched_counts')
        need(type(counts) is dict and set(counts) == {'1','2'}
             and all(type(x) is int and x >= 10 for x in counts.values())
             and 20 <= sum(counts.values()) <= 4096, 'Exact matched target support')
    for mouse in MICE:
        area_counts = []
        for area in AREAS:
            rows = [r for r in design['cases'] if r['mouse'] == mouse and r['area'] == area]
            queries = [t for r in rows for t in r['query_id']]
            need(len(queries) == len(set(queries)), 'Query trials appear in exactly one fold')
            universe = set(queries); counts = rows[0]['matched_counts']
            need(len(universe) == sum(counts.values()), 'Matched complete source support')
            for r in rows:
                need(r['matched_counts'] == counts
                     and set(r['train_id']) == universe - set(r['query_id']),
                     'Each training set is the complement of its query fold')
            area_counts.append(counts)
        need(area_counts[0] == area_counts[1], 'M1/S1 matched counts per target within mouse')

def schedule():
    return [(panel,cid) for panel in PANELS for cid in case_ids()]

def visible(panel):
    need(panel in PANELS,'selected panel')
    if panel=='trusted_reference':return ('input.npz','case.json')
    return ('input.npz','case.json',*COMMON_DOCS,*(CONTROL_DOCS if panel=='reference_code_control' else ()))
