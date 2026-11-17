from .deadline import boundary
from .custody import Custody,custody,failure_notice,observation,reader_details
"""Collector admission binds process-owned outputs to their complete source/role roster."""
import math
from .errors import require
from .objects import Reader,canonical,decode,digest,fields,finite_rows,check_pin,unique_paths
from .process import accounting_complete


KINDS={'executable','method_plan','corpus','preprocessing','architecture','state','loss_trace','schedule_trace','prediction','representation','soup','claim','resource','scope','inert_marker'}
REQUIRED={
 'executable':('kind','source_id','entrypoint','interpreter','environment','dependencies','build_request'),
 'method_plan':('families','obligations','variant_graph','search_policy','budget_allocation','reuse_policy','confirmatory_manifest','scientific_profiles'),
 'corpus':('sources','recordings','exclusions','preprocessing','rights','producer_receipts'),
 'preprocessing':('raw_support','epoch_support','unit_projection','clock_mapping','fitted_dependencies','recipe','state','exclusions'),
 'architecture':('configuration','parameter_schema','parameter_counts','trained_mask','geometry','patches','position','mask','objective','schedule'),
 'state':('format','tensor_index','configuration','trained_mask','fitted_dependencies','initial_state','search_receipts','selected_trial','selection_criterion','objective','schedule'),
 'loss_trace':('objective_profile','batch_reduction','components','alpha','lambda','phase','secondary_enabled','backpropagated_scalar','mask_identity','optimizer_updates','producer','rank','accumulation','support'),
 'schedule_trace':('profile','steps','resume','rank_exposure','producer'),
 'prediction':('scores','representation','events','classes','state','support','query_policy'),
 'representation':('features','events','state','fitted_dependencies'),
 'soup':('state','members','weights','tensor_schema','buffer_policy','member_metrics','selection_policy'),
 'claim':('obligations','hypotheses','methods','citations','limitations','results'),
 'resource':('attempts','gross','amortized','failed_costs','unavailable_measurements'),
 'scope':('families','obligations','cases','scientific_products','missing','gates'),
 'inert_marker':('marker',)}


def passive_state(reader,details):
    require(details['format']=='safetensors','states must be passive safe tensors')
    index=details['tensor_index'];require(index,'empty state index')
    # Validate each safe-tensor container header and every disjoint tensor range.
    for item in index:
        raw=reader.read(item['object']);require(len(raw)>=8,'short state container')
        n=int.from_bytes(raw[:8],'little');require(0<n<=16*1024*1024 and 8+n<=len(raw),'state header cap')
        header=decode(raw[8:8+n]);require(type(header) is dict,'state tensor dictionary');ranges=[]
        sizes={'F64':8,'F32':4,'F16':2,'BF16':2,'I64':8,'I32':4,'I16':2,'I8':1,'U8':1,'BOOL':1}
        for name,t in header.items():
            if name=='__metadata__':
                require(type(t) is dict and all(type(k) is type(v) is str for k,v in t.items()),'safe metadata');continue
            fields(t,('dtype','shape','data_offsets'))
            require(t['dtype'] in sizes and all(type(d) is int and d>=0 for d in t['shape']),'state tensor type')
            a,b=t['data_offsets'];require(type(a) is type(b) is int and 0<=a<=b<=len(raw)-8-n,'tensor range')
            require(b-a==math.prod(t['shape'])*sizes[t['dtype']],'state tensor bytes');ranges.append((a,b))
        cursor=0
        for a,b in sorted(ranges):require(a==cursor,'overlapping or unexplained state bytes');cursor=b
        require(cursor==len(raw)-8-n and ranges,'state byte census')


