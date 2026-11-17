"""Trust starts at a controller-supplied exact root selection, never a candidate file."""
from .custody import read_pin,parse,need,descriptor,pin,encode
from .guard import RequiredUnscorable,distinct

OPERATIONS=('prepare','independent_reference','native_reference','candidate','collect','grade','report')
PREREQUISITES={
 'prepare':['G02','G03','G04','G05','G06','G07','G08','G10','G11','G13'],
 'independent_reference':['G01','G02','G03','G04','G05','G06','G07','G08','G09','G10','G11','G13'],
 'native_reference':['G01','G02','G03','G04','G05','G06','G07','G08','G09','G10','G11','G13'],
 'candidate':['G01','G02','G03','G04','G05','G06','G07','G08','G09','G10','G11','G12','G13','G16'],
 'collect':['G13','G16'],
 'grade':['G12','G13','G16'],
 'report':[]
}
class Selection:
    def __init__(self,root,selected_pin,budget):
        self.root=root;self.pin=descriptor(selected_pin,2_000_000)
        self.body=parse(read_pin(root,selected_pin,2_000_000,budget))
        need(self.body['schema']=='critical_init_root_operation_selection_v1','external selected authority schema')
        need(self.body['issuer_role']=='independent_root_controller','authority outside candidate influence')
        need(self.body['canonical_id']=='PAPER-FIND-050','correct canonical assignment')
        self.budget=budget
    def admit(self,operation):
        need(operation in OPERATIONS and operation in self.body['selected_operations'],'explicit operation authority')
        if operation!='report':
            need(self.body['phase']=='SCIENTIFIC_EXECUTION','build phase cannot launch authentic work')
        qualifications=self.body['qualification_pins']
        for gate in PREREQUISITES[operation]:
            if gate not in qualifications:raise RequiredUnscorable(gate,'Missing independently selected qualification record')
            q=parse(read_pin(self.root,qualifications[gate],2_000_000,self.budget))
            need(q['gate']==gate and q['verdict']=='qualified'and q['issuer_role']=='independent_reviewer','qualified original external evidence')
            need(q['scope_digest']==self.body['scope_digest']and q['evidence'],'same full scientific scope and concrete closure evidence')
            # Every ordinary qualification body is authenticated, not inferred from a true flag.
            for evidence in q['evidence']:read_pin(self.root,evidence,self.body['evidence_cap_bytes'],self.budget)
        return self.body

