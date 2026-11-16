"""Closed prospective study choices. Policy is scope, never native authority."""
from dataclasses import dataclass
from enum import Enum
from .contracts import need,ARMS,MATCH_SEEDS,PANELS

class Tier(Enum):
    A0='A0_F_PRIMARY'
    A1='A1_PAIRED_PRIMARY'
    A2='A2_TOOL_FACTOR'
    A3='A3_TOOL_REPEAT_FACTOR'

@dataclass(frozen=True)
class StudyPolicy:
    tier:Tier
    panels:tuple
    adopted_initial:bool
    head:str='wheel_velocity'
    budget:int=10
    realization:str='anatomy'
    seeds:tuple=MATCH_SEEDS
    reference_arms:tuple=ARMS
    candidate_arms:tuple=('BR','BC')
    def validate(self):
        need(type(self) is StudyPolicy and type(self.tier) is Tier,'closed policy type')
        expected=panels_for(self.tier)
        need(self.panels==expected and self.head=='wheel_velocity' and self.budget==10 and self.realization=='anatomy','fixed primary scientific axes')
        need(self.seeds==MATCH_SEEDS and self.reference_arms==ARMS and self.candidate_arms==('BR','BC'),'all ten seeds/six reference/two candidate arms')
        need(type(self.adopted_initial) is bool and self.adopted_initial==(self.tier is Tier.A0),'only initial A0 root selection is current')
        return self
    def require_selected(self):
        self.validate();need(self.adopted_initial,'future A1/A2/A3 require separate prospective adoption before effects')
        return self

def panels_for(tier):
    need(type(tier) is Tier,'closed tier')
    modes=('F',) if tier is Tier.A0 else ('F','I')
    tools=('T0',) if tier in (Tier.A0,Tier.A1) else ('T0','T1')
    repeats=(0,1,2) if tier is Tier.A3 else (0,)
    return tuple(p for p in PANELS if p[0] in modes and p[1] in tools and p[2] in repeats)

def policy(tier=Tier.A0):
    return StudyPolicy(tier,panels_for(tier),tier is Tier.A0).validate()

def panel_name(panel):
    need(type(panel) is tuple and panel in PANELS,'exact panel identity')
    return '/'.join(map(str,panel))

NOT_SELECTED='NOT_SELECTED_PROSPECTIVELY'
def tier_dispositions(selected):
    selected.require_selected()
    return tuple((t.value,'SELECTED_SOURCE_SCOPE' if t is selected.tier else NOT_SELECTED) for t in Tier)
