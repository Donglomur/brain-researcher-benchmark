"""Closed structural contracts. No input access or numerical library imports."""
from dataclasses import dataclass
import json
import math

TASK = 'NEURAL-061'
COMMIT = '6fbd666fe8170a2165f5198c1f490911424a654d'
HEADS = ('choice', 'reward', 'stimulus_contrast', 'whisker_motion_energy',
         'wheel_speed', 'right_paw_speed', 'left_paw_speed', 'licking_rate', 'wheel_velocity')
CLASSES = {'choice': 2, 'reward': 2, 'stimulus_contrast': 5}
ARMS = ('B', 'BR', 'BC', 'R', 'C', 'ZERO')
BUDGETS = (5, 10, 20)
MATCH_SEEDS = tuple(range(10))
REALIZATIONS = ('anatomy', 'stratified_anatomy_shuffle')
PANELS = tuple((mode, tool, rep) for mode in ('F', 'I') for tool in ('T0', 'T1') for rep in (0, 1, 2))
CONTRASTS = (('replacement', 'BC', 'BR'), ('addition', 'B', 'BR'),
             ('region_only', 'C', 'R'), ('neural_information', 'ZERO', 'BR'))
RATE_EDGES_HZ = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)

class ContractError(ValueError):
    pass

class ScientificUnavailable(Exception):
    """A prespecified support deficiency, never an execution/native failure."""
    def __init__(self,reason,details):
        super().__init__(reason);self.reason=reason;self.details=details

def need(condition, label):
    if not condition:
        raise ContractError(label)

def closed(value, fields, label):
    need(type(value) is dict and set(value) == set(fields), label)
    return value

def text(value):
    need(type(value) is str and 0 < len(value.encode('utf8')) <= 512, 'bounded literal identity')
    return value

def finite(value):
    need(type(value) in (int, float) and math.isfinite(value), 'finite non-boolean number')
    return float(value)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')

def identifier(value):
    """Typed IDs are not coerced: integer 0 and string '0' remain distinct."""
    need(type(value) in (int, str), 'literal source identifier')
    return (type(value).__name__, value)

@dataclass(frozen=True)
class Unit:
    index: int
    unit_id: str
    cluster_id: int
    probe: str
    session: str
    animal: str
    region: str
    rate: float
    qc_neural: str
    qc_alignment: str
    label: float | None

def units(rows, session, animal, probes, regions):
    need(type(rows) is tuple and rows, 'complete immutable original unit axis')
    need(all(type(u) is Unit for u in rows), 'typed original unit rows')
    need(tuple(u.index for u in rows) == tuple(range(len(rows))), 'unfiltered original row order')
    need(len({u.unit_id for u in rows}) == len(rows), 'unique original unit UUID')
    need(len({(u.probe, u.cluster_id) for u in rows}) == len(rows), 'probe-local cluster composite key')
    for u in rows:
        need(u.session == session and u.animal == animal and u.probe in probes, 'actual hierarchy join')
        need(u.region in regions or u.region in ('void', 'root', '<MISSING>'), 'complete ontology disposition')
        need(u.qc_neural in ('PASS', 'WARNING', 'FAIL') and u.qc_alignment in ('PASS', 'WARNING', 'FAIL'), 'known QC vocabulary')
        need(finite(u.rate) >= 0 and (u.label is None or 0 <= finite(u.label) <= 1), 'training-only rate and original/missing unit label')
    return rows

def cohort(rows):
    need(type(rows) is tuple and len(rows) == 452, 'full 423 plus 29 session census')
    seen = set(); probes = set(); labs = {}; roles = {'source': [], 'evaluation': []}
    for r in rows:
        closed(r, ('session', 'animal', 'lab', 'probes', 'role', 'fold'), 'cohort record')
        need(r['role'] in roles and r['session'] not in seen, 'unique corpus session')
        seen.add(r['session']); roles[r['role']].append(r)
        need(type(r['probes']) is tuple and r['probes'] and len(set(r['probes'])) == len(r['probes']), 'complete probe list')
        need(not probes.intersection(r['probes']), 'one session per probe'); probes.update(r['probes'])
        need(r['animal'] not in labs or labs[r['animal']] == r['lab'], 'one source lab per animal')
        labs[r['animal']] = r['lab']
        need(r['fold'] is None if r['role'] == 'evaluation' else type(r['fold']) is int and 0 <= r['fold'] < 5, 'source-only animal fold')
    sa = {r['animal'] for r in roles['source']}; ea = {r['animal'] for r in roles['evaluation']}
    need(len(roles['source']) == 423 and len(roles['evaluation']) == 29 and len(sa) == 126 and len(ea) == 13 and not sa & ea, 'complete disjoint animals')
    for a in sa:
        need(len({r['fold'] for r in roles['source'] if r['animal'] == a}) == 1, 'animal never split between folds')
    fold_counts=[len({r['animal'] for r in roles['source'] if r['fold']==f}) for f in range(5)]
    need(fold_counts==[26,25,25,25,25],'complete original five-fold source-animal allocation')
    return roles

def atlas(doc):
    closed(doc,('version','regions','grey_regions','source_pin'),'complete earlier atlas declaration')
    text(doc['version']);need(type(doc['regions']) is tuple and type(doc['grey_regions']) is tuple,'immutable ontology axes')
    need(len(set(doc['regions']))==len(doc['regions']) and set(doc['grey_regions'])<=set(doc['regions']),'grey matter is exact full-atlas subset')
    for r in doc['regions']:text(r)
    closed(doc['source_pin'],('path','bytes','sha256'),'source descriptor is not runtime authority')
    return doc

def catalogue(region_rows):
    """All selected Beryl grey-matter regions; absence is a report row, not pruning."""
    need(type(region_rows) is tuple and region_rows, 'earlier complete ontology roster')
    need(len(set(region_rows)) == len(region_rows) and tuple(sorted(region_rows)) == region_rows, 'fixed unique region family')
    for region in region_rows: text(region)
    return tuple((h, r, k, seed, realization) for h in HEADS for r in region_rows
                 for k in BUDGETS for seed in MATCH_SEEDS for realization in REALIZATIONS)

def panel_key(panel):
    need(type(panel) is tuple and panel in PANELS, 'one full-panel treatment')
    return '/'.join(map(str, panel))
