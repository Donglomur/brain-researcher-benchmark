"""Portable invented graph tests. No Provider instance, subprocess, or model runs.

Fixture construction derives from the accepted cerebellar companion's invented
public generator. Five declared fake mice are arithmetic fixtures, not identities.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'candidate'
if not SOURCE.is_dir(): SOURCE = HERE
spec = importlib.util.spec_from_file_location('_executor_entry', SOURCE / 'entry.py')
entry = importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
ctx = entry.context()
c = ctx.module('controller')
worker = ctx.module('phase_worker')
contract = ctx.module('vendor_transport.contract')
CHECKS = []
def check(value, message):
    if not value: raise AssertionError(message)
    CHECKS.append(message)
def refuses(call, message):
    try: call()
    except (ValueError, KeyError): CHECKS.append(message)
    else: raise AssertionError(message)

def invented_public():
    public = {'schema':'neural030_cerebellar_public_v1','cases':[],
        'view_scope':'retrospective_processed_within_session_calibration','query_target_feedback':False}
    i = 0
    for condition, delay, count in (('one_second_expert',1.,5),('two_second_novice',2.,5),('two_second_expert',2.,6)):
        for _ in range(count):
            i += 1; sid = format(i,'032x'); bins = int(delay*10)
            case = {'session_id':sid,'condition':condition,'delay_s':delay,'train':[],'development':[],'query':[]}
            for split, orders in (('train',(1,4)),('development',(7,)),('query',(9,10))):
                for order in orders:
                    row = {'trial_id':format(100000+i*100+order,'032x'),'session_id':sid,'trial_order':order,
                        'delay_s':delay,'stage':condition,'neural_time':[k*.1 for k in range(bins)],
                        'grc':[[float(i+order+k) for k in range(bins)]],
                        'cf':[[float((k+order)%2) for k in range(bins)]],
                        'handle_time':[k*.05 for k in range(bins*2)],
                        'handle':[[float(k) for k in range(bins*2)],[float(order) for k in range(bins*2)]]}
                    if split != 'query': row['counts'] = [float((k+i+order)%3) for k in range(bins)]
                    case[split].append(row)
            public['cases'].append(case)
    return public

def write(root,name,value):
    b = value if type(value) is bytes else c.encoded(value)
    p = root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b)
    return {'path':str(p),**c.pin(b)}

def fixture(root):
    public = invented_public(); public_op = write(root,'PUBLIC.json',public)
    procedure = {'schema':'neural030_frozen_procedure_v1','task_id':'NEURAL-030',
        'source_roles':{'select':'select.py','fit':'fit.py','infer':'infer.py'},'recipes':[{'penalty':1},{'penalty':10}]}
    proc = write(root,'PROCEDURE.json',procedure)
    sources = {role:write(root,role+'.py',b'# Invented source, deliberately never executed.\npass\n') for role in c.PHASES}
    commitment = write(root,'COMMITMENT.json',{'schema':'neural030_frozen_commitment_v1','procedure':c.pin(c.encoded(procedure)),
        'sources':{k:{x:v[x] for x in ('bytes','sha256')} for k,v in sources.items()},'sealed_before_input_access':True})
    expected=[]; fixed=[]
    for case in public['cases']:
        for row in case['query']:
            n=int(row['delay_s']*10)
            expected.append({'trial_id':row['trial_id'],'session_id':case['session_id'],'bin_count':n,'counts':[1]*n})
            fixed.append({'trial_id':row['trial_id'],'counts':[2.]*n})
    binding={'verification_status':'operator_attested','binding_id':'a'*32,'evidence_sha256':'b'*64,
        'session_to_mouse':{case['session_id']:format((i%5)+200,'032x') for i,case in enumerate(public['cases'])}}
    private={'expected':write(root,'EXPECTED.json',expected),'mouse_binding':write(root,'MICE.json',binding),
             'fixed_reference':write(root,'FIXED.json',fixed)}
    limits={k:1 for k in contract.RESOURCE_KEYS}
    limits.update(producer_seconds=2,memory_bytes=134217728,cpu_nanos=1000000000,pids=32,scratch_bytes=1048576,
        max_files=32,max_directories=32,max_file_bytes=131072,max_output_bytes=1048576,manifest_bytes=65536,
        max_cli_calls=100,max_cli_bytes=1048576,inventory_bytes=65536,source_read_bytes=4194304,host_write_bytes=4194304)
    now=time.monotonic()
    request={'schema':'neural030_frozen_execution_v1','mode':'frozen_program','mismatch':False,'root':str(root/'run'),
        'public':public_op,'procedure':proc,'sources':sources,'commitment':commitment,'private_evaluation':private,
        'clock':{'origin':now-1,'deadline':now+2000},'io':{'read_bytes':16777216,'write_bytes':16777216},
        'native':{'docker_binary':'/invented/docker','docker_socket':'/invented/docker.sock','image':'sha256:'+'c'*64,
                  'transport_source':{'bytes':987,'sha256':'93df92be5b388f4b2896805c8e02f0c41f301d1c86e6b06709444c1075ade0e4'},
                  'read_bytes':33554432,'write_bytes':33554432,'image_inventory_sha256':'d'*64},
        'phase_limits':{k:copy.deepcopy(limits) for k in c.PHASES},'stdout_bytes':1024,'stderr_bytes':1024,'public_bytes_limit':1048576}
    return request,commitment

def admit(root,request,commitment,authority_edit=None):
    rp=write(root,'REQUEST.json',request)
    authority={'schema':'neural030_frozen_authority_v1','request':{k:rp[k] for k in ('bytes','sha256')},
        'source':entry.SOURCE_PIN,'authorized':True,'native_runtime_qualified':True,'input_preparation_admitted':True,
        'capacity_qualified':True,'qualification_record':{'bytes':1,'sha256':'e'*64},
        'commitment':{k:commitment[k] for k in ('bytes','sha256')}}
    if authority_edit: authority_edit(authority)
    ap=write(root,'AUTHORITY.json',authority)
    return c.preflight(rp['path'],{k:rp[k] for k in ('bytes','sha256')},ap['path'],{k:ap[k] for k in ('bytes','sha256')},entry.SOURCE_PIN)

class SpyProvider:
    """Inert stand-in only: real request/worker code, invented capture receipts."""
    constructed=0
    def __init__(self,control,quarantine,binary,socket,engine_pin,exposures,reads,writes):
        type(self).constructed+=1; self.control=control; self.quarantine=quarantine; self.exposures=dict(exposures)
        self.receipts={}; self.calls=[]; self.model_by_cell={}; self.bad_selection=False
    def execute_phase(self,request,mounts,deadline,journal):
        contract.validate_request(request,mounts,deadline)
        exposure=c.decode(Path(self.exposures[request['exposure']['sha256']]).read_bytes())
        contract.validate_exposure(exposure,request,mounts)
        for mount in mounts.values():
            for name,p in mount['files'].items():
                path=Path(mount['path'])/name if mount['kind']=='directory' else Path(mount['path'])
                check(c.pin(path.read_bytes())==p,'actual mounted body pin')
        job=c.decode(Path(mounts['/job.json']['path']).read_bytes())
        packet=c.decode(Path(mounts['/view/VIEW.json']['path']).read_bytes())
        phase=job['phase']; cell=(job['session_id'],job['arm'])
        expected={'select':{'train','development'},'fit':{'train'},'infer':{'query','required_predictions'}}[phase]
        check(set(packet)==set(c.candidate_views.ENVELOPE_FIELDS)|expected,'exact phase input fields '+phase)
        if phase!='infer': check('query' not in packet and 'required_predictions' not in packet,'query withheld from selection/fit')
        if phase=='fit': check('development' not in packet,'development never enters final fit')
        if job['arm']=='context_handle':
            for split in expected-{'required_predictions'}:
                check(all(not {'grc','cf','neural_time'}&set(row) for row in packet[split]),'context arm physically neural free')
        check(('/model' in mounts)==(phase=='infer'),'model only on inference')
        check(('/recipe.json' in mounts)==(phase!='select'),'selection can export only index before fixed recipe')
        out=self.quarantine/request['phase_id']; out.mkdir(mode=0o700)
        def inert_runner(argv,timing,outcap,errcap,**kwargs):
            check(argv==worker.candidate_argv(job),'fixed candidate ABI')
            if phase=='select':
                value={'schema':'neural030_selection_v1','session_id':job['session_id'],'arm':job['arm'],'recipe_index':1}
                if self.bad_selection: value['unpermitted_fitted_state']=[1,2]
                (out/'artifacts/SELECTION.json').write_bytes(c.encoded(value))
            elif phase=='fit':
                recipe=c.decode(Path(mounts['/recipe.json']['path']).read_bytes())
                check(recipe=={'recipe_index':1,'recipe':{'penalty':10}},'finite precommitted recipe transfer')
                model=c.encoded({'invented':True,'cell':cell,'recipe':recipe})
                (out/'artifacts/model').mkdir(); (out/'artifacts/model/state.json').write_bytes(model)
                self.model_by_cell[cell]=c.pin(model)
            else:
                check(mounts['/model']['files']=={'state.json':self.model_by_cell[cell]},'same exact captured fitted state per cell')
                response={'schema':'neural030_prediction_v1','task_id':'NEURAL-030','session_id':job['session_id'],
                    'arm':job['arm'],'predictions':[{'trial_id':row['trial_id'],'counts':[1.]*row['bin_count']} for row in packet['required_predictions']]}
                (out/'artifacts/PREDICTIONS.json').write_bytes(c.encoded(response))
            return {'stdout':b'','stderr':b''}
        raw=c.encoded(request)
        worker.execute(raw,job,out,runner=inert_runner)
        manifest=c.decode((out/'OUTPUTS.json').read_bytes())
        files={**manifest['files'],'OUTPUTS.json':c.pin((out/'OUTPUTS.json').read_bytes())}
        receipt={'status':'captured','producer_closed_before_capture':True,'all_native_resources_closed':True,
            'phase_id':request['phase_id'],'request_sha256':c.pin(raw)['sha256'],'quarantine_root':str(out),
            'output_inventory':{'complete':True,'files':files},'inert_fixture':True}
        rp=c.pin(c.encoded(receipt)); self.receipts[request['phase_id']]=(receipt,rp)
        self.calls.append((phase,job,request,mounts)); journal('inert_engineering_phase',{'phase':phase})
        return {'receipt':receipt,'receipt_pin':rp}
    def observe(self,identity,request_sha,receipt_pin,deadline):
        receipt,rp=self.receipts[identity]
        check(rp==receipt_pin and receipt['request_sha256']==request_sha,'fresh observer exact identity')
        return {'receipt':receipt,'receipt_pin':rp}

def run():
    with tempfile.TemporaryDirectory(prefix='neural030-invented-') as tmp:
        root=Path(tmp).resolve(); request,commitment=fixture(root)
        prepared=admit(root,request,commitment)
        # Explicit substitution happens only in this engineering harness. The
        # production launcher offers no backend, provider, or worker injection.
        backend=c.NativeBackend(prepared,ctx.worker_source()); backend.kind='inert_engineering'; backend.provider_class=SpyProvider
        original_read=c.read; private_paths={v['path'] for v in request['private_evaluation'].values()}; private_reads=[]
        def watched(path,*a,**kw):
            if str(path) in private_paths:
                check(backend.provider is not None and len(backend.provider.calls)==192,'private target opened only after192 complete phases')
                check((prepared['root']/'CANDIDATE_OUTPUTS.json').is_file(),'full candidate predictions committed before private score')
                private_reads.append(str(path))
            return original_read(path,*a,**kw)
        c.read=watched
        try: result=c._run_graph(prepared,backend,ctx.worker_source())
        finally: c.read=original_read
        check(result['completed_phases']==192 and result['case_arm_cells']==64,'complete192/64 support')
        check(len(private_reads)==3 and result['backend']=='inert_engineering','private three operands and explicit invented realm')
        check(result['scientific_qualification'] is False and result['semantic_model_consumption_verified'] is False,'no scientific or model-semantic promotion')
        check(result['evaluation']['mismatch_alignment_diagnostic'] is None,'no mismatch scientific claim')
        check([r[0] for r in backend.provider.calls]==list(c.PHASES)*64,'all64 ordered select-fit-infer chains')
        snapshots=[m['/procedure']['files'] for _,_,_,m in backend.provider.calls]
        check(all(x==snapshots[0] for x in snapshots),'same actual source/procedure snapshot across all192 calls')
        # Admission failures never construct a Provider or create an execution root.
        for i,(field,value) in enumerate((('mode','case_adaptive'),('mismatch',True),('stdout_bytes',True))):
            d=root/('refuse'+str(i)); d.mkdir(); r,cm=fixture(d); r[field]=value
            before=SpyProvider.constructed
            refuses(lambda:admit(d,r,cm),'preflight refusal '+field)
            check(SpyProvider.constructed==before and not Path(r['root']).exists(),'no provider/root on forbidden admission')
        for i,flag in enumerate(('authorized','native_runtime_qualified','input_preparation_admitted','capacity_qualified')):
            d=root/('authority'+str(i)); d.mkdir(); r,cm=fixture(d)
            refuses(lambda:admit(d,r,cm,lambda a:a.update({flag:False})),'unqualified '+flag)
        d=root/'clock';d.mkdir();r,cm=fixture(d);r['clock']['deadline']=time.monotonic()+1
        refuses(lambda:admit(d,r,cm),'full192 reserve cannot become a smaller fallback')
        d=root/'tamper';d.mkdir();r,cm=fixture(d);Path(r['sources']['fit']['path']).write_bytes(b'pass\n')
        refuses(lambda:admit(d,r,cm),'committed source tamper before provider')
        # Strict full capture joins reject partial closure and forged cross-case completion.
        phase,job,req,mounts=backend.provider.calls[1]
        receipt,rp=backend.provider.receipts[req['phase_id']]
        captured={'receipt':copy.deepcopy(receipt),'receipt_pin':rp,'request_pin':c.pin(c.encoded(req))}
        captured['receipt']['all_native_resources_closed']=False
        refuses(lambda:c._captured(captured,prepared,phase,req['phase_id'],job),'unclosed resources never become fitted state')
        captured['receipt']=copy.deepcopy(receipt);captured['receipt']['output_inventory']['files'].pop('STDERR.txt')
        refuses(lambda:c._captured(captured,prepared,phase,req['phase_id'],job),'partial fit base inventory refused')
        captured['receipt']=copy.deepcopy(receipt);wrong=copy.deepcopy(job);wrong['arm']='cf'
        refuses(lambda:c._captured(captured,prepared,phase,req['phase_id'],wrong),'cross-arm trusted completion refused')
        # One failed first selection exercises actual error custody, without a
        # second full192 execution or opening any private operand.
        d=root/'badselect';d.mkdir();r,cm=fixture(d);p=admit(d,r,cm)
        class BadSpy(SpyProvider):
            def __init__(self,*a,**kw): super().__init__(*a,**kw);self.bad_selection=True
        bad=c.NativeBackend(p,ctx.worker_source());bad.kind='inert_engineering';bad.provider_class=BadSpy
        refuses(lambda:c._run_graph(p,bad,ctx.worker_source()),'arbitrary selection state cannot transfer to final fit')
        failed=c.decode((p['root']/'FAILED.json').read_bytes())
        check(failed['completed_phases']==1 and failed['score_unavailable'] and not (p['root']/'RESULT.json').exists(),'failed selection blocks fit and all scoring')
        report={'schema':'neural030_frozen_executor_invented_controls_v1','assertions':len(CHECKS),
            'full_inert_graph_phases':192,'failed_inert_graph_phases':1,'native_provider_instances':0,
            'candidate_subprocesses':0,'authentic_inputs':False,'scientific_qualification':False,
            'distinct_checks':list(dict.fromkeys(CHECKS)),'full_graph_host_io_reserved':result['host_io_reserved']}
        print(json.dumps(report,sort_keys=True))

if __name__=='__main__':
    try: run()
    finally: ctx.close()
