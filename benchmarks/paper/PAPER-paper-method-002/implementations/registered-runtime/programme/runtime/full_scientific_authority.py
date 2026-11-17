"""Explicitly bounded full-route operator receipt; legacy authority is unchanged."""
from .strict import Root,require,relative,integer
from .authority import Authority,REQUIRED_CAPABILITIES

class FullAuthority(Authority):
    def __init__(self,custody,receipt_path,expected_pin,limits,*,clock):
        require(type(custody)is Root,'original protected operator root')
        require(set(limits)=={'receipt_bytes','evidence_member_bytes','evidence_total_bytes'},'explicit full authority metadata bounds')
        for name,value in limits.items():integer(value,name,1)
        self.root=custody;self.receipt=custody.json(receipt_path,limits['receipt_bytes'],pin=expected_pin,clock=clock)
        r=self.receipt
        require(r.get('schema')=='jaxley_full_scientific_operator_qualification_v1','distinct full scientific receipt schema')
        require(r.get('task_id')=='PAPER-paper-method-002'and r.get('mode')=='authentic','genuine protected qualification required')
        require(set(r.get('capabilities',{}))==REQUIRED_CAPABILITIES,'complete external capability roster')
        require(r.get('source_program_sha256')and r.get('scientific_profile_sha256'),'full source/profile identity')
        require(r.get('unresolved_required_gates')==[],'all actual qualification remains external')
        total=0
        for key,row in r['capabilities'].items():
            require(type(row)is dict and row.get('decision')=='accepted','unaccepted capability '+key)
            require(type(row.get('evidence'))is list and row['evidence'],'original external evidence')
            for evidence in row['evidence']:
                relative(evidence['path']);n=integer(evidence['bytes'],'evidence bytes')
                require(n<=limits['evidence_member_bytes'],'evidence member bound');total+=n
                require(total<=limits['evidence_total_bytes'],'whole evidence bound')
                custody.authenticate(evidence['path'],evidence,cap=n,clock=clock)
