"""Source-bound primitive receipts, then one own-coefficient endpoint replay."""
import math

import numpy as np

import artifact_reader as io
import reference_math as numerical


def check(ok,message):
    if not ok:raise ValueError(message)


def numeric(value):
    check(type(value)in(int,float) and math.isfinite(value),'finite numeric scalar');return float(value)


def equal(actual,expected,*,atol=1e-6,rtol=1e-6):
    if expected is None:check(actual is None,'required null')
    elif type(expected)is bool:check(type(actual)is bool and actual==expected,'Boolean mismatch')
    elif type(expected)is int:check(type(actual)is int and actual==expected,'integer mismatch')
    elif type(expected)is float:check(abs(numeric(actual)-expected)<=atol+rtol*abs(expected),'numeric mismatch')
    elif type(expected)is str:check(type(actual)is str and actual==expected,'string mismatch')
    elif type(expected)is dict:
        check(type(actual)is dict and set(expected)<=set(actual),'required record fields')
        for key,value in expected.items():equal(actual[key],value,atol=atol,rtol=rtol)
    elif type(expected)is list:
        check(type(actual)is list and len(actual)==len(expected),'ordered list dimension')
        for a,b in zip(actual,expected):equal(a,b,atol=atol,rtol=rtol)
    else:raise ValueError('unsupported canonical type')


def keyed(rows,keys):
    check(type(rows)is list,'keyed record list');out={}
    for row in rows:
        check(type(row)is dict and all(k in row for k in keys),'record key')
        key=tuple(row[k]for k in keys);check(all(type(v)in(str,int) for v in key),'typed key')
        check(key not in out,'duplicate record');out[key]=row
    return out


def keyed_equal(actual,expected,keys,**kwargs):
    a=keyed(actual,keys);b=keyed(expected,keys);check(set(a)==set(b),'complete keyed records')
    for key in b:equal(a[key],b[key],**kwargs)


def strings(value,size):
    check(isinstance(value,np.ndarray) and value.shape==(size,) and value.dtype.kind in 'SU','string axis shape/type')
    out=[]
    for v in value.tolist():
        v=v.decode('utf-8')if type(v)is bytes else v
        check(type(v)is str and v,'axis token');out.append(v)
    return out


def axis(value,expected):
    found=strings(value,len(expected));check(len(set(found))==len(found) and set(found)==set(expected),'axis identity')
    return [found.index(v)for v in expected]


def integers(value,shape):
    check(isinstance(value,np.ndarray) and value.shape==shape and value.dtype.kind in 'iu','integer array domain')
    return value


def close_array(actual,expected):
    actual=np.asarray(actual);expected=np.asarray(expected)
    check(actual.shape==expected.shape,'array shape')
    if expected.dtype.kind=='b':check(actual.dtype.kind=='b' and np.array_equal(actual,expected),'source mask')
    elif expected.dtype.kind in 'iu':check(actual.dtype.kind in 'iu' and np.array_equal(actual,expected),'integer source receipt')
    else:
        check(actual.dtype.kind in 'iuf' and np.isfinite(actual).all(),'finite real array')
        check(np.allclose(actual,expected,atol=1e-8,rtol=1e-6),'source primitive receipt')


def metadata(actual,reference):
    equal(actual,dict(schema_version='petvt-metadata-v2',task_id='PETVT-001',status='complete',**reference['pins']))
    keyed_equal(actual['source_files'],reference['source_files'],['path'])
    expected=reference['source_observed']['persons'];found=keyed(actual['source_observed']['persons'],['subject_id'])
    check(set(found)=={(p['subject_id'],)for p in expected},'metadata source cohort')
    for person in expected:
        # Clock quantities permit integer/float numeric representations. Counts
        # and original row IDs remain exact integers rather than tolerant reals.
        view=dict(person);view['source_clock']=dict(person['source_clock'])
        for key in ('scan_start_s','injection_start_s','image_reference_s','half_life_s'):
            view['source_clock'][key]=float(view['source_clock'][key])
        equal(found[person['subject_id'],],view,atol=1e-6,rtol=0)
    check(type(actual['warnings'])is list and all(type(w)is str for w in actual['warnings']),'warning strings')
    software=actual['software'];check(type(software)is dict and all(type(software.get(k))is str and software[k]
        for k in ('python','numpy','scipy')),'software provenance strings')


