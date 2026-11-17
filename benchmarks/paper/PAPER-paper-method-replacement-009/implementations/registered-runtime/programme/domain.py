"""Closed metadata boundary. No dataset, numerical, or process imports."""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re

CANONICAL = 'PAPER-paper-method-replacement-009'
TARGETS = ('choice', 'prior', 'wheel-speed', 'whisker-motion-energy')
PROFILES = ('paper433', 'released_code', 'prospective40')
CONDITIONS = ('paper_data', 'paper_data_author_code')
PARTITIONS = ('train', 'validation', 'test')
METHODS = ('linear', 'mlp', 'single_rrr', 'multi_rrr', 'multi_region_rrr', 'multi_linear', 'multi_mlp',
           'hmm', 'bmm_hmm', 'empirical_bmm_hmm', 'lg_ar1', 'empirical_lg_ar1',
           'rrr_bmm_hmm', 'rrr_lg_ar1', 'improved')
DIAGNOSTICS = ('pca_ari', 'conditional_residual', 'oracle_state', 'smoothing',
               'neuron_pruning', 'region_timing', 'rank_curve', 'session_scaling',
               'fourier', 'imposter_null', 'unaligned', 'allen', 'primate', 'timing')
OBLIGATIONS = tuple('F'+str(i) for i in range(1, 9)) + tuple('S'+str(i) for i in range(1, 9))

class Refusal(ValueError):
    pass

class MissingDefinition(Refusal):
    """A required source/identity/scientific rule was never selected."""

def closed(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise Refusal(label + ': closed fieldset')
    return value

def integer(v, lo=0, hi=2**63-1):
    if type(v) is not int or not lo <= v <= hi:
        raise Refusal('integer domain')
    return v

def text(v):
    if type(v) is not str or not v or '\x00' in v or len(v.encode()) > 4096:
        raise Refusal('text domain')
    return v

def unique(values, label):
    # Typed IDs are never equated by Python's True == 1 or str coercion.
    keys = [(type(x).__name__, x) for x in values]
    if len(set(keys)) != len(keys):
        raise Refusal(label + ': duplicate')
    return values

def identity(v):
    closed(v, ('kind', 'value'), 'identity')
    if v['kind'] == 'integer': integer(v['value'])
    elif v['kind'] == 'text': text(v['value'])
    else: raise Refusal('identity kind')
    return (v['kind'], v['value'])

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')

def strict_json(raw):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d: raise Refusal('duplicate JSON key')
            d[k] = v
        return d
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refusal('nonfinite JSON')))

def relative(v):
    text(v)
    if v.startswith('/') or '\\' in v or any(x in ('', '.', '..') for x in v.split('/')):
        raise Refusal('unsafe relative path')
    return v

@dataclass(frozen=True)
class Pin:
    path: str
    bytes: int
    sha256: str
    def __post_init__(self):
        relative(self.path); integer(self.bytes)
        if not re.fullmatch('[0-9a-f]{64}', self.sha256): raise Refusal('sha256')
    @classmethod
    def parse(cls, v):
        closed(v, ('path', 'bytes', 'sha256'), 'Pin')
        return cls(**v)
    def document(self):
        return {'path': self.path, 'bytes': self.bytes, 'sha256': self.sha256}

@dataclass(frozen=True)
class Limits:
    member_bytes: int
    total_bytes: int
    members: int
    jobs: int
    wall_ns: int
    cpu_ns: int
    memory_bytes: int
    processes: int
    def __post_init__(self):
        for v in self.__dict__.values(): integer(v, 1)
        if self.member_bytes > self.total_bytes: raise Refusal('member > total')
    @classmethod
    def parse(cls, v):
        closed(v, tuple(cls.__dataclass_fields__), 'Limits'); return cls(**v)

@dataclass(frozen=True)
class Case:
    case_id: str
    session: str
    animal: str
    dataset: str
    target: str
    region: str
    availability: str
    reason: str | None
    source: Pin | None
    trial_support: Pin | None
    def __post_init__(self):
        for x in (self.case_id, self.session, self.animal, self.dataset, self.target, self.region): text(x)
        if self.availability not in ('available', 'unavailable'): raise Refusal('availability')
        if self.availability == 'available':
            if self.source is None or self.trial_support is None or self.reason is not None:
                raise Refusal('available case has missing lineage')
        elif self.reason is None or self.source is not None or self.trial_support is not None:
            raise Refusal('unavailable case must retain reason without invented arrays')
    @classmethod
    def parse(cls, v):
        closed(v, tuple(cls.__dataclass_fields__), 'Case')
        q = dict(v)
        for k in ('source', 'trial_support'): q[k] = None if q[k] is None else Pin.parse(q[k])
        return cls(**q)

@dataclass(frozen=True)
class Job:
    job_id: str
    condition: str
    method: str
    case_ids: tuple
    configuration: Pin
    original_source: Pin
    split: Pin
    role: str
    def __post_init__(self):
        text(self.job_id)
        if self.condition not in CONDITIONS or self.method not in METHODS + DIAGNOSTICS:
            raise Refusal('job dispatch')
        if self.role not in ('candidate', 'reference', 'postcapture_diagnostic'): raise Refusal('job role')
        if not self.case_ids: raise Refusal('empty job')
        unique(self.case_ids, 'job cases')
        if self.method == 'improved' and self.role != 'candidate': raise Refusal('improvement owner')
        if self.method in DIAGNOSTICS and self.role != 'postcapture_diagnostic': raise Refusal('diagnostic role')

