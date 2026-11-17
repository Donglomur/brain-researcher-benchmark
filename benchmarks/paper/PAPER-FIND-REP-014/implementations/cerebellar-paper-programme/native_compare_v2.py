"""Source-typed native calibration comparison; no scientific values or fitting.

Successor to native_compare.py, retained unchanged for historical provenance.
This module is not enrolled in the frozen programme execution manifest.
"""
import math
import re
from core import need, BRANCHES


# MATLAB numeric storage does not determine scientific type: the original
# table uses doubles for both source identities and continuous measurements.
# MainData.m 603-618, 669-702 defines these columns. nb_export.m serializes
# them as <root>/{condition}/<column>, retaining their source MATLAB class.
_TABLES = {'GrCsChronInfo', 'CFsChronInfo'}
_DISCRETE_COLUMNS = {
    'hasDLC', 'nOmit', 'sessionNum', 'cellNum', 'otherCellNum',
    'sortIx', 'sortIxi', 'prerewSortIx',
}
_CONTINUOUS_COLUMNS = {
    'stTau', 'reliab', 'delay_activ_cent', 'delay_activ_cent_4s',
    'delay_activ_centi', 'prerew_grc', 'postrew', 'postomit', 'del_act',
    'half_del_act', 'prerewmbase_grc', 'mvmag', 'prerewmrewdec_grc',
}
_DISCRETE_ROOTS = {
    'ant_sig', 'anti_sig', 'post', 'mvCFs', 'postcfs', 'antIO', 'ant',
    'isIO', 'isCtrl', 'isNorm', 'isGt', 'sessnums', 'chronCellNums',
    # passiveMFB.m 51-52; IOChRmine.m 43-50; gtacr1.m 70-77:
    # nnz/length counts and cumsum of binary event indicators, stored double.
    'antbysess', 'ncsbysess', 'cumultrials', 'cumultrials_opto',
}
_INTEGER_CLASSES = {
    'logical', 'int8', 'int16', 'int32', 'int64',
    'uint8', 'uint16', 'uint32', 'uint64',
}


def _exact_leaf(record):
    key = record['key']
    parts = key.split('/')
    if parts[0] in _TABLES:
        # Empty cells/zero-width tables carry structural records without a
        # source_class. Their zero elements are checked by the original shape
        # path. Never silently give a new source table column a tolerance.
        if 'source_class' not in record:
            need(_shape(record['shape']) == 0, 'Only empty untyped table leaves')
            return True
        need(len(parts) == 3 and re.fullmatch(r'\{[1-9][0-9]*\}', parts[1]),
             'Exact exported chronic-table column path')
        column = parts[2]
        need(column in _DISCRETE_COLUMNS | _CONTINUOUS_COLUMNS,
             'Unreviewed chronic-table column: ' + column)
        return column in _DISCRETE_COLUMNS or record['source_class'] in _INTEGER_CLASSES
    return parts[0] in _DISCRETE_ROOTS or record.get('source_class') in _INTEGER_CLASSES


def _numbers(value):
    return value if type(value) is list else [value]


def _shape(value):
    need(type(value) is list and all(type(n) is int and n>=0 for n in value),'Exact MATLAB shape')
    return math.prod(value)


def compare(reference,candidate,branch):
    keys={'schema','family','records','roots','metadata','matlab_version'}
    for tree in (reference,candidate):
        need(type(tree) is dict and set(tree)==keys and tree['schema']=='filio_native_numeric_v1' and tree['family']==branch,'Exact native tree and branch')
        need(type(tree['roots']) is list and {r['name'] for r in tree['roots']}==set(BRANCHES[branch]['targets']) and len(tree['roots'])==len(BRANCHES[branch]['targets']),'All declared roots including empties')
    need(candidate['roots']==reference['roots'],'Full native root class/shape/empty declarations')
    ref={r['key']:r for r in reference['records']};got={r['key']:r for r in candidate['records']}
    need(len(ref)==len(reference['records']) and len(got)==len(candidate['records']) and set(ref)==set(got),'Every complete native scalar-tree leaf')
    total=matched=0;rows=[]
    for key,r in ref.items():
        c=got[key];need(set(c)==set(r) and c['shape']==r['shape'] and c.get('source_class')==r.get('source_class'),'Exact leaf schema/class/shape')
        n=_shape(r['shape']);rv,cv,rc,cc=map(_numbers,(r['values'],c['values'],r['codes'],c['codes']))
        need(all(len(x)==n for x in (rv,cv,rc,cc)),'No cropped native leaf')
        integer=_exact_leaf(r)
        count=0
        for a,b,sa,sb in zip(rv,cv,rc,cc):
            need(type(sa) is int and type(sb) is int and sa in (0,1,2,3) and sb in (0,1,2,3) and type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b),'Finite native export placeholders and exact integer status codes')
            ok=sa==sb and (sa!=0 and a==b==0 or sa==0 and (a==b if integer else abs(a-b)<=1e-8+1e-6*abs(a)))
            count+=int(ok)
        # Empty leaves are structural obligations; they are not fabricated scalars.
        rows.append({'key':key,'elements':n,'matched':count,'exact_discrete':integer});total+=n;matched+=count
    # Full masks/membership/metadata are mandatory, never compared on a selected axis.
    def metadata(a,b,path):
        nonlocal total,matched
        need(type(a)==type(b),'Metadata type '+path)
        if type(a) is dict:
            need(set(a)==set(b),'Full metadata keys '+path)
            for k in a:metadata(a[k],b[k],path+'/'+k)
        elif type(a) is list:
            need(len(a)==len(b),'Full metadata axes '+path)
            for i,(x,y) in enumerate(zip(a,b)):metadata(x,y,path+'/'+str(i))
        elif type(a) is float:
            need(math.isfinite(a) and math.isfinite(b),'Finite metadata');total+=1;matched+=int(abs(a-b)<=1e-8+1e-6*abs(a))
        else:
            total+=1;matched+=int(a==b)
    metadata(reference['metadata'],candidate['metadata'],'metadata')
    need(total>0,'Nonempty full native comparison')
    return {'branch':branch,'matched':matched,'elements':total,'fraction':matched/total,'leaves':rows,'all_roots_present':True,'matlab_versions':{'reference':reference['matlab_version'],'candidate':candidate['matlab_version']}}


def grade(payload,store):
    need(set(payload)=={'schema','branch','reference','A','B'} and payload['schema']=='paper_i_worker_native_grade_v1' and payload['branch'] in BRANCHES,'Exact private branch grade')
    trees={}
    for role in ('reference','A','B'):
        r=payload[role];need(set(r)=={'path','pin'},'Bound native JSON');trees[role]=store.json(r['path'],r['pin'])
    return {'schema':'paper_i_native_branch_grade_v1','complete':True,'branch':payload['branch'],'arms':{r:compare(trees['reference'],trees[r],payload['branch']) for r in ('A','B')},'biological_truth':False}
