"""Independent bounded typed-output admission, with no scientific estimator."""
import hashlib
import math
import re
from protocol import need,natural,sha,descriptor,decode,digest

WIDTHS=dict(double=8,single=4,int8=1,uint8=1,int16=2,uint16=2,int32=4,uint32=4,int64=8,uint64=8,logical=1,char=2)
LIMITS={'max_snapshots','max_nodes','max_depth','max_files','max_total_bytes','max_leaf_bytes','max_snapshot_bytes','max_workspace_bytes','max_cache_bytes'}
STORAGE={'little_endian_column_major','complex_separate_planes_column_major','sparse_triplets_column_major','cell_column_major','struct_column_major','string_elements_UTF8_with_missing_mask','table_columns','categorical_codes_and_categories','source_bound_function_handle_description','graphics_handle_explicitly_excluded','native_model_array_column_major','declared_native_model_property_projection'}

def limits(value):
    need(type(value) is dict and set(value)==LIMITS,'exact capture limits')
    for key,n in value.items():natural(n,key);need(n<=2**53,'MATLAB exact-double limit')
    return value

class CapturedReader:
    """The external read callback exposes only one independently closed output tree.

    read(name, offset, count) returns <=count bytes. The observer must establish
    immutable ordinary files/no symlinks; this parser does not invent OS custody.
    """
    def __init__(self,read,budget,cap):self.read=read;self.budget=budget;self.cap=limits(cap);self.seen={};self.nodes=0
    def blob(self,d,*,metadata=False,logical=False):
        descriptor(d);name=d['path']
        need('/' not in name and name not in self.seen,'fresh owned basename')
        need(len(self.seen)<self.cap['max_files'],'file count cap')
        maximum=self.cap['max_snapshot_bytes'] if metadata else max(self.cap['max_leaf_bytes'],self.cap['max_cache_bytes'])
        need(d['bytes']<=maximum and sum(v['bytes'] for v in self.seen.values())+d['bytes']<=self.cap['max_total_bytes'],'capture extent cap')
        h=hashlib.sha256();parts=[];offset=0
        while offset<d['bytes']:
            n=min(65536,d['bytes']-offset);self.budget.charge('read_bytes',n)
            b=self.read(name,offset,n);need(type(b) is bytes and len(b)==n,'short captured body')
            if logical:need(all(v in (0,1) for v in b),'invalid logical raw values')
            h.update(b)
            if metadata:parts.append(b)
            offset+=n
        self.budget.charge('read_bytes',1);need(self.read(name,offset,1)==b'','captured growth')
        need(h.hexdigest()==d['sha256'],'captured hash differs')
        self.seen[name]=d.copy()
        return b''.join(parts) if metadata else None
    def leaf(self,d):
        need(type(d) is dict and set(d)=={'path','bytes','sha256','class','shape','byte_order','layout','NaN_Inf_policy'},'exact raw leaf')
        need(re.fullmatch(r'leaf-[0-9]{9,16}\.bin',d['path']) is not None and d['class'] in WIDTHS,'raw leaf name/class')
        shape=d['shape'];need(type(shape) is list and len(shape)>=2 and len(shape)<=32,'bounded MATLAB shape')
        for n in shape:natural(n,'dimension',True)
        need(math.prod(shape)*WIDTHS[d['class']]==d['bytes']<=self.cap['max_leaf_bytes'],'typed raw extent')
        need(d['byte_order']=='little' and d['layout']=='MATLAB_column_major'
             and d['NaN_Inf_policy']=='preserved_in_raw_floating_payload_not_JSON','literal raw encoding')
        self.blob({k:d[k] for k in ('path','bytes','sha256')},logical=d['class']=='logical')
    def walk(self,v,depth=0):
        need(depth<=self.cap['max_depth']+16,'bounded descriptor nesting')
        if type(v) is list:
            for child in v:self.walk(child,depth+1)
        elif type(v) is dict:
            if set(v)=={'path','bytes','sha256','class','shape','byte_order','layout','NaN_Inf_policy'}:
                self.leaf(v);return
            if 'storage' in v:
                self.nodes+=1;need(self.nodes<=self.cap['max_nodes'],'typed node count')
                need(v['storage'] in STORAGE and type(v.get('class')) is str,'known typed storage')
                need(type(v.get('shape')) is list and len(v['shape'])>=2,'typed node shape')
                for n in v['shape']:natural(n,'node dimension',True)
                if v['storage']=='little_endian_column_major':
                    need(v['leaf']['class']==v['class'] and v['leaf']['shape']==v['shape'],'node/leaf type equality')
                if v['storage']=='complex_separate_planes_column_major':
                    need(all(v[k]['class']==v['class'] and v[k]['shape']==v['shape'] for k in ('real','imaginary')),'complex plane shape/class')
            for child in v.values():self.walk(child,depth+1)

def projected_schema(value):
    """Value-free leaf geometry for an independently predetermined public schema."""
    if type(value) is list:return [projected_schema(x) for x in value]
    if type(value) is dict:
        if {'path','bytes','sha256','class','shape','byte_order','layout'}<=set(value):
            return {k:value[k] for k in ('class','shape','bytes','byte_order','layout')}
        return {k:projected_schema(v) for k,v in value.items() if k not in ('context_id','capture_spec_sha256')}
    return value

