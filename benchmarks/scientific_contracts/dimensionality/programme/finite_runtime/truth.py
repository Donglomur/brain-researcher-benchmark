"""Source-owned generated-truth transport and stage/producer admission.

No generator, estimator or rational certificate calculation runs here. Future
qualified calls decode only the original scalar/certificate transport, check its
exact emitted-float identity, and retain the original issuer/cost lineage.
"""
from __future__ import annotations
import ast
import math
import struct
from .common import require, identity, decode, exact_keys

STAGES={'development':'training_truth','calibration':'calibration_truth','evaluation':'protected_truth'}
OBSERVATION_ROLES=frozenset({'reference_input','raw_preparation_input','training_input','calibration_input','R_input','I_input'})
OBSERVATION_OUTPUTS=frozenset({'trials','mask','row_weights','column_weights'})
RADII=((1,20),(1,10),(1,5),(7,20),(1,2),(3,4))

def prediction_input(desc):
    """Common active guard, before any lane-specific role rewriting."""
    require(desc.get('role') in OBSERVATION_ROLES,'TRUTH_OR_PRIVATE_GENERATOR_OUTPUT_IN_CASE')
    require(not desc.get('logical_output','').removeprefix('result/outputs/').startswith('private_'),
            'PRIVATE_GENERATOR_OUTPUT_IN_CASE')
    if 'prediction_origin' in desc:
        origin=desc['prediction_origin']
        exact_keys(origin,{'role','producer','descriptor_sha256'})
        require(origin['role'] in OBSERVATION_ROLES and origin['producer']==desc['producer'],
                'PREDICTION_ORIGIN_ROLE_SUBSTITUTION')
    return desc

def prediction_view(desc,role):
    prediction_input(desc)
    require(role in OBSERVATION_ROLES,'INVALID_PREDICTION_VIEW_ROLE')
    return {**desc,'role':role,'prediction_origin':{'role':desc['role'],
        'producer':desc['producer'],'descriptor_sha256':identity(desc)}}

def npy_payload(body,desc,kind):
    """Bounded, nonexecuting decoder for scalar float64 or certificate uint8 only."""
    require(type(body)is bytes and len(body)<=266240 and body[:6]==b'\x93NUMPY','TRUTH_TRANSPORT_FORMAT')
    version=body[6:8];require(version in (b'\x01\x00',b'\x02\x00'),'TRUTH_NPY_VERSION')
    width=2 if version==b'\x01\x00' else 4;start=8+width
    require(len(body)>=start,'TRUTH_NPY_TRUNCATED')
    n=int.from_bytes(body[8:start],'little');require(0<n<=4096 and start+n<=len(body),'TRUTH_NPY_HEADER_BOUND')
    try:header=ast.literal_eval(body[start:start+n].decode('ascii'))
    except (ValueError,SyntaxError,UnicodeError,TypeError) as exc:raise ValueError('invalid bounded truth transport header') from exc
    exact_keys(header,{'descr','fortran_order','shape'})
    require(header['fortran_order'] is False and type(header['shape'])is tuple,'TRUTH_NPY_LAYOUT')
    raw=body[start+n:]
    if kind=='scalar':
        require(header['descr'] in ('<f8','>f8') and header['shape']==(1,) and
                desc['dtype']=='float64' and desc['shape']==[1] and len(raw)==8,'TRUTH_SCALAR_LAYOUT')
        value=struct.unpack(('<' if header['descr']=='<f8' else '>')+'d',raw)[0]
        require(math.isfinite(value) and value>0,'TRUTH_SCALAR_DOMAIN');return value
    require(kind=='certificate' and header['descr']=='|u1' and len(header['shape'])==1 and
            type(header['shape'][0])is int and 0<header['shape'][0]<=262144 and
            header['shape'][0]==len(raw) and desc['shape']==[len(raw)] and desc['dtype']=='uint8',
            'TRUTH_CERTIFICATE_LAYOUT')
    return decode(raw,262144)

