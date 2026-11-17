"""Protected NEURAL-079 full-grid grader. Import performs no I/O or grading.

Ordinary authenticated descriptors are the only input route. No numeric result
callback, submitted score, study-success hook, arbitrary scorer or target cache.
"""
import hashlib
import itertools
import json
import math
import os
import stat
import types

PERSONS=tuple('sub-%02d'%i for i in range(1,7))
Q=127*1800
DRAWS=10000
NUMERIC_PIN={'bytes':37987,'sha256':'4d34de93b9659d1cc68090458057b6e184847a33d4b7095a0b7876fe96313eb3'}
LIMIT_KEYS=('max_rows','max_query_rows','max_columns','max_matrix_elements','max_live_float_slots')
POINT_ROWS=('pearson','pearson_status','mse','mse_status','normalized_mse','normalized_mse_status','constant_prediction','pearson_rounding_excess')
STATUS={'defined':0,'undefined_target':1,'underflow':2,'overflow':3,'denominator':4,'correlation_range':5,'nonfinite_result':6,'undefined_variance':7}
SOURCE_SCOPE='fixed fitted models/training/selection, observed six-person cohort and empirical curated videos; no refit uncertainty or confirmatory population inference'


class GradeRefusal(ValueError):
    def __init__(self,code,detail=''):
        self.code,self.detail=code,detail
        super().__init__(code+(': '+detail if detail else ''))


def require(ok,code,detail=''):
    if not ok: raise GradeRefusal(code,detail)


def fields(value,keys):
    require(type(value) is dict and set(value)==set(keys),'closed_schema',','.join(keys))
    return value


def integer(value,low=0):
    require(type(value) is int and value>=low,'integer')
    return value


def pin(value):
    fields(value,('bytes','sha256'));integer(value['bytes'])
    require(type(value['sha256']) is str and len(value['sha256'])==64 and all(x in '0123456789abcdef' for x in value['sha256']),'pin')
    return value


def object_descriptor(value):
    fields(value,('path','bytes','sha256'));pin({key:value[key] for key in ('bytes','sha256')})
    path=value['path']
    require(type(path) is str and path and not path.startswith('/') and '\\' not in path and '\x00' not in path and all(part not in ('','.','..') for part in path.split('/')),'ordinary_descriptor')
    return value


def matrix_descriptor(value,rows,rows_pin,columns_pin,canonical=False,metric=False):
    fields(value,('object','shape','dtype','rows_pin','columns_pin','lineage_pin'))
    object_descriptor(value['object'])
    require(value['shape']==[rows,Q] and value['dtype'] in ('<f4','<f8'),'full_matrix_shape')
    if canonical: require(value['dtype']=='<f4','canonical_target_dtype')
    if metric: require(value['dtype']=='<f8','independent_metric_dtype')
    require(value['object']['bytes']==rows*Q*(4 if value['dtype']=='<f4' else 8),'matrix_extent')
    for name in ('rows_pin','columns_pin','lineage_pin'):pin(value[name])
    require(value['rows_pin']==rows_pin and value['columns_pin']==columns_pin,'matrix_axis_join')
    return value


def candidate_ids():
    return tuple('%s-%s-seed%d-%s'%(mode,tool,seed,signal) for mode in ('F','I') for tool in ('basic','fit-helper') for seed in range(3) for signal in ('measured','mismatch','absent'))


def point_ids():
    return candidate_ids()+tuple('reference/%s/%s'%(signal,family) for signal in ('measured','mismatch') for family in ('R1','R2','R3'))+('mean/measured','mean/mismatch','zero')


def native_ids():
    return ('native-visual-features','native-language-features')+tuple('native-%s-%s'%(branch,person) for branch in ('visual','language') for person in PERSONS)+tuple('native-partial-'+person for person in PERSONS)+('native-statistics','native-plot')


def _native_record(row):
    fields(row,('id','outcome','source_pin','observed_record_pin','closure_pin','output_manifest_pin','comparison_evidence_pin','comparison_policy_pin','undefined_reason'))
    require(row['id'] in native_ids(),'native_identity')
    require(row['outcome'] in ('captured_match','captured_mismatch','captured_undefined_nonfinite'),'captured_complete_native_outcome')
    for name in ('source_pin','observed_record_pin','closure_pin','output_manifest_pin','comparison_evidence_pin','comparison_policy_pin'):pin(row[name])
    if row['outcome']=='captured_undefined_nonfinite':
        require(type(row['undefined_reason']) is str and 0<len(row['undefined_reason'])<=512,'native_undefined_reason')
    else:require(row['undefined_reason'] is None,'finite_native_reason')
    return row


def contrast_spec():
    out=[]
    for tool in ('basic','fit-helper'):
        for signal in ('measured','mismatch','absent'):
            out.append(('mode','I/%s/%s'%(tool,signal),'F/%s/%s'%(tool,signal),tool=='fit-helper' and signal=='measured'))
    for mode in ('F','I'):
        for signal in ('measured','mismatch','absent'):
            out.append(('helper','%s/fit-helper/%s'%(mode,signal),'%s/basic/%s'%(mode,signal),False))
    for mode in ('F','I'):
        for tool in ('basic','fit-helper'):
            left='%s/%s/measured'%(mode,tool)
            out.extend((('information',left,'%s/%s/mismatch'%(mode,tool),False),('information',left,'%s/%s/absent'%(mode,tool),False),('reference_gain',left,'champion/measured',mode=='I' and tool=='fit-helper')))
    return tuple({'id':'%02d'%i,'kind':kind,'lhs':left,'rhs':right,'primary':primary} for i,(kind,left,right,primary) in enumerate(out))


def accepted_integer(value,n):
    integer(value);require(value<(1<<64) and n in (6,102),'counter_integer_domain')
    ceiling=(1<<64)-((1<<64)%n)
    return None if value>=ceiling else value%n


def counter_indices(draw,axis,context=None):
    integer(draw);require(draw<DRAWS and axis in ('person','video'),'counter_domain')
    count=6 if axis=='person' else 102
    result=[]
    for position in range(count):
        rejection=0
        while True:
            if context is not None:context.tick()
            message='NEURAL-079/prospective-CI-v1/b='+str(draw)+'/a='+axis+'/j='+str(position)+'/k='+str(rejection)
            digest=hashlib.sha256(message.encode('utf-8')).digest()
            value=accepted_integer(int.from_bytes(digest[:8],'big'),count)
            if value is not None:
                result.append(value);break
            rejection+=1
    return tuple(result)


def linear_quantile(values,probability):
    require(type(values) in (tuple,list) and values and 0<=probability<=1,'quantile_support')
    require(all(type(v) in (float,int) and math.isfinite(v) for v in values),'finite_quantile')
    ordered=sorted(values);position=(len(ordered)-1)*probability
    left,right=math.floor(position),math.ceil(position)
    return ordered[left]+(position-left)*(ordered[right]-ordered[left])


