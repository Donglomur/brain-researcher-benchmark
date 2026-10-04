"""Pure source-independent SOCIALBRAIN artifact validation after trusted setup.

bind_reporting_kernel consumes SHA-bound private code bytes once. The pure
verify_artifacts(actual,canonical) performs no filesystem/source reads and no
reconstruction. Canonical source quantities condition eligibility/fidelity only;
all reported endpoints are replayed from accepted cleaned series exactly once.
"""
import hashlib
import math
import re
import types

import numpy as np

from io_contract import finite_tree, need, number

SOURCE_SHA='9458c48ac61e1e8b0ee36d513ebf6e7613e889a9895747ca46d4c7bd50af8d0b'
METHOD_SHA='fb75a7cc8858de75f4269175d57c41cb70bf182409c0c68410931976672c5a12'
SCHEMA_SHA='f1388ffa06e5a04a684287724e5b86e914896980f4e0c7fa3366c8d1bd2f23c4'
KERNEL_SHA='89db8ca04db493d5f8522246200b7c8b11562856b2fb977f201748b1ebb1f4d6'
SUBJECT_IDS=tuple(f'sub-pixar{i:03d}' for i in range(1,156))
N_CHILDREN,N_ADULTS=122,33
ROI_IDS=('DMPFC','MMPFC','VMPFC','PCC','RTPJ','LTPJ','rSII','lSII','rINS','lINS','dACC','MFG')
PIPELINE_IDS=('without_GSR','with_GSR')
METRICS=('within_tom','within_pain','across_network','across_network_gsr')
_KERNEL=None
_BOUND_SHA=None


def bind_reporting_kernel(raw):
    global _KERNEL,_BOUND_SHA
    need(type(KERNEL_SHA) is str and re.fullmatch('[0-9a-f]{64}',KERNEL_SHA),'unfrozen_kernel')
    need(type(raw) is bytes and len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==KERNEL_SHA,'private_kernel_identity')
    module=types.ModuleType('_socialbrain_private_reporting')
    exec(compile(raw,'<SHA-bound SOCIALBRAIN reporting kernel>','exec'),module.__dict__)
    _KERNEL=module; _BOUND_SHA=KERNEL_SHA


def pins():
    result=dict(source_manifest_sha256=SOURCE_SHA,method_sha256=METHOD_SHA,
                output_schema_sha256=SCHEMA_SHA,reporting_kernel_sha256=KERNEL_SHA)
    need(all(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) for value in result.values()),'unfrozen_private_pins')
    return result


def fields(obj,names):
    need(type(obj) is dict and set(names)<=set(obj),'required_object_fields')
    return {name:obj[name] for name in names}


def scalar_equal(actual,expected,atol=0.,rtol=0.):
    if expected is None: need(actual is None,'required_null')
    elif type(expected) is bool: need(type(actual) is bool and actual==expected,'exact_boolean')
    elif type(expected) is int: need(type(actual) is int and actual==expected,'exact_integer')
    elif type(expected) is float:
        value=number(actual,json_mode=True)
        need(math.isfinite(expected) and abs(value-expected)<=atol+rtol*abs(expected),'numeric_tolerance')
    elif type(expected) is str: need(type(actual) is str and actual==expected,'exact_string')
    elif type(expected) is list:
        need(type(actual) is list and len(actual)==len(expected),'ordered_list')
        for a,b in zip(actual,expected): scalar_equal(a,b,atol,rtol)
    elif type(expected) is dict:
        fields(actual,expected)
        for key,value in expected.items(): scalar_equal(actual[key],value,atol,rtol)
    else: raise ValueError('invalid_canonical_type')


def keyed(rows,names):
    need(type(rows) is list,'keyed_records_list'); result={}
    for row in rows:
        values=fields(row,names); key=[]
        for name,value in values.items():
            if name in ('frame_index',): need(type(value) is int and value>=0,'record_integer_key')
            else: need(type(value) is str and value,'record_string_key')
            key.append(value)
        key=tuple(key); need(key not in result,'duplicate_record_key'); result[key]=row
    return result


def paired_records(actual,expected,keys):
    a,b=keyed(actual,keys),keyed(expected,keys)
    need(set(a)==set(b),'record_membership')
    return ((a[key],b[key]) for key in b)


def compare_records(actual,expected,keys,required,atol=0.,rtol=0.):
    for a,b in paired_records(actual,expected,keys):
        scalar_equal(fields(a,required),fields(b,required),atol,rtol)


