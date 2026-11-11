"""Original operator/root authentication before any scientific or participant body."""
import base64,time
from pathlib import Path
from .domain import fields,need,sha,encoded,parse,pin,registry,uint,digest,limits,exposure
from .storage import read,source_closure
from .runtime.resource_policy import VERSION,EXCLUDED

GATES=('taxonomy_source','taxonomy_alignment','taxonomy_rights','original_image_alignment','image_rights','epoch_identity','time_coverage','repetition_identity','sequence_overlap_disclosure','mvnn_scope_disclosure','source_closure','F_semantics','I_semantics','source_freeze','host_memory','local_daemon','cgroup_v2','native_cleanup','output_capture','protected_target_custody','budget_capacity','complete_control_suite','independent_whole_review','scientific_reference_parity')

class Authority:
    def __init__(self,root_bytes,expected_digest,qualification_bytes,public_key_bytes,budget):
        self.root_bytes=root_bytes;self.digest=digest(expected_digest);self.budget=budget;self.attempts=[];self.programmes={}
        need(sha(root_bytes)==self.digest,'externally selected root bytes')
        self.root=parse(root_bytes)
        self.canonical_root=encoded(self.root)
        fields(self.root,('schema','source_root','source_members','asset_root','assets','native_profile','resource_policy','limits','cell_limits','fit_seconds','infer_seconds','programmes','exposure','qualification_subject'))
        need(self.root['schema']=='neural057-original-campaign-v1','no donor/legacy root fallback')
        from .runtime.budget import Budget
        need(type(budget) is Budget and encoded(limits(self.root['limits']))==encoded(budget.global_limits),'same actual original budget/counters, no substituted envelope')
        limits(self.root['cell_limits']);exposure(self.root['exposure'])
        q=parse(qualification_bytes);fields(q,('schema','subject','gates','signature'))
        need(q['schema']=='neural057-original-qualification-v1' and q['subject']==self.root['qualification_subject'],'task-specific source/native/data qualification')
        subject=q['subject'];fields(subject,('root_sha256_without_qualification_subject','source_sha256','asset_manifest_sha256','programmes_sha256','resource_policy_sha256','exposure_sha256'))
        body={k:v for k,v in self.root.items() if k!='qualification_subject'}
        need(subject=={'root_sha256_without_qualification_subject':sha(encoded(body)),'source_sha256':sha(encoded(self.root['source_members'])),'asset_manifest_sha256':sha(encoded(self.root['assets'])),'programmes_sha256':sha(encoded(self.root['programmes'])),'resource_policy_sha256':sha(encoded(self.root['resource_policy'])),'exposure_sha256':sha(encoded(self.root['exposure']))},'complete fixed qualification subject inverse')
        need(type(q['gates']) is dict and set(q['gates'])==set(GATES) and all(x=='qualified' for x in q['gates'].values()),'all current prerequisite gates independently qualified')
        need(type(public_key_bytes) is bytes and len(public_key_bytes)==32,'externally trusted original issuer public key')
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        unsigned={k:v for k,v in q.items() if k!='signature'}
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(base64.b64decode(q['signature'],validate=True),encoded(unsigned))
        policy=self.root['resource_policy'];fields(policy,('schema','expected_unobserved_native_quantities','native_io_hard_cap','services','interpretation'))
        need(policy['schema']==VERSION and policy['expected_unobserved_native_quantities']==list(EXCLUDED) and policy['native_io_hard_cap'] is None and policy['services']=='none','explicit proposed measured scope; total native-I/O cap is unsupported')
        identity={'version':VERSION,'bytes':len(encoded(policy)),'sha256':sha(encoded(policy))};budget.bind_resource_policy(identity,policy)
        need(self.root['native_profile']['resource_policy']==identity,'one original policy across host and child')
        profile=self.root['native_profile']
        fields(profile,('schema','resource_policy','services','image','pull','network','daemon_id','docker_host','docker_binary','docker_binary_pin','closure_reserve_seconds','memory_bytes','host_memory_bytes','pids','scratch_bytes','delegated_cgroup_root'))
        need(profile['services']=='none','closed no-service runtime')
        pin(profile['docker_binary_pin']);need(Path(profile['docker_binary']).is_absolute() and profile['docker_binary_pin']['path']==Path(profile['docker_binary']).name,'exact selected executable mapping')
        for k in ('fit_seconds','infer_seconds'):uint(self.root[k],True)
        for name in ('source_root','asset_root'):need(Path(self.root[name]).is_absolute(),'literal independently selected root')
        self.sources=source_closure(Path(self.root['source_root']),self.root['source_members'],budget)
        need(set(self.root['programmes'])=={'F','I'},'both original pre-exposure programmes')
        for mode,d in self.root['programmes'].items():
            fields(d,('source','policy'));pin(d['source'])
            p=d['policy'];fields(p,('mode','fit_scope','inference_scope','services','same_person_cross_cell_state'))
            need(p=={'mode':mode,'fit_scope':'other_nine_people_training_concepts_only','inference_scope':'same_cell_immutable_fit_state_only','services':'none','same_person_cross_cell_state':False},'closed F/I exposure contract')
            self.programmes[mode]=read(self.root['asset_root'],d['source'],budget,131072)
        self.qualified=True

    def validate_live(self):
        need(self.qualified and sha(self.root_bytes)==self.digest and encoded(self.root)==self.canonical_root,'same original root/authority, exact typed canonical value')
        self.budget.admit('original N057 authority')

    def retain(self,attempt):
        self.validate_live();need(not any(x is attempt for x in self.attempts),'one actual attempt registration');self.attempts.append(attempt)

    def validate_sources(self):
        self.validate_live()
        current=source_closure(Path(self.root['source_root']),self.root['source_members'],self.budget)
        need(current==self.sources,'same complete original source closure before phase and after all phases')
