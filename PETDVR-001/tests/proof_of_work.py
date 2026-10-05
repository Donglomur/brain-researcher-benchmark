"""Complete fixed-window/source validation; no preferred result or prose gate."""
import csv
from decimal import Decimal,InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import numpy as np

PIPELINE='petdvr-fixed-window-reference-logan-v2'
MANIFEST_SHA='9ca371309a1a5b5e8ebbc80b5c40d1b766bff666774b9f243f6cc27ca1def6a6'
METHOD_SHA='f82719c34120a87a0a2143294a45e1f9db115a7f83afe40d0168e13e4dab3d69'
TARGETS=['highbinding','left_thalamus','right_thalamus','left_caudate','right_caudate','left_putamen','right_putamen']
KEYS={'source_frames.csv':('subject','session','frame_index'),
      'graph_points.csv':('subject','session','target','frame_index'),
      'window_fits.csv':('subject','session','target','end_policy','start_min'),
      'fit_points.csv':('subject','session','target','end_policy','start_min','frame_index')}
STRINGS={'subject','session','target','end_policy','graph_status','ratio_status','fit_status','r_squared_status',
         'ratio_cv_status','ratio_trend_status','point_status'}
INTS={'frame_index','start_min','n_window','n_fit','n_ratio','first_window_frame','last_window_frame','first_fit_frame','last_fit_frame'}
BOOLS={'graph_valid','in_fit'}
TIMES={'frame_start_s','frame_end_s','frame_duration_s','frame_mid_s','requested_end_s','actual_window_start_s',
       'actual_window_end_s','actual_fit_first_mid_s','actual_fit_last_mid_s'}
GRAPH={'integral_target_bq_min_per_ml','integral_reference_bq_min_per_ml','x_min','y_min','target_over_reference','reference_over_target'}
MOMENTS={'Sxx_min2','Sxy_min2','Syy_min2'}

def require(value,message):
    if not value:raise AssertionError(message)

def number(value,label='number'):
    require(not isinstance(value,(bool,np.bool_)) and isinstance(value,(str,int,float,np.integer,np.floating)),f'{label}: invalid numeric type')
    try:result=float(value)
    except (ValueError,TypeError,OverflowError) as exc:raise AssertionError(f'{label}: invalid numeric') from exc
    require(math.isfinite(result),f'{label}: nonfinite numeric')
    return result

def integer(value,label='integer'):
    require(not isinstance(value,(bool,np.bool_)),f'{label}: boolean integer')
    try:result=Decimal(str(value).strip())
    except (InvalidOperation,ValueError) as exc:raise AssertionError(f'{label}: invalid integer') from exc
    require(result.is_finite() and result==result.to_integral_value(),f'{label}: noninteger')
    return int(result)

def boolean(value):
    if isinstance(value,bool):return value
    if str(value).lower() in ('true','false'):return str(value).lower()=='true'
    value=integer(value);require(value in (0,1),'Invalid boolean');return bool(value)

def read_json(path):
    def constant(value):raise AssertionError(f'Nonfinite JSON {value}')
    def pairs(items):
        out={}
        for key,value in items:
            require(key not in out,'Duplicate JSON key');out[key]=value
        return out
    return json.loads(Path(path).read_text(),parse_constant=constant,object_pairs_hook=pairs)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def tol(field):
    if field in TIMES:return 1e-9,0
    if field in TARGETS or field=='reference':return 1e-6,1e-8
    if field in GRAPH:return 1e-7,1e-8
    if field in MOMENTS:return 1e-10,1e-8
    if field=='rank_threshold_min2':return 0,1e-8
    return 1e-7,1e-7

def uncertainty(field,reference):
    atol,rtol=tol(field);return atol+rtol*abs(number(reference))

def close(value,reference,field):
    value=number(value,field);reference=number(reference,field)
    require(abs(value-reference)<=uncertainty(field,reference),f'{field}: source numeric mismatch')

def parse(field,value):
    require(value is not None,'Missing CSV value');value=value.strip()
    if field in STRINGS:return value
    if value=='':return None
    if field in INTS:return integer(value,field)
    if field in BOOLS:return boolean(value)
    return number(value,field)

def keyed(rows,keys):
    out={}
    for row in rows:
        require(isinstance(row,dict) and set(keys)<=set(row),'Missing record identity')
        key=tuple(integer(row[k],k) if k in INTS else row[k] for k in keys)
        require(key not in out,'Duplicate identity');out[key]=row
    return out