def conditional_interval(values):
    require(len(values)==DRAWS,'complete_10000_draws')
    return _interval_values(values)


def _interval_values(values):
    require(len(values)>0,'interval_support')
    undefined=[i for i,value in enumerate(values) if value is None]
    if undefined:return {'status':'undefined','interval':None,'undefined_draws':undefined,'scope':SOURCE_SCOPE}
    return {'status':'conditional_fixed_models','interval':[linear_quantile(values,.025),linear_quantile(values,.975)],'undefined_draws':[],'scope':SOURCE_SCOPE}


def _mean_or_none(values):
    if any(v is None for v in values):return None
    require(values and all(math.isfinite(v) for v in values),'finite_mean')
    scale=max(abs(v) for v in values)
    if scale==0:return 0.0
    return _scaled_mean(math.fsum(v/scale for v in values),scale,len(values))


def _scaled_mean(total,scale,count):
    if total==0 or scale==0:return 0.0
    normalized=total/count
    if normalized==0:return None
    left,le=math.frexp(scale);right,re=math.frexp(normalized)
    try:value=math.ldexp(left*right,le+re)
    except OverflowError:return None
    return value if value!=0 and math.isfinite(value) else None


def _conditions(estimator_values):
    require(set(estimator_values)==set(candidate_ids())|{'champion/measured'},'complete_paired_estimators')
    result={'champion/measured':estimator_values['champion/measured']}
    for mode in ('F','I'):
        for tool in ('basic','fit-helper'):
            for signal in ('measured','mismatch','absent'):
                result['%s/%s/%s'%(mode,tool,signal)]=_mean_or_none([estimator_values['%s-%s-seed%d-%s'%(mode,tool,seed,signal)] for seed in range(3)])
    return result


def draw_contrasts(estimator_values):
    conditions=_conditions(estimator_values)
    return {item['id']:None if conditions[item['lhs']] is None or conditions[item['rhs']] is None else conditions[item['lhs']]-conditions[item['rhs']] for item in contrast_spec()}


def point_contrasts(person_values):
    require(all(len(v)==6 for v in person_values.values()),'six_paired_people')
    by_person=[draw_contrasts({key:value[p] for key,value in person_values.items()}) for p in range(6)]
    return {item['id']:{'per_person':[by_person[p][item['id']] for p in range(6)],'mean':_mean_or_none([by_person[p][item['id']] for p in range(6)])} for item in contrast_spec()}


def sign_sensitivity(effects):
    out={}
    for item in contrast_spec():
        if not item['primary']:continue
        values=effects[item['id']]['per_person'];observed=effects[item['id']]['mean']
        require(len(values)==6,'six_sign_effects')
        if observed is None or any(v is None for v in values):
            out[item['id']]={'status':'undefined','p_sensitivity':None,'holm_sensitivity':None,'all64_means':None};continue
        require(observed==_mean_or_none(values),'observed_sign_statistic_join')
        distributions=[]
        for code in range(64):
            signs=[1 if (code>>(5-person))&1 else -1 for person in range(6)]
            distributions.append(_mean_or_none([sign*value for sign,value in zip(signs,values)]))
        if any(value is None for value in distributions):
            out[item['id']]={'status':'undefined','p_sensitivity':None,'holm_sensitivity':None,'all64_means':distributions};continue
        out[item['id']]={'status':'assumption_dependent_sensitivity','p_sensitivity':sum(value>=observed for value in distributions)/64,'holm_sensitivity':None,'all64_means':distributions}
    if all(row['p_sensitivity'] is not None for row in out.values()):
        previous=0.0
        for rank,key in enumerate(sorted(out,key=lambda k:(out[k]['p_sensitivity'],k))):
            previous=min(1.0,max(previous,(2-rank)*out[key]['p_sensitivity']))
            out[key]['holm_sensitivity']=previous
    return {'comparisons':out,'joint_sign_invariance_established':False,'scope':'Sensitivity arithmetic only; pooled training and common videos can couple participant effects. No confirmatory population finding.'}


def _neumaier(total,compensation,index,value):
    old=float(total[index]);new=old+value
    compensation[index]+=(old-new)+value if abs(old)>=abs(value) else (value-new)+old
    total[index]=new


def _scaled_add(total,compensation,scales,index,values):
    # Pearson magnitudes are <=1; MSE magnitudes are nonnegative. Adaptive
    # scaling therefore avoids a huge nonnegative sum without introducing
    # cancellation between huge positive and negative calibration values.
    incoming=max((abs(float(v)) for v in values),default=0.0)
    scale=max(float(scales[index]),incoming)
    if scale==0:return
    if scales[index]!=scale:
        ratio=float(scales[index])/scale
        total[index]*=ratio;compensation[index]*=ratio;scales[index]=scale
    _neumaier(total,compensation,index,math.fsum(float(v)/scale for v in values))


def _numeric_status(error):
    require(getattr(error,'code',None) in STATUS and error.code!='defined','non_metric_numeric_failure',str(error))
    return STATUS[error.code]


def _pearson_columns(numeric,prediction,target,limits,context=None):
    import numpy as np
    width=prediction.shape[1]
    values=np.zeros(width);status=np.zeros(width,dtype=np.uint8);constant=np.zeros(width);excess=np.zeros(width)
    for column in range(width):
        if context is not None:context.tick()
        try:
            result=numeric.pearson(prediction[:,column:column+1],target[:,column:column+1],limits=limits)
            values[column]=result['values'][0];constant[column]=result['constant_prediction'][0];excess[column]=result['rounding_excess'][0]
        except numeric.NumericError as error:
            status[column]=_numeric_status(error)
        if context is not None:context.tick()
    return values,status,constant,excess


def _point_columns(numeric,prediction,target,variance,limits,context=None):
    import numpy as np
    width=prediction.shape[1];result=np.zeros((len(POINT_ROWS),width))
    r,status,constant,excess=_pearson_columns(numeric,prediction,target,limits,context)
    result[0],result[1],result[6],result[7]=r,status,constant,excess
    for column in range(width):
        if context is not None:context.tick()
        for value_row,status_row,normalization in ((2,3,None),(4,5,variance[column:column+1])):
            if normalization is not None and normalization[0]<=0:
                result[status_row,column]=STATUS['undefined_variance'];continue
            try:result[value_row,column]=numeric.mse(prediction[:,column:column+1],target[:,column:column+1],normalization,limits=limits)[0]
            except numeric.NumericError as error:result[status_row,column]=_numeric_status(error)
        if context is not None:context.tick()
    return result


