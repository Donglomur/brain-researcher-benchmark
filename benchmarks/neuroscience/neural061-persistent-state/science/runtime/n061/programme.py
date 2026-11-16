"""Earlier metadata planning and the source-owned complete programme call chain.

No native admission issuer exists in this packet. Successful allocation is not
inferred from this finite operation catalogue or a supplied status. The internal
sequence states the real scientific producers that must follow that boundary.
"""
from dataclasses import dataclass
from .contracts import need,cohort,atlas,canonical
from .policy import policy
from .catalogue import build
from .resource_demand import compile_plan

@dataclass(frozen=True)
class ProgrammePlan:
    catalogue:object
    operations:object
    original_cohort:tuple
    original_ontology:object
    aliases:object
    metadata_snapshot:bytes
    alias_snapshot:tuple
    def validate(self):
        self.catalogue.validate();self.catalogue.policy.require_selected()
        need(self.operations.catalogue is self.catalogue,'same pre-effect catalogue and demand producer')
        cohort(self.original_cohort);atlas(self.original_ontology)
        need(canonical({'cohort':self.original_cohort,'ontology':self.original_ontology})==self.metadata_snapshot,'original pre-effect metadata bytes, not a changed same-shaped roster')
        need(tuple((self.aliases.session(r['session']),self.aliases.animal(r['animal'])) for r in self.original_cohort)==self.alias_snapshot,'same earlier opaque alias projection')
        source=tuple(pair[0] for r,pair in zip(self.original_cohort,self.alias_snapshot,strict=True) if r['role']=='source')
        evaluation=tuple(pair for r,pair in zip(self.original_cohort,self.alias_snapshot,strict=True) if r['role']=='evaluation')
        need(source==self.catalogue.source and tuple(s for s,_ in evaluation)==self.catalogue.evaluation,'source/evaluation original relative ordinal order')
        need(evaluation==self.catalogue.session_animals,'same exact biological evaluation inverse')
        return self

def build_plan(cohort_rows,ontology,opaque,selected=None):
    selected=policy() if selected is None else selected
    selected.require_selected();cohort(cohort_rows);regions=atlas(ontology)['grey_regions']
    public={}
    for ordinal,row in enumerate(cohort_rows):
        sid=opaque.session(row['session'])
        need(sid not in public,'one original session alias, no hash equivalence')
        public[sid]={'session':sid,'animal':opaque.animal(row['animal']),'role':row['role'],'fold':row['fold'],'ordinal':ordinal}
    cat=build(selected,regions,public)
    snapshot=canonical({'cohort':cohort_rows,'ontology':ontology})
    aliases=tuple((opaque.session(r['session']),opaque.animal(r['animal'])) for r in cohort_rows)
    return ProgrammePlan(cat,compile_plan(cat),tuple(cohort_rows),ontology,opaque,snapshot,aliases).validate()

def execute(plan,originals,host,late_host,owner):
    plan.validate()
    # Source-demand counts do not confer measured capacity or an actual provider.
    plan.operations.require_native_allocation()
    from .preparation import prepare
    from .production import collect
    from .grading import score
    from .report import programme_report
    prepared=prepare(originals,plan.original_cohort,plan.original_ontology,owner,plan.aliases,plan.catalogue.policy,plan)
    produced=collect(prepared,host,owner)
    # Preparation's private projection stays in the trusted target issuer. It is
    # not handed to an author/fit/predict process or to the late public argument.
    public={k:v for k,v in prepared.items() if k!='private'}
    scored=score(public,produced,late_host,owner)
    return programme_report(produced,scored)