@dataclass(frozen=True)
class Plan:
    profile: str
    cohort: Pin
    source_selection: Pin
    historical_definition: Pin | None
    cases: tuple
    jobs: tuple
    panels: tuple
    limits: Limits
    unresolved: tuple

def parse_plan(v):
    closed(v, ('schema', 'canonical_id', 'profile', 'cohort', 'source_selection',
               'historical_definition', 'cases', 'jobs', 'panels', 'limits', 'unresolved'), 'Plan')
    if v['schema'] != 'trial_session_study_plan_v1' or v['canonical_id'] != CANONICAL:
        raise Refusal('plan version/canonical')
    if v['profile'] not in PROFILES: raise Refusal('profile')
    cases = tuple(Case.parse(c) for c in v['cases']); unique([c.case_id for c in cases], 'cases')
    jobs = []
    for j in v['jobs']:
        closed(j, tuple(Job.__dataclass_fields__), 'Job')
        jobs.append(Job(j['job_id'], j['condition'], j['method'], tuple(j['case_ids']),
                        Pin.parse(j['configuration']), Pin.parse(j['original_source']),
                        Pin.parse(j['split']), j['role']))
    unique([j.job_id for j in jobs], 'jobs')
    plan = Plan(v['profile'], Pin.parse(v['cohort']), Pin.parse(v['source_selection']),
                None if v['historical_definition'] is None else Pin.parse(v['historical_definition']),
                cases, tuple(jobs), tuple(v['panels']), Limits.parse(v['limits']), tuple(v['unresolved']))
    validate_plan(plan)
    return plan

def validate_plan(p):
    ids = {c.case_id for c in p.cases}
    if len(p.jobs) > p.limits.jobs: raise Refusal('job capacity')
    for j in p.jobs:
        if not set(j.case_ids) <= ids: raise Refusal('foreign job case')
    ibl = [c for c in p.cases if c.dataset == 'ibl']
    sessions = {c.session for c in ibl}
    if p.profile == 'paper433':
        if len({c.session for c in ibl if c.region != 'all'}) != 433 or len({c.region for c in ibl if c.region != 'all'}) != 270:
            raise Refusal('full paper 433/270 population, not RE40')
        if p.historical_definition is None: raise MissingDefinition('historical cohort/split/panel definition')
    elif p.profile == 'prospective40' and len(sessions) != 40:
        raise Refusal('separate prospective40 population')
    if p.profile == 'prospective40':
        for s in sessions:
            if {c.target for c in ibl if c.session == s and c.region == 'all'} != set(TARGETS):
                raise Refusal('each RE session retains all four target dispositions')
    if p.profile == 'paper433':
        # 433/270 is the choice/prior brain-wide study, NOT 433 complete-camera sessions.
        regional = [c for c in ibl if c.region != 'all']
        for key in {(c.session,c.region) for c in regional}:
            if {c.target for c in regional if (c.session,c.region)==key} != {'choice','prior'}:
                raise Refusal('each observed brain-wide session-region retains choice/prior dispositions')
    # Incomplete physical coverage remains a visible disposition. It never qualifies a full run.
    pair = {}
    for j in p.jobs:
        if j.role != 'candidate': continue
        key = (j.method, j.case_ids, canonical(j.configuration.document()), canonical(j.split.document()))
        pair.setdefault(key, set()).add(j.condition)
    if any(v != set(CONDITIONS) for v in pair.values()): raise Refusal('unpaired candidate job')
    for c in p.cases:
        if c.availability != 'available': continue
        if not any(c.case_id in j.case_ids and j.role == 'reference' for j in p.jobs):
            raise Refusal('missing independent reference case')
    panel_ids = []
    for row in p.panels:
        closed(row, ('panel_id', 'obligation', 'case_ids', 'job_ids', 'recipe', 'availability', 'reason'), 'Panel')
        text(row['panel_id']); panel_ids.append(row['panel_id'])
        if row['obligation'] not in OBLIGATIONS or not set(row['case_ids']) <= ids:
            raise Refusal('panel population')
        if not set(row['job_ids']) <= {j.job_id for j in p.jobs}: raise Refusal('panel job')
        if row['availability'] == 'available':
            Pin.parse(row['recipe'])
            if row['reason'] is not None: raise Refusal('available panel reason')
        elif row['availability'] == 'unavailable':
            text(row['reason'])
            if row['recipe'] is not None: raise Refusal('unavailable panel recipe')
        else: raise Refusal('panel disposition')
    unique(panel_ids, 'panels')
    if p.profile == 'paper433' and {x['obligation'] for x in p.panels} != set(OBLIGATIONS):
        raise Refusal('full main and supplement obligation census')

def readiness(p):
    reasons = list(p.unresolved)
    reasons += ['case:'+c.case_id+':'+c.reason for c in p.cases if c.availability == 'unavailable']
    reasons += ['panel:'+x['panel_id']+':'+x['reason'] for x in p.panels if x['availability'] == 'unavailable']
    return {'source_plan_closed': True, 'scientifically_qualified': False,
            'runtime_admitted': False, 'unresolved': reasons}
