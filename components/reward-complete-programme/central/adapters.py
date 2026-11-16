"""Genuine exact S2 preparation and lifecycle bridges, with explicit target custody."""
from pathlib import Path
import copy
from .io import need,digest,sha,encode,decode,capture
from .source import ROOT,paper,neural,configuration

def paper_full_pipeline(corpus,branch='retrospective_processed',native_exports=()):
    return paper('pipeline').build(corpus,configuration(),branch,native_exports)
def paper_improvement_bank(prepared,registry,baseline_provider,feature_provider,density_spec):
    return paper('queries').assemble(prepared,registry,baseline_provider,feature_provider,density_spec)
def paper_native_jobs():
    config=configuration()
    return paper('native').build_native_jobs(paper('pipeline').source_roles(config),config['MODEL_PROGRAMME'],
                                             {'sha256':'SOURCE_CORPUS_NOT_YET_QUALIFIED'},None,config['FIGURE_OBLIGATIONS'])
def original_paper_boundary(*args,**kwargs):
    # Exact original ten-argument worker/absence/holder/receipt protocol. Invocation
    # requires the accepted routine's separate qualified runtime admission.
    return paper('controller').original_run_unit_boundary(*args,**kwargs)

def prepare_neural(corpus,slot,source_prior=None,seed=0):
    """Filter the declared domain, then use the accepted native-clock projection."""
    p=neural('prepare');c=neural('contracts').cell(slot['cell_id'],slot['task'])
    selected=copy.deepcopy(corpus)
    selected['animals']=[a for a in selected['animals'] if a['condition'].startswith('FC-')==(slot['domain']=='aversive')]
    bank=p.prepare(selected,slot['task'],slot['view'],slot['endpoint'])
    train,query=p.split(bank,slot['held'],slot['fold_kind'])
    extras={}
    if c['input_control_contract']['training_neural_state']=='timing_destroyed':
        modified,receipt=p.destroy_session_timing(selected,sorted({r['animal'] for r in train}),seed)
        shifted=p.prepare(modified,slot['task'],slot['view'],slot['endpoint']);shift_train,_=p.split(shifted,slot['held'],slot['fold_kind'])
        extras={'timing_training':shift_train,'timing_receipt':receipt,'timing_continuous':shifted['continuous_training_source']}
    public=p.project(bank,train,query,slot['cell_id'],seed,source_prior=source_prior,**extras)
    return {'public':public,'private':query,'source_export_digest':digest(corpus),'domain_export_digest':digest(selected),
            'training_animals':sorted({r['animal'] for r in train}),
            'support':public['endpoint_support'],'source_transform':'explicit domain partition; no resampling',
            'scientific_qualification':False}

def paper_engineering(job,slot,output,public,private_factory,source_commit,bootstrap=20):
    """Stopped output first; typed reference or supported private targets second."""
    need(public.get('engineering_only') is True,'invented paper input only')
    controller=paper('controller');scoring=paper('protected_score')
    body=capture(job['program']['path'],job['program'],131072)
    declared={k:v for k,v in public.items() if k!='staged_access_files'}
    need(source_commit['before_public_input_release'] is True and source_commit['program_sha256']==sha(body)
         and source_commit['declared_public_sha256']==digest(declared)
         and source_commit['scope_sha256']==digest(paper('pipeline').full_scope(configuration())),
         'complete pre-release program/public/scope commitment')
    if 'access_contract_sha256' in public:
        need(source_commit['access_contract_sha256']==public['access_contract_sha256'],'pre-release paired access commitment')
    if slot['mode']=='improvement':
        support=job['support_precommit']
        need(source_commit['support_manifest_sha256']==support['support_manifest_sha256'] and
             digest(source_commit)==support['source_commit_sha256'] and support['before_candidate_prediction'] is True,
             'pre-prediction full support/source commitment')
        def score(private,collected):
            need(private['source_commit_sha256']==digest(source_commit) and
                 private['registered']['support_precommit']==support,'target-last support registration unchanged')
            return scoring.score_improvement_submission(private,collected,bootstrap=bootstrap)
    else:
        def score(private,collected):
            need(set(private)=={'reference'},'protected reproduction reference package')
            return scoring.score_reproduction_submission(private['reference'],collected,slot['full_panel_ids'])
    precommit_path=Path(output).parent/(Path(output).name+'.full-source.json')
    with precommit_path.open('xb') as stream:stream.write(encode(source_commit))
    return controller.engineering_run(body,public,output,private_factory,score,
                       timeout=job['timeout_seconds'],max_output=job['output_cap_bytes'])

