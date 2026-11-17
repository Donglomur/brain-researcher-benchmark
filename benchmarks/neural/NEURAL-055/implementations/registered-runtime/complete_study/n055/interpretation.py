"""Post-score original operator handoff, not pre-existing interpretation data.

The immutable plan selects services/policies/resources, never completed reports.
The trusted operator later supplies exact newly produced original records through
a fixed finite mailbox. Independent signed evidence binds each current subject.
Only source-owned aggregate projections are exposed; targets stay in Protected.
"""
import os,time
from pathlib import Path
from .common import require,keys,integer,finite,relative,descriptor,capture,parse,encoded,sha,pin,FailureCarrier,diagnostic_type
from .reporting import RUBRIC,METRICS,interpretation as score_interpretation

COMPARISONS=('C01','C02','C03','C04')
RESOURCES=('cpu_seconds','read_bytes','write_bytes','files','stream_bytes','model_calls')
POLICY='same_current_blinded_aggregate_no_prediction_feedback_no_retry_v1'

def admit_policy(value):
    if value is None:return
    keys(value,('schema','author','reviewers','adjudicator','rubric','policy','clock_domain','limits','closure_reserve_seconds','control_directory','response_bytes','result_bytes','memory_bytes','maximum_input_tokens','maximum_output_tokens'))
    require(value['schema']=='neural055-postscore-interpretation-policy-v1' and value['policy']==POLICY,'post-score policy, not a completed report descriptor')
    require(type(value['clock_domain'])is str and 0<len(value['clock_domain'])<=512,'prequalified common original monotonic clock domain')
    require(value['rubric']=={'dimensions':list(RUBRIC),'anchors':{'0':'absent_or_incorrect','1':'partly_correct_material_omission','2':'complete_and_supported'}},'original six ordinal rubric dimensions')
    require(type(value['reviewers'])is list and len(value['reviewers'])==2,'two precommitted independent reviewers')
    services=[value['author'],*value['reviewers'],value['adjudicator']]
    for service in services:
        keys(service,('identity','source','qualification'))
        require(type(service['identity'])is str and service['identity'].strip(),'actual service/reviewer identity')
        for d in (service['source'],service['qualification']):
            descriptor(d);integer(d['bytes'],1)
    require(len({s['identity']for s in services})==4,'distinct author, two reviewers and adjudicator')
    keys(value['limits'],('wall_seconds',*RESOURCES))
    finite(value['limits']['wall_seconds'],True);finite(value['limits']['cpu_seconds'],True)
    for k in RESOURCES[1:]:integer(value['limits'][k],1)
    finite(value['closure_reserve_seconds'],True)
    require(value['closure_reserve_seconds']<value['limits']['wall_seconds'],'reserve within original selected interpretation span')
    for key in ('memory_bytes','maximum_input_tokens','maximum_output_tokens'):integer(value[key],1)
    relative(value['control_directory'])
    require(value['response_bytes']==1048576 and value['result_bytes']==16777216,'fixed bounded ordinary handoff bodies')

