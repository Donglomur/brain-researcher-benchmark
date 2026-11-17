"""Exact original per-cell/arm query capabilities and global source-only F."""
from dataclasses import dataclass
from .contracts import need
from .policy import panel_name

@dataclass(frozen=True)
class AuthorContext:
    catalogue:object
    panel:tuple
    animal:object
    cell:object
    arm:object
    source_sessions:tuple
    evaluation_sessions:tuple
    def request(self):
        c=self.catalogue;c.policy.validate();need(self.panel in c.policy.panels,'selected exact panel')
        mode,tool,rep=self.panel
        need(self.source_sessions==c.source,'full source census')
        if mode=='F':need(self.animal is self.cell is self.arm is None and not self.evaluation_sessions,'one global source-only F context')
        else:
            need(self.animal in c.animals and self.cell in c.cells and self.arm in c.policy.candidate_arms,'exact isolated I animal/cell/arm')
            need(self.evaluation_sessions==tuple(s for s,a in c.session_animals if a==self.animal),'one animal same-cell/seed/arm context; no union')
        return {'task':'NEURAL-061','panel':self.panel,'animal':self.animal,'cell':self.cell,'arm':self.arm,
                'source_sessions':self.source_sessions,'evaluation_sessions':self.evaluation_sessions,
                'access':'source_only' if mode=='F' else 'only_current_cell_arm_and_current_animal','tool_policy':tool}

def author_contexts(cat,panel):
    cat.validate();need(panel in cat.policy.panels,'selected panel')
    if panel[0]=='F':return (AuthorContext(cat,panel,None,None,None,cat.source,()),)
    return tuple(AuthorContext(cat,panel,a,c,arm,cat.source,tuple(s for s,animal in cat.session_animals if animal==a))
                 for a in cat.animals for c in cat.cells for arm in cat.policy.candidate_arms)

def checked_view(view,context,cell,arm,session,training):
    context.request();need(cell in context.catalogue.cells and arm in context.catalogue.policy.candidate_arms,'selected scientific cell and arm')
    need(session in (context.source_sessions if training else context.catalogue.evaluation if context.panel[0]=='F' else context.evaluation_sessions),'exact original session capability')
    if context.panel[0]=='I':need(cell==context.cell and arm==context.arm,'no cross-arm/region/seed I state')
    if view['status']=='complete':
        need(view['session']==session and view['cell']==cell and view['arm']==arm,'actual projected view inverse')
        need(all(('values' in w)==training for w in view['windows']),'source labels only; evaluation no values')
    return view
