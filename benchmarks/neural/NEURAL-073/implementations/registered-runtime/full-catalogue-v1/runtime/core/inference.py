"""Pure, canonical matched inference settings and three-repetition randomness.

No vendor endpoint/default or seed support is inferred. Independently qualified
adapter evidence must cover every effective setting, including argv overrides.
Wire confirmations record actual application, not proof of endpoint compliance.
"""
from dataclasses import dataclass
import math
import re
from .custody import CustodyError, canonical, digest, require_digest

# Closed canonical semantics. Adapter qualification maps these to actual native
# settings; unsupported/unrepresentable effective knobs fail admission. There is
# deliberately no generic vendor_options escape hatch for a second seed policy.
_PARAMETER_KINDS = {
    'temperature':'float', 'top_p':'float', 'top_k':'int', 'min_p':'float',
    'frequency_penalty':'float', 'presence_penalty':'float',
    'repetition_penalty':'float', 'reasoning_effort':'str',
    'reasoning_budget_tokens':'int', 'stop_sequences':'strings',
    'response_format':'str',
}


def _keys(value, names, role):
    if type(value) is not dict or set(value) != set(names):
        raise CustodyError('closed inference fields: '+role)


def _text(value, role, maximum=256):
    if type(value) is not str or not value or '\x00' in value or len(value.encode('utf-8')) > maximum:
        raise CustodyError('bounded inference text: '+role)
    return value


def _rep(value):
    if type(value) is not int or value not in (0,1,2):
        raise CustodyError('exact repetition index 0,1,2 required')
    return value


@dataclass(frozen=True)
class InferenceParameter:
    name: str
    kind: str
    value: object

    def __post_init__(self):
        if type(self.name) is not str or self.name not in _PARAMETER_KINDS or self.kind != _PARAMETER_KINDS[self.name]:
            raise CustodyError('unknown inference setting or noncanonical type; seeds are schedule-only')
        v = self.value
        if self.kind == 'float':
            if type(v) is not float or not math.isfinite(v):
                raise CustodyError('finite exact binary64 setting required')
            if self.name in ('temperature','repetition_penalty') and v < 0:
                raise CustodyError('negative sampling setting')
            if self.name == 'top_p' and not 0 < v <= 1:
                raise CustodyError('top_p range')
            if self.name == 'min_p' and not 0 <= v <= 1:
                raise CustodyError('min_p range')
        elif self.kind == 'int':
            if type(v) is not int or not 0 <= v <= (1<<53)-1:
                raise CustodyError('nonnegative exact integer setting required')
        elif self.kind == 'str':
            _text(v,self.name)
        elif self.kind == 'strings':
            if type(v) is not tuple or len(v)>32 or len(set(v))!=len(v):
                raise CustodyError('immutable unique stop sequence list required')
            for item in v:
                _text(item,self.name,4096)

    def to_dict(self):
        return {'name':self.name,'kind':self.kind,
                'value':list(self.value) if self.kind=='strings' else self.value}

    @classmethod
    def from_dict(cls, value):
        _keys(value,('name','kind','value'),'parameter')
        v=value['value']
        if value['kind']=='strings':
            if type(v) is not list:raise CustodyError('JSON sequence setting must be list')
            v=tuple(v)
        return cls(value['name'],value['kind'],v)


@dataclass(frozen=True)
class InferenceSettings:
    parameters: tuple
    completeness_evidence_digest: str

    def __post_init__(self):
        require_digest(self.completeness_evidence_digest)
        if type(self.parameters) is not tuple or not 1 <= len(self.parameters) <= len(_PARAMETER_KINDS) or any(type(p) is not InferenceParameter for p in self.parameters):
            raise CustodyError('nonempty immutable typed inference settings required')
        names=[p.name for p in self.parameters]
        if names!=sorted(set(names)):
            raise CustodyError('inference settings must be canonical sorted unique names')

    def to_dict(self):
        return {'schema':'n073_inference_settings_v1',
                'parameters':[p.to_dict() for p in self.parameters],
                'completeness_evidence_digest':self.completeness_evidence_digest}

    @classmethod
    def from_dict(cls, value):
        _keys(value,('schema','parameters','completeness_evidence_digest'),'settings')
        if value['schema']!='n073_inference_settings_v1' or type(value['parameters']) is not list or not 1 <= len(value['parameters']) <= len(_PARAMETER_KINDS):
            raise CustodyError('inference settings schema/extent')
        return cls(tuple(InferenceParameter.from_dict(p) for p in value['parameters']),value['completeness_evidence_digest'])

    @property
    def binding_digest(self):return digest(self.to_dict())