def _fitting_moments(numeric,values,limits,context=None):
    import numpy as np
    mean=np.empty(values.shape[1]);variance=np.empty_like(mean)
    for column in range(values.shape[1]):
        if context is not None:context.tick()
        state=numeric.moments(values[:,column:column+1],limits=limits)
        mean[column]=state['mean'][0];variance[column]=state['variance'][0]
        if context is not None:context.tick()
    return {'mean':mean,'variance':variance}


def posterior_columns(channels):
    if type(channels) is not list or len(channels)!=127:return None,'missing_complete_127_channel_roster'
    if any(type(name) is not str or not name for name in channels) or len(set(channels))!=127:return None,'unknown_or_invalid_channel_name_admission'
    selected=tuple(i for i,name in enumerate(channels) if 'O' in name or 'P' in name)
    return (selected,None) if selected else (None,'empty_literal_OP_secondary')


def _disjoint_target_paths(protected_paths,ordinary_paths):
    require(not set(protected_paths).intersection(ordinary_paths),'target_role_alias_before_release')


def _private_numeric_module(source,filename):
    require(type(source) is bytes and len(source)==NUMERIC_PIN['bytes'] and hashlib.sha256(source).hexdigest()==NUMERIC_PIN['sha256'],'exact_independent_numeric_source')
    module=types.ModuleType('_neural079_independent_protected_numeric_v2')
    module.__file__=filename
    exec(compile(source,filename,'exec'),module.__dict__)
    return module