def read_table(path,fields,keys):
    with Path(path).open(newline='') as handle:
        reader=csv.DictReader(handle)
        require(reader.fieldnames and len(reader.fieldnames)==len(set(reader.fieldnames)),'Missing/duplicate CSV headers')
        require(set(fields)<=set(reader.fieldnames),'Missing CSV columns')
        rows=[]
        for row in reader:
            require(None not in row,'Malformed CSV width')
            rows.append({field:parse(field,row[field]) for field in fields})
    return keyed(rows,keys)

def match_table(actual,expected,name):
    require(set(actual)==set(expected),f'{name}: incomplete or wrong source membership')
    for key,row in expected.items():
        for field,ref in row.items():
            value=actual[key][field]
            if ref is None:require(value is None,f'{name}.{field}: undefined must be blank')
            elif field in STRINGS|INTS|BOOLS:require(type(value)==type(ref) and value==ref,f'{name}.{field}: category/source mismatch')
            else:close(value,ref,field)

def recursive(actual,expected,label,closed=True,numeric=False):
    if isinstance(expected,dict):
        require(isinstance(actual,dict) and set(expected)<=set(actual),f'{label}: missing object keys')
        if closed:require(set(actual)==set(expected),f'{label}: extra scientific keys')
        for key in expected:recursive(actual[key],expected[key],key,closed=closed,numeric=numeric)
    elif isinstance(expected,list):
        require(isinstance(actual,list) and len(actual)==len(expected),f'{label}: wrong list shape')
        for a,b in zip(actual,expected):recursive(a,b,label,closed=closed,numeric=numeric)
    elif isinstance(expected,bool):require(type(actual) is bool and actual==expected,f'{label}: boolean mismatch')
    elif isinstance(expected,int):
        require(isinstance(actual,(int,float)) and not isinstance(actual,bool),f'{label}: numeric JSON type')
        require(integer(actual,label)==expected,f'{label}: count mismatch')
    elif isinstance(expected,float):
        require(isinstance(actual,(int,float)) and not isinstance(actual,bool),f'{label}: numeric JSON type')
        if numeric:close(actual,expected,label)
        else:require(number(actual)==expected,f'{label}: changed method/source value')
    else:require(type(actual)==type(expected) and actual==expected,f'{label}: value mismatch')

def match_summary(actual,reference):
    for field in reference:
        require(field in actual,f'Missing summary {field}')
        if field in ('paired_changes','group_windows'):
            keys=('subject','target','end_policy','start_min') if field=='paired_changes' else ('target','end_policy','start_min')
            a,b=keyed(actual[field],keys),keyed(reference[field],keys)
            require(set(a)==set(b),f'{field}: incomplete summary support')
            for key in b:
                require(set(b[key])<=set(a[key]),f'{field}: missing required record fields')
                selected={k:a[key].get(k) for k in b[key]}
                for ordered in ('defined_scans','represented_subjects','defined_pair_subjects'):
                    if ordered in selected:
                        require(isinstance(selected[ordered],list),f'{ordered}: expected list')
                        selected[ordered]=sorted(selected[ordered])
                recursive(selected,b[key],field,numeric=True)
        elif field in ('targets','start_min','end_policies'):
            require(isinstance(actual[field],list),'Summary identity list')
            if field=='start_min':require(sorted(integer(v) for v in actual[field])==sorted(reference[field]),'Start grid')
            else:require(sorted(actual[field])==sorted(reference[field]),f'{field}: membership')
        else:recursive(actual[field],reference[field],field)

def match_metadata(actual,reference):
    for field,expected in reference.items():
        require(field in actual,f'Missing metadata {field}')
        if field=='software_versions':
            versions=actual[field]
            require(isinstance(versions,dict) and versions and all(isinstance(k,str) and k.strip() and isinstance(v,str) and v.strip() for k,v in versions.items()),'Invalid software provenance')
        elif field=='source_observed':
            require(isinstance(actual[field],dict) and 'scans' in actual[field],'Missing measured scan metadata')
            a=keyed(actual[field]['scans'],('subject','session'));b=keyed(expected['scans'],('subject','session'))
            require(set(a)==set(b),'Metadata scan membership')
            for key,row in b.items():
                require(set(row)<=set(a[key]),'Missing source observation fields')
                recursive({f:a[key][f] for f in row},row,'source_observed',numeric=False)
        else:recursive(actual[field],expected,field)

def arithmetic(actual,calculated,budget,label):
    require(math.isfinite(calculated) and abs(number(actual)-calculated)<=budget+1e-12,f'{label}: inconsistent submitted arithmetic')

