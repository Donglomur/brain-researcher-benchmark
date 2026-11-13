"""Actual pooled prediction scoring and immutable source-selected statistics.

Only score_prediction imports NumPy. No code here reads files, opens targets,
loads a model, executes a provider or certifies external source authority.
"""
import hashlib
import struct
from fractions import Fraction
from .nomad_stat_math import (Budget,Refusal,need,fields,integer,pin,bytes_pin,budget,
    encode,decode,rational,from_rational,projected,quantiles,signed_rank)

_TOKEN=object()
class _Frozen:
    __slots__=('_raw','_pin')
    def __init__(self,body,b,token):
        need(token is _TOKEN,'private_source_construction_only')
        raw=encode(body,b);object.__setattr__(self,'_raw',raw);object.__setattr__(self,'_pin',(len(raw),hashlib.sha256(raw).hexdigest()))
    def __setattr__(self,name,value):raise TypeError('immutable source product')
    @property
    def pin(self):return {'bytes':self._pin[0],'sha256':self._pin[1]}
    def body(self,limits):return decode(self._raw,budget(limits))
class CapturedFacts(_Frozen):__slots__=()
class ScoreProduct(_Frozen):__slots__=()
class StatisticalRoster(_Frozen):__slots__=()


def capture_facts(documents,selection,limits):
    """Resolve exact JSON-pointer values from full captured bytes.

    selection is supplied by the independently chosen owner source policy.
    This mathematical layer checks bytes/values; it does not grant that policy
    authentic historical authority by accepting a metadata flag.
    """
    b=budget(limits);fields(selection,('schema','selection_id','mode','bindings'))
    need(selection['schema']=='nomad_statistical_selection_v1' and selection['mode'] in ('original','test_only'), 'selected_fact_mode')
    need(type(selection['selection_id']) is str and selection['selection_id'],'selection_identity')
    need(type(documents) is dict and type(selection['bindings']) is dict,'captured_document_map')
    b.take(items=len(selection['bindings']))
    keys={v['document'] for v in selection['bindings'].values()}
    need(set(documents)==keys,'no_unselected_source_documents')
    parsed={};values={};provenance={}
    for name,row in selection['bindings'].items():
        fields(row,('document','pin','pointer'));pin(row['pin'])
        need(type(name) is str and type(row['pointer']) is list and len(row['pointer'])<=64,'bounded_source_pointer')
        raw=documents[row['document']]
        need(type(raw) is bytes and len(raw)==row['pin']['bytes'] and len(raw)<=b.limits['json_bytes'],'captured_source_extent')
        b.take(copy_bytes=len(raw),operations=len(raw))
        need(bytes_pin(raw)==row['pin'],'actual_captured_document_digest')
        if row['document'] not in parsed:parsed[row['document']]=decode(raw,b)
        value=parsed[row['document']]
        for key in row['pointer']:
            need(type(value) is dict and type(key) is str and key in value or type(value) is list and type(key) is int and 0<=key<len(value),'actual_source_pointer')
            value=value[key]
        values[name]=value;provenance[name]=dict(row)
    return CapturedFacts({'schema':'nomad_captured_statistical_facts_v1','selection_id':selection['selection_id'],
        'mode':selection['mode'],'selection_pin':bytes_pin(encode(selection,b)), 'values':values,'provenance':provenance},b,_TOKEN)

SUPPORT_KEYS=('schema','product_id','task','method','method_profile_pin','source_pin','reference_id','query_id',
              'role','sample_ids','axis_ids','target_support_pin','prediction_artifact_pin','target_artifact_pin','prediction_lineage_pin','expected_numpy_version')