class Collector:
    def __init__(self,required,ledger,mode,guard=None):
        self.custody=Custody();self.guard=guard;self.unresolved={}
        self.required=required;self.ledger=ledger;self.mode=mode;self.products={};self.terminal={};self.current_collection=None;self.collections={}

    def begin_boundary(self,phase):
        if phase=='Collector.collect':self.current_collection=None

    def release_boundary_success(self,phase):
        if phase=='Collector.collect':self.current_collection=None

    def retain_boundary_failure(self,exc,phase):
        if phase!='Collector.collect' or self.current_collection is None:return
        self.reject_collection(self.current_collection['job']['id'])

    def reject_collection(self,job_id):
        """Guard-free failure cleanup of this owned transaction, never new work.

        The record is retained through the outer Controller boundary. Eligibility
        is revoked before fallible reporting or terminal bookkeeping, including
        artifacts changed before Exposure's own closing journal failed.
        """
        current=self.collections.get(job_id)
        if current is None:return
        job=current['job'];receipt=current['receipt'];exposure=current['exposure']
        for identity in current['artifact_ids']:
            artifact=exposure.artifacts.get(identity)
            if artifact is not None:artifact['eligible']=False
        current['rejected']=True
        # Preserve earlier successful collections and their reusable ancestry.
        for name in job['expected_outputs']:
            item=self.products.get(name)
            if item is not None and item.get('producer_job')==job['id']:self.products.pop(name)
        self.terminal.pop(job['id'],None)
        if receipt.get('scope_quiescent',False) and accounting_complete(receipt):
            self.terminal[job['id']]={'status':'failed','receipt':receipt,'collection_failure':True}
        else:self.unresolved[job['id']]={'job':job,'receipt':receipt}

    def fail(self,job,receipt):
        require(job['id'] not in self.terminal,'job already terminal')
        if not receipt.get('scope_quiescent',False) or not accounting_complete(receipt):
            self.unresolved[job['id']]={'job':job,'receipt':receipt}
            try:require(False,'unresolved original process scope or resource accounting is not a terminal bank slot')
            except BaseException as exc:
                failure_notice(self,exc,'Collector.fail:unresolved','collection_unresolved_scope',lambda:self.unresolved[job['id']]);raise
        require(receipt['exit_code'] is not None or receipt['pid'] is None,'unobserved child completion is not a terminal bank slot')
        self.terminal[job['id']]={'status':'failed','receipt':receipt}
        self.ledger.append('collection_failed',{'job':job['id'],'receipt':receipt,'required_outputs':job['expected_outputs']})

    @boundary
    def collect(self,job,receipt,output_root,exposure,bound_specs=None):
        require(job['id'] not in self.terminal,'job already terminal')
        require(job['id'] not in self.collections,'collection transaction replay')
        current={'job':job,'receipt':receipt,'exposure':exposure,'artifact_ids':[],'rejected':False}
        self.collections[job['id']]=current;self.current_collection=current
        require(receipt.get('scope_quiescent',False),'process scope not observed quiescent')
        require(accounting_complete(receipt),'original process resources not reconciled')
        require(receipt['natural_completion'] and receipt['exit_code']==0 and receipt['failure_reason'] is None,'failed process cannot produce completed outputs')
        require(receipt['stdin_bytes_requested']==receipt['stdin_bytes_delivered'],'incomplete original input delivery')
        require(receipt['source_id']==job['source'],'original source mismatch')
        request=receipt['request_body']
        require(digest(canonical(request))==receipt['request']['sha256'],'original request bytes')
        require(all(request[k]==job[j] for k,j in (('job_id','id'),('programme_id','programme'),('domain','domain'),('context','context'),('stage','stage'),('operation','operation'),('payload','payload'),('source_id','source'))),'original request semantic job identity')
        rows={r['path']:r for r in receipt['outputs']};require('products.json' in rows,'missing actual product index')
        reader=Reader(output_root,sum(r['bytes']+1 for r in receipt['outputs'])*2+1,len(receipt['outputs'])*2+1,guard=self.guard)
        with observation(self,'Collector.collect',{'job':job['id'],'reader':None},'collection_original_read_cost',lambda d:d.update(reader=reader_details(reader),terminal_admitted=job['id'] in self.terminal)):
            index=reader.json(rows['products.json']);fields(index,('schema','job_id','products'))
            require(index['schema']=='reve-process-product-index-v1' and index['job_id']==job['id'],'product index request identity')
            declared={r['id']:r for r in index['products']}
            require(len(declared)==len(index['products']) and set(declared)==set(job['expected_outputs']),'exact complete output census')
            admitted={};used={'products.json'}
            for identifier,item in declared.items():
                if self.guard:self.guard()
                fields(item,('id','kind','objects','details','source','request','parent_states','objective_profile','exposure_context'))
                expected=(bound_specs or self.required)[identifier]
                require(item['kind'] in KINDS and item['kind']==expected['kind'],'product type')
                require(item['kind']!='inert_marker' or self.mode=='inert-control','inert output cannot qualify science')
                require(item['source']==job['source'] and item['request']==receipt['request']['sha256'] and item['exposure_context']==job['context'],'product source/request/context')
                require(item['parent_states']==expected['parent_states'] and item['objective_profile']==expected['objective_profile'],'state/objective binding')
                fields(item['details'],REQUIRED[item['kind']]);unique_paths(item['objects'])
                from .method_lineage import collect_method_lineage
                method_lineage=collect_method_lineage(job,request,item,expected,self.products)
                for obj in item['objects']:
                    require(obj['path'] in rows and rows[obj['path']]==obj,'unclosed object')
                    require(obj['path'] not in used,'multiply owned output');used.add(obj['path']);reader.read(obj)
                if item['kind']=='executable':
                    d=item['details'];require(d['kind']=='registered_interpreted_entrypoint','unqualified executable ABI')
                    require(d['source_id']==job['source'] and d['environment']==receipt['environment'] and d['build_request']==receipt['request']['sha256'],'actual build source/request/environment')
                    require({k:d[k] for k in ('entrypoint','interpreter','dependencies')}==expected['executable'],'build does not match registered executable/dependencies')
                    require(not item['objects'],'registered source is separate from passive output objects')
                elif item['kind']=='method_plan':
                    d=item['details'];require(set(d['families'])=={f'RV-{i:02d}' for i in range(1,14)} and set(d['obligations'])=={f'O{i:02d}' for i in range(1,55)},'complete method plan')
                    require(d['variant_graph'] and d['search_policy'] and d['budget_allocation'] and d['reuse_policy'],'incomplete learner plan')
                    require(d['confirmatory_manifest']==expected['confirmatory_manifest'] and d['scientific_profiles']==expected['scientific_profiles'],'plan cannot change selected scientific purposes')
                elif item['kind']=='loss_trace':
                    d=item['details'];require(d['objective_profile']==item['objective_profile'] and d['phase'] in ('train','evaluate'),'loss intent binding')
                    require(d['producer']==receipt['request']['sha256'] and d['components'],'original loss producer')
                    require(d['alpha']>0 and d['lambda']>=0 and d['batch_reduction'] in ('pooled_mask_v1','equal_example'),'explicit loss scaling')
                    require({x['name'] for x in d['components']}==({'primary','secondary'} if d['secondary_enabled'] and d['phase']=='train' else {'primary'}),'absent secondary is not measured zero')
                    require(len({x['name'] for x in d['components']})==len(d['components']),'duplicate reconstruction component')
                    masks=[]
                    for component in d['components']:
                        fields(component,('name','examples'));require(component['examples'],'empty reconstruction batch')
                        for example in component['examples']:
                            fields(example,('id','prediction','mask','target'));array=example['prediction'];fields(array,('object','shape','dtype'))
                            require(array['object'] in item['objects'] and array['dtype'] in ('<f4','<f8'),'reconstruction object ownership')
                            require(array['shape']==[len(example['mask']),200] and example['mask'] and len(set(example['mask']))==len(example['mask']) and all(type(x) is int and x>=0 for x in example['mask']),'masked array support')
                            from .objects import npy_header
                            npy_header(reader.read(array['object']),array);masks.append({'component':component['name'],'example':example['id'],'mask':example['mask'],'target':example['target']})
                    require(d['mask_identity']==digest(canonical(masks)),'complete actual mask identity')
                elif item['kind']=='schedule_trace':
                    d=item['details'];require(d['producer']==receipt['request']['sha256'] and d['steps'] in item['objects'],'original schedule trace source')
                elif item['kind']=='prediction':
                    d=item['details'];require(d['events']==expected['events'] and d['classes']==expected['classes'],'prediction event/class order')
                    require(d['state']==expected['state'] and d['support']==expected['support'] and d['query_policy']==expected['query_policy'],'prediction state/support')
                    require(d['representation'] in ('probabilities','raw_logits','hard_ncm'),'prediction representation')
                    if expected['purpose'] in ('I-person','I-person-montage'):require(d['representation'] in ('probabilities','hard_ncm'),'protected purpose requires declared probabilities; native logits remain distinct')
                    require(d['scores']['object'] in item['objects'],'score object not owned')
                    raw=reader.read(d['scores']['object']);values=finite_rows(raw,[len(d['events']),len(d['classes'])],d['scores']['dtype'])
                    if d['representation']!='raw_logits':
                        for start in range(0,len(values),len(d['classes'])):
                            row=values[start:start+len(d['classes'])]
                            require(all(0<=v<=1 for v in row) and abs(sum(row)-1)<=1e-6,'probability simplex')
                            if d['representation']=='hard_ncm':require(sum(v==1 for v in row)==1 and all(v in (0,1) for v in row),'NCM one hot')
                elif item['kind']=='state':
                    if expected.get('scientific_cases') is not None:
                        require(item['details']['configuration'].get('scientific_cases')==expected['scientific_cases'],'actual state immutable scientific question lineage')
                    require(all(x['object'] in item['objects'] for x in item['details']['tensor_index']),'state object ownership')
                    passive_state(reader,item['details'])
                elif item['kind']=='soup':
                    d=item['details'];require(len(d['members'])==len(d['weights'])>=5 and abs(sum(d['weights'])-1)<1e-12,'complete soup members/weights')
                    require(len(set(d['members']))==len(d['members']),'duplicate soup member')
                    require(d['members']==expected['soup_members'] and d['state']==expected['soup_state'],'actual member and soup state bindings')
                    require(len(d['members'])==expected['member_count'] and all(math.isfinite(x) and x>=0 for x in d['weights']),'complete selected soup including TUEV/Small')
                elif item['kind']=='claim':require(set(item['details']['obligations'])==set(expected['obligations']),'claim coverage')
                identity=digest(canonical(item))
                require(identity not in exposure.artifacts,'artifact identity already registered')
                # Own the identity before register_artifact can mutate Exposure
                # and then fail in its journal, observation or boundary guard.
                current['artifact_ids'].append(identity)
                exposure.register_artifact(identity,job['context'],expected['ancestry'],'product',receipt['attempt_id'])
                admitted[identifier]={'identity':identity,'product':item,'original_process':receipt,'output_root':str(output_root),'qualified':False,'producer_job':job['id'],'producer_stage':job['stage'],'method_lineage':method_lineage,'producer_job_identity':digest(canonical(job)),'producer_programme':job['programme'],'producer_domain':job['domain'],'producer_run':job['run'],'producer_request':receipt['request']}
            require(used==set(rows),'unexpected process output files')
            require(not set(admitted)&set(self.products),'product replay')
            exposure.close_products([v['identity'] for v in admitted.values()])
            self.products.update(admitted);self.terminal[job['id']]={'status':'closed','receipt':receipt}
            self.ledger.append('collection_closed',{'job':job['id'],'products':{k:v['identity'] for k,v in admitted.items()},'receipt':receipt,'reader_cost':{'bytes':reader.bytes,'files':reader.files}})
            return admitted


    @boundary
    def barrier(self,all_jobs,required_ids=None):
        require(not self.unresolved,'unresolved original process scope blocks barrier')
        require(all(row.get('receipt') is None or row['receipt'].get('schema')!='reve-original-process-receipt-v1' or accounting_complete(row['receipt']) for row in self.terminal.values()),'unresolved original resource accounting blocks barrier')
        require(set(self.terminal)=={j['id'] for j in all_jobs},'all original jobs must close before targets')
        missing=sorted((set(self.required) if required_ids is None else set(required_ids))-set(self.products))
        result={'schema':'reve-global-closed-bank-v1','products':{k:v['identity'] for k,v in self.products.items()},'missing_products':missing,
                'jobs':{k:v['status'] for k,v in self.terminal.items()},'complete':not missing,'science_qualified':False}
        result['receipt']=self.ledger.append('global_barrier',result)
        return result
