"""Authenticate the complete accepted paper scope and captured ordinary source."""
from pathlib import Path
from .codec import capture, parse, need, pin


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_NAMES = ('OBLIGATIONS','WORKFLOW','GATES','EVALUATION_CONTRACT',
                  'DATA_DEPENDENCIES','NATIVE_BRANCH_MAP','TRANSMITTER_PROTOCOL')


def load_catalog(source_descriptor, meter=None):
    raw = capture(ROOT, source_descriptor, cap=1048576, meter=meter)
    catalogue = parse(raw)
    need(catalogue['schema']=='banc_full_source_catalog_v1', 'source catalogue schema')
    bytarget = {}
    captured = {}
    for row in catalogue['files']:
        name = row['target']
        need(name not in bytarget, 'duplicate source member')
        d = {'path':name,'bytes':row['bytes'],'sha256':row['sha256']}
        body = capture(ROOT,d,cap=1048576,meter=meter)
        bytarget[name] = d
        captured[name] = body
    contracts = {name:parse(captured['contracts/'+name+'.json']) for name in CONTRACT_NAMES}
    scope(contracts)
    return catalogue, bytarget, captured, contracts


def scope(c):
    rows = c['OBLIGATIONS']['rows']
    families = c['WORKFLOW']['families']
    need(len(rows)==96 and len({x['id'] for x in rows})==96, 'all96 unique paper panels')
    need(len(families)==18, 'all18 workflow families')
    need(len(c['WORKFLOW']['legacy_entries'])==24, 'all24 legacy entries')
    need(len(c['GATES']['gates'])==16, 'all16 scientific gates')
    need(len(c['NATIVE_BRANCH_MAP']['rows'])==7, 'all7 operator/specification/wrapper branches')
    seen = set()
    for family in families:
        need(family['id'] not in seen and set(family['dependencies']) <= seen, 'complete ordered DAG')
        seen.add(family['id'])
    need(all(x['workflow_family'] in seen for x in rows), 'all panel producer families known')
    need(c['TRANSMITTER_PROTOCOL']['future_predictive_improvement']['selected'] is False,
         'no implicit new transmitter test branch')
    return {'panels':96,'families':18,'legacy_entries':24,'gates':16,'operator_branches':7}