def safe_aggregate(paired,source,campaign,numerical):
    """Closed projection: no cell records, query IDs, target maps or raw arrays."""
    require([c['id']for c in paired['contrasts']]==['C%02d'%i for i in range(1,33)],'whole32 numerical contrast support')
    rows=[]
    allowed=('id','status','reason','paired','joint_conditional_band','exploratory_secondary')
    for c in paired['contrasts']:
        row={k:c[k]for k in allowed if k in c}
        if 'qualification_dependencies'in c:
            q=c['qualification_dependencies'];row['qualification_dependencies']={k:v for k,v in q.items()if k!='expected_cell_keys'}
            row['qualification_dependencies']['required_cell_count']=len(q['expected_cell_keys'])
            row['qualified_joint_family_disposition']=c['qualified_joint_family_disposition']
        rows.append(row)
    conditions=[]
    for row in paired['conditions']:
        require(len(row['key'])==4 and set(row['metrics'])==set(METRICS),'complete aggregate metrics only')
        key=list(row['key']);key[0]=key[0]if key[0]in('R0','R1','R2','R3')else'CANDIDATE'
        conditions.append({'condition':key,'metrics':row['metrics']})
    unavailable=[]
    for row in paired['unavailable_conditions']:
        key=list(row['key']);key[0]=key[0]if key[0]in('R0','R1','R2','R3')else'CANDIDATE'
        statuses={}
        for cell in row['missing']:statuses[cell['status']]=statuses.get(cell['status'],0)+1
        unavailable.append({'condition':key,'required_cells':row['required_cells'],'missing_status_counts':statuses,'status':row['status']})
    return {'schema':'neural055-current-safe-interpretation-aggregate-v1','source':source,'campaign':campaign,
            'numerical_report_identity':{k:numerical[k]for k in('bytes','sha256')},'conditions':conditions,'unavailable_conditions':unavailable,'contrasts':rows,
            'resource_policy':paired.get('resource_policy'),'resource_interpretation':paired.get('resource_interpretation'),
            'schedule_draws':paired['schedule_draws'],'replicate_aggregation':paired['replicate_aggregation'],
            'comparison_ids':list(COMPARISONS),'limitations':{'one_public_dataset':True,'whole_paper_noncoverage':True,
            'population_pvalues':None,'open_scientific_gates':30,'scientific_qualification_claim':False},
            'private_targets_query_maps_cell_outputs_excluded':True,'system_identity_blinding':'structural alias plus separately required independent procedural qualification'}

