"""Actual selected expected graph and explicit held full-study catalogue."""
from dataclasses import dataclass
from .contracts import need,text,catalogue as full_cells,ARMS,PANELS,CONTRASTS
from .policy import StudyPolicy,panel_name,NOT_SELECTED

@dataclass(frozen=True)
class OutputKey:
    panel:str
    cell:tuple
    session:str
    arm:str

@dataclass(frozen=True)
class StudyCatalogue:
    policy:StudyPolicy
    regions:tuple
    cells:tuple
    source:tuple
    evaluation:tuple
    animals:tuple
    session_animals:tuple
    expected:tuple
    def required_arms(self,panel):
        if panel=='REFERENCE':return self.policy.reference_arms
        need(panel in tuple(panel_name(p) for p in self.policy.panels),'selected actual candidate panel')
        return self.policy.candidate_arms
    def validate(self):
        need(type(self) is StudyCatalogue,'source-owned typed catalogue');self.policy.validate()
        need(len(self.source)==423 and len(self.evaluation)==29 and len(self.animals)==13,'whole original cohort metadata')
        need(len(set(self.source+self.evaluation))==452,'unique complete sessions')
        need(self.cells==tuple((self.policy.head,r,10,s,'anatomy') for r in self.regions for s in self.policy.seeds),'all region and seed cells')
        panels=('REFERENCE',)+tuple(panel_name(p) for p in self.policy.panels)
        wanted=tuple(OutputKey(p,c,s,a) for p in panels for c in self.cells for s in self.evaluation for a in self.required_arms(p))
        need(self.expected==wanted and len(set(wanted))==len(wanted),'complete selected reference/candidate output graph')
        need(tuple(s for s,_ in self.session_animals)==self.evaluation and set(a for _,a in self.session_animals)==set(self.animals),'same biological inverse')
        return self

def build(selected,regions,public):
    selected.validate();full_cells(regions)
    need(type(public) is dict and len(public)==452,'whole prepared session map')
    ordered=sorted(public,key=lambda s:public[s]['ordinal'])
    need(tuple(public[s]['ordinal'] for s in ordered)==tuple(range(452)),'full source ordinal inverse')
    source=tuple(s for s in ordered if public[s]['role']=='source');evaluation=tuple(s for s in ordered if public[s]['role']=='evaluation')
    need(len({public[s]['animal'] for s in source})==126 and not {public[s]['animal'] for s in source}&{public[s]['animal'] for s in evaluation},'whole disjoint biological source')
    animals=tuple(sorted({public[s]['animal'] for s in evaluation}));cells=tuple((selected.head,r,10,s,'anatomy') for r in regions for s in selected.seeds)
    panels=('REFERENCE',)+tuple(panel_name(p) for p in selected.panels)
    expected=tuple(OutputKey(p,c,s,a) for p in panels for c in cells for s in evaluation for a in (selected.reference_arms if p=='REFERENCE' else selected.candidate_arms))
    return StudyCatalogue(selected,regions,cells,source,evaluation,animals,tuple((s,public[s]['animal']) for s in evaluation),expected).validate()

def sensitivity_catalogue(cat):
    """No prediction body or biological unavailable status for unselected work."""
    cat.validate();selected=set(cat.cells)
    return tuple({'cell':c,'reference_arms':ARMS,'status':'SELECTED_S0' if c in selected else NOT_SELECTED} for c in full_cells(cat.regions))

def exploratory_catalogue(cat):
    cat.validate();panels=('REFERENCE',)+tuple(panel_name(p) for p in PANELS)
    return tuple({'key':(p,h,r,k,u,name),'status':'SELECTED_PRIMARY_REFERENCE' if (p,h,k,u,name)==('REFERENCE','wheel_velocity',10,'anatomy','replacement') else NOT_SELECTED}
                 for p in panels for h,r,k,seed,u in full_cells(cat.regions) if seed==0 for name,_,_ in CONTRASTS)
