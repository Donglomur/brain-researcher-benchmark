"""Private complete 67-root native comparison; no regenerated scientific values."""
import math
from core import need, BRANCHES


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
        integer=key.split('/')[0] in {'ant_sig','anti_sig','post','mvCFs','postcfs','antIO','ant','isIO','isCtrl','isNorm','isGt','sessnums','chronCellNums','GrCsChronInfo','CFsChronInfo'} or r.get('source_class') in ('logical','int8','int16','int32','int64','uint8','uint16','uint32','uint64')
        count=0
        for a,b,sa,sb in zip(rv,cv,rc,cc):
            need(sa in (0,1,2,3) and sb in (0,1,2,3) and type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b),'Finite native export placeholders and exact status codes')
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