class ProtectedGrader:
    def __init__(self,context,repository,independent_numeric,output_fd,limits,coordinate_block,selected):
        from n079_effects import EffectContext
        require(type(context) is EffectContext and context.role=='grader','actual_protected_grader_context')
        fields(limits,LIMIT_KEYS)
        for value in limits.values():integer(value,1)
        integer(coordinate_block,1);require(coordinate_block<=Q,'coordinate_block')
        fields(selected,('schema','work_id','study_pin','grader_source_pin','source_closure_pin','observation_pin','allocation_pin','index','index_observation_pin','independent_numeric','dependency_admission_pin','max_index_bytes','output_prefix','capacity'))
        require(selected['schema']=='n079_protected_grader_selection_v1' and selected['work_id']=='target-last-grader','selected_grader')
        for key in ('study_pin','grader_source_pin','source_closure_pin','observation_pin','allocation_pin','index_observation_pin','dependency_admission_pin'):pin(selected[key])
        require(selected['grader_source_pin']==context.source_pin and selected['study_pin']==context.effect_admission['study_pin'] and selected['allocation_pin']==context.effect_admission['allocation_pin'],'selected_context_join')
        object_descriptor(selected['index']);object_descriptor(independent_numeric)
        require(independent_numeric==selected['independent_numeric'] and {key:independent_numeric[key] for key in NUMERIC_PIN}==NUMERIC_PIN,'exact_independent_numeric_source')
        integer(selected['max_index_bytes'],1)
        prefix=selected['output_prefix'];require(type(prefix) is str and 0<len(prefix)<=80 and all(c.isalnum() or c in '._-' for c in prefix) and prefix not in ('.','..'),'output_prefix')
        fields(selected['capacity'],('max_open_matrices','max_bootstrap_draws','max_point_coordinate_correlations','max_bootstrap_coordinate_correlations','max_inner_coordinate_reductions','max_numeric_block_applications','max_array_payload_read_bytes','max_output_payload_bytes'))
        for value in selected['capacity'].values():integer(value,1)
        self.context,self.repository,self.numeric_descriptor,self.output_fd=context,repository,dict(independent_numeric),output_fd
        self.limits,self.width,self.selected=dict(limits),coordinate_block,json.loads(json.dumps(selected,allow_nan=False))
        self.work_id=selected['work_id'];self.readers=[];self.writers=[];self.used=False;self.progress={'phase':'constructed','inner_vectors_read':0,'point_coordinates':0,'bootstrap_coordinates':0,'raw_mse_coordinates':0,'normalized_mse_coordinates_attempted':0,'fitting_variance_coordinates':0,'reserved_numeric_block_applications':0}
        self.numeric=None

    def _ordinary_bytes(self,descriptor,ceiling):
        object_descriptor(descriptor);require(descriptor['bytes']<=ceiling,'ordinary_read_ceiling')
        require(2*descriptor['bytes']<=8*self.limits['max_live_float_slots'],'ordinary_read_live_extent')
        self.context.ledger.charge(self.work_id,{'source_read_bytes':descriptor['bytes']},'full ordinary metadata/source read before allocation')
        fd=self.repository.open(descriptor);primary=None
        try:
            observed=os.fstat(fd);require(stat.S_ISREG(observed.st_mode) and observed.st_size==descriptor['bytes'],'actual_ordinary_extent')
            initial=(observed.st_dev,observed.st_ino,observed.st_size)
            data=bytearray();digest=hashlib.sha256();offset=0
            while offset<descriptor['bytes']:
                self.context.tick();chunk=os.pread(fd,min(65536,descriptor['bytes']-offset),offset)
                require(chunk,'full_ordinary_read');data.extend(chunk);digest.update(chunk);offset+=len(chunk)
            final=os.fstat(fd)
            require((final.st_dev,final.st_ino,final.st_size)==initial and digest.hexdigest()==descriptor['sha256'],'ordinary_identity')
            return bytes(data)
        except BaseException as error:primary=error;raise
        finally:
            from n079_common import close_all
            close_all([('protected ordinary descriptor',lambda:os.close(fd))],primary)

    def _identity(self,value):
        from n079_common import identity
        return identity(value,self.context.encoding_limits)

    def _charge_numeric(self,count,reason):
        self.context.ledger.charge(self.work_id,{'numeric_block_applications':count},reason)
        self.progress['reserved_numeric_block_applications']+=count

    def _load(self,payload):
        from n079_common import bounded_decode
        fields(payload,('index',));require(payload['index']==self.selected['index'],'selected_index_only')
        self.context.require_effect('grade_targets',self.work_id)
        self.index_admission=self.context.authority.exchange('grading_index_admission',{'index':payload['index'],'index_observation_pin':self.selected['index_observation_pin'],'study_pin':self.selected['study_pin'],'source_closure_pin':self.selected['source_closure_pin'],'observation_pin':self.selected['observation_pin'],'allocation_pin':self.selected['allocation_pin'],'numeric_source':self.numeric_descriptor,'dependency_admission_pin':self.selected['dependency_admission_pin']})
        raw=self._ordinary_bytes(payload['index'],self.selected['max_index_bytes']);index=bounded_decode(raw,self.context.encoding_limits)
        source=self._ordinary_bytes(self.numeric_descriptor,NUMERIC_PIN['bytes'])
        self.numeric=_private_numeric_module(source,self.numeric_descriptor['path'])
        return index

    def _validate(self,index):
        fields(index,('schema','task','study_pin','source_closure_pin','observation_pin','allocation_pin','coordinate_pin','query_rows_pin','fit_rows_pin','metric_rows_pin','channels','partitions','candidates','reference_inner','reference_final','means','targets','native','closure'))
        require(index['schema']=='n079_protected_grade_index_v1' and index['task']=='NEURAL-079','canonical_index')
        for key in ('study_pin','source_closure_pin','observation_pin','allocation_pin'):
            pin(index[key]);require(index[key]==self.selected[key],'index_admission_join',key)
        for key in ('coordinate_pin','query_rows_pin','fit_rows_pin','metric_rows_pin'):pin(index[key])
        fields(index['closure'],('controller_pin','reference_pin','native_pin','preparation_pin','feature_pin','reports_pin','observer_closeout_pin','source_admission_pin','original_clock_pin','complete_input_observation_pin'))
        for value in index['closure'].values():pin(value)
        require(type(index['partitions']) is list and len(index['partitions'])==5,'five_partitions')
        partitions={}
        for row in index['partitions']:
            fields(row,('fold','fit_rows_pin','validation_rows_pin'));require(type(row['fold']) is int and row['fold'] in range(5) and row['fold'] not in partitions,'partition_grid')
            pin(row['fit_rows_pin']);pin(row['validation_rows_pin']);partitions[row['fold']]=row
        self.predictions={};self.candidate_rows={};self.final_rows={};self.inner_groups={};self.target_rows={};self.mean_rows={}
        require(type(index['candidates']) is list and len(index['candidates'])==36,'complete36_candidates')
        for candidate in index['candidates']:
            fields(candidate,('id','observed_record_pin','seal_pin','closure_pin','report','queries','predictions'))
            name=candidate['id'];require(name in candidate_ids() and name not in self.candidate_rows,'candidate_identity')
            for key in ('observed_record_pin','seal_pin','closure_pin'):pin(candidate[key])
            fields(candidate['report'],('object','seal_pin','observed_record_pin'));object_descriptor(candidate['report']['object']);pin(candidate['report']['seal_pin']);pin(candidate['report']['observed_record_pin'])
            require(type(candidate['queries']) is list and len(candidate['queries'])==102,'complete102_queries')
            observed=set()
            for row in candidate['queries']:
                fields(row,('video_id','record_pin','closure_pin'));require(type(row['video_id']) is int and row['video_id'] in range(1001,1103) and row['video_id'] not in observed,'query_identity');observed.add(row['video_id']);pin(row['record_pin']);pin(row['closure_pin'])
            require(type(candidate['predictions']) is list and len(candidate['predictions'])==6,'six_candidate_people')
            seen=set()
            for row in candidate['predictions']:
                fields(row,('person','matrix'));require(row['person'] in PERSONS and row['person'] not in seen,'candidate_person');seen.add(row['person'])
                matrix_descriptor(row['matrix'],102,index['query_rows_pin'],index['coordinate_pin']);self.predictions[name,row['person']]=row['matrix']
            self.candidate_rows[name]=candidate
        require(type(index['reference_inner']) is list and len(index['reference_inner'])==5460,'complete5460_inner')
        jobs=set();inner_keys=set()
        for row in index['reference_inner']:
            fields(row,('person','signal','family','setting','fold','job_id','fit_record_pin','state_manifest_pin','prediction_commitment','metric_observation_pin','metric_source_pin','fit_rows_pin','validation_rows_pin','metrics'))
            person,signal,family,fold=row['person'],row['signal'],row['family'],row['fold']
            require(person in PERSONS and signal in ('measured','mismatch') and family in ('R1','R2','R3') and type(fold) is int and fold in range(5),'inner_grid')
            require(row['setting'] in self.numeric.settings(family),'inner_setting')
            key=(person,signal,family,row['setting']['id'],fold);require(key not in inner_keys,'duplicate_inner');inner_keys.add(key)
            require(type(row['job_id']) is str and row['job_id'] and row['job_id'] not in jobs,'unique_logical_reference_fit_record');jobs.add(row['job_id'])
            for name in ('fit_record_pin','state_manifest_pin','prediction_commitment','metric_observation_pin','metric_source_pin','fit_rows_pin','validation_rows_pin'):pin(row[name])
            require(row['metric_source_pin']==NUMERIC_PIN and row['fit_rows_pin']==partitions[fold]['fit_rows_pin'] and row['validation_rows_pin']==partitions[fold]['validation_rows_pin'],'independent_inner_lineage')
            matrix_descriptor(row['metrics'],1,index['metric_rows_pin'],index['coordinate_pin'],metric=True)
            self.inner_groups.setdefault((person,signal,family),[]).append(row)
        expected={(p,s,f,setting['id'],fold) for p in PERSONS for s in ('measured','mismatch') for f in ('R1','R2','R3') for setting in self.numeric.settings(f) for fold in range(5)}
        require(inner_keys==expected,'full_exact_inner_grid')
        require(type(index['reference_final']) is list and len(index['reference_final'])==36,'complete36_final')
        for row in index['reference_final']:
            fields(row,('person','signal','family','setting','job_id','fit_record_pin','state_manifest_pin','selection_record_pin','fit_rows_pin','prediction'))
            key=(row['person'],row['signal'],row['family']);require(key in self.inner_groups and key not in self.final_rows,'final_grid')
            require(row['setting'] in self.numeric.settings(row['family']),'final_setting')
            require(type(row['job_id']) is str and row['job_id'] and row['job_id'] not in jobs,'unique_logical_final_fit_record');jobs.add(row['job_id'])
            for name in ('fit_record_pin','state_manifest_pin','selection_record_pin','fit_rows_pin'):pin(row[name])
            require(row['fit_rows_pin']==index['fit_rows_pin'],'final_fit_rows')
            matrix_descriptor(row['prediction'],102,index['query_rows_pin'],index['coordinate_pin']);self.final_rows[key]=row
            self.predictions['reference/%s/%s'%(row['signal'],row['family']),row['person']]=row['prediction']
        require(len(jobs)==5496,'all5496_observed_logical_fit_records')
        require(type(index['means']) is list and len(index['means'])==12,'complete12_mean_states')
        for row in index['means']:
            fields(row,('person','signal','training_state_pin','observed_record_pin','fit_rows_pin','prediction'))
            key=(row['person'],row['signal']);require(row['person'] in PERSONS and row['signal'] in ('measured','mismatch') and key not in self.mean_rows,'mean_grid')
            for name in ('training_state_pin','observed_record_pin','fit_rows_pin'):pin(row[name])
            require(row['fit_rows_pin']==index['fit_rows_pin'],'mean_fit_rows');matrix_descriptor(row['prediction'],102,index['query_rows_pin'],index['coordinate_pin'])
            self.mean_rows[key]=row;self.predictions['mean/'+row['signal'],row['person']]=row['prediction']
        require(type(index['targets']) is list and len(index['targets'])==6,'six_targets')
        for row in index['targets']:
            fields(row,('person','query','fit','transform_pin','observed_record_pin'));require(row['person'] in PERSONS and row['person'] not in self.target_rows,'target_person')
            pin(row['transform_pin']);pin(row['observed_record_pin'])
            matrix_descriptor(row['query'],102,index['query_rows_pin'],index['coordinate_pin'],canonical=True);matrix_descriptor(row['fit'],1000,index['fit_rows_pin'],index['coordinate_pin'],canonical=True)
            self.target_rows[row['person']]=row
        require(type(index['native']) is list and len(index['native'])==22,'complete22_native_companions')
        names=set()
        for row in index['native']:
            _native_record(row);require(row['id'] not in names,'native_identity');names.add(row['id'])
        protected_paths=[row[name]['object']['path'] for row in self.target_rows.values() for name in ('query','fit')]
        early_paths=[self.selected['index']['path'],self.numeric_descriptor['path']]
        early_paths.extend(row['metrics']['object']['path'] for row in index['reference_inner'])
        early_paths.extend(value['object']['path'] for value in self.predictions.values())
        early_paths.extend(row['report']['object']['path'] for row in index['candidates'])
        _disjoint_target_paths(protected_paths,early_paths)
        self.posterior,self.posterior_reason=posterior_columns(index['channels'])
        return index

    def _preflight(self,index):
        capacity=self.selected['capacity']
        array_reads=sum(row['metrics']['object']['bytes'] for row in index['reference_inner'])+sum(d['object']['bytes'] for d in self.predictions.values())+sum(row[name]['object']['bytes'] for row in self.target_rows.values() for name in ('query','fit'))
        output_bytes=(45*6*len(POINT_ROWS)*Q+2*37*DRAWS+2*24*DRAWS)*8
        result_metadata_cap=integer(self.context.encoding_limits['bytes'],1)
        column_blocks=(Q+self.width-1)//self.width
        floors={'max_open_matrices':282,'max_bootstrap_draws':DRAWS,'max_point_coordinate_correlations':45*6*Q,'max_bootstrap_coordinate_correlations':37*DRAWS*6*Q,'max_inner_coordinate_reductions':5460*Q,'max_numeric_block_applications':(5736+37*DRAWS*6)*column_blocks+30106,'max_array_payload_read_bytes':array_reads+output_bytes,'max_output_payload_bytes':output_bytes+result_metadata_cap}
        self.input_payload_bytes=array_reads;self.output_identity_read_bytes=output_bytes
        for key,required in floors.items():require(capacity[key]>=required,'capacity_dominance',key)
        # Fixed tables plus all45 one-person prediction blocks, target/fit reads,
        # point-output block, gather copies, accumulators and output scratch.
        width=min(self.width,Q)
        slots=max((2*result_metadata_cap+7)//8,4*DRAWS*37+2*DRAWS*102+2*DRAWS*6+100000+(45*102+4*1000+45*6*len(POINT_ROWS)+8*102)*width)
        matrices=(DRAWS*102,DRAWS*37,45*6*len(POINT_ROWS)*width,1000*width,102*width)
        require(self.limits['max_rows']>=DRAWS and self.limits['max_query_rows']>=102 and self.limits['max_columns']>=max(width,102,37) and self.limits['max_matrix_elements']>=max(matrices) and self.limits['max_live_float_slots']>=slots,'selected_numeric_extent')
        self.context.ledger.charge(self.work_id,{'logical_float_slots':slots},'complete protected grading owned live-slot reservation before arrays')
        self.floors=floors;self.live_slots=slots

    def _reader(self,descriptor):
        from n079_arrays import MatrixReader
        reader=MatrixReader(self.context,self.repository,descriptor,self.limits,self.work_id);self.readers.append(reader);return reader

    def _selections(self,index):
        selections={}
        for key in sorted(self.inner_groups):
            records=[]
            for row in sorted(self.inner_groups[key],key=lambda r:(r['setting']['id'],r['fold'])):
                reader=self._reader(row['metrics']);total=0.;compensation=0.;primary=None
                try:
                    for start in range(0,Q,self.width):
                        self._charge_numeric(1,'one complete independent inner-vector coordinate-block reduction')
                        values=reader.block((0,),start,min(Q,start+self.width))[0]
                        require(all(-1<=float(v)<=1 for v in values),'inner_metric_range')
                        value=math.fsum(float(v) for v in values);new=total+value
                        compensation+=(total-new)+value if abs(total)>=abs(value) else (value-new)+total;total=new
                    records.append({'setting_id':row['setting']['id'],'fold':row['fold'],'score':(total+compensation)/Q})
                    self.progress['inner_vectors_read']+=1
                except BaseException as error:primary=error;raise
                finally:reader.close(primary);self.readers.remove(reader)
            self._charge_numeric(1,'one complete family-grid selection')
            choice=self.numeric.select_setting(key[2],records)
            require(self.final_rows[key]['setting']==choice['setting'],'final_setting_matches_independent_inner_selection')
            selections[key]=choice
        champions={}
        self._charge_numeric(6,'six per-person measured champion selections')
        for person in PERSONS:
            family=min(('R1','R2','R3'),key=lambda name:(-selections[person,'measured',name]['mean_score'],('R1','R2','R3').index(name)))
            champions[person]=family
        self.selections,self.champions=selections,champions
        summary={'families':[{'person':key[0],'signal':key[1],'family':key[2],**value} for key,value in sorted(selections.items())],'measured_champions':champions,'all5460_vectors_read':self.progress['inner_vectors_read']==5460}
        require(summary['all5460_vectors_read'],'inner_complete_read')
        return summary

    def _writer(self,suffix,rows,columns,lineage):
        from n079_arrays import MatrixWriter
        writer=MatrixWriter(self.context,self.output_fd,self.selected['output_prefix']+'-'+suffix+'.bin',rows,columns,'<f8',self.limits,self.work_id,lineage)
        self.writers.append(writer);return writer

    def _lineage(self,rows,columns,index):
        return {'rows_pin':self._identity(rows),'columns_pin':columns,'lineage_pin':self._identity({'index':self.selected['index'],'release':self.target_release,'independent_numeric':NUMERIC_PIN,'selection':self.selection_pin})}

    def _write_result(self,result):
        from n079_common import canonical,close_all
        self.context.require_effect('numeric_state',self.work_id)
        raw=canonical(result,self.context.encoding_limits)
        self.context.reserve_storage(len(raw),self.work_id)
        self.context.ledger.charge(self.work_id,{'write_bytes':len(raw),'data_read_bytes':len(raw)},'ordinary grade index write plus complete identity reread, before creation')
        name=self.selected['output_prefix']+'-grade.json';parent=None;fd=None;primary=None
        try:
            parent=os.dup(self.output_fd)
            fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            initial=os.fstat(fd);require(stat.S_ISREG(initial.st_mode) and initial.st_nlink==1,'ordinary_grade_index')
            done=0
            while done<len(raw):
                self.context.tick();count=os.write(fd,raw[done:]);require(count>0,'complete_grade_index_write');done+=count
            os.fsync(fd);os.fsync(parent)
            digest=hashlib.sha256();offset=0
            while offset<len(raw):
                self.context.tick();chunk=os.pread(fd,min(65536,len(raw)-offset),offset);require(chunk,'complete_grade_index_identity');digest.update(chunk);offset+=len(chunk)
            final=os.fstat(fd)
            require((final.st_dev,final.st_ino)==(initial.st_dev,initial.st_ino) and final.st_size==len(raw) and final.st_nlink==1 and digest.hexdigest()==hashlib.sha256(raw).hexdigest(),'stable_grade_index')
            return {'path':name,'bytes':len(raw),'sha256':digest.hexdigest()}
        except BaseException as error:primary=error;raise
        finally:
            operations=[]
            if fd is not None:operations.append(('grade index descriptor',lambda:os.close(fd)))
            if parent is not None:operations.append(('grade index directory',lambda:os.close(parent)))
            close_all(operations,primary)

    def _run(self,index,prediction_readers):
        import numpy as np
        targets={person:{name:self._reader(self.target_rows[person][name]) for name in ('query','fit')} for person in PERSONS}
        videos=np.empty((DRAWS,102),dtype=np.uint8);multiplicity=np.zeros((DRAWS,6),dtype=np.uint8)
        self._charge_numeric(2*DRAWS,'complete person/video resample-vector generation')
        for draw in range(DRAWS):
            self.context.tick();videos[draw]=counter_indices(draw,'video',self.context)
            for person in counter_indices(draw,'person',self.context):multiplicity[draw,person]+=1
        unique=int(np.count_nonzero(multiplicity))
        bootstrap_ids=candidate_ids()+('champion/measured',);estimators=point_ids()
        boot_sum=np.zeros((DRAWS,37));boot_comp=np.zeros_like(boot_sum);boot_bad=np.zeros((DRAWS,37),dtype=np.uint8)
        point_sum=np.zeros((45,6,3));point_comp=np.zeros_like(point_sum);point_scales=np.zeros_like(point_sum);point_bad=np.zeros((45,6,3),dtype=np.uint8)
        secondary_sum=np.zeros((45,6,3,3));secondary_comp=np.zeros_like(secondary_sum);secondary_scales=np.zeros_like(secondary_sum);secondary_bad=np.zeros((45,6,3,3),dtype=np.uint8)
        failures={};self.bootstrap_failures={};constant_counts=np.zeros((45,6),dtype=np.int64);rounding={'point_count':0,'bootstrap_count':0,'maximum_abs_excess':0.0}
        rows=[{'estimator':estimator,'person':person,'field':field} for estimator in estimators for person in PERSONS for field in POINT_ROWS]
        point_writer=self._writer('point',len(rows),Q,self._lineage(rows,index['coordinate_pin'],index))
        for start in range(0,Q,self.width):
            stop=min(Q,start+self.width);width=stop-start
            output=np.zeros((len(rows),width))
            masks=[]
            for scope in range(3):
                mask=[]
                for coordinate in range(start,stop):
                    channel,time=divmod(coordinate,1800);within=0<=-100000+2000*time<=3000000
                    posterior=self.posterior is not None and channel in self.posterior
                    mask.append(posterior if scope==0 else within if scope==1 else posterior and within)
                masks.append(mask)
            for person_index,person in enumerate(PERSONS):
                self.context.tick();target=targets[person]['query'].block(tuple(range(102)),start,stop)
                fit=targets[person]['fit'].block(tuple(range(1000)),start,stop)
                self._charge_numeric(1,'one complete fitting-variance coordinate block')
                moments=_fitting_moments(self.numeric,fit,self.limits,self.context)
                self.progress['fitting_variance_coordinates']+=width
                predictions=[]
                for estimator in estimators:
                    if estimator=='zero':prediction=np.zeros((102,width))
                    else:prediction=prediction_readers[estimator,person].block(tuple(range(102)),start,stop)
                    if estimator.startswith('mean/'):
                        require(np.all(prediction==moments['mean'][None,:]),'actual_mean_baseline_matches_fitting_values',estimator+'/'+person)
                    predictions.append(prediction)
                self._charge_numeric(45,'all45 point-estimator metric coordinate blocks')
                for estimator_index,prediction in enumerate(predictions):
                    values=_point_columns(self.numeric,prediction,target,moments['variance'],self.limits,self.context)
                    begin=(estimator_index*6+person_index)*len(POINT_ROWS);output[begin:begin+len(POINT_ROWS)]=values
                    self.progress['point_coordinates']+=width
                    self.progress['raw_mse_coordinates']+=width
                    self.progress['normalized_mse_coordinates_attempted']+=int(np.count_nonzero(moments['variance']>0))
                    constant_counts[estimator_index,person_index]+=int(np.count_nonzero(values[6]))
                    rounding['point_count']+=int(np.count_nonzero(values[7]));rounding['maximum_abs_excess']=max(rounding['maximum_abs_excess'],float(np.max(np.abs(values[7]))))
                    for metric,(value_row,status_row) in enumerate(((0,1),(2,3),(4,5))):
                        invalid=values[status_row]!=0
                        if np.any(invalid):
                            point_bad[estimator_index,person_index,metric]=1
                            key='%s/%s/%s'%(estimators[estimator_index],person,POINT_ROWS[value_row])
                            record=failures.setdefault(key,{'undefined_coordinates':0,'first_coordinate':None,'status_counts':{}})
                            for offset in np.flatnonzero(invalid):
                                code=str(int(values[status_row,offset]));record['status_counts'][code]=record['status_counts'].get(code,0)+1;record['undefined_coordinates']+=1
                                if record['first_coordinate'] is None:record['first_coordinate']=start+int(offset)
                        _scaled_add(point_sum,point_comp,point_scales,(estimator_index,person_index,metric),values[value_row])
                        for scope,mask in enumerate(masks):
                            selected_values=[float(values[value_row,i]) for i,take in enumerate(mask) if take]
                            if any(bool(invalid[i]) for i,take in enumerate(mask) if take):secondary_bad[estimator_index,person_index,metric,scope]=1
                            _scaled_add(secondary_sum,secondary_comp,secondary_scales,(estimator_index,person_index,metric,scope),selected_values)
                bootstrap_prediction_indices=list(range(36))+[estimators.index('reference/measured/'+self.champions[person])]
                self._charge_numeric(37*int(np.count_nonzero(multiplicity[:,person_index])),'all37 actual unique-person resample coordinate blocks')
                for draw in range(DRAWS):
                    count=int(multiplicity[draw,person_index])
                    if count==0:continue
                    self.context.tick();sampled_target=target[videos[draw]]
                    for estimator_index,prediction_index in enumerate(bootstrap_prediction_indices):
                        sampled_prediction=predictions[prediction_index][videos[draw]]
                        values,status,_,excess=_pearson_columns(self.numeric,sampled_prediction,sampled_target,self.limits,self.context)
                        self.progress['bootstrap_coordinates']+=width
                        if np.any(status):
                            boot_bad[draw,estimator_index]=1
                            name=bootstrap_ids[estimator_index]+'/'+person
                            row=self.bootstrap_failures.setdefault(name,{'undefined_coordinate_computations':0,'first_draw':draw,'first_coordinate':start+int(np.flatnonzero(status)[0]),'status_counts':{}})
                            row['undefined_coordinate_computations']+=int(np.count_nonzero(status))
                            for code in range(1,8):
                                count_code=int(np.count_nonzero(status==code))
                                if count_code:row['status_counts'][str(code)]=row['status_counts'].get(str(code),0)+count_code
                        _neumaier(boot_sum,boot_comp,(draw,estimator_index),count*math.fsum(float(v) for v in values))
                        rounding['bootstrap_count']+=int(np.count_nonzero(excess));rounding['maximum_abs_excess']=max(rounding['maximum_abs_excess'],float(np.max(np.abs(excess))))
            point_writer.append_columns(start,output)
            self.context.journal.append('protected_grading_coordinate_block',{'start':start,'stop':stop,'point_coordinates':self.progress['point_coordinates'],'bootstrap_coordinates':self.progress['bootstrap_coordinates']})
        point_descriptor=point_writer.finish()
        require(self.progress['point_coordinates']==45*6*Q and self.progress['bootstrap_coordinates']==unique*37*Q,'full_numeric_coverage')
        self._charge_numeric(1,'complete point and fixed-secondary aggregate summaries')
        point_scores={};secondary={}
        denominators=(None if self.posterior is None else len(self.posterior)*1800,127*1501,None if self.posterior is None else len(self.posterior)*1501)
        for e,estimator in enumerate(estimators):
            point_scores[estimator]={}
            secondary[estimator]={}
            for metric,name in enumerate(('pearson','mse','normalized_mse')):
                people=[None if point_bad[e,p,metric] else _scaled_mean(float(point_sum[e,p,metric]+point_comp[e,p,metric]),float(point_scales[e,p,metric]),Q) for p in range(6)]
                point_scores[estimator][name]={'persons':people,'mean':_mean_or_none(people),'aggregate_range_undefined_people':[PERSONS[p] for p in range(6) if people[p] is None and not point_bad[e,p,metric]]}
                secondary[estimator][name]={}
                for scope,label in enumerate(('literal_OP_channels','time_0_to_3_seconds_inclusive','literal_OP_and_time_0_to_3_inclusive')):
                    people=[None if denominators[scope] is None or secondary_bad[e,p,metric,scope] else _scaled_mean(float(secondary_sum[e,p,metric,scope]+secondary_comp[e,p,metric,scope]),float(secondary_scales[e,p,metric,scope]),denominators[scope]) for p in range(6)]
                    secondary[estimator][name][label]={'persons':people,'mean':_mean_or_none(people),'coordinate_count':denominators[scope],'unavailable_reason':self.posterior_reason if scope in (0,2) else None}
        champion_people=[point_scores['reference/measured/'+self.champions[p]]['pearson']['persons'][i] for i,p in enumerate(PERSONS)]
        self._charge_numeric(1,'complete paired point-contrast programme')
        effects=point_contrasts({**{e:point_scores[e]['pearson']['persons'] for e in candidate_ids()},'champion/measured':champion_people})
        bootstrap_numerator=boot_sum+boot_comp
        with np.errstate(under='ignore',over='ignore',invalid='ignore'):
            bootstrap_scores=bootstrap_numerator/(6*Q)
        aggregate_undefined=(bootstrap_numerator!=0)&(bootstrap_scores==0)
        aggregate_undefined|=~np.isfinite(bootstrap_scores)
        boot_bad|=aggregate_undefined
        self.bootstrap_aggregate_undefined_count=int(np.count_nonzero(aggregate_undefined))
        contrast_values=np.zeros((DRAWS,24));contrast_bad=np.zeros((DRAWS,24),dtype=np.uint8)
        self._charge_numeric(DRAWS,'all10000 complete24-contrast draw reductions')
        for draw in range(DRAWS):
            actual={name:None if boot_bad[draw,e] else float(bootstrap_scores[draw,e]) for e,name in enumerate(bootstrap_ids)}
            values=draw_contrasts(actual)
            for c,item in enumerate(contrast_spec()):
                value=values[item['id']]
                if value is None:contrast_bad[draw,c]=1
                else:contrast_values[draw,c]=value
        intervals={'estimators':{},'contrasts':{}}
        self._charge_numeric(62,'all61 complete conditional intervals plus the64-sign/Holm programme')
        for e,name in enumerate(bootstrap_ids):
            self.context.tick();intervals['estimators'][name]=conditional_interval([None if boot_bad[b,e] else float(bootstrap_scores[b,e]) for b in range(DRAWS)])
        for c,item in enumerate(contrast_spec()):
            self.context.tick();intervals['contrasts'][item['id']]=conditional_interval([None if contrast_bad[b,c] else float(contrast_values[b,c]) for b in range(DRAWS)])
        def write_draws(suffix,values,invalid,names):
            labels=[{'estimator_or_contrast':name,'field':field} for name in names for field in ('value','undefined')]
            writer=self._writer(suffix,len(labels),DRAWS,self._lineage(labels,self._identity({'draw_ids':list(range(DRAWS)),'generator':'NEURAL-079/prospective-CI-v1'}),index))
            for start in range(0,DRAWS,self.width):
                stop=min(DRAWS,start+self.width);block=np.zeros((len(labels),stop-start))
                for e in range(len(names)):
                    block[2*e]=np.where(invalid[start:stop,e],0.0,values[start:stop,e]);block[2*e+1]=invalid[start:stop,e]
                writer.append_columns(start,block)
            return writer.finish()
        estimator_draws=write_draws('bootstrap-estimators',bootstrap_scores,boot_bad,bootstrap_ids)
        contrast_draws=write_draws('bootstrap-contrasts',contrast_values,contrast_bad,[r['id'] for r in contrast_spec()])
        return {'schema':'n079_protected_numeric_grade_v1','point':point_scores,'point_array':point_descriptor,'point_row_order':rows,'point_status_codes':STATUS,'undefined_point_coordinates':failures,'constant_prediction_counts':constant_counts.tolist(),'rounding':rounding,'secondary_views':secondary,'secondary_rule':{'posterior':'case-sensitive O in channel or P in channel','times_microseconds':'0<=-100000+2000*time_index<=3000000; endpoints included;1501 samples/channel'},'champion':{'families':self.champions,'measured_person_pearson':champion_people,'mean_pearson':_mean_or_none(champion_people)},'contrasts':{'roster':list(contrast_spec()),'effects':effects,'intervals':intervals['contrasts'],'sign_sensitivity':sign_sensitivity(effects)},'bootstrap':{'estimators':list(bootstrap_ids),'draws':DRAWS,'estimator_array':estimator_draws,'contrast_array':contrast_draws,'estimator_intervals':intervals['estimators'],'generator':'NEURAL-079/prospective-CI-v1 SHA256 first8 big-endian rejection sampling','shared_video_vectors':True,'participant_position_count':DRAWS*6,'actual_unique_person_draw_pairs':unique,'conceptual_coordinate_correlations':37*DRAWS*6*Q,'actual_coordinate_correlations':self.progress['bootstrap_coordinates'],'reused_position_coordinate_correlations':37*(DRAWS*6-unique)*Q,'scope':SOURCE_SCOPE},'capacity':{'required_floors':self.floors,'selected':self.selected['capacity'],'owned_live_float_slots_upper':self.live_slots,'array_payload_reads':'MatrixReader block payload only; repository authentication, source/dependency, journal and OS reads remain separately admitted/observed','physical_or_whole_workload_feasibility':False},'reference_dominance':{'required_comparator':'per-person inner-selected measured R1/R2/R3 champion','primary_gain_contrast':'23','point_gain':effects['23']['mean'],'positive_point_gain':None if effects['23']['mean'] is None else effects['23']['mean']>0,'meaningful_scientific_margin':None,'SOTA_or_scientific_qualification':False},'complete_full_primary_available':all(point_scores[e]['pearson']['mean'] is not None for e in estimators),'target_release':self.target_release,'index':self.selected['index'],'report_seals_closed':36,'report_score':'separate owner rubric from actual observed evidence; no report score is accepted here'}

    def grade(self,payload):
        from n079_common import close_all,error_record
        require(not self.used,'single_grade_invocation');self.used=True;primary=None
        try:
            self.progress['phase']='index_admission';index=self._validate(self._load(payload));self._preflight(index)
            self.progress['phase']='independent_inner_selection';selection=self._selections(index);self.selection_pin=self._identity(selection)
            prediction_readers={key:self._reader(value) for key,value in sorted(self.predictions.items())}
            for candidate in index['candidates']:
                self._ordinary_bytes(candidate['report']['object'],self.selected['max_index_bytes'])
            join={'index':self.selected['index'],'index_admission':self.index_admission,'closure':index['closure'],'selection_pin':self.selection_pin,'prediction_objects_pin':self._identity([d['object'] for _,d in sorted(self.predictions.items())]),'report_objects_pin':self._identity([r['report'] for r in sorted(index['candidates'],key=lambda r:r['id'])]),'reference_fit_records':5496,'candidate_bundles':36,'native_jobs':22,'reports':36}
            self.context.journal.append('protected_grading_pre_target_join',join)
            self.progress['phase']='target_last_release';self.target_release=self.context.authority.exchange('target_last_release',join)
            self.progress['phase']='full_protected_metrics';result=self._run(index,prediction_readers)
            result['independent_selections']=selection;result['selection_pin']=self.selection_pin
            result['actual_numeric_work']=dict(self.progress)
            result['actual_numeric_work']['expected_successful_numeric_block_applications']=(5736+37*result['bootstrap']['actual_unique_person_draw_pairs'])*((Q+self.width-1)//self.width)+30106
            require(result['actual_numeric_work']['reserved_numeric_block_applications']==result['actual_numeric_work']['expected_successful_numeric_block_applications'],'complete_numeric_application_accounting')
            result['undefined_encoding']='Every array value with nonzero paired status is mathematically undefined. Its finite stored zero is an encoding placeholder, never a metric value, imputation or successful-subset contribution.'
            result['native_companion_outcomes']=index['native']
            result['native_undefined_nonfinite_ids']=[row['id'] for row in index['native'] if row['outcome']=='captured_undefined_nonfinite']
            result['native_undefined_implies_reproduction_false']=bool(result['native_undefined_nonfinite_ids'])
            result['native_superiority_or_parity_claim']=False
            result['bootstrap']['undefined_coordinate_details']=self.bootstrap_failures
            result['bootstrap']['aggregate_range_undefined_draw_estimators']=self.bootstrap_aggregate_undefined_count
            result['whole_study_scientific_qualification']='Not established by this numerical grader; native reproduction, report quality, external custody and scientific qualification remain distinct.'
            result['complete_benchmark_admitted']=False
            result['axis_custody']={'full127_name_roster_present':self.posterior_reason not in ('missing_complete_127_channel_roster','unknown_or_invalid_channel_name_admission'),'independent_exact_axis_admission_required':True,'coordinate_pin':index['coordinate_pin'],'outer_admission_hold':self.posterior_reason if self.posterior_reason in ('missing_complete_127_channel_roster','unknown_or_invalid_channel_name_admission') else None,'helper_cannot_establish_outer_admission':True}
            result['capacity']['reader_input_payload_bytes']=self.input_payload_bytes
            result['capacity']['writer_output_identity_read_bytes']=self.output_identity_read_bytes
            result['capacity']['array_payload_reads']='Known floor includes MatrixReader input blocks and MatrixWriter full output identity reads. Repository authentication, source/dependency, metadata, journal and OS reads require separate admission/observation.'
            result['input_index']=result.pop('index')
            result['input_index_observation_pin']=self.selected['index_observation_pin']
            result['capacity']['result_metadata_encoding_cap']=self.context.encoding_limits['bytes']
            self.progress['phase']='grade_index_write';descriptor=self._write_result(result)
            self.context.journal.append('protected_numeric_grade_seal',{'index':descriptor,'input_index':self.selected['index'],'progress':dict(self.progress)})
            self.progress['phase']='numeric_outputs_sealed'
            return {'index':descriptor}
        except BaseException as error:
            primary=error;error.n079_prefix=dict(self.progress)
            try:self.context.journal.append('protected_grade_failure',{'failure':error_record(error),'progress':dict(self.progress)})
            except BaseException as secondary:
                errors=getattr(error,'typed_secondary_errors',[]);errors.append({'type':type(secondary).__name__,'stage':'grade failure journal'});error.typed_secondary_errors=errors
            raise
        finally:
            close_all([('protected array reader',lambda r=reader:r.close(primary)) for reader in reversed(self.readers)]+[('protected array writer',lambda w=writer:w.close(primary)) for writer in reversed(self.writers)],primary)