@dataclass(frozen=True)
class RepetitionSchedule:
    mode: str
    seeds: tuple
    randomness_evidence_digest: str

    def __post_init__(self):
        require_digest(self.randomness_evidence_digest)
        if type(self.seeds) is not tuple or self.mode not in ('seed_triplet','independent_draws'):
            raise CustodyError('explicit typed repetition randomness schedule required')
        if self.mode=='seed_triplet':
            if len(self.seeds)!=3 or any(type(s) is not int or not 0<=s<(1<<63) for s in self.seeds) or len(set(self.seeds))!=3:
                raise CustodyError('three distinct exact nonnegative seeds required')
        elif self.seeds:
            raise CustodyError('independent no-seed policy cannot contain seeds')

    def to_dict(self):
        return {'schema':'n073_repetition_schedule_v1','mode':self.mode,
                'seeds':list(self.seeds),'randomness_evidence_digest':self.randomness_evidence_digest,
                'request_rule':'fixed_repetition_seed_each_request' if self.mode=='seed_triplet' else 'record_each_independent_generation'}

    @classmethod
    def from_dict(cls, value):
        _keys(value,('schema','mode','seeds','randomness_evidence_digest','request_rule'),'schedule')
        if value['schema']!='n073_repetition_schedule_v1' or type(value['seeds']) is not list or len(value['seeds'])>3:
            raise CustodyError('repetition schedule schema/extent')
        obj=cls(value['mode'],tuple(value['seeds']),value['randomness_evidence_digest'])
        if value['request_rule']!=obj.to_dict()['request_rule']:
            raise CustodyError('unbound request seed/draw rule')
        return obj

    def seed_for(self,repetition):
        _rep(repetition)
        return self.seeds[repetition] if self.mode=='seed_triplet' else None


@dataclass(frozen=True)
class InferencePolicy:
    settings: InferenceSettings
    schedule: RepetitionSchedule

    def __post_init__(self):
        if type(self.settings) is not InferenceSettings or type(self.schedule) is not RepetitionSchedule:
            raise CustodyError('typed inference settings and schedule required')

    def to_dict(self):
        return {'schema':'n073_inference_policy_v1','settings':self.settings.to_dict(),
                'schedule':self.schedule.to_dict()}

    @classmethod
    def from_dict(cls,value):
        _keys(value,('schema','settings','schedule'),'policy')
        if value['schema']!='n073_inference_policy_v1':raise CustodyError('inference policy schema')
        return cls(InferenceSettings.from_dict(value['settings']),RepetitionSchedule.from_dict(value['schedule']))

    @property
    def binding_digest(self):return digest(self.to_dict())

    def binding_for(self,repetition):
        _rep(repetition)
        return {'schema':'n073_context_inference_v1','policy':self.to_dict(),
                'policy_digest':self.binding_digest,'repetition':repetition,
                'seed':self.schedule.seed_for(repetition)}


def validate_binding(value):
    _keys(value,('schema','policy','policy_digest','repetition','seed'),'context binding')
    if value['schema']!='n073_context_inference_v1':raise CustodyError('context inference schema')
    p=InferencePolicy.from_dict(value['policy'])
    expected=p.binding_for(value['repetition'])
    if canonical(value)!=canonical(expected):raise CustodyError('inference policy/repetition/seed mismatch')
    return expected


def require_applied_inference(actual,expected):
    a=validate_binding(actual);e=validate_binding(expected)
    if canonical(a)!=canonical(e):
        raise CustodyError('effective inference settings/schedule differ from admitted policy')
    return a


def validate_generation_record(record,*,binding,context_id,request_id,failed,seen_draw_ids=()):
    """Check original adapter-reported application/draw evidence, never infer it.

    The independently admitted randomness evidence must establish that records
    reflect actual backend calls and that no deterministic seed was available in
    independent mode. A fabricated echo or unique local ID proves neither.
    """
    binding=validate_binding(binding)
    _keys(record,('schema','context_id','request_id','mode','seed','draw_id',
                  'randomness_evidence_digest','provider_record','provider_record_digest','sampled'),'generation record')
    schedule=binding['policy']['schedule']
    if (record['schema']!='n073_generation_inference_v1' or record['context_id']!=context_id or
        record['request_id']!=request_id or record['mode']!=schedule['mode'] or
        type(record['seed']) is not type(binding['seed']) or record['seed']!=binding['seed'] or
        record['randomness_evidence_digest']!=schedule['randomness_evidence_digest']):
        raise CustodyError('generation seed/draw identity mismatch')
    if type(failed) is not bool or type(record['sampled']) is not bool or (not record['sampled'] and not failed):
        raise CustodyError('successful generation must carry actual sampling evidence')
    if schedule['mode']=='seed_triplet' or not record['sampled']:
        if record['draw_id'] is not None:raise CustodyError('seeded call cannot claim independent draw identity')
    else:
        _text(record['draw_id'],'independent draw ID',512)
        if record['draw_id'] in seen_draw_ids:raise CustodyError('independent generation draw reused')
    original=record['provider_record']
    if type(original) is not dict or not original or len(canonical(original))>65536:
        raise CustodyError('bounded original inference provider record required')
    require_digest(record['provider_record_digest'])
    if digest(original)!=record['provider_record_digest']:
        raise CustodyError('original inference provider record digest mismatch')
    # Canonical roundtrip avoids retaining mutable backend objects in receipts.
    import json
    return json.loads(canonical(record))