def canonical_primitives(actual,reference):
    a=actual['arrays'];subjects=reference['subject_ids'];s=axis(a['subject_ids'],subjects)
    arms=list(numerical.ASSUMPTIONS);estimators=list(numerical.ESTIMATORS)
    arm=axis(a['assumption_ids'],arms);e=axis(a['estimator_ids'],estimators)
    axis(a['cortical_column_ids'],reference['method']['source']['cortical_columns'])
    frame_keys=[(sid,i)for sid in subjects for i in range(len(reference['persons'][sid]['frame_starts_s']))]
    knot_keys=[(sid,i)for sid in subjects for i in reference['persons'][sid]['knot_rows']]
    for prefix,keys in (('frame',frame_keys),('knot',knot_keys)):
        labels=strings(a[prefix+'_subject_ids'],len(keys));field='frame_indices'if prefix=='frame'else'knot_source_rows'
        ids=integers(a[field],(len(keys),)).tolist();found=list(zip(labels,ids))
        check(len(set(found))==len(keys) and set(found)==set(keys),'complete '+prefix+' row keys')
        positions={key:i for i,key in enumerate(found)};order=[positions[key]for key in keys]
        fields=('frame_start_s','frame_end_s','tissue_concentration','tissue_integral','plasma_integral','plasma_integral_defined','fit_mask')if prefix=='frame'else('knot_time_s','parent_input')
        for field in fields:
            pieces=[]
            for sid in subjects:
                p=reference['persons'][sid];key={'frame_start_s':'frame_starts_s','frame_end_s':'frame_ends_s'}.get(field,field)
                pieces.append(p[key]if key in p else p['primitive'][key])
            expected=np.concatenate(pieces,axis=0);value=a[field]
            check(value.shape==expected.shape,'primitive exact shape before slicing')
            value=value[order]
            if field in ('plasma_integral','plasma_integral_defined','parent_input'):value=value[:,arm]
            close_array(value,expected)
    shape=(len(subjects),2,2);coefs=a['coefficients'];check(coefs.shape==shape+(2,) and coefs.dtype.kind in 'iuf' and np.isfinite(coefs).all(),'coefficient array domain')
    expected_masks=np.zeros(shape,dtype=bool);ranks=np.full(shape,-1,dtype=np.int64);diag=np.zeros(shape,dtype=bool)
    scales=np.zeros(shape+(2,));singular=np.zeros_like(scales)
    for i,sid in enumerate(subjects):
        for j,assumption in enumerate(arms):
            for z,estimator in enumerate(estimators):
                m=reference['persons'][sid]['models'][assumption,estimator];idx=(i,j,z)
                expected_masks[idx]=m['coefficients']is not None
                if m['rank']is not None:ranks[idx]=m['rank']
                if m['column_scales']is not None:diag[idx]=True;scales[idx]=m['column_scales'];singular[idx]=m['singular_values']
    for field,expected in [('coefficients_defined',expected_masks),('model_rank',ranks),('model_diagnostics_defined',diag),('model_column_scales',scales),('model_singular_values',singular)]:
        check(a[field].shape==expected.shape,'model receipt shape');close_array(a[field][np.ix_(s,arm,e)],expected)
    ordered=coefs[np.ix_(s,arm,e)];check(np.allclose(ordered[~expected_masks],0,atol=1e-8,rtol=0),'masked coefficient receipt')
    return ordered


def csv_value(token,kind):
    check(type(token)is str,'CSV field type')
    if token=='':return None
    if kind=='bool':check(token in ('true','false'),'CSV Boolean');return token=='true'
    if kind=='int':
        check(token.isascii() and token.isdecimal(),'CSV count token');return int(token)
    value=float(token);check(math.isfinite(value),'CSV finite number');return value


def verify(actual,reference):
    subjects=reference['subject_ids'];check(reference['status']=='complete' and len(subjects)==7,'complete private reference')
    metadata(actual['metadata'],reference);coefs=canonical_primitives(actual,reference)
    rows=keyed(actual['rows'],['subject_id','assumption_id','estimator_id']);models={};expected_keys=set()
    for i,sid in enumerate(subjects):
        for j,assumption in enumerate(numerical.ASSUMPTIONS):
            for z,estimator in enumerate(numerical.ESTIMATORS):
                key=(sid,assumption,estimator);expected_keys.add(key);check(key in rows,'missing fit row')
                m=reference['persons'][sid]['models'][assumption,estimator];expected=dict(m)
                coeff=m['coefficients']
                if coeff is not None:
                    supported=estimator!='ma1'or numerical.denominator_supported(coeff)
                    coeff=numerical.accept_coefficients(coefs[i,j,z],coeff,estimator,supported)
                    expected.update(numerical.replay(estimator,coeff,supported))
                    expected['residual_rss'],expected['rss_status']=numerical.rss(m['design'],m['response'],coeff)
                check(rows[key]['status']==expected['status'] and rows[key]['rss_status']==expected['rss_status'],'fit status')
                target=dict(n_fit_rows=m['n_fit_rows'],rank=m['rank'],coefficient_0=None if coeff is None else float(coeff[0]),
                    coefficient_1=None if coeff is None else float(coeff[1]),vt=expected['vt'],nonpositive_vt=expected['nonpositive_vt'],residual_rss=expected['residual_rss'])
                for field,value in target.items():
                    kind='bool'if field=='nonpositive_vt'else'int'if field in ('n_fit_rows','rank')else'float'
                    equal(csv_value(rows[key][field],kind),value,
                          atol=1e-8 if field in ('coefficient_0','coefficient_1') else 1e-6)
                models[key]=expected['vt']
    check(set(rows)==expected_keys,'closed participant fit key family')
    summary=actual['summary'];equal(summary,{'schema_version':'petvt-summary-v2','status':'complete'})
    groups=[];changes=[];paired=[]
    for assumption in numerical.ASSUMPTIONS:
        for estimator in numerical.ESTIMATORS:
            groups.append(dict(assumption_id=assumption,estimator_id=estimator,**numerical.group([models[s,assumption,estimator]for s in subjects])))
    for estimator in numerical.ESTIMATORS:
        values=[]
        for sid in subjects:
            av,bv=[models[sid,arm,estimator]for arm in numerical.ASSUMPTIONS]
            value=None if av is None or bv is None else bv-av;status='unavailable_pair'if value is None else'ok'
            if value is not None and not math.isfinite(value):value=None;status='numerical_failure'
            values.append(value);changes.append(dict(subject_id=sid,estimator_id=estimator,status=status,delta_vt=value))
        paired.append(dict(estimator_id=estimator,**numerical.group(values)))
    keyed_equal(summary['groups'],groups,['assumption_id','estimator_id'])
    keyed_equal(summary['paired_changes'],changes,['subject_id','estimator_id'])
    keyed_equal(summary['paired_summaries'],paired,['estimator_id'])
    check(type(actual['findings'])is str and actual['findings'].strip(),'findings text')
    return dict(status='ok',n_subjects=7,n_records=28)


def validate(output,reference):
    result=verify(io.read_output(output),reference)
    io.inventory(__import__('pathlib').Path(output))
    return result