def text_axis(value,expected_length):
    # Zero-width strings may have many logical elements without payload bytes.
    # Bound required axes before any Python-list allocation or UTF-8 decoding.
    need(isinstance(value,np.ndarray) and value.shape==(expected_length,)
         and value.dtype.kind in 'US','string_axis')
    if value.dtype.kind=='S':
        try: result=[x.decode('utf-8') for x in value.tolist()]
        except UnicodeDecodeError: raise ValueError('axis_utf8') from None
    else: result=value.tolist()
    need(all(type(x) is str and x and '\0' not in x for x in result),'literal_axis')
    return result


def axis_order(value,expected):
    values=text_axis(value,len(expected))
    need(len(values)==len(expected) and len(set(values))==len(values) and set(values)==set(expected),'axis_membership')
    return [values.index(key) for key in expected]


def numeric_array(value,shape):
    need(isinstance(value,np.ndarray) and value.dtype.kind in 'iuf' and value.shape==shape,'real_array_shape_type')
    result=np.ascontiguousarray(value,dtype=np.float64)
    need(np.isfinite(result).all(),'finite_array'); return result


def close_array(actual,expected,atol,rtol):
    expected=np.asarray(expected,dtype=np.float64)
    need(actual.shape==expected.shape and np.isfinite(expected).all(),'canonical_shape_finite')
    with np.errstate(over='ignore',invalid='ignore'):
        equal=np.abs(actual-expected)<=atol+rtol*np.abs(expected)
    need(np.all(equal),'source_primitive_tolerance')


def canonical_primitives(arrays,canonical):
    required=('subject_ids','roi_ids','pipeline_ids','frame_subject_ids','frame_indices','raw_roi',
              'global_signal','cleaned_roi','canonical_active')
    fields(arrays,required)
    # All extras have the same bounded safe finite storage contract as required arrays.
    for value in arrays.values():
        need(isinstance(value,np.ndarray) and value.ndim<=32 and value.dtype.kind in 'biufUS'
             and not value.dtype.hasobject and value.dtype.fields is None,'array_storage_type')
        if value.dtype.kind=='f': need(np.isfinite(value).all(),'nonfinite_array')
    so=axis_order(arrays['subject_ids'],SUBJECT_IDS)
    ro=axis_order(arrays['roi_ids'],ROI_IDS); po=axis_order(arrays['pipeline_ids'],PIPELINE_IDS)
    expected_frames=[(sid,i) for sid in SUBJECT_IDS for i in range(len(canonical['persons'][sid]['frame_indices']))]
    n=len(expected_frames); frame_sid=text_axis(arrays['frame_subject_ids'],n)
    frame=numeric_array(arrays['frame_indices'],(n,))
    need(len(frame_sid)==n and np.all(frame==np.floor(frame)) and np.all((frame>=0)&(frame<n)),'frame_axis')
    keys=list(zip(frame_sid,map(int,frame)))
    need(len(set(keys))==n and set(keys)==set(expected_frames),'frame_membership')
    positions={key:i for i,key in enumerate(keys)}; order=[positions[key] for key in expected_frames]
    raw=numeric_array(arrays['raw_roi'],(n,12))[order][:,ro]
    gs=numeric_array(arrays['global_signal'],(n,))[order]
    clean=numeric_array(arrays['cleaned_roi'],(n,2,12))[order][:,po][:,:,ro]
    mask=arrays['canonical_active']
    need(isinstance(mask,np.ndarray) and mask.dtype.kind=='b' and mask.shape==(len(SUBJECT_IDS),2,12),'active_mask_type_shape')
    mask=mask[so][:,po][:,:,ro]
    accepted={}; reference={}; activity={}; cursor=0
    for i,sid in enumerate(SUBJECT_IDS):
        source=canonical['persons'][sid]; length=len(source['frame_indices']); sl=slice(cursor,cursor+length); cursor+=length
        need(np.array_equal(np.asarray(source['frame_indices']),np.arange(length)),'canonical_frame_axis')
        close_array(raw[sl],source['raw_roi'],1e-5,1e-6)
        close_array(gs[sl],source['global_signal'],1e-5,1e-6)
        need(np.array_equal(mask[i],source['canonical_active']),'canonical_activity_mismatch')
        accepted[sid]=clean[sl]; reference[sid]=source['cleaned_roi']; activity[sid]=source['canonical_active']
    return accepted,reference,activity


HEADER_FIELDS=('shape','selected_affine','storage_dtype','spatial_units','temporal_units','zooms','raw_toffset',
               'raw_scl_slope','raw_scl_inter','effective_slope','effective_intercept')


