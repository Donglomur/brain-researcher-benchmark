"""Complete descriptor-driven reference study; no selected fit may disappear."""
import hashlib,json,os,stat
from pathlib import Path
import common as c
import schedule,arrays

THRESHOLDS=(.01,.03,.1,.2,.3,.4,.5,.6,.7,.8,.9,.95,.99)
MONTAGE_THRESHOLDS=(.0001,.0003,.001,.003,.01,.03,.1,.3,.5,1.0)

def located(root,name,pin):
    c.need(type(pin)is dict and set(pin)=={'bytes','sha256'},'exact prepared body pin')
    return {'path':str(root/name),**pin}

def preparation(config,budget,legacy):
    c.exact(config,('receipt','public_root','private_root','selected_source_manifest','selected_original_roster'))
    public=c.absolute(config['public_root']);private=c.absolute(config['private_root'])
    c.need(not(public==private or public.is_relative_to(private)or private.is_relative_to(public)),'disjoint public and private preparation roots')
    prep=c.capture_json(config['receipt'],budget,[private]);c.need(prep['schema']=='neural010-original-preparation-v1'and prep['status']=='prepared_not_runtime_or_scientifically_qualified','whole original preparation receipt')
    c.need(type(prep['records'])is int and prep['records']==686 and type(prep['people'])is int and prep['people']==23 and type(prep['source_folders'])is int and prep['source_folders']==24,'full686/23/24 preparation')
    c.need(c.typed_equal(prep['source_manifest'],config['selected_source_manifest'])and c.typed_equal(prep['source_roster'],config['selected_original_roster'])and prep['global_assessment_release_authorized']is False,'independently selected original/source preparation identity')
    panel_pin=located(public,'panel.json',prep['panel']);meta_pin=located(public,'metadata.json',prep['metadata'])
    panel_raw=c.capture(panel_pin,budget,[public]);panel=legacy['scorer'].panel(c.parse(panel_raw));metadata=c.capture_json(meta_pin,budget,[public])
    c.exact(metadata,('schema','records'));c.need(metadata['schema']=='neural010-target-free-metadata-v1','target-free metadata schema')
    rows=metadata['records'];people=schedule.support(rows);c.need(sum(r['duration_seconds']for r in rows)<=10000000,'whole observed-time bound')
    c.need([r['recording_id']for r in rows]==sorted(panel),'exact sorted full panel/metadata join')
    for r in rows:
        c.exact(r,('recording_id','patient_id','duration_seconds','montage_id','channel_count','channel_labels','source_edf','target_free_projection'))
        p=panel[r['recording_id']];c.need(p['patient_id']==r['patient_id']and p['duration_seconds']==r['duration_seconds']and c.typed_equal(r['target_free_projection'],{k:p[k]for k in('bytes','sha256')}),'original projection/person/duration identity')
        c.integer(r['channel_count'],1,512);c.need(type(r['channel_labels'])is list and len(r['channel_labels'])==r['channel_count']and all(type(x)is str and x for x in r['channel_labels']),'complete genuine channel-label multiset')
        c.need(hashlib.sha256(c.encoded(sorted(r['channel_labels']),False)).hexdigest()==r['montage_id'],'montage retains duplicate derivations')
    expected=[p+'/final'for p in people]+[p+'/inner/'+q for p in people for q in people if q!=p]
    views=prep['views'];c.need(type(views)is list and len(views)==529 and len({v['name']for v in views})==529 and {v['name']for v in views}==set(expected),'all23 final and506 inner view groups')
    view_map={}
    for v in views:
        c.exact(v,('name','artifacts'));keys={'TRAIN.json','SUPPORT.json','QUERY.json'}
        if '/inner/'in v['name']:keys.add('VALIDATION.json')
        c.exact(v['artifacts'],keys)
        view_map[v['name']]={k:located(private/'views'/v['name'],k,pin)for k,pin in v['artifacts'].items()}
    # No assessment body, original annotation body, training/validation label
    # body or private identity key is opened here.
    return {'receipt':prep,'receipt_pin':config['receipt'],'public_root':public,'private_root':private,'rows':rows,'people':people,'panel':panel,'panel_raw':panel_raw,'panel_pin':panel_pin,'metadata_pin':meta_pin,'views':view_map}

def condition(arm):return 'joint'if arm=='candidate'else arm
def family(arm):return 'strong'if arm in schedule.STRONG else arm
def record_files(bindings):
    if bindings is None:return []
    return [d for r in bindings.values()for d in r.values()]

