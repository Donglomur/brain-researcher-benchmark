"""Full-person/run/passages joins for a future Broad phoneme extension.

No authentic population is instantiated here. The source declares 32 Broad
people and two Sherlock1 sessions; actual release identity/availability, reduced
file maps, passage equivalence and calibration are required private operands.
Neither the official loader's skipped rows nor this compiler's descriptors are
evidence of measured availability. No data files are accessed by this module.
"""
from dataclasses import dataclass
from fractions import Fraction
from .contracts import Asset,Pin,Refusal,need,fields,identity,rational,exact_unique,no_qualification

@dataclass(frozen=True)
class Clock:
    sample_count: int
    sample_zero_seconds: str
    annotation_to_recording_seconds: str
    evidence: Pin
    rate_hz: int=250
    def __post_init__(self):
        need(type(self.sample_count) is int and 125<=self.sample_count<=100000000,'full recording sample count')
        need(type(self.rate_hz) is int and self.rate_hz==250,'selected 250-Hz phoneme representation')
        rational(self.sample_zero_seconds);rational(self.annotation_to_recording_seconds)
        need(type(self.evidence) is Pin,'clock evidence identity required, not a verified boolean')
    def start(self,annotation_seconds):
        delta=(rational(annotation_seconds)+rational(self.annotation_to_recording_seconds)-
               rational(self.sample_zero_seconds))*self.rate_hz
        need(delta>=0,'event precedes recording; no max(0) clamp')
        first=delta.numerator//delta.denominator
        need(first+125<=self.sample_count,'whole 125-sample event extent; no truncation')
        return first

@dataclass(frozen=True)
class Run:
    key: tuple
    person: str
    narrative: str
    passage_groups: tuple
    representation: str
    recording: Asset
    annotations: Asset
    clock: Clock
    channels: Pin
    release: Pin
    def __post_init__(self):
        need(type(self.key) is tuple and len(self.key)==4,'source subject/session/task/run key')
        for x in self.key:identity(x)
        identity(self.person);identity(self.narrative)
        exact_unique(self.passage_groups,'whole-recording source-equivalence support')
        for x in self.passage_groups:identity(x)
        need(self.representation in ('full','reduced'),'explicit full/reduced file representation')
        need(type(self.recording) is Asset and type(self.annotations) is Asset and type(self.clock) is Clock,
             'typed complete source/clock joins')
        need(type(self.channels) is Pin and type(self.release) is Pin,'channel and release identity')

def parse_run(value):
    fields(value,('key','person','narrative','passage_groups','representation','recording','annotations','clock','channels','release'))
    c=value['clock'];fields(c,('sample_count','sample_zero_seconds','annotation_to_recording_seconds','rate_hz','evidence'))
    return Run(tuple(value['key']),value['person'],value['narrative'],tuple(value['passage_groups']),value['representation'],
               Asset.parse(value['recording']),Asset.parse(value['annotations']),
               Clock(c['sample_count'],c['sample_zero_seconds'],c['annotation_to_recording_seconds'],Pin.parse(c['evidence']),c['rate_hz']),
               Pin.parse(value['channels']),Pin.parse(value['release']))

def complete_release(runs, expected_keys, expected_people):
    """Exact requested scope, including missing members; never skip a failed run."""
    runs=tuple(runs);expected_keys=exact_unique((tuple(k) for k in expected_keys),'selected release run keys')
    people=exact_unique(expected_people,'selected biological people')
    need(all(type(r) is Run for r in runs),'typed source runs')
    need(len(runs)==len(expected_keys) and {r.key for r in runs}==set(expected_keys),'complete selected run coverage')
    need(len({r.key for r in runs})==len(runs),'no duplicate or substitute run')
    need({r.person for r in runs}==set(people),'exact biological-person denominator')
    need(len({r.recording.path for r in runs})==len(runs),'no one file pretending to be several recordings')
    # Same bytes across distinct biological identities requires explicit source
    # investigation, not automatic duplication of observations.
    need(len({r.recording.pin for r in runs})==len(runs),'recording content cannot be duplicated across runs')
    return {r.key:r for r in runs}