def score_prediction(prediction,target,support,limits):
    b=budget(limits);fields(support,SUPPORT_KEYS)
    need(support['schema']=='nomad_prediction_support_v1','prediction_support_schema')
    for name in ('method_profile_pin','source_pin','target_support_pin','prediction_artifact_pin','target_artifact_pin','prediction_lineage_pin'):pin(support[name])
    for name in ('product_id','task','method','reference_id','query_id'):
        need(type(support[name]) is str and 0<len(support[name])<=b.limits['identifier_chars'],'bounded_literal_identity',field=name)
    need(support['role'] in ('anchor','query','calibration','first_evaluation','post_first_evaluation'),'explicit_prediction_role')
    # Exact array type only. No coercion, ufunc finite-mask allocation or dtype cast.
    import numpy as np
    need(type(prediction) is np.ndarray and type(target) is np.ndarray,'exact_numpy_arrays')
    need(prediction.ndim==target.ndim==2 and prediction.dtype==target.dtype==np.dtype('float64')
         and prediction.shape==target.shape,'rank2_matched_binary64_arrays')
    need(prediction.dtype.str==target.dtype.str=='<f8' and prediction.flags.c_contiguous and target.flags.c_contiguous,
         'canonical_C_contiguous_little_endian_no_hidden_copy')
    n,d=target.shape
    need(n>0 and d>0,'nonempty_complete_prediction_support')
    cells=n*d;b.take(input_cells=6*cells,items=n+d,operations=6*cells,copy_bytes=32*cells)
    need(type(support['expected_numpy_version']) is str and support['expected_numpy_version']==np.__version__, 'selected_actual_numpy_version')
    for key,count in (('sample_ids',n),('axis_ids',d)):
        ids=support[key];need(type(ids) in (list,tuple) and len(ids)==count,'full_axis_shape_join',axis=key)
        lease=count*96;b.hold(lease);b.take(copy_bytes=lease)
        need(all(type(x) is str and x and len(x)<=b.limits['identifier_chars'] for x in ids)
             and len(set(ids))==count,'unique_complete_axis_identities',axis=key)
    support_raw=encode(support,b)
    scratch=d*(512+12*((b.limits['integer_bits']+7)//8))+256
    invalid_bound=2*cells*160
    b.hold(scratch+invalid_bound);b.take(copy_bytes=scratch+invalid_bound)
    try:
        hp=hashlib.sha256(b'NOMAD-CONSUMED-F64-ROWMAJOR-V1\0'+struct.pack('>QQ',n,d))
        ht=hashlib.sha256(b'NOMAD-CONSUMED-F64-ROWMAJOR-V1\0'+struct.pack('>QQ',n,d))
        for array,hasher in ((prediction,hp),(target,ht)):
            view=memoryview(array).cast('B')
            try:
                for start in range(0,len(view),65536):hasher.update(view[start:start+65536])
            finally:view.release()
        badp=[];badt=[]
        for i in range(n):
            for j in range(d):
                p=float(prediction[i,j]);t=float(target[i,j])
                if not np.isfinite(p):badp.append([i,j])
                if not np.isfinite(t):badt.append([i,j])
        body={'schema':'nomad_computed_score_product_v1','support':decode(support_raw,b),
              'support_pin':bytes_pin(support_raw),'shape':[n,d], 'numpy_version':np.__version__,
              'consumed_prediction_digest':hp.hexdigest(),'consumed_target_digest':ht.hexdigest(),
              'consumed_encoding':'domain plus big-endian shape then little-endian f64 row-major, not an ordinary-file pin',
              'invalid_prediction_cells':badp,'invalid_target_cells':badt,'constant_target_axes':[],
              'value':None,'exact_value':None,'components':None,'original_constant_axis_policy':'unavailable_if_any_axis_constant',
              'planned_consumed_cells':6*cells,'actual_consumed_cells':4*cells,
              'input_layout':{'dtype':'<f8','C_contiguous':True,'prediction_writeable':bool(prediction.flags.writeable),'target_writeable':bool(target.flags.writeable)},
              'hash_strategy':'bounded direct memoryview before scan; consumed scalar commitments during exact accumulation',
              'array_caller_owned_bytes':prediction.nbytes+target.nbytes,'original_profile_admitted':False}
        if badp or badt:
            body['status']='unavailable_nonfinite_target' if badt else 'invalid_nonfinite_prediction'
            body['budget_prefix_before_freeze']=b.snapshot()
            return ScoreProduct(body,b,_TOKEN)
        sy=[Fraction(0) for _ in range(d)];sq=[Fraction(0) for _ in range(d)];sse=[Fraction(0) for _ in range(d)]
        # This second pass consumes the same complete values, with independently
        # checked hashes. Mutation between passes refuses instead of mixing data.
        hp2=hashlib.sha256(b'NOMAD-CONSUMED-F64-ROWMAJOR-V1\0'+struct.pack('>QQ',n,d))
        ht2=hashlib.sha256(b'NOMAD-CONSUMED-F64-ROWMAJOR-V1\0'+struct.pack('>QQ',n,d))
        for i in range(n):
            for j in range(d):
                p=float(prediction[i,j]);t=float(target[i,j]);hp2.update(struct.pack('<d',p));ht2.update(struct.pack('<d',t))
                a=b.number(p);y=b.number(t);delta=b.add(a,-y)
                sy[j]=b.add(sy[j],y);sq[j]=b.add(sq[j],b.mul(y,y));sse[j]=b.add(sse[j],b.mul(delta,delta))
        body['actual_consumed_cells']=6*cells
        need(hp2.digest()==hp.digest() and ht2.digest()==ht.digest(),'array_values_changed_during_scoring')
        sst=[b.add(sq[j],-b.div(b.mul(sy[j],sy[j]),Fraction(n))) for j in range(d)]
        need(all(x>=0 for x in sst),'exact_nonnegative_centered_target_energy')
        total_sse=Fraction(0);total_sst=Fraction(0)
        for a,c in zip(sse,sst):total_sse=b.add(total_sse,a);total_sst=b.add(total_sst,c)
        body['constant_target_axes']=[support['axis_ids'][j] for j,v in enumerate(sst) if v==0]
        body['components']={'sse_axes':[rational(v,b) for v in sse],'sst_axes':[rational(v,b) for v in sst],
                            'target_sums':[rational(v,b) for v in sy], 'sse_total':rational(total_sse,b),'sst_total':rational(total_sst,b),
                            'arithmetic':'exact dyadic operands and exact centered rational sums; no raw float square materialization'}
        if total_sst==0:body['status']='undefined_zero_total_target_energy'
        elif body['constant_target_axes']:body['status']='unavailable_constant_target_axis'
        else:
            value=b.add(Fraction(1),-b.div(total_sse,total_sst));projection=projected(value)
            body['exact_value']=rational(value,b);body['value']=projection['value']
            body['status']='computed' if projection['status']=='finite' else 'undefined_'+projection['status']
        body['budget_prefix_before_freeze']=b.snapshot()
        return ScoreProduct(body,b,_TOKEN)
    finally:b.release(scratch+invalid_bound)


def compile_statistical_roster(facts,limits):
    from .nomad_stat_roster import compile_roster
    need(type(facts) is CapturedFacts,'actual_captured_fact_set')
    b=budget(limits);return StatisticalRoster(compile_roster(facts.body(b),b),b,_TOKEN)


def reduce_statistical_study(roster,products,statistical_profile,limits):
    from .nomad_stat_roster import reduce_roster
    need(type(roster) is StatisticalRoster and type(statistical_profile) is CapturedFacts,'actual_source_constructed_roster_and_profile')
    need(type(products) in (list,tuple) and all(type(p) is ScoreProduct for p in products),'computed_score_products_only')
    b=budget(limits);b.take(items=len(products))
    rows={}
    for product in products:
        row=product.body(b);pid=row['support']['product_id']
        need(pid not in rows,'duplicate_computed_product_id');rows[pid]=row
    return reduce_roster(roster.body(b),rows,statistical_profile.body(b),b)


def _anchor_decrease_rows(anchor,query,b):
    a=anchor['support'];q=query['support']
    need(a['role']=='anchor' and q['role']=='query' and a['method']==q['method']
         and a['method_profile_pin']==q['method_profile_pin'] and a['source_pin']==q['source_pin']
         and a['task']==q['task'] and a['reference_id']==a['query_id']==q['reference_id']
         and a['axis_ids']==q['axis_ids'],'method_specific_fixed_reference_anchor_join')
    if anchor['status']!='computed' or query['status']!='computed':return None
    return b.add(from_rational(anchor['exact_value'],b),-from_rational(query['exact_value'],b))

def decrease(anchor,query,limits):
    """Actual scored anchor minus next-day product; pair calendar is separately bound."""
    need(type(anchor) is ScoreProduct and type(query) is ScoreProduct,'actual_scored_anchor_and_query')
    b=budget(limits);a=anchor.body(b);q=query.body(b);value=_anchor_decrease_rows(a,q,b)
    return {'schema':'nomad_computed_anchor_decrease_v1','anchor_product_pin':anchor.pin,
        'query_product_pin':query.pin,'anchor_status':a['status'],'query_status':q['status'],
        'status':'computed' if value is not None else 'unavailable_invalid_scored_product',
        'value':None if value is None else {'exact':rational(value,b),**projected(value)},
        'calendar_claim':'Caller source roster separately binds the exact one-day pair; subtraction alone does not authenticate a day gap.'}