def admit(index_descriptor,read,budget,request,generated,expected,inventory):
    """Authenticate all leaf bytes and source-defined projections after custody.

    This accepts captured typed artifacts, not agreement with another producer.
    A native saved MAT sidecar is preserved by exact bytes but remains semantically
    unadmitted; scientific values must come from the typed capture instead.
    """
    cap=limits(request['limits']);r=CapturedReader(read,budget,cap)
    need(index_descriptor['path']=='CAPTURE_INDEX.json','fixed index locator')
    index=decode(r.blob(index_descriptor,metadata=True),cap['max_snapshot_bytes'])
    required={'schema','status','source','snapshots','native_cache','files_before_footer','bytes_reserved_before_footer','nodes','limits','native_qualified','outer_natural_zero_established','directory_durability_established'}
    need(set(index)==required and index['schema']=='ach_native_capture_index_v1' and index['status']=='root_returned_provisional','exact provisional footer')
    source=dict(root_id=request['root_id'],mode=request['mode'],context_id=request['context_id'],capture_spec_sha256=generated['capture_spec_sha256'],original_source_sha256=request['original_source_sha256'])
    need(index['source']==source and index['limits']==cap,'exact original source/context/spec')
    need(all(index[k] is False for k in ('native_qualified','outer_natural_zero_established','directory_durability_established')),'producer cannot assert outer authority')
    specs=[generated['capture_spec']['root_contract']]+generated['capture_spec']['external_helpers']
    anchors={item['source']['author_relative_path']+'::'+a['function']+'::L'+str(a['line']):a['kind'] for item in specs for a in item['capture_anchors']}
    taps={a['tag'] for a in specs[0]['transforms'] if a['kind']=='identity_value_tap'}
    records=[];root_return=0
    need(type(index['snapshots']) is list and 0<len(index['snapshots'])<=cap['max_snapshots'],'complete bounded snapshot list')
    for i,d in enumerate(index['snapshots'],1):
        need(d['path']==f'snapshot-{i:09d}.json','exact ordered snapshot names')
        x=decode(r.blob(d,metadata=True),cap['max_snapshot_bytes'])
        need(type(x.get('sequence')) is int and x['sequence']==i and all(x.get(k)==source[k] for k in ('root_id','mode','context_id','capture_spec_sha256')),'snapshot original identity/sequence')
        if x.get('schema')=='ach_native_snapshot_v1':
            need(x.get('anchor') in anchors and x.get('kind')==anchors[x['anchor']],'original capture anchor')
            need(type(x.get('workspace')) is dict,'complete captured workspace')
            natural(x.get('workspace_whos_bytes'),'workspace extent',True);need(x['workspace_whos_bytes']<=cap['max_workspace_bytes'],'workspace cap')
            root_return+=int(x['kind']=='root_return')
        else:need(x.get('schema')=='ach_native_value_tap_v1' and x.get('anchor') in taps,'declared single-evaluation value tap')
        r.walk(x);records.append(x)
    need(root_return==1 and records[-1].get('kind')=='root_return','exact final root return')
    cache=index['native_cache']
    if request['mode']=='forced_recompute':
        need(set(cache)=={'present','path','bytes','sha256','artifact_type','body_schema_admitted','recomputed_not_cache_input'}
             and cache['present'] is True and cache['path']=='native-recomputed-cache.mat'
             and cache['artifact_type']=='original_native_save_MAT' and cache['body_schema_admitted'] is False
             and cache['recomputed_not_cache_input'] is True,'exact recomputed saved sidecar')
        need(cache['bytes']<=cap['max_cache_bytes'],'saved MAT cap')
        r.blob({k:cache[k] for k in ('path','bytes','sha256')})
    else:need(cache=={'present':False},'no recomputation cache in native/replay mode')
    selected=[];tree={'snapshots':records}
    for selector in expected['selectors']:
        v=tree
        for part in selector:v=v[part]
        selected.append(projected_schema(v))
    need(digest(selected)==expected['shape_signature'],'pre-admitted full numerical-output schema')
    need(type(inventory) is list and len({d['path'] for d in inventory})==len(inventory),'independent unique output inventory')
    need({d['path']:descriptor(d) for d in inventory}==r.seen,'independent full owned file inventory')
    natural(index['files_before_footer'],'footer files',True);natural(index['bytes_reserved_before_footer'],'footer bytes',True);natural(index['nodes'],'footer nodes',True)
    need(index['files_before_footer']+1==len(r.seen),'footer file-accounting equality')
    need(index['nodes']==r.nodes,'exact independently traversed typed-node count')
    actual_before=sum(d['bytes'] for name,d in r.seen.items() if name!='CAPTURE_INDEX.json')
    unused_cache=cap['max_cache_bytes']-cache['bytes'] if request['mode']=='forced_recompute' else 0
    need(index['bytes_reserved_before_footer']==actual_before+unused_cache,'exact sink reservation accounting')
    need(index['bytes_reserved_before_footer']+index_descriptor['bytes']<=cap['max_total_bytes'],'complete reserved footer cap')
    return dict(index=index_descriptor,files=[r.seen[k] for k in sorted(r.seen)],shape_signature=expected['shape_signature'],
                obligation=expected['obligation'],coverage_receipt=expected['coverage_receipt'],
                native_cache_semantics_qualified=False,scientific_result=False,full_paper_complete=False)
