"""Real independent semantic-review request/response route, without future-hash cycles.

The pre-exposure plan binds an issuer/service and request ABI, not an impossible
receipt hash depending on future operations. The response is captured only after
that original review process. Missing or opaque review stays unqualified.
"""
from pathlib import Path
from .common import require,capture,encoded,parse,pin,sha,keys
from .registry import token
from .seals import file_identity

class SemanticService:
    def __init__(self,spec,operator_root,authority,runner,journal,budget):
        self.spec=spec;self.operator_root=Path(operator_root);self.authority=authority;self.runner=runner;self.journal=journal;self.budget=budget
        self.originals=[]
        if spec is None:self.programme=None;return
        keys(spec,('schema','issuer','programme','interpreter','seconds','output_cap','role','scope'))
        require(spec['schema']=='neural055-independent-semantic-service-v1' and spec['role']=='independent_semantic_review','closed independent service role')
        require(spec['scope']=='complete_source_operation_cell_phase_and_no_query_fit','whole semantic review scope')
        self.programme=capture(operator_root,spec['programme'],budget,1048576)
    def assess(self,cell,subject):
        if self.spec is None:return {'status':'mode_compliance_unqualified','reason':'independent semantic source/service evidence absent','receipt':None}
        start=self.budget.clock();deadline=min(self.budget.deadline,start+self.spec['seconds']);ident=token(cell)+'-semantic'
        request={'schema':'neural055-semantic-review-request-v1','cell':cell,'subject':subject,'subject_sha256':sha(encoded(subject)),
                 'prohibited':'target access, candidate execution or policy change','no_target_roles':True}
        d=self.journal.json(ident+'-REQUEST.json',request);request_path=self.journal.root/d['path']
        response=self.journal.root/(ident+'-RESPONSE.json');programme=self.journal.root/(ident+'-reviewer.py')
        self.journal.write(programme.name,self.programme)
        observation=self.runner.run(ident,[self.spec['interpreter'],'-I','-B',str(programme),'--request',str(request_path),'--response',str(response)],deadline,self.spec['output_cap'],kind='independent_review')
        self.originals.append(observation)
        self.budget.check('after original semantic review',deadline)
        # Source/issuer trust and signed actual subject are checked independently.
        p=file_identity(response,self.budget,self.spec['output_cap'])
        descriptor=dict(path=response.name,mode=oct(response.stat().st_mode&0o777),role='qualification_report',**p)
        raw=capture(response.parent,descriptor,self.budget,self.spec['output_cap'])
        receipt=self.authority.verify_bytes(raw,'semantic_operation_review',subject)
        require(receipt['issuer']==self.spec['issuer'],'preselected independent semantic issuer')
        self.budget.check('after semantic response admission',deadline)
        return {'status':'qualified','receipt':p,'original_review_process':observation.document(),'limitations':receipt['limitations']}
