"""Source-bound primitive validation and own-receipt reporting replay."""
import math
import re
import numpy as np
import artifact_reader as reader
import information_kernel as kernel

need=reader.need
ARRAYS=('unit_ids','bin_ids','draw_ids','occupancy_seconds','raw_counts','shifted_counts',
        'shift_offsets_seconds','shift_defined')
NULLABLE=('null_mean_bits_per_spike','shift_adjusted_bits_per_spike','p_upper')
FLOAT_FIELDS=('mean_rate_hz','raw_bits_per_spike',*NULLABLE)

def close(value,expected,atol=1e-6,rtol=1e-9):
    a=np.asarray(value,dtype=np.float64);b=np.asarray(expected,dtype=np.float64)
    need(a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all(),'finite_shape')
    need(np.all(np.abs(a-b)<=atol+rtol*np.abs(b)),'numeric_tolerance')

def uid(value):
    need(type(value) is str and re.fullmatch(r'-?(0|[1-9][0-9]*)',value)
         and str(int(value))==value,'literal_unit_id')
    return value

def exact(observed,expected):
    if expected is None:need(observed is None,'json_null')
    elif type(expected) is bool:need(type(observed) is bool and observed==expected,'json_boolean')
    elif type(expected) is int:need(reader.integer(observed,True)==expected,'json_integer')
    elif type(expected) is float:need(reader.number(observed,True)==expected,'json_source_number')
    elif isinstance(expected,str):need(type(observed) is str and observed==expected,'json_string')
    elif isinstance(expected,list):
        need(isinstance(observed,list) and len(observed)==len(expected),'json_list')
        for a,b in zip(observed,expected):exact(a,b)
    elif isinstance(expected,dict):
        need(isinstance(observed,dict) and set(expected)<=set(observed),'json_fields')
        for key,value in expected.items():exact(observed[key],value)
    else:raise ValueError('unsupported_reference_type')

def index_axis(actual,expected,string=False):
    a=np.asarray(actual);need(a.ndim==1,'axis_shape')
    if string:
        need(a.dtype.kind=='U','unit_axis_unicode')
        values=[uid(str(v)) for v in a]
    else:
        need(a.dtype.kind in 'iu','integer_axis')
        values=[int(v) for v in a]
    want=list(expected)
    need(len(values)==len(set(values)) and set(values)==set(want),'axis_identity')
    mapping={v:i for i,v in enumerate(values)}
    return [mapping[v] for v in want]

def primitives(arrays,reference):
    need(isinstance(arrays,dict) and set(ARRAYS)<=set(arrays),'required_arrays')
    c=reference['arrays'];units=[str(v) for v in c['unit_ids']]
    ui=index_axis(arrays['unit_ids'],units,True)
    bi=index_axis(arrays['bin_ids'],list(range(20)))
    di=index_axis(arrays['draw_ids'],list(range(300)))
    n=len(ui)
    o=np.asarray(arrays['occupancy_seconds'])
    need(o.dtype.kind in 'iuf' and o.shape==(20,),'occupancy_shape_type')
    o=np.asarray(o[bi],dtype='f8')
    need(np.array_equal(o==0,c['occupancy_seconds']==0) and np.all(o>=0),'occupancy_support')
    close(o,c['occupancy_seconds'],1e-9,1e-12)
    shape={'raw_counts':(n,20),'shifted_counts':(n,300,20),
           'shift_offsets_seconds':(n,300),'shift_defined':(n,300)}
    result={'occupancy_seconds':o}
    for key in shape:
        a=np.asarray(arrays[key]);need(a.shape==shape[key],'primitive_shape')
        if key.endswith('counts'):
            need(a.dtype.kind in 'iu' and np.all(a>=0),'integer_counts')
        elif key=='shift_defined':need(a.dtype.kind=='b','defined_mask_boolean')
        else:need(a.dtype.kind in 'iuf' and np.isfinite(a).all(),'offset_type')
        if a.ndim==3:a=a[np.ix_(ui,di,bi)]
        elif key=='raw_counts':a=a[np.ix_(ui,bi)]
        else:a=a[np.ix_(ui,di)]
        if key=='shift_offsets_seconds':close(a,c[key],1e-10,0)
        else:need(np.array_equal(a,c[key]),'source_primitive_mismatch')
        result[key]=a
    need(np.array_equal(result['shift_defined'],result['shifted_counts'].sum(2)>0),'defined_mask_consistency')
    return result,units