class Numerical:
    """Original full neural Workflow, including actual prebank F report process."""
    def __init__(self,root,plan):
        self.workflow=neural('workflow').Workflow(root)
        self.workflow.begin(plan)
    def stage(self,job,public,private):return self.workflow.prepare_job(job,public,private)
    def produce(self,job,program,timeout,cap):
        w=self.workflow;state=w._state()['jobs'][job]
        if neural('contracts').cell(state['cell_id'],state['task'])['mode']=='I':w.commit_interactive_program(job,program)
        folder=w.root/'jobs'/job
        receipt=neural('workflow').run_engineering_producer(program,folder/'public/input.json',folder/'outputs',timeout,cap)
        return w.collect(job,receipt)
    def close_and_grade(self):
        need(self.workflow.close()=='closed','all producers must close and seal before any grade')
        return self.workflow.grade_once()
    def finish(self,interactive_reports):return self.workflow.finish(interactive_reports)

class PacketBank:
    """Same bounded policy grammar for F and I; rubric opened only after sealing."""
    def __init__(self,root,task,cell_id,bank_schema_id,prebank_policy=None):
        self.root=Path(root);need(not self.root.exists(),'fresh packet namespace');self.root.mkdir(parents=True)
        self.task=task;self.cell_id=cell_id;self.bank_schema_id=bank_schema_id;self.cell=neural('contracts').cell(cell_id,task)
        need(self.cell['tier']=='P','packet tier');self.state='prebank';self.sealed={};self.packets={}
        if self.cell['mode']=='F':
            need(prebank_policy is not None,'F policy before packet bank')
            neural('packet_bank').commit_F_policy(self.root/'F_policy.json',prebank_policy,cell_id,task,bank_schema_id)
            self.f_commit_sha256=sha(capture(self.root/'F_policy.json'))
        else:need(prebank_policy is None,'I policy is committed after its packet')
    def release(self,packets):
        need(self.state=='prebank' and packets,'one packet bank release')
        for p in packets:
            neural('packet').validate_packet(p,self.cell,self.task)
            need(p['bank_schema_id']==self.bank_schema_id and p['packet_id'] not in self.packets,'packet bank/unique identity')
            self.packets[p['packet_id']]=copy.deepcopy(p)
        (self.root/'packets.json').write_bytes(encode(packets));self.packet_digest=digest(packets);self.state='released'
    def commit_I(self,packet_id,raw):
        need(self.state=='released' and self.cell['mode']=='I' and packet_id not in self.sealed,'one I policy after packet')
        policy=neural('packet').validate_policy(raw,self.cell,self.task,self.packets[packet_id]);self.sealed[packet_id]=encode(policy)
        (self.root/(sha(packet_id.encode())+'.policy.json')).write_bytes(self.sealed[packet_id])
    def grade_once(self,rubric_factory):
        need(self.state=='released','packet grade once')
        need(digest(decode(capture(self.root/'packets.json')))==self.packet_digest,'packet bytes unchanged')
        if self.cell['mode']=='I':need(set(self.sealed)==set(self.packets),'all I policies sealed before rubric')
        else:need(sha(capture(self.root/'F_policy.json'))==self.f_commit_sha256,'F prebank policy bytes changed')
        self.state='consumed';(self.root/'CONSUMED.json').write_bytes(encode({'rubric_opened_after_policy_seal':True}))
        rubrics=rubric_factory();need(set(rubrics)==set(self.packets),'full protected rubric bank')
        if self.cell['mode']=='F':
            need(sha(capture(self.root/'F_policy.json'))==self.f_commit_sha256,'F policy changed during rubric opening')
            ordered=list(self.packets)
            result=neural('packet_bank').evaluate_committed(self.root/'F_policy.json',[self.packets[k] for k in ordered],[rubrics[k] for k in ordered])
        else:
            result=[neural('packet').evaluate(self.sealed[k],p,self.cell_id,self.task,rubrics[k]) for k,p in self.packets.items()]
        (self.root/'RESULT.json').write_bytes(encode(result));self.state='complete';return result