def compare_header(actual,expected):
    a,b=fields(actual,HEADER_FIELDS),fields(expected,HEADER_FIELDS)
    need(type(a['storage_dtype']) is str,'header_dtype_string')
    try: dtype=np.dtype(a['storage_dtype']); want=np.dtype(b['storage_dtype'])
    except (TypeError,ValueError): raise ValueError('header_dtype') from None
    need(dtype.kind in 'iuf' and dtype.fields is None and not dtype.hasobject and dtype==want,'header_dtype')
    a=dict(a); b=dict(b); del a['storage_dtype']; del b['storage_dtype']
    scalar_equal(a,b,1e-10,1e-9)


def compare_normalization(actual,expected):
    """Compare source receipts with explicit, non-mutating maximum aliases."""
    scalar_equal(fields(actual,('dtype','operator')),fields(expected,('dtype','operator')))
    names=[name for name in ('maximum','source_maximum') if name in actual]
    need(bool(names),'normalization_source_maximum')
    values=[number(actual[name],json_mode=True) for name in names]
    need(all(value==values[0] for value in values),'normalization_alias_conflict')
    scalar_equal(values[0],float(expected['maximum']),1e-10,1e-9)
    if 'normalized_maximum' in actual:
        scalar_equal(actual['normalized_maximum'],1.,1e-10,1e-9)


def validate_metadata(actual,canonical,replay):
    fixed=dict(schema_version='socialbrain-metadata-v2',task_id='SOCIALBRAIN-001',dataset_id='ds000228',
               status='complete',**pins())
    scalar_equal(actual,fixed)
    need(type(actual.get('analysis_scope')) is str and actual['analysis_scope'].strip(),'analysis_scope')
    need(type(actual.get('warnings')) is list and all(type(x) is str for x in actual['warnings']),'warnings')
    versions=fields(actual.get('software_versions'),('python','numpy','scipy','nibabel','nilearn','scikit_learn'))
    need(all(type(value) is str and value.strip() for value in versions.values()),'software_strings')
    compare_records(actual.get('source_files'),canonical['source_files'],('path',),
        ('path','role','subject_id','size_bytes','sha256'))
    compare_records(actual.get('cohort'),canonical['cohort'],('subject_id',),
        ('subject_id','age','group','mean_fd','mean_fd_observed_count','mean_fd_missing_frame_indices'),1e-10,1e-9)
    for a,b in paired_records(actual.get('roi_definitions'),canonical['roi_definitions'],('roi_id',)):
        scalar_equal(fields(a,('roi_id','network')),fields(b,('roi_id','network')))
        scalar_equal(a.get('radius_mm'),float(b['radius_mm']))
        scalar_equal(a.get('center_mm'),list(map(float,b['center_mm'])))
    observed,wanted=actual.get('source_observed'),canonical['source_observed']
    fields(observed,('participants_column_names','template','persons','frame_alignment'))
    scalar_equal(observed['participants_column_names'],wanted['participants_column_names'])
    need(type(observed['frame_alignment']) is str and observed['frame_alignment'].strip(),'frame_alignment')
    a,b=observed['template'],wanted['template']
    scalar_equal(fields(a,('path','sha256')),fields(b,('path','sha256')),1e-10,1e-9)
    compare_normalization(a.get('normalization'),b['normalization'])
    compare_header(a.get('header'),b['header'])
    person_fields=('subject_id','bold_path','confounds_path','frame_count','confound_column_names','selected_confound_columns',
                   'excluded_confound_columns','mean_fd_sum','mean_fd_observed_count')
    for a,b in paired_records(observed['persons'],wanted['persons'],('subject_id',)):
        scalar_equal(fields(a,person_fields),fields(b,person_fields),1e-10,1e-9)
        compare_header(a.get('bold_header'),b['bold_header'])
        compare_records(a.get('missing_selected_entries'),b['missing_selected_entries'],('frame_index','column_name'),
                        ('frame_index','column_name','original_token','applied_value'))
        compare_records(a.get('roi_supports'),b['roi_supports'],('roi_id',),('roi_id','n_voxels','support_sha256'))
        scalar_equal(fields(a.get('global_support'),('n_voxels','support_sha256')),fields(b['global_support'],('n_voxels','support_sha256')))
    observed,wanted=actual.get('analysis_observed'),canonical['analysis_observed']
    fields(observed,('persons','child_motion_nuisance_rank'))
    scalar_equal(observed['child_motion_nuisance_rank'],replay['analysis_observed']['child_motion_nuisance_rank'])
    for a,b in paired_records(observed['persons'],wanted['persons'],('subject_id',)):
        for ap,bp in paired_records(a.get('pipelines'),b['pipelines'],('pipeline_id',)):
            scalar_equal(fields(ap,('pipeline_id','cleaning_rank','n_active_rois')),fields(bp,('pipeline_id','cleaning_rank','n_active_rois')))
            compare_records(ap.get('roi_activity'),bp['roi_activity'],('roi_id',),
                ('roi_id','raw_centered_l2','residual_centered_l2','activity_threshold','active'),1e-10,1e-6)