def validate_algebra(tables,reference,summary):
    frames=tables['source_frames.csv'];graphs=tables['graph_points.csv'];fits=tables['window_fits.csv'];points=tables['fit_points.csv']
    refs=reference['source_frames.csv'];rg=reference['graph_points.csv'];rf=reference['window_fits.csv'];rp=reference['fit_points.csv']
    # Source-bound cumulative areas preserve every earlier frame, including zeros.
    for key,graph in graphs.items():
        subject,session,target,index=key;frame=frames[subject,session,index];rframe=refs[subject,session,index]
        for channel,field in ((target,'integral_target_bq_min_per_ml'),('reference','integral_reference_bq_min_per_ml')):
            terms=[];budget=uncertainty(field,rg[key][field])
            for j in range(index+1):
                source=frames[subject,session,j];rs=refs[subject,session,j];weight=.5 if j==index else 1.
                duration=source['frame_duration_s']/60;err_duration=uncertainty('frame_duration_s',rs['frame_duration_s'])/60
                terms.append(weight*source[channel]*duration)
                budget+=weight*(abs(duration)*uncertainty(channel,rs[channel])+abs(source[channel])*err_duration)
            arithmetic(graph[field],math.fsum(terms),budget,'Frame-average integral')
        # Product relations remain meaningful when a permitted tiny denominator rounds0.
        relations=[]
        if rg[key]['graph_status']=='ok':
            relations.extend([('x_min',target,'integral_reference_bq_min_per_ml'),('y_min',target,'integral_target_bq_min_per_ml')])
            ratio=graph['reference_over_target'];er=uncertainty('reference_over_target',rg[key]['reference_over_target']);ed=uncertainty(target,rframe[target])
            budget=uncertainty('reference',rframe['reference'])+abs(frame[target])*er+abs(ratio)*ed+er*ed
            arithmetic(frame['reference'],ratio*frame[target],budget,'Reciprocal concentration ratio')
        if rg[key]['ratio_status']=='ok':
            ratio=graph['target_over_reference'];er=uncertainty('target_over_reference',rg[key]['target_over_reference']);ed=uncertainty('reference',rframe['reference'])
            budget=uncertainty(target,rframe[target])+abs(frame['reference'])*er+abs(ratio)*ed+er*ed
            arithmetic(frame[target],ratio*frame['reference'],budget,'Target/reference ratio')
        for coordinate,denominator,numerator in relations:
            ec=uncertainty(coordinate,rg[key][coordinate]);ed=uncertainty(denominator,rframe[denominator])
            budget=uncertainty(numerator,rg[key][numerator])+abs(frame[denominator])*ec+abs(graph[coordinate])*ed+ec*ed
            arithmetic(graph[numerator],graph[coordinate]*frame[denominator],budget,'Graph coordinate')
    for key,row in points.items():
        if not rp[key]['in_fit']:continue
        fit=fits[key[:-1]];rfit=rf[key[:-1]];gkey=key[:3]+(key[-1],);graph=graphs[gkey]
        es=uncertainty('logan_slope',rfit['logan_slope']);ex=uncertainty('x_min',rg[gkey]['x_min'])
        budget=uncertainty('predicted_y_min',rp[key]['predicted_y_min'])+abs(graph['x_min'])*es+abs(fit['logan_slope'])*ex+es*ex+uncertainty('intercept_min',rfit['intercept_min'])
        arithmetic(row['predicted_y_min'],fit['logan_slope']*graph['x_min']+fit['intercept_min'],budget,'Fit prediction')
        budget=uncertainty('residual_y_min',rp[key]['residual_y_min'])+uncertainty('predicted_y_min',rp[key]['predicted_y_min'])+uncertainty('y_min',rg[gkey]['y_min'])
        arithmetic(row['residual_y_min'],row['predicted_y_min']-graph['y_min'],budget,'Signed residual')
    for key,fit in fits.items():
        members=[p for p in points if p[:-1]==key]
        eligible=[p for p in members if rp[p]['graph_valid']]
        if eligible:
            gkeys=[p[:3]+(p[-1],) for p in eligible]
            x=np.array([graphs[p]['x_min'] for p in gkeys]);y=np.array([graphs[p]['y_min'] for p in gkeys])
            ex=np.array([uncertainty('x_min',rg[p]['x_min']) for p in gkeys]);ey=np.array([uncertainty('y_min',rg[p]['y_min']) for p in gkeys])
            dx=x-np.mean(x);dy=y-np.mean(y);edx=ex+np.mean(ex);edy=ey+np.mean(ey)
            calculations={'Sxx_min2':(float(np.sum(dx*dx)),float(np.sum(2*np.abs(dx)*edx+edx*edx))),
                          'Sxy_min2':(float(np.sum(dx*dy)),float(np.sum(np.abs(dx)*edy+np.abs(dy)*edx+edx*edy))),
                          'Syy_min2':(float(np.sum(dy*dy)),float(np.sum(2*np.abs(dy)*edy+edy*edy)))}
            for field,(value,error) in calculations.items():
                arithmetic(fit[field],value,uncertainty(field,rf[key][field])+error,'Centered graph moment')
            rank=1e-24*max(1,float(np.sum(x*x)))
            rank_error=1e-24*float(np.sum(2*np.abs(x)*ex+ex*ex))
            # No generic absolute epsilon is allowed to hide this tiny diagnostic.
            require(abs(fit['rank_threshold_min2']-rank)<=uncertainty('rank_threshold_min2',rf[key]['rank_threshold_min2'])+rank_error,'Rank-threshold arithmetic')
        ratio_keys=[p[:3]+(p[-1],) for p in members if rg[p[:3]+(p[-1],)]['ratio_status']=='ok']
        if ratio_keys:
            values=[graphs[p]['target_over_reference'] for p in ratio_keys]
            budget=uncertainty('ratio_mean',rf[key]['ratio_mean'])+sum(uncertainty('target_over_reference',rg[p]['target_over_reference']) for p in ratio_keys)/len(values)
            arithmetic(fit['ratio_mean'],math.fsum(values)/len(values),budget,'Ratio mean')
            max_error=max(uncertainty('target_over_reference',rg[p]['target_over_reference']) for p in ratio_keys)
            for field,op in (('ratio_min',min),('ratio_max',max)):
                arithmetic(fit[field],op(values),uncertainty(field,rf[key][field])+max_error,'Ratio extrema')
            difference=np.asarray(values)-fit['ratio_mean']
            errors=np.array([uncertainty('target_over_reference',rg[p]['target_over_reference']) for p in ratio_keys])+uncertainty('ratio_mean',rf[key]['ratio_mean'])
            sd=fit['ratio_population_sd'];esd=uncertainty('ratio_population_sd',rf[key]['ratio_population_sd'])
            budget=2*abs(sd)*esd+esd*esd+float(np.mean(2*np.abs(difference)*errors+errors*errors))
            arithmetic(sd*sd,float(np.mean(difference*difference)),budget,'Population ratio SD')
            if rf[key]['ratio_cv_status']=='ok':
                cv=fit['ratio_cv'];ecv=uncertainty('ratio_cv',rf[key]['ratio_cv']);em=uncertainty('ratio_mean',rf[key]['ratio_mean'])
                arithmetic(sd,cv*abs(fit['ratio_mean']),esd+abs(fit['ratio_mean'])*ecv+abs(cv)*em+ecv*em,'Ratio CV denominator')
            if rf[key]['ratio_trend_status']=='ok':
                times=np.array([frames[p[0],p[1],p[3]]['frame_mid_s']/60 for p in ratio_keys]);dt=times-np.mean(times)
                numerator=float(np.sum(dt*difference));denominator=float(np.sum(dt*dt));slope=fit['ratio_time_slope_per_min']
                et=2e-9/60;en=float(np.sum(np.abs(dt)*errors+np.abs(difference)*et+errors*et));ed=float(np.sum(2*np.abs(dt)*et+et*et))
                es=uncertainty('ratio_time_slope_per_min',rf[key]['ratio_time_slope_per_min'])
                arithmetic(numerator,slope*denominator,en+abs(denominator)*es+abs(slope)*ed+es*ed,'Ratio temporal trend')
        if rf[key]['fit_status']!='ok':continue
        residual=[points[p]['residual_y_min'] for p in eligible]
        errors=[uncertainty('residual_y_min',rp[p]['residual_y_min']) for p in eligible]
        budget=uncertainty('sse_min2',rf[key]['sse_min2'])+sum(2*abs(r)*e+e*e for r,e in zip(residual,errors))
        arithmetic(fit['sse_min2'],math.fsum(r*r for r in residual),budget,'Residual SSE')
        rmse=fit['rmse_min'];er=uncertainty('rmse_min',rf[key]['rmse_min'])
        arithmetic(fit['sse_min2'],rmse*rmse*len(eligible),uncertainty('sse_min2',rf[key]['sse_min2'])+len(eligible)*(2*abs(rmse)*er+er*er),'RMSE divisor')
        if rf[key]['r_squared_status']=='ok':
            ey=uncertainty('Syy_min2',rf[key]['Syy_min2']);er2=uncertainty('r_squared',rf[key]['r_squared'])
            budget=uncertainty('sse_min2',rf[key]['sse_min2'])+abs(1-fit['r_squared'])*ey+abs(fit['Syy_min2'])*er2+ey*er2
            arithmetic(fit['sse_min2'],(1-fit['r_squared'])*fit['Syy_min2'],budget,'R-squared denominator')
    pairs=keyed(summary['paired_changes'],('subject','target','end_policy','start_min'))
    for key,pair in pairs.items():
        subject,target,end,start=key
        for session,field in (('ses-baseline','baseline_slope'),('ses-rescan','rescan_slope')):
            fk=(subject,session,target,end,start)
            if rf[fk]['fit_status']=='ok':
                budget=uncertainty(field,rf[fk]['logan_slope'])+uncertainty('logan_slope',rf[fk]['logan_slope'])
                arithmetic(pair[field],fits[fk]['logan_slope'],budget,'Paired source slope')
        if pair['pair_status']=='ok':
            budget=sum(uncertainty(f,pair[f]) for f in ('rescan_minus_baseline','rescan_slope','baseline_slope'))
            arithmetic(pair['rescan_minus_baseline'],pair['rescan_slope']-pair['baseline_slope'],budget,'Signed paired change')
    for group in summary['group_windows']:
        suffix=(group['target'],group['end_policy'],integer(group['start_min']))
        selected=[k for k in fits if k[2:]==suffix and rf[k]['fit_status']=='ok']
        if selected:
            budget=uncertainty('mean_logan_slope',group['mean_logan_slope'])+sum(uncertainty('logan_slope',rf[k]['logan_slope']) for k in selected)/len(selected)
            arithmetic(group['mean_logan_slope'],math.fsum(fits[k]['logan_slope'] for k in selected)/len(selected),budget,'Equal-scan mean')
        pk=[k for k in pairs if k[1:]==suffix and pairs[k]['pair_status']=='ok']
        if pk:
            budget=uncertainty('mean_rescan_minus_baseline',group['mean_rescan_minus_baseline'])+sum(uncertainty('rescan_minus_baseline',pairs[k]['rescan_minus_baseline']) for k in pk)/len(pk)
            arithmetic(group['mean_rescan_minus_baseline'],math.fsum(pairs[k]['rescan_minus_baseline'] for k in pk)/len(pk),budget,'Equal-pair signed mean')

