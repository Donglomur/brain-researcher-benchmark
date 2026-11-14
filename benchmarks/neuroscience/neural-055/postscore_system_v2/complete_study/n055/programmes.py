"""Pre-exposure source commitments and full-cell isolated programme staging."""
import os
from pathlib import Path
from .common import require,parse,encoded,sha,keys,capture,stamp
from .registry import token
from .participant_contract import interface_identity

class Programmes:
    def __init__(self,plan,source,operator_root,authority,journal,budget):
        self.plan=plan;self.source=source;self.budget=budget;self.journal=journal
        # Public documents are source-owned and available in the portable source
        # before submission. Their exact pins enter the independent commitment.
        self.public_interface=interface_identity(source)
        self.captured=source.submitted(operator_root,plan['submission'])
        self.policy=parse(self.captured['common_policy']['body'])
        keys(self.policy,('schema','F','I','common_dependencies','offline_costs','exposure_declaration','participant_interface','resource_policy'))
        require(self.policy['resource_policy']==budget.resource_policy,'same pre-exposure resource definition')
        require(self.policy['schema']=='neural055-complete-preexposure-policies-v3','explicit versioned full policies')
        require(self.policy['participant_interface']==self.public_interface,'same complete participant ABI reviewed before commitment')
        for mode in ('F','I'):
            p=self.policy[mode]
            keys(p,('source_sha256','initializer','dependencies','services','inference_restrictions'))
            require(p['source_sha256']==self.captured[mode]['sha256'],'same exact condition source')
            require(p['initializer']=='fresh_full_cell_and_phase_from_permitted_seal','full-cell initialization')
            require(type(p['dependencies'])is list and type(p['services'])is list,'full reviewed capability graph')
        self.subject={'schema':'neural055-preexposure-method-subject-v1','runtime_source':source.identity,'resource_policy':budget.resource_policy,
                      'submitted':{k:v['sha256'] for k,v in self.captured.items()},
                      'policy':self.policy,'mode_permissions':plan['mode_permissions'],'participant_interface':self.public_interface,
                      'actual_service_registry':plan['native_profile']['model_providers'],
                      'actual_model_token_limits':plan['native_profile']['model_token_limits'],
                      'complete_registry':sha(encoded(plan['cells'])),'exposure':plan['exposure_declaration']}
        self.review=authority.verify(plan['pre_exposure_review'],'source_method_review',self.subject)
        self.base=journal.root/'programmes';self.base.mkdir(mode=0o700);self.paths={};self.identities={}
        for mode in ('F','I'):
            path=self.base/(mode+'.py');journal.write(str(path.relative_to(journal.root)),self.captured[mode]['body'])
            os.chmod(path,0o444);self.paths[mode]=path;self.identities[mode]=stamp(path.lstat())
        self.receipt=journal.json('PRE_EXPOSURE_SOURCE.json',self.subject)
        self.exposures=[];self.closed_contexts=[];self.active=None
        budget.check('after complete pre-exposure commitment')
    def enter(self,cell,phase,seal=None):
        require(self.active is None,'fresh no-sibling mutable service context')
        mode=cell['mode'];require(mode in self.paths and phase in ('FIT','INFER'),'exact participant phase')
        path=self.paths[mode]
        require(stamp(path.lstat())==self.identities[mode],'unchanged global submitted programme')
        body=capture(path.parent,dict(path=path.name,bytes=len(self.captured[mode]['body']),
                    sha256=self.captured[mode]['sha256'],mode='0o444',role='precommitted_participant_source'),
                    self.budget,131072)
        require(body==self.captured[mode]['body'],'same full submitted bytes')
        if phase=='INFER':require(seal is not None and seal.cell==cell,'same-cell original seal only')
        self.active={'resource_policy':self.budget.resource_policy,'cell':dict(cell),'phase':phase,'source':sha(body),'context_id':token(dict(cell,phase=phase)),
                     'rehydration':None if seal is None else seal.document['model'],
                     'policy':self.policy[mode],'other_cell_state':False}
        self.exposures.append(dict(self.active));self.budget.check('before first permitted cell exposure')
        return path,dict(self.active)
    def retire(self,cell,phase):
        require(self.active is not None and self.active['cell']==cell and self.active['phase']==phase,'retire original cell context')
        self.closed_contexts.append(dict(self.active));self.active=None
        self.budget.check('after original service/context retirement')
    def unchanged(self):
        require(self.active is None,'no mutable participant context remains')
        for mode,path in self.paths.items():require(stamp(path.lstat())==self.identities[mode],'global source unchanged')
        return self.subject