def verify(actual,reference):
    need(reference['status']=='complete','full_reference_required')
    p,units=primitives(actual['arrays'],reference)
    replay=kernel.replay(p['occupancy_seconds'],p['raw_counts'],p['shifted_counts'],units)
    rows=actual['rows'];need(len(rows)==len(units),'eligible_row_count')
    keyed={}
    for row in rows:
        key=uid(row['unit_id']);need(key not in keyed,'duplicate_unit_row');keyed[key]=row
    need(set(keyed)==set(units),'eligible_identity')
    accepted=[]
    for expected in replay:
        row=keyed[expected['unit_id']]
        out=dict(unit_id=expected['unit_id'],n_spikes=reader.integer(row['n_spikes']),status=row['status'])
        need(out['n_spikes']==expected['n_spikes'] and out['status']==expected['status'],'row_discrete')
        for field in FLOAT_FIELDS:
            if expected[field] is None:need(row[field]=='','null_receipt');out[field]=None
            else:
                out[field]=reader.number(row[field]);close(out[field],expected[field])
        if out['status']=='ok':
            need(0<=out['p_upper']<=1,'probability_domain')
            error=abs(out['shift_adjusted_bits_per_spike']-(out['raw_bits_per_spike']-out['null_mean_bits_per_spike']))
            bound=sum(1e-6+1e-9*abs(expected[k]) for k in
                      ('shift_adjusted_bits_per_spike','raw_bits_per_spike','null_mean_bits_per_spike'))
            need(error<=bound,'linear_receipt_coherence')
        accepted.append(out)
    expected_results=kernel.summarize(accepted);results=actual['results']
    for key,want in expected_results.items():
        need(key in results,'result_field')
        if type(want) is float:close(reader.number(results[key],True),want)
        else:exact(results[key],want)
    metadata=actual['metadata']
    for key,value in dict(schema_version='ratplace-output-v2',task_id='RATPLACE-001',
                          status=expected_results['status'],pins=reference['pins'],
                          source_observed=reference['source_observed']).items():
        need(key in metadata,'metadata_field');exact(metadata[key],value)
    records=metadata['all_units'];need(isinstance(records,list),'unit_ledger')
    ledger={}
    for record in records:
        key=uid(record['unit_id']);need(key not in ledger,'duplicate_ledger_unit');ledger[key]=record
    need(set(ledger)=={r['unit_id'] for r in reference['all_units']},'all_unit_coverage')
    for row in reference['all_units']:exact(ledger[row['unit_id']],row)
    analysis=metadata['analysis'];want=reference['analysis']
    for key,value in want.items():
        need(key in analysis,'analysis_field')
        if key in ('grid_edges_raw','window_seconds','valid_observed_seconds'):
            if key=='grid_edges_raw':
                need(isinstance(analysis[key],list) and len(analysis[key])==2,'grid_edges')
                for a,b in zip(analysis[key],value):close(a,b,1e-9,1e-12)
            else:close(analysis[key],value,1e-9,1e-12)
        else:exact(analysis[key],value)
    need(type(actual['findings']) is str and bool(actual['findings'].strip()),'findings')
    return {'status':'verified','n_units':len(units),'authority':'original_counts_and_own_receipts'}

def validate_output_directory(output,reference):
    actual=reader.read_output(output);result=verify(actual,reference);reader.recheck(actual)
    return result