def validate_table(rows,replay):
    for actual,expected in paired_records(rows,replay['participant_rows'],('subject_id',)):
        scalar_equal(actual.get('group'),expected['group'])
        for key in ('age','mean_fd'):
            scalar_equal(number(actual.get(key)),float(expected[key]),1e-10,1e-9)
        for key in METRICS:
            status=key+'_status'; scalar_equal(actual.get(status),expected[status])
            value=actual.get(key)
            if expected[key] is None: need(type(value) is str and value=='','csv_null')
            else:
                value=number(value); need(-1<=value<=1,'metric_domain')
                scalar_equal(value,float(expected[key]),1e-6,1e-6)


def validate_results(actual,replay):
    fixed=dict(schema_version='socialbrain-results-v2',task_id='SOCIALBRAIN-001',status='complete',
               **{key:value for key,value in pins().items() if key!='reporting_kernel_sha256'})
    scalar_equal(actual,fixed)
    expected=replay['age_effects']
    for name in METRICS:
        record=fields(actual.get(name),expected[name])
        for key in ('r','motion_adjusted_rank_r'):
            if record[key] is not None: need(-1<=number(record[key],json_mode=True)<=1,'r_domain')
        for key in ('p','motion_adjusted_rank_p'):
            if record[key] is not None: need(0<=number(record[key],json_mode=True)<=1,'p_domain')
    for key in ('adult_means','adult_support'):
        need(type(actual.get(key)) is dict and set(actual[key])==set(METRICS),'metric_dictionary_membership')
    for value in actual['adult_means'].values():
        if value is not None: need(-1<=number(value,json_mode=True)<=1,'adult_mean_domain')
    scalar_equal(actual,expected,1e-6,1e-6)


def verify_artifacts(actual,canonical):
    """Pure validation; no source/private file reads and no expected endpoints."""
    expected_pins=pins()
    need(_KERNEL is not None and _BOUND_SHA==KERNEL_SHA,'kernel_not_bound')
    need(type(canonical) is dict and canonical.get('status')=='complete','canonical_complete_required')
    scalar_equal(canonical.get('pins'),expected_pins)
    need(canonical.get('subject_ids')==list(SUBJECT_IDS) and canonical.get('roi_ids')==list(ROI_IDS)
         and canonical.get('pipeline_ids')==list(PIPELINE_IDS),'canonical_axis_identity')
    need(set(canonical['persons'])==set(SUBJECT_IDS) and set(canonical['covariates'])==set(SUBJECT_IDS),'canonical_person_membership')
    required=('signal_evidence.npz','network_connectivity.csv','age_effects.json','run_metadata.json','findings.md')
    fields(actual,required)
    for name in ('age_effects.json','run_metadata.json'): finite_tree(actual[name])
    need(type(actual['findings.md']) is str and actual['findings.md'].strip(),'findings')
    accepted,reference,active=canonical_primitives(actual['signal_evidence.npz'],canonical)
    replay=_KERNEL.analyze(accepted,reference,active,canonical['covariates'],list(SUBJECT_IDS),
                          expected_children=N_CHILDREN,expected_adults=N_ADULTS)
    validate_table(actual['network_connectivity.csv'],replay)
    validate_results(actual['age_effects.json'],replay)
    validate_metadata(actual['run_metadata.json'],canonical,replay)
    return dict(status='ok',n_subjects=len(SUBJECT_IDS),n_children=N_CHILDREN,n_adults=N_ADULTS)


def validate_output_directory(output,canonical):
    """Thin I/O wrapper; source/private authority is supplied by trusted caller."""
    from io_contract import output_inventory,read_output
    before=output_inventory(output)
    result=verify_artifacts(read_output(output),canonical)
    need(before==output_inventory(output),'output_changed_during_validation')
    return result