def broad_declaration(runs, expected_keys, expected_people):
    index=complete_release(runs,expected_keys,expected_people)
    need(len(expected_people)==32 and len(index)==64,'complete source-declared Broad 32-person/two-session extent')
    for person in expected_people:
        rows=[r for r in runs if r.person==person]
        need(len(rows)==2 and {r.key[1] for r in rows}=={'11','12'} and
             all(r.key[2]=='Sherlock1' for r in rows),'every Broad person has both declared sessions')
        need(len({r.key[0] for r in rows})==1,'one source-subject identity per biological person')
    need(len({r.key[0] for r in runs})==32,'no biological-person aliases')
    return index

@dataclass(frozen=True)
class Case:
    case_id: str
    axis: str
    person: str
    train: tuple
    tune: tuple
    calibrate: tuple
    query: tuple
    calibration_samples: int
    calibration_policy: Pin
    def __post_init__(self):
        identity(self.case_id);identity(self.person)
        need(self.axis in ('person_transfer','narrative_transfer','joint_person_narrative_transfer'),'separately named transfer axis')
        need(type(self.calibration_samples) is int and self.calibration_samples>=0 and type(self.calibration_policy) is Pin,
             'explicit equal calibration budget and source recipe')

def join_case(case,index):
    need(type(case) is Case,'typed prospective case')
    groups={n:tuple(tuple(k) for k in getattr(case,n)) for n in ('train','tune','calibrate','query')}
    need(groups['train'] and groups['query'],'nonempty full training/query groups')
    flat=[k for keys in groups.values() for k in keys]
    need(len(flat)==len(set(flat)) and set(flat)<=set(index),'disjoint known whole-run roles')
    rows={n:tuple(index[k] for k in keys) for n,keys in groups.items()}
    need({r.person for r in rows['query']}=={case.person},'query biological identity')
    need(all(r.person==case.person for r in rows['calibrate']),'target-person-only calibration')
    need(bool(rows['calibrate'])==(case.calibration_samples>0),'zero-label transfer distinct from supervised adaptation')
    if case.axis in ('person_transfer','joint_person_narrative_transfer'):
        need(all(r.person!=case.person for r in rows['train']+rows['tune']),'target person absent from all source fitting/tuning')
    query_groups={g for r in rows['query'] for g in r.passage_groups}
    fitting_groups={g for n in ('train','tune','calibrate') for r in rows[n] for g in r.passage_groups}
    overlap=sorted(query_groups&fitting_groups)
    if case.axis in ('narrative_transfer','joint_person_narrative_transfer'):
        need(not overlap,'global repeated-passage closure across all persons and adaptation')
    return {'rows':rows,'shared_query_passage_groups':overlap,
            'narrative_transfer_claim':case.axis!='person_transfer',
            'calibration_samples':case.calibration_samples,'calibration_policy':case.calibration_policy.json()}

def compile_cases(cases,index,expected_cases,expected_people,arms):
    """All specified cases and controls; protocol selection is an explicit input."""
    cases=tuple(cases);need(len(cases)==len(expected_cases) and {c.case_id for c in cases}==set(expected_cases),'full frozen case denominator')
    need(len({c.case_id for c in cases})==len(cases),'unique cases')
    required={'neural','time_shifted_neural','timing','acoustic','transcript'}
    need(set(arms)==required and len(arms)==len(required),'all canonical information controls; no convenient omission')
    axes={c.axis for c in cases};need({'person_transfer','narrative_transfer'}<=axes,'both canonical transfer questions remain separate')
    joined={c.case_id:join_case(c,index) for c in cases}
    for axis in axes:
        selected=[c for c in cases if c.axis==axis]
        need({c.person for c in selected}==set(expected_people),'all people on each stated transfer axis')
        need(len({(c.calibration_samples,c.calibration_policy) for c in selected})==1,'equal calibration budget/recipe across people')
    jobs=[{'case_id':c.case_id,'person':c.person,'axis':c.axis,'arm':a,'condition':condition,
           'roles':{n:[list(r.key) for r in joined[c.case_id]['rows'][n]] for n in ('train','tune','calibrate','query')}}
          for c in cases for condition in ('frozen_program','case_adaptive_equal_inputs_tools_compute') for a in arms]
    return {'jobs':jobs,'support':joined,'source_only':True,'admission':no_qualification()}