def certificate_shape(cert):
    """Validate closed identity metadata, never recalculate rational bounds."""
    fractions={'radius','analytic_trace_lower','analytic_denominator_lower','emitted_float_exact_fraction',
        'absolute_logtruth_error_bound','absolute_logtruth_error_ceiling','max_exponential_interval_width'}
    intervals={'mean_kernel','mean_squared_kernel','mean_squared_conditional_kernel',
        'trace_covariance','trace_covariance_squared','gamma_interval'}
    exact_keys(cert,fractions|intervals|{'schema','method','dimension','kernel','distribution','target',
        'intrinsic_dimension_is_not_truth','Taylor_even_upper_degree','Taylor_odd_lower_degree',
        'polynomial_terms_evaluated','polynomial_term_ceiling','sampling_or_monte_carlo_used','scientific_qualification'})
    def fraction(row):
        exact_keys(row,{'numerator','denominator'})
        for name,text in row.items():
            require(type(text)is str and 0<len(text)<=262144,'CERTIFICATE_INTEGER_TEXT')
            digits=text[1:] if name=='numerator' and text.startswith('-') else text
            require(digits and digits.isascii() and digits.isdigit() and
                    (digits=='0' or not digits.startswith('0')) and text!='-0' and
                    (name!='denominator' or digits!='0'),'CERTIFICATE_CANONICAL_INTEGER')
    for name in fractions:fraction(cert[name])
    for name in intervals:
        exact_keys(cert[name],{'lower','upper'});fraction(cert[name]['lower']);fraction(cert[name]['upper'])
    require(type(cert['dimension'])is int and cert['dimension'] in (1,2,3,5,8) and
        cert['kernel']=='0.5*exp(-squared_euclidean_distance/2)' and
        cert['distribution']=='independent uniform Euclidean balls centered at zero' and
        type(cert['Taylor_even_upper_degree'])is int and cert['Taylor_even_upper_degree']==24 and
        type(cert['Taylor_odd_lower_degree'])is int and cert['Taylor_odd_lower_degree']==25 and
        type(cert['polynomial_terms_evaluated'])is int and 0<cert['polynomial_terms_evaluated']<=3000000 and
        type(cert['polynomial_term_ceiling'])is int and cert['polynomial_term_ceiling']==3000000 and
        cert['absolute_logtruth_error_ceiling']=={'numerator':'1','denominator':'100000'} and
        cert['scientific_qualification']=='requires independent source and numerical qualification',
        'F12_CERTIFICATE_CLOSED_METHOD_IDENTITY')