class Postscore:
    def __init__(self,plan,source,root,authority,journal,budget):
        self.plan=plan;self.source=source;self.root=Path(root);self.authority=authority;self.journal=journal;self.budget=budget
        self.policy=plan['interpretation'];admit_policy(self.policy)
        if self.policy is not None:
            require(self.policy['memory_bytes']<=plan['native_profile']['memory_bytes'],'postscore memory bound within original selected cap')
            require(budget.token_ledger is not None,'existing original campaign token ledger for postscore')
        self.campaign=sha(encoded(plan));self.carrier=FailureCarrier();self.originals=[];self.records={};self.consumed=set()
        self.aggregate=None;self.started=None;self.deadline=None;self.baseline=None;self.requests=[]
    def point(self):
        b=self.budget
        return {'cpu_seconds':b.cpu+b.own_cpu(),'read_bytes':b.read_bytes,'write_bytes':b.write_bytes,'files':b.files,'stream_bytes':b.stream_bytes,'model_calls':b.model_calls}
    def check(self,stage):
        self.budget.check('postscore:'+stage,self.deadline)
        current=self.point()
        for key in RESOURCES:require(current[key]-self.baseline[key]<=self.policy['limits'][key],'original postscore '+key+' allowance')
    def selected(self,descriptor,cap):
        self.check('before bounded original body')
        body=capture(self.root,descriptor,self.budget,cap)
        self.check('after bounded original body');return body
    def await_response(self,sequence,role):
        """One preselected mailbox path per operation; no callback or retry."""
        folder=self.root/str(relative(self.policy['control_directory']))
        require(folder.is_absolute() and folder.is_dir() and not any(p.is_symlink()for p in(folder,*folder.parents)),'literal protected operator mailbox')
        path=folder/('%02d-%s.json'%(sequence,role))
        while True:
            self.check('waiting for original operator response')
            try:s=path.lstat()
            except FileNotFoundError:
                time.sleep(min(.05,max(0,self.deadline-self.budget.clock())));continue
            require(s.st_size<=self.policy['response_bytes'],'finite original response extent')
            # Capture authenticates the exact stable ordinary file on its one
            # original read. No unbounded read is done merely to invent a pin.
            from .common import stamp as identity
            import stat
            require(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'ordinary unlinked original response')
            self.budget.admit_read(s.st_size+1);fd=None;raw=bytearray();first=None;observation={'path':str(path),'before_identity':identity(s),'raw':raw,'closed':False,'failures':[]}
            self.carrier.retain(observation)
            try:
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);require(identity(os.fstat(fd))==identity(s),'same original response handle')
                while len(raw)<=s.st_size:
                    chunk=os.read(fd,min(65536,s.st_size+1-len(raw)))
                    raw.extend(chunk);self.budget.read(len(chunk))
                    self.check('after original response read')
                    if not chunk:break
                require(len(raw)==s.st_size and identity(os.fstat(fd))==identity(s)and identity(path.lstat())==identity(s),'complete stable original response')
            except BaseException as exc:
                first=exc;observation['failures'].append(('read',exc))
            finally:
                if fd is not None:
                    try:os.close(fd);observation['closed']=True
                    except BaseException as exc:
                        observation['failures'].append(('close',exc));first=exc if first is None else first
                        self.budget.uncertain('postscore-response:'+str(path),'managed_descriptor_closure',exc,descriptor=fd)
            if first is not None:raise first
            raw=bytes(raw)
            self.check('after original response capture')
            publication=self.journal.write('INTERPRETATION_RESPONSE_%02d.json'%sequence,raw)
            return parse(raw),{'path':str(path.relative_to(self.root)),**pin(raw),'mode':oct(stat.S_IMODE(s.st_mode)),'role':'original_postscore_response'},publication
    def operation(self,role,service,input_descriptor):
        sequence=len(self.requests);require(sequence<4 and role not in self.consumed,'finite no-retry postscore operation')
        self.budget.admit('before new original postscore request',self.deadline)
        self.consumed.add(role);self.check('before original request')
        point=self.point();reserved_bytes,reserved_files=self.budget.reserved()
        remaining={k:min(self.policy['limits'][k]-(point[k]-self.baseline[k]),self.budget.limits[k]-point[k]-(reserved_bytes if k=='write_bytes'else reserved_files if k=='files'else 0))for k in RESOURCES}
        require(all(v>=0 for v in remaining.values()),'original residual reporting resources')
        request={'schema':'neural055-postscore-operation-request-v1','resource_policy':self.budget.resource_policy,'source':self.source.identity,'campaign':self.campaign,
                 'original_origin':self.budget.origin,'original_deadline':self.budget.deadline,'postscore_deadline':self.deadline,'clock_domain':self.policy['clock_domain'],
                 'created':self.budget.clock(),'sequence':sequence,'role':role,'actor':service['identity'],'actor_source':service['source'],
                 'aggregate':self.aggregate,'input':input_descriptor,'rubric':self.policy['rubric'],'policy':self.policy['policy'],
                 'comparisons':list(COMPARISONS),'result_not_known_before_request':True,'maximum_original_operation_resources':remaining,
                 'input_namespace':'exact files in this journal; no other journal or protected input is an actor capability'}
        tokens=self.budget.token_ledger.reserve_external(self.policy['maximum_input_tokens'],self.policy['maximum_output_tokens'])
        request['token_reservation']=dict(tokens);request['memory_limit_bytes']=self.policy['memory_bytes']
        raw=encoded(request);name='INTERPRETATION_REQUEST_%02d.json'%sequence
        request_pin={'path':name,**pin(raw),'mode':'0o600','role':'original_postscore_request'}
        pending=[{'operation':'postscore-'+sha(raw),'quantity':'pending_original_'+k,'request':request_pin,'observed':None}for k in RESOURCES]
        owned={'request':request,'request_pin':request_pin,'publication':None,'original_token_reservation':tokens,
               'pending_original_costs':pending,'publication_status':'owned_before_visibility'}
        # Ownership and uncertainty precede open/write/fsync: a complete or
        # partial visible request is never assumed to have caused zero work.
        self.requests.append(owned);self.carrier.retain(owned);self.budget.unknown.extend(pending)
        try:
            owned['publication']=self.journal.write(name,raw)
            owned['publication_status']='complete_original_publication'
        except BaseException as exc:
            owned['publication_status']='failed_original_publication_effect_unresolved'
            owned['publication_error']={'type':diagnostic_type(exc)}
            raise
        response,response_pin,publication=self.await_response(sequence,role)
        original={'role':role,'request':request,'response':response,'response_pin':response_pin,'publication':publication,'admitted':False}
        self.originals.append(original);self.carrier.retain(original)
        response_fields=('schema','role','request_sha256','actor','actor_source','result','original_operation','qualification')
        keys(response,(*response_fields,'blinding_qualification')if role=='author'else response_fields)
        require(response['schema']=='neural055-postscore-operation-response-v1'and response['role']==role and response['request_sha256']==sha(raw),'same current original request')
        require(response['actor']==service['identity']and response['actor_source']==service['source'],'precommitted actual service')
        operation=parse(self.selected(response['original_operation'],4194304));original['original_operation']=operation
        keys(operation,('schema','resource_policy','resource_scope','source','actor','actor_source','request_sha256','aggregate','input','result','clock_domain','origin','end','natural','reaped','descendants_absent','status','unknown','costs','original_processes','memory_peak_bytes','memory_limit_bytes','memory_scope','token_usage'))
        require(operation['schema']=='neural055-original-postscore-operation-v1'and operation['source']==self.source.identity and operation['actor']==service['identity']and operation['actor_source']==service['source'],'original producer identity')
        require(operation['request_sha256']==sha(raw)and operation['aggregate']==self.aggregate and operation['input']==input_descriptor and operation['result']==response['result'],'exact current aggregate/report input and output')
        require(operation['resource_policy']==self.budget.resource_policy and operation['resource_scope']=='selected_measured_vector_with_original_whole_cost_scope','same postscore source resource definition')
        require(operation['clock_domain']==self.policy['clock_domain'],'same independently qualified original clock domain')
        finite(operation['origin']);finite(operation['end'])
        require(request['created']<=operation['origin']<=operation['end']<=self.budget.clock()<=self.deadline,'actual post-request completion inside original clock')
        require(operation['natural']is True and operation['reaped']is True and operation['descendants_absent']is True and operation['status']=='complete_original'and operation['unknown']==[],'complete original report operation, no unknown completion')
        require(type(operation['original_processes'])is list and operation['original_processes'],'original external process evidence required')
        require(len({d['sha256']for d in operation['original_processes']})==len(operation['original_processes']),'unique original report process census')
        for d in operation['original_processes']:
            process=parse(self.selected(d,4194304))
            require(process['reaped']is True and process['group_absent']is True and process['returncode']==0 and process['natural']is True,'actual natural original reporting process')
            require(operation['origin']<=process['origin']<=process['end']<=operation['end'],'original producer chronology')
            finite(process['cpu_seconds']);require(process['cpu_seconds']>=0,'known original producer CPU, not unknown zero')
        subject={'source':self.source.identity,'campaign':self.campaign,'original_origin':self.budget.origin,'policy':sha(encoded(self.policy)),
                 'request':request_pin,'response_payload':{k:v for k,v in response.items()if k!='qualification'},'aggregate':self.aggregate,'input':input_descriptor,
                 'actor':service,'result':response['result'],'original_operation':response['original_operation']}
        self.authority.verify(response['qualification'],'postscore_scientific_interpretation_operation',subject)
        if operation['memory_peak_bytes'] is None:self.budget.unknown.append({'operation':role,'quantity':'postscore_memory_peak_bytes','observed':None})
        integer(operation['memory_peak_bytes']);require(operation['memory_limit_bytes']==self.policy['memory_bytes'] and operation['memory_peak_bytes']<=operation['memory_limit_bytes'] and operation['memory_scope']=='full_original_external_reporting_operation','known enforced full original postscore memory')
        usage=operation['token_usage']
        if type(usage)is not dict or any(usage.get(k)is None for k in ('input_tokens','output_tokens')):self.budget.unknown.append({'operation':role,'quantity':'postscore_actual_model_tokens','observed':None})
        self.budget.token_ledger.settle_external(tokens,usage)
        costs=operation['costs'];keys(costs,RESOURCES)
        for k,v in costs.items():
            if v is None:self.budget.unknown.append({'operation':role,'quantity':'postscore_'+k})
            finite(v);require(v>=0,'known nonnegative full original operation costs')
            if k!='cpu_seconds':integer(v)
        # All original supervisor/provider/publication work belongs in this
        # independently authenticated snapshot; child CPU is not substituted.
        ident='postscore-'+sha(encoded({'request':request_pin,'operation':response['original_operation']}))
        self.budget.physical(ident,{'kind':'postscore_'+role,'cpu_seconds':costs['cpu_seconds'],'original_operation':response['original_operation'],'full_original_external_costs':costs})
        # Retain/debit every known actual quantity before any cap check can
        # raise. An over-budget original does not lose its remaining counters.
        for k in ('read_bytes','write_bytes','files','stream_bytes','model_calls'):setattr(self.budget,k,getattr(self.budget,k)+costs[k])
        if self.budget.resource_policy is not None:
            from .resource_policy import unobserved
            self.budget.native_unobserved.extend(unobserved(ident,self.budget.resource_policy))
        original['exact_original_costs_joined']=True
        self.requests[-1]['pending_cost_resolution']={'status':'joined_once','original_operation':response['original_operation'],'costs':costs}
        self.budget.unknown[:]=[x for x in self.budget.unknown if not any(x is own for own in pending)]
        reserved_bytes,reserved_files=self.budget.reserved()
        require(self.budget.write_bytes+reserved_bytes<=self.budget.limits['write_bytes'],'external original writes preserve publication reserve')
        require(self.budget.files+reserved_files<=self.budget.limits['files'],'external original files preserve publication reserve')
        for k in RESOURCES:
            require(costs[k]<=remaining[k],'original external operation exceeded pre-request '+k)
            require(self.point()[k]-self.baseline[k]<=self.policy['limits'][k],'original postscore cumulative '+k)
            require(self.point()[k]<=self.budget.limits[k],'original global resource allowance')
        result=parse(self.selected(response['result'],self.policy['result_bytes']))
        original['result']=result;original['admitted']=True;self.check('after original operation admission')
        return result,response['result']
    def run(self,paired,numerical_report):
        if self.policy is None:return {'status':'unavailable','reason':'interpretation_not_selected','records':{},'numerical_validity_unchanged':True}
        self.started=self.budget.clock();self.baseline=self.point()
        whole=min(self.budget.deadline,*self.budget.action_deadlines)if self.budget.action_deadlines else self.budget.deadline
        self.deadline=min(whole,self.started+self.policy['limits']['wall_seconds'])-self.policy['closure_reserve_seconds']
        status='unavailable';first=None
        try:
            require(self.started<self.deadline,'postscore reserve inside remaining original deadline')
            with self.budget.action(self.deadline):
                self.budget.admit('postscore service policy admission',self.deadline)
                self.check('service policy admission')
                for service in [self.policy['author'],*self.policy['reviewers'],self.policy['adjudicator']]:
                    self.selected(service['source'],16777216)
                    self.authority.verify(service['qualification'],'postscore_service_qualification',{'source':self.source.identity,'service_identity':service['identity'],'service_source':service['source'],'policy':self.policy['policy'],'rubric':self.policy['rubric'],'clock_domain':self.policy['clock_domain'],'resource_policy':self.budget.resource_policy,'operation_limits':{k:self.policy[k]for k in ('memory_bytes','maximum_input_tokens','maximum_output_tokens')}})
                aggregate=safe_aggregate(paired,self.source.identity,self.campaign,numerical_report)
                raw=encoded(aggregate);published=self.journal.write('INTERPRETATION_SAFE_AGGREGATE.json',raw)
                self.aggregate={'path':published['path'],**pin(raw),'mode':'0o600','role':'safe_postscore_aggregate'}
                author,author_pin=self.operation('author',self.policy['author'],self.aggregate)
                keys(author,('schema','aggregate','comparisons'))
                require(author['schema']=='neural055-current-scientific-report-v1'and author['aggregate']==self.aggregate and set(author['comparisons'])==set(COMPARISONS),'all four current reports')
                for value in author['comparisons'].values():
                    keys(value,('machine_interpretation','scientific_report'))
                    require(type(value['machine_interpretation'])is dict and type(value['scientific_report'])is str and value['scientific_report'].strip(),'machine and narrative interpretation')
                # The independently produced blinding receipt is outside the
                # report it authenticates. Neither subject includes its own
                # signature/receipt descriptor or an enclosing response hash.
                self.authority.verify(self.originals[-1]['response']['blinding_qualification'],'postscore_blinded_report',{'source':self.source.identity,'campaign':self.campaign,'aggregate':self.aggregate,'report':author_pin,'reviewers':[s['identity']for s in self.policy['reviewers']]})
                judgments=[];pins=[]
                for i,service in enumerate(self.policy['reviewers'],1):
                    result,result_pin=self.operation('reviewer_'+str(i),service,author_pin)
                    self.judgment(result,service,author_pin);judgments.append(result);pins.append(result_pin)
                disagreements=[c for c in COMPARISONS if judgments[0]['comparisons'][c]['scores']!=judgments[1]['comparisons'][c]['scores']]
                adjudication=None
                if disagreements:
                    body={'schema':'neural055-current-adjudication-input-v1','aggregate':self.aggregate,'report':author_pin,'judgments':pins,'comparisons':disagreements,'rubric':self.policy['rubric']}
                    raw=encoded(body);published=self.journal.write('INTERPRETATION_ADJUDICATION_INPUT.json',raw)
                    adjudication,_=self.operation('adjudicator',self.policy['adjudicator'],{'path':published['path'],**pin(raw),'mode':'0o600','role':'current_adjudication_input'})
                    keys(adjudication,('schema','aggregate','report','judgments','reviewer','comparisons'))
                    require(adjudication['schema']=='neural055-current-interpretation-adjudication-v1'and adjudication['aggregate']==self.aggregate and adjudication['report']==author_pin and adjudication['judgments']==pins and adjudication['reviewer']==self.policy['adjudicator']['identity']and set(adjudication['comparisons'])==set(disagreements),'exact current disagreements and distinct adjudicator')
                    for value in adjudication['comparisons'].values():self.ratings(value)
                for c in COMPARISONS:
                    self.records[c]={**author['comparisons'][c],'blinded_to_system':True,
                        'initial':{'reviewer_1':judgments[0]['comparisons'][c],'reviewer_2':judgments[1]['comparisons'][c]},
                        'adjudication':None if c not in disagreements else adjudication['comparisons'][c]}
                score_interpretation(self.records);self.check('all current scientific report judgments complete');status='complete_current_postscore_interpretation'
        except BaseException as exc:
            first=exc;self.carrier.fail(exc,'postscore_interpretation')
        result={'schema':'neural055-original-postscore-disposition-v1','resource_policy':self.budget.resource_policy,'status':status,'records':self.records if first is None else{},
                'aggregate':self.aggregate,'original_requests':self.requests,'original_operations':self.originals,
                'errors':self.carrier.document(),'original_deadline':self.budget.deadline,'postscore_deadline':self.deadline,
                'numerical_report':numerical_report,'numerical_validity_unchanged':True,'no_retries':True,
                'source_or_scientific_qualification_claim':False}
        self.carrier.retain(result)
        return result
    def ratings(self,value):
        keys(value,('scores','reasons','rationale'))
        require(set(value['scores'])==set(RUBRIC)and all(type(x)is int and x in(0,1,2)for x in value['scores'].values()),'all six ordinal scores')
        require(set(value['reasons'])==set(RUBRIC)and all(type(x)is str and x.strip()for x in value['reasons'].values()),'retained original reasons per item')
        require(type(value['rationale'])is str and value['rationale'].strip(),'original overall rationale')
    def judgment(self,result,service,report):
        keys(result,('schema','aggregate','report','reviewer','comparisons'))
        require(result['schema']=='neural055-current-interpretation-judgment-v1'and result['aggregate']==self.aggregate and result['report']==report and result['reviewer']==service['identity']and set(result['comparisons'])==set(COMPARISONS),'same exact blinded report and aggregate for each independent reviewer')
        for value in result['comparisons'].values():self.ratings(value)