def bootstrap_floor(request_pin,source_files):
    c.descriptor(request_pin);c.need(type(source_files)is list and len(source_files)==9,'complete8 reference files plus manifest')
    names={Path(d['path']).name for d in source_files};c.need(names=={'SOURCE_MANIFEST.json','reference_cli.py','common.py','contracts.py','event_protocol.py','features.py','learners.py','math_core.py','selection.py'},'exact reference bootstrap source roster')
    for d in source_files:c.descriptor(d)
    entry=next(d for d in source_files if Path(d['path']).name=='reference_cli.py')
    return request_pin['bytes']+sum(d['bytes']for d in source_files)+entry['bytes']+10

class ReferenceStudy:
    def __init__(self,prepared,native,reference_source,limits,output_root,budget,legacy):
        self.p=prepared;self.native=native;self.source=reference_source;self.limits=limits;self.root=c.absolute(str(output_root));self.budget=budget;self.legacy=legacy
        self.requests=c.new_directory(self.root/'requests',budget);self.ops={};self.features={};self.operations=[];self.final={};self.entered=[];self.failed=[]
        self.identity={k:reference_source[k]for k in('bytes','sha256')};self.script=str(Path(reference_source['path']).parent/'reference_cli.py')
        self.reference_source_files=native.source_files
    def read_output(self,desc,work):return c.capture_json(desc,self.budget,[work])
    def features_for(self,people,arm):
        if arm not in('candidate','signal_reference'):return None
        key='eeg_features'if arm=='candidate'else'signal_features'
        return {r['recording_id']:{'feature_receipt':self.features[r['recording_id']]['descriptor'],key:self.features[r['recording_id']]['body']['features'if arm=='candidate'else'signal']}for r in self.p['rows']if r['patient_id']in people}
    def request(self,job):
        kind=job['kind'];request={'schema':'neural010-reference-request-v1','command':kind,'source_identity':self.identity,'limits':self.limits};inputs=[];opaque=[]
        if kind=='features':
            row=next(r for r in self.p['rows']if r['recording_id']==job['recording_id']);wave=located(self.p['public_root'],'signals/'+row['recording_id']+'.h5',row['target_free_projection'])
            request.update(record=row,waveform=wave);inputs.append(wave);return request,inputs,opaque
        arm=job['arm'];outer=job['outer'];inner=job['inner'];context={'panel_people':self.p['people'],'outer_person':outer,'inner_person':inner}
        group=outer+'/final'if inner is None else outer+'/inner/'+inner;view=self.p['views'][group]
        if kind=='fit':
            selected=self.ops[job['dependencies'][0]]if job['dependencies']else None
            selection=None if selected is None else selected['output'];grid=job['grid']
            if selected is not None and arm in schedule.STRONG:grid=selected['body']['grid_index']
            bindings=self.features_for(job['training_people'],arm)
            request.update(family=family(arm),condition=condition(arm),grid_index=grid,records=view['TRAIN.json'],support=view['SUPPORT.json'],support_sha256=view['SUPPORT.json']['sha256'],expected_people=len(job['training_people']),context=context,selection=selection,feature_bindings=bindings)
            inputs.extend([view['TRAIN.json'],view['SUPPORT.json'],*record_files(bindings)]);opaque.append(view['TRAIN.json']['path'])
            if selection:inputs.append(selection)
        elif kind=='infer':
            fit=self.ops[job['dependencies'][0]];fb=fit['body'];bindings=self.features_for(job['query_people'],arm)
            threshold=None if inner is not None or arm=='signal_reference'else fb['selection_threshold']
            request.update(model=fb['model'],fit_receipt=fit['output'],records=view['QUERY.json'],threshold=threshold,feature_bindings=bindings)
            inputs.extend([fb['model'],fit['output'],view['QUERY.json'],*record_files(bindings)])
        elif kind=='validate':
            prediction=self.ops[job['dependencies'][1]];request.update(predictions=prediction['output'],records=view['VALIDATION.json'],thresholds=list(THRESHOLDS if arm in schedule.STRONG else MONTAGE_THRESHOLDS))
            inputs.extend([prediction['output'],prediction['body']['fit_receipt'],view['VALIDATION.json']]);opaque.append(view['VALIDATION.json']['path'])
            inputs.extend(r['probabilities']for r in prediction['body']['records'])
        else:
            deps=[self.ops[x]['output']for x in job['dependencies']]
            request.update(family=family(arm),condition=condition(arm),context=context,validation_receipts=deps,expected_validation_people=job['training_people']);inputs.extend(deps)
        return request,inputs,opaque
    def admit(self,job,request,request_pin,native,complete,out,*,completion_descriptor):
        work=Path(native['work_root']);c.descriptor(completion_descriptor)
        c.exact(complete,('schema','command','request','source_identity','output','limits','read_reserved_bytes','write_reserved_bytes','artifact_bytes_before_completion','completion_bytes','artifact_bytes_total','source_read_reservations','native_qualification','physical_cost_measured','interpreter_library_io_included'))
        c.need(complete['schema']=='neural010-command-completion-v2'and complete['command']==job['kind']and c.typed_equal(complete['request'],request_pin)and c.typed_equal(complete['source_identity'],self.identity),'actual complete command/request/source lineage')
        c.need(c.typed_equal(complete['limits'],self.limits)and complete['native_qualification']is False and complete['physical_cost_measured']is False and complete['interpreter_library_io_included']is False,'output cannot qualify or measure uninstrumented interpreter/library/physical costs')
        for key in('read_reserved_bytes','write_reserved_bytes','artifact_bytes_before_completion','completion_bytes','artifact_bytes_total'):c.integer(complete[key],0)
        c.need(complete['completion_bytes']==completion_descriptor['bytes']and c.pin(c.encoded(complete,False))=={k:completion_descriptor[k]for k in('bytes','sha256')},'exact original canonical completion bytes including own publication')
        c.need(complete['artifact_bytes_total']==complete['artifact_bytes_before_completion']+complete['completion_bytes']<=complete['write_reserved_bytes']<=self.limits['max_output_bytes']and complete['read_reserved_bytes']<=self.limits['max_input_bytes'],'all actual output bytes and declared IO reservations inside preallocated worker caps')
        source_reservations=complete['source_read_reservations'];c.exact(source_reservations,('entry','bootstrap','imports'))
        entry=next(d['bytes']for d in self.reference_source_files if Path(d['path']).name=='reference_cli.py');floor=bootstrap_floor(request_pin,self.reference_source_files)
        c.need(type(source_reservations['entry'])is int and source_reservations['entry']==entry and type(source_reservations['bootstrap'])is int and source_reservations['bootstrap']==floor-entry and type(source_reservations['imports'])is int and source_reservations['imports']==0 and floor<=complete['read_reserved_bytes'],'exact complete source bootstrap reservations, no sibling import rereads')
        c.need(c.typed_equal(native['worker_io_reservation'],{'read_bytes':self.limits['max_input_bytes'],'write_bytes':self.limits['max_output_bytes']})and native['worker_io_reservation_refunded']is False,'whole parent retains each full pre-attempt worker IO cap')
        c.need(c.typed_equal(out['source_identity'],self.identity),'exact reference method source')
        kind=job['kind']
        if kind=='features':
            c.need(c.typed_equal(out['record'],request['record'])and c.typed_equal(out['waveform'],request['waveform'])and out['rows']==request['record']['duration_seconds']and type(out['eeg_columns'])is int and out['eeg_columns']==33,'full original target-free feature lineage')
            self.features[job['recording_id']]={'descriptor':complete['output'],'body':out}
        else:
            expected={'panel_people':self.p['people'],'outer_person':job['outer'],'inner_person':job['inner']}
            c.need(c.typed_equal(out['context'],expected)and out['family']==family(job['arm'])and out['condition']==condition(job['arm']),'exact outer/inner/method context')
            if kind=='fit':
                c.need(c.typed_equal(out['request'],request)and out['support_sha256']==request['support_sha256']and c.typed_equal(out['training_people'],job['training_people'])and out['grid_index']==request['grid_index']and c.typed_equal(out['selection'],request['selection']),'fit/source/config/support/selection joins')
                c.need(c.typed_equal(out['prepared_training_view'],request['records']),'exact isolated training view')
            elif kind=='infer':
                c.need(c.typed_equal(out['model'],request['model'])and c.typed_equal(out['fit_receipt'],request['fit_receipt'])and c.typed_equal(out['prepared_query_view'],request['records']),'same sealed fit state before query')
                expected_rows=[r for r in self.p['rows']if r['patient_id']in job['query_people']]
                c.need([r['recording_id']for r in out['records']]==[r['recording_id']for r in sorted(expected_rows,key=lambda r:(r['patient_id'],r['recording_id']))],'full current held-person prediction support')
                if job['inner']is None:self.final[(job['outer'],job['arm'])]={'output':complete['output'],'body':out,'native':native['receipt']}
            elif kind=='validate':
                c.need(c.typed_equal(out['predictions'],request['predictions'])and c.typed_equal(out['prepared_validation_view'],request['records'])and out['person']==job['inner'],'validation only after sealed exact prediction')
            else:c.need(c.typed_equal(out['validation_receipts'],request['validation_receipts'])and c.typed_equal(out['expected_validation_people'],request['expected_validation_people']),'all22 training-person inner selections')
        # Stream-authenticate every output artifact, including full model bytes.
        # This integrity pass is not a prediction, label parser or scientific fit.
        artifacts=[];worker_only=[]
        if kind in('fit','infer','validate'):
            field={'fit':'training_manifest','infer':'query_manifest','validate':'validation_records'}[kind]
            normalized=out[field];c.descriptor(normalized)
            c.need(normalized['path']==str(work/'output/NORMALIZED_RECORDS.json'),'literal complete worker normalized-view output')
            normal=self.read_output(out['normalization'],work)
            c.need(normal['schema']=='neural010-worker-normalization-v1'and c.typed_equal(normal['source_identity'],self.identity)and c.typed_equal(normal['prepared_view'],request['records'])and c.typed_equal(normal['normalized_records'],normalized),'original-to-normalized worker lineage')
            c.need(c.typed_equal(normal['context'],out['context'])and normal['condition']==out['condition']and normal['role']=={'fit':'train','infer':'query','validate':'validation'}[kind],'exact normalized role/context/condition')
            c.need(normal['feature_bindings_sha256']==hashlib.sha256(c.encoded(request.get('feature_bindings'),False)).hexdigest(),'exact permitted target-free feature binding map')
            c.need(normal['host_label_read_required']is False,'labels normalized only within the admitted worker')
            if kind in('fit','validate'):worker_only.append(normalized)
        def walk(value):
            if type(value)is dict:
                if set(value)=={'path','bytes','sha256'}:
                    p=Path(value['path'])
                    if any(c.typed_equal(value,d)for d in worker_only):return
                    if p.is_relative_to(work):c.authenticate_stream(value,self.budget,[work]);artifacts.append(value)
                else:
                    for v in value.values():walk(v)
            elif type(value)is list:
                for v in value:walk(v)
        walk(out);return {'authenticated_artifacts':artifacts,'worker_only_label_outputs':worker_only}
    def run(self):
        expected_ids=[]
        try:
            for job in schedule.reference_jobs(self.p['rows']):
                expected_ids.append(job['id']);self.entered.append(job['id']);request,inputs,opaque=self.request(job)
                req=c.publish_json(self.requests/('%06d.json'%len(self.operations)),request,self.budget)
                c.need(self.limits['max_input_bytes']>=bootstrap_floor(req,self.native.source_files),'complete worker bootstrap floor is reserved before launch')
                worker_io={'read_bytes':self.limits['max_input_bytes'],'write_bytes':self.limits['max_output_bytes']}
                native=self.native.run(job['id'],self.script,[job['kind'],'--request',req['path'],'--request-sha256',req['sha256'],'--read-cap-bytes',str(self.limits['max_input_bytes']),'--output','{WORK}/output'],[req,*inputs],opaque_inputs=opaque,worker_io=worker_io)
                work=Path(native['work_root'])
                stdout=c.capture({'path':str(Path(native['receipt']['path']).parent/'stdout.bin'),'bytes':native['observation']['streams']['stdout']['bytes'],'sha256':native['observation']['streams']['stdout']['sha256']},self.budget,[Path(native['receipt']['path']).parent])
                complete_pin=c.parse(stdout);c.descriptor(complete_pin);c.need(complete_pin['path']==str(work/'output/COMPLETE.json'),'literal current completion artifact')
                complete=self.read_output(complete_pin,work);c.descriptor(complete['output']);out=self.read_output(complete['output'],work)
                artifacts=self.admit(job,request,req,native,complete,out,completion_descriptor=complete_pin)
                operation={'job':job,'request':req,'completion':complete_pin,'output':complete['output'],'native':native['receipt'],**artifacts,'record':native['receipt'],'previous':None if not self.operations else self.operations[-1]['record'],'status':'completed','returncode':0,'natural_completion':True,'unknown_survivors':False}
                self.operations.append(operation);self.ops[job['id']]={**operation,'body':out}
                self.budget.check_clock()
        except BaseException:
            if self.entered and(len(self.operations)<len(self.entered)):self.failed.append(self.entered[-1])
            raise
        schedule.complete_reference_admission(self.p['rows'],self.operations)
        c.need(set(self.final)=={(p,a)for p in self.p['people']for a in c.ARMS},'all92 complete final fold streams')
        return {'schema':'neural010-reference-study-provisional-v1','preparation':self.p['receipt_pin'],'panel':self.p['panel_pin'],'metadata':self.p['metadata_pin'],'reference_source':self.source,'operations':self.operations,'final_folds':[{'outer':p,'arm':a,**self.final[(p,a)]}for p in self.p['people']for a in c.ARMS],'reference_counts':schedule.expected_counts(),'observer_own_exit_established':False,'assessment_operand_opened':False,'global_assessment_release_authorized':False}