class GeneratedTruth:
    def __init__(self,preparation):
        self.preparation=preparation;self.products={};self.outputs={};self.cache={};self.original_failures=[]

    def register(self,job,record):
        """Called with the actual returned Science record, never a case-supplied scalar."""
        p=self.preparation;p.meter.checkpoint('generated_truth_producer_registration')
        require(job['id'] not in self.products,'TRUTH_PRODUCER_REPLACED')
        req=record['request'];response=record['response']
        require(req['operation']==job['operation'] and req['issuer_namespace']=='trusted_preparation' and
                response['request_sha256']==identity(req) and record['product_sha256']==identity(response),
                'TRUTH_ORIGINAL_RESPONSE_SUBSTITUTION')
        require(response['source_manifest_sha256']==req['source_manifest_sha256']==p.science.source['source_manifest_sha256'] and
                response['lineage']==req['lineage'] and req['lineage']['preparation_id']==job['id'],
                'TRUTH_PRODUCER_SOURCE_OR_LINEAGE_SUBSTITUTION')
        require(req['protocol']['original_source_sha256']==job['original_source_sha256'] and
                req['protocol']['source_qualification_id']==job['source_qualification_id'],
                'TRUTH_ORIGINAL_SOURCE_SUBSTITUTION')
        require(req['protocol']=={**job['protocol'],'source_qualification_id':job['source_qualification_id'],
                'original_source_sha256':job['original_source_sha256']} and
                req['lineage']['input_identities']=={k:p.registry[v]['sha256'] for k,v in job['inputs'].items()},
                'TRUTH_ORIGINAL_REQUEST_INPUT_SUBSTITUTION')
        if job['operation']=='generator.world':
            require(req['parameters']==job['parameters'],'TRUTH_GENERATOR_PARAMETER_SUBSTITUTION')
            context=job['truth_context'];exact_keys(context,{'world_id','family','cell','cell_index','stage','target_ids'})
            require(context==req['lineage']['truth_context'] and context['stage']==req['protocol']['generation_stage'] and
                    context['family']==job['parameters']['family'] and context['cell_index']==job['parameters']['cell_index'] and
                    context['stage'] in STAGES and type(context['world_id'])is str and context['world_id'] and
                    type(context['target_ids'])is list and context['target_ids'] and
                    len(set(context['target_ids']))==len(context['target_ids']), 'GENERATOR_TRUTH_CONTEXT_SUBSTITUTION')
            require(type(context['cell_index'])is int and 0<=context['cell_index']<6 and
                    type(context['cell']) in (str,int) and all(type(x)is str and x for x in context['target_ids']),
                    'GENERATOR_CONTEXT_SCALAR_TYPES')
        require(len(self.products)<65536,'FINITE_TRUTH_PRODUCER_BOUND')
        # Keep original returned record strongly, including completion/receipt.
        self.products[job['id']]={'job':job,'record':record,'record_identity':identity(record)}
        for logical,key in job['output_bindings'].items():
            require(key not in self.outputs,'TRUTH_OUTPUT_ID_REUSED')
            desc=p.registry[key]
            require(desc in response['artifacts'] and desc['logical_output']==logical,
                    'TRUTH_OUTPUT_NOT_IN_ORIGINAL_RESPONSE')
            self.outputs[key]={'job':job['id'],'descriptor':dict(desc)}

    def _record(self,job_id):
        require(job_id in self.products,'MISSING_ORIGINAL_GENERATOR_PRODUCT',job_id)
        product=self.products[job_id]
        require(identity(product['record'])==product['record_identity'],'ORIGINAL_GENERATOR_PRODUCT_CHANGED')
        return product

    def _observation(self,key,root,trail=(),seen=None):
        p=self.preparation;p.meter.checkpoint('truth_original_input_ancestry')
        seen=set() if seen is None else seen
        require(len(seen)<4096,'TRUTH_INPUT_ANCESTRY_BOUND')
        require(len(trail)<64 and key not in trail and key in self.outputs,'UNBOUND_GENERATED_INPUT_ANCESTRY')
        if key in seen:return
        seen.add(key)
        origin=self.outputs[key];desc=p.registry[key]
        require(desc==origin['descriptor'],'GENERATED_INPUT_DESCRIPTOR_REPLACED');prediction_input(desc)
        product=self._record(origin['job']);job=product['job']
        if origin['job']==root:
            require(desc['logical_output'].removeprefix('result/outputs/') in OBSERVATION_OUTPUTS,
                    'PRIVATE_GENERATOR_OUTPUT_AS_OBSERVATION');return
        require(job['operation']=='preparation.transform' and job['inputs'] and len(job['inputs'])<=256,
                'UNBOUND_GENERATED_CASE_TRANSFORM')
        require(product['record']['request']['lineage']['input_identities']==
                {k:p.registry[v]['sha256'] for k,v in job['inputs'].items()},'GENERATED_TRANSFORM_INPUT_CHANGED')
        for parent in job['inputs'].values():self._observation(parent,root,trail+(key,),seen)

    def _read(self,desc,stage,kind,access):
        p=self.preparation;p.meter.checkpoint('before_generated_truth_transport')
        if stage=='evaluation':
            require(access is not None,'EVALUATION_TRUTH_BEFORE_TARGET_LAST')
            require(access.plan is p.plan and access.store is p.science.store,'TRUTH_ACCESS_OWNER_SUBSTITUTION')
            access.check('before_generated_'+kind+'_body')
        role=STAGES[stage] if kind=='scalar' or stage=='evaluation' else STAGES[stage]+'_certificate'
        require(desc['role']==role and 0<desc['bytes']<=(4200 if kind=='scalar' else 266240),
                'TRUTH_STAGE_OR_EXTENT_SUBSTITUTION')
        body=p.science.store.read(desc,{role})
        p.meter.checkpoint('before_generated_truth_transport_decode')
        value=npy_payload(body,desc,kind)
        p.meter.checkpoint('after_generated_truth_transport_decode');return value

    def _scalar(self,job_id,stage,access):
        p=self.preparation;product=self._record(job_id);job=product['job'];r=product['record']
        require(job['operation']=='generator.world' and job['truth_context']['stage']==stage,
                'TRUTH_GENERATION_STAGE_SUBSTITUTION')
        if stage=='evaluation':
            require(access is not None,'EVALUATION_TRUTH_BEFORE_TARGET_LAST')
            require(access.plan is p.plan and access.store is p.science.store,'TRUTH_ACCESS_OWNER_SUBSTITUTION')
            access.check('generated_truth_cached_or_new_use')
        if job_id in self.cache:return self.cache[job_id]
        outputs={d['logical_output']:d for d in r['response']['artifacts']}
        scalar=outputs['result/outputs/private_truth'];value=self._read(scalar,stage,'scalar',access)
        certificate=outputs.get('result/outputs/private_truth_certificate')
        if job['parameters']['family']=='F12':
            require(certificate is not None,'F12_CERTIFICATE_MISSING')
            cert=self._read(certificate,stage,'certificate',access);certificate_shape(cert);params=job['parameters']
            cell=params['cell_index'];require(type(cell)is int and 0<=cell<6,'F12_CELL_SUBSTITUTION')
            numerator,denominator=value.as_integer_ratio()
            require(cert['schema']=='finite_F12_rational_population_truth_v1' and
                    cert['method']=='F12_centered_gaussian_ball_exact_moment_Taylor24_25_v1' and
                    cert['dimension']==params['rank'] and cert['radius']=={'numerator':str(RADII[cell][0]),'denominator':str(RADII[cell][1])} and
                    cert['emitted_float_exact_fraction']=={'numerator':str(numerator),'denominator':str(denominator)} and
                    cert['target']=='finite_radius_centered_kernel_population_participation_ratio' and
                    cert['intrinsic_dimension_is_not_truth'] is True and
                    cert['sampling_or_monte_carlo_used'] is False,
                    'F12_SCALAR_CERTIFICATE_WORLD_SUBSTITUTION')
        else:require(certificate is None,'UNEXPECTED_TRUTH_CERTIFICATE')
        lineage={'schema':'finite_generated_scalar_truth_lineage_v1','preparation_id':job_id,
            'context':job['truth_context'],'generator_parameters_sha256':identity(job['parameters']),
            'original_source_sha256':job['original_source_sha256'],
            'scientific_source_sha256':r['request']['source_manifest_sha256'],
            'original_product_sha256':r['product_sha256'],'original_process_receipt':r['process_receipt'],
            'original_completion':r['completion'],'truth_descriptor':scalar,'certificate_descriptor':certificate}
        # Adoption precedes fallible journal work; no retry erases a failed attempt.
        self.cache[job_id]={'truth':value,'lineage':lineage}
        try:p.journal.append('GENERATED_TRUTH_MATERIALIZED',{
            'preparation_id':job_id,'generation_stage':stage,'lineage_sha256':identity(lineage),
            'original_record_sha256':product['record_identity'],
            'truth_descriptor':scalar,'certificate_descriptor':certificate})
        except BaseException as exc:
            self.original_failures.append((job_id,exc));raise
        return self.cache[job_id]

    def materialize(self,case,stage,*,access=None):
        p=self.preparation;p.meter.checkpoint('generated_truth_case_admission')
        require(not self.original_failures,'ORIGINAL_TRUTH_MATERIALIZATION_FAILURE')
        binding=case['truth_binding'];exact_keys(binding,{'preparation_id','generation_stage'})
        require(binding['generation_stage']==stage and stage in STAGES,'TRUTH_CASE_STAGE_SUBSTITUTION')
        product=self._record(binding['preparation_id']);context=product['job']['truth_context']
        require(case['world_id']==context['world_id'] and case['family']==context['family'] and
                type(case['cell'])is type(context['cell']) and case['cell']==context['cell'] and case['target_identity'] in context['target_ids'],
                'TRUTH_CASE_WORLD_OR_TARGET_SUBSTITUTION')
        arrays=p.case_arrays(case)
        seen=set()
        for key in case['input_ids'].values():self._observation(key,binding['preparation_id'],seen=seen)
        value=self._scalar(binding['preparation_id'],stage,access)
        if 'public_truth' in case:
            require(stage!='evaluation' and type(case['public_truth']) in (int,float) and
                    float(case['public_truth']).hex()==value['truth'].hex(),'SUPPLIED_PUBLIC_TRUTH_SUBSTITUTION')
        p.meter.checkpoint('after_generated_truth_case_admission')
        return {**value,'case_identity':identity({'case_id':case['case_id'],'input_sha256':case['input_sha256'],
            'target_identity':case['target_identity'],'binding':binding}), 'input_descriptors':arrays}

    def expected(self,original,case,stage,*,access=None):
        value=self.materialize(case,stage,access=access)
        joins={'case_id':case['case_id'],'world_id':case['world_id'],'family':case['family'],
               'cell':case['cell'],'view':case['view'],'input_identity':case['input_sha256'],
               'target_identity':case['target_identity']}
        require(all(original.get(k)==v for k,v in joins.items()),'SCALAR_TARGET_CASE_JOIN_SUBSTITUTION')
        if 'truth' in original:
            require(type(original['truth']) in (int,float) and float(original['truth']).hex()==value['truth'].hex(),
                    'SUPPLIED_SCALAR_TRUTH_SUBSTITUTION')
        return {**original,**joins,'truth':value['truth']}

    def label(self,key,stage):
        require(stage in {'development','calibration'} and key in self.outputs,'UNISSUED_PUBLIC_LABEL')
        origin=self.outputs[key];desc=self.preparation.registry[key]
        require(desc==origin['descriptor'] and desc['logical_output']=='result/outputs/private_truth',
                'WRONG_PUBLIC_LABEL_PRODUCT')
        self._scalar(origin['job'],stage,None)
        require(not self.original_failures,'ORIGINAL_TRUTH_MATERIALIZATION_FAILURE')
        return desc


