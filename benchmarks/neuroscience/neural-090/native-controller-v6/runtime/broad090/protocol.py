"""Root-selected prospective Broad protocol; no model/data work on import."""
from dataclasses import dataclass
from programme.contracts import need

ARMS=('neural','time_shifted_neural','timing','acoustic','transcript')
PROTECTED=ARMS[:3]
EXPOSED=ARMS[3:]
MODES=('frozen_program','case_adaptive_equal_inputs_tools_compute')
SEEDS=tuple(range(10))
EPSILON=1e-6
CLASSES=39
WINDOW=125
BATCH=256
CALIBRATION_EPOCHS=10
SOURCE_MAX_EPOCHS=10
LEARNING_RATE=1e-4

@dataclass(frozen=True)
class Case:
    person: str
    query_chapter: str
    axis: str
    budget: str
    def __post_init__(self):
        need(self.person in tuple(str(i) for i in range(1,33)),'all32 Broad identities only')
        need(self.query_chapter in ('11','12'),'both fixed chapter directions')
        need(self.axis in ('held_chapter','joint_person_held_chapter','exposed_person'),'three separate estimands')
        expected=('full','1024') if self.axis=='held_chapter' else ('0','1024')
        need(self.budget in expected,'axis-specific training or calibration budget')
    @property
    def source_chapter(self):return '12' if self.query_chapter=='11' else '11'
    @property
    def key(self):return '/'.join((self.axis,self.person,self.query_chapter,self.budget))
    @property
    def primary_eligible(self):return self.axis!='exposed_person'
    @property
    def calibration_count(self):return 0 if self.axis=='held_chapter' else int(self.budget)

def cases():
    return tuple(Case(p,c,a,b) for p in map(str,range(1,33)) for c in ('11','12')
                 for a in ('held_chapter','joint_person_held_chapter','exposed_person')
                 for b in (('full','1024') if a=='held_chapter' else ('0','1024')))

def jobs():
    return tuple({'case':c.key,'person':c.person,'chapter':c.query_chapter,'axis':c.axis,'budget':c.budget,
                  'mode':m,'seed':s,'arm':a,'target_exposure':('protected' if a in PROTECTED else 'stimulus_exposed_diagnostic'),
                  'person_condition_exposed':not c.primary_eligible}
                 for c in cases() for m in MODES for s in SEEDS for a in ARMS)

def work_key(job):return '|'.join((job['case'],job['mode'],str(job['seed']),job['arm']))

def full_work_identity(work):
    expected={work_key(j) for j in jobs()};actual=[work_key(j) for j in work]
    need(len(actual)==len(set(actual))==len(expected) and set(actual)==expected,'complete38400 jobs/384 cases; no omissions')
    return expected

PHONEMES=('aa', 'ae', 'ah', 'ao', 'aw', 'ay', 'b', 'ch', 'd', 'dh', 'eh', 'er', 'ey', 'f', 'g', 'hh', 'ih', 'iy', 'jh', 'k', 'l', 'm', 'n', 'ng', 'ow', 'oy', 'p', 'r', 's', 'sh', 't', 'th', 'uh', 'uw', 'v', 'w', 'y', 'z', 'zh')
TIMING_L2=1e-4