def load_reference(path=None):
    path=Path(path) if path else Path(__file__).with_name('reference.npz')
    with np.load(path,allow_pickle=False) as archive:
        require('reference_json' in archive,'Obsolete reference; rebuild independently from original sources')
        payload=json.loads(str(archive['reference_json'].item()))
    require(payload.get('pipeline_id')==PIPELINE and payload.get('provenance')=='independent-original-tsv-centered-scaled-lstsq','Untrusted reference provenance')
    require(set(payload['tables'])==set(KEYS),'Reference table schema')
    counts={'source_frames.csv':140,'graph_points.csv':980,'window_fits.csv':280,'fit_points.csv':3584}
    for name,count in counts.items():
        require(len(payload['tables'][name])==count,f'Reference full coverage: {name}')
        keyed(payload['tables'][name],KEYS[name])
    meta=payload['metadata']
    require(meta['source_manifest_sha256']==MANIFEST_SHA and meta['method_contract_sha256']==METHOD_SHA,'Stale reference source/method')
    require(len(meta['source_sha256'])==24 and meta['status']=='ok','Incomplete reference provenance')
    require(len(payload['summary']['paired_changes'])==140 and len(payload['summary']['group_windows'])==70,'Incomplete reference summaries')
    return payload

def validate_output_directory(output,reference=None):
    reference=load_reference() if reference is None else reference;output=Path(output)
    contract=reference['metadata']['method_contract'];tables={};expected={}
    for name,keys in KEYS.items():
        require((output/name).is_file(),f'Missing {name}')
        expected[name]=keyed(reference['tables'][name],keys)
        tables[name]=read_table(output/name,contract['outputs'][name],keys)
        match_table(tables[name],expected[name],name)
    summary=read_json(output/'summary.json');require(isinstance(summary,dict),'Summary object required')
    match_summary(summary,reference['summary'])
    match_metadata(read_json(output/'run_metadata.json'),reference['metadata'])
    validate_algebra(tables,expected,summary)
    require((output/'findings.md').is_file() and (output/'findings.md').read_text().strip(),'Missing/empty findings')
    return tables