def validate_generator_job(job):
    context=job['truth_context'];exact_keys(context,{'world_id','family','cell','cell_index','stage','target_ids'})
    require(context['stage'] in STAGES and context['stage']==job['protocol']['generation_stage'] and
        context['family']==job['parameters']['family'] and type(context['cell_index'])is int and
        0<=context['cell_index']<6 and context['cell_index']==job['parameters']['cell_index'] and
        type(context['world_id'])is str and 0<len(context['world_id'])<=512 and
        type(context['cell']) in (str,int) and type(context['target_ids'])is list and
        0<len(context['target_ids'])<=256 and all(type(x)is str and 0<len(x)<=512 for x in context['target_ids']) and
        len(set(context['target_ids']))==len(context['target_ids']), 'INVALID_PRESEALED_GENERATOR_TRUTH_CONTEXT')


def validate_truth_graph(data):
    """Finite metadata preflight; no arrays/certificates/target bodies are opened."""
    jobs=data['preparation_P02']+data['preparation_P06']
    generated={j['id']:j for j in jobs if j['operation']=='generator.world'}
    require(len({j['id'] for j in jobs})==len(jobs) and len(generated)<=65536,'FINITE_GENERATOR_GRAPH_REQUIRED')
    for job in generated.values():validate_generator_job(job)
    cases=[]
    for pools in data['reference_development'].values():
        for rows in pools.values():cases.extend((case,'development') for case in rows)
    for rows in data['reference_calibration'].values():cases.extend((case,'calibration') for case in rows)
    for rows in data['participant_calibration'].values():cases.extend((case,'calibration') for case in rows)
    cases.extend((case,'evaluation') for case in data['I_cases'] if case['kind']=='known_truth')
    seen={}
    for case,stage in cases:
        binding=case['truth_binding'];exact_keys(binding,{'preparation_id','generation_stage'})
        require(binding['preparation_id'] in generated and binding['generation_stage']==stage,'UNPLANNED_GENERATED_CASE')
        job=generated[binding['preparation_id']];context=job['truth_context']
        require(context['stage']==job['protocol']['generation_stage']==stage and
                context['world_id']==case['world_id'] and context['family']==case['family']==job['parameters']['family'] and
                context['cell']==case['cell'] and context['cell_index']==job['parameters']['cell_index'] and
                case['target_identity'] in context['target_ids'],'PLANNED_TRUTH_CASE_SUBSTITUTION')
        if case['case_id'] in seen:require(seen[case['case_id']]==(stage,identity(case)),'PUBLIC_CASE_ALIAS_CHANGED')
        seen[case['case_id']]=(stage,identity(case))
    return {'generator_worlds':len(generated),'distinct_truth_cases':len(seen),
        'additional_materialization_read_capacity':sum(4201+(266241 if j['parameters']['family']=='F12' else 0)
            for j in generated.values()),'max_simultaneous_certificate_decode_bytes':266240,
        'cache_world_bound':65536,'source_only_preflight':True}
