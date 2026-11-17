"""C4 full-roster prediction contract. Imports do not read data or train models."""
import hashlib,json,math,os,re,stat
from pathlib import Path
TASK='PAPER-paper-method-replacement-003'
REV='703a10fb43fc7fe0076c9c331e6b52d3195b5e60'
CLASSES=('GoC','MLI','MFB','PkC_ss','PkC_cs')
METHODS=('logistic_regression','random_forest','gaussian_process','deep','improved')
DOMAINS=('mouse_loo','monkey_transfer')
ARMS=('paper_and_data','paper_data_official_code')
ENGINEERED_COLUMNS=('mfr', 'mifr', 'med_isi', 'mode_isi', 'prct5ISI', 'entropy', 'CV2_mean', 'CV2_median', 'CV', 'IR', 'Lv', 'LvR', 'LcV', 'SI', 'SKW', 'std_isi', 'burst_idx', 'acg_burst_vs_mfr', 'acg_oscill_vs_mfr', 'trough_voltage', 'trough_t', 'peak_voltage', 'peak_t', 'repolarisation_t', 'depolarisation_t', 'peak_50_width', 'trough_50_width', 'onset_t', 'onset_amp', 'wvf_width', 'peak_trough_ratio', 'tau_recovery', 'multiplicative_a_recovery', 'repolarisation_slope', 'depolarisation_slope', 'spatial_decay_24um', 'dendritic_comp_amp')
MAX_JSON=32_000_000

def need(ok,why):
    if not ok:raise ValueError(why)
def exact(x,keys):need(type(x) is dict and set(x)==set(keys),'exact object fields')
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(x):return hashlib.sha256(enc(x)).hexdigest()
def pairs(rows):
    out={}
    for k,v in rows:need(k not in out,'duplicate JSON key');out[k]=v
    return out
def capture(path,cap=MAX_JSON):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_size<=cap,'bounded regular input');b=bytearray()
        while len(b)<=cap:
            z=os.read(fd,min(1048576,cap+1-len(b)))
            if not z:break
            b.extend(z)
        c=os.fstat(fd);need(len(b)==a.st_size and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(c.st_dev,c.st_ino,c.st_size,c.st_mtime_ns,c.st_ctime_ns),'stable input');return bytes(b)
    finally:os.close(fd)
def decode(b):return json.loads(b.decode('utf8'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def load(p):return decode(capture(p))
def fresh(p):p=Path(p);need(not p.exists() and not p.is_symlink(),'fresh output');return p
def save(p,x):
    b=enc(x);need(len(b)<=MAX_JSON,'output cap')
    with Path(p).open('xb') as f:f.write(b)
def ident(x):need(type(x) is str and re.fullmatch(r'[a-zA-Z0-9_-]{1,96}',x) is not None,'opaque identifier')
def sha(x):need(type(x) is str and re.fullmatch('[0-9a-f]{64}',x) is not None,'sha256')
def number(x):
    need(type(x) in (int,float),'number')
    try:finite=math.isfinite(x)
    except (OverflowError,ValueError):finite=False
    need(finite,'finite number');return x
def ids(x):need(type(x) is list and len(x)>0 and len(x)==len(set(x)),'unique nonempty IDs');[ident(v) for v in x]
def query(q,production=True):
    exact(q,('schema','task_id','source_revision','classes','repeats','input_index_sha256','selection_sha256','pretraining_sha256','run_config_sha256','domains','scope'))
    need(q['schema']=='c4_query_v1' and q['task_id']==TASK and q['source_revision']==REV,'identity')
    need(q['classes']==list(CLASSES) and type(q['repeats']) is int and q['repeats']==10,'five-class ten-repeat contract')
    for k in ('input_index_sha256','selection_sha256','pretraining_sha256','run_config_sha256'):sha(q[k])
    need(q['scope']=='full_selected_c4_mouse_monkey','full central scope');exact(q['domains'],DOMAINS)
    allids=[]
    for dom in DOMAINS:
        exact(q['domains'][dom],('unit_ids','label_basis','model_members_per_repeat'))
        x=q['domains'][dom];ids(x['unit_ids']);need(len(x['unit_ids'])<=20000,'unit cap');allids+=x['unit_ids']
        need(x['label_basis']==('mouse_source_ground_truth' if dom=='mouse_loo' else 'monkey_expert_reference'),'reference-truth distinction')
        exact(x['model_members_per_repeat'],METHODS)
        for m,n in x['model_members_per_repeat'].items():need(type(n) is int and 1<=n<=20000,'model cardinality')
        expected=1 if dom=='mouse_loo' else len(q['domains']['mouse_loo']['unit_ids'])
        need(x['model_members_per_repeat']['deep']==expected,'source LOO ensemble cardinality')
        need(all(x['model_members_per_repeat'][m]==1 for m in METHODS[:3]),'source baseline one model per instantiation/query')
    need(len(allids)==len(set(allids)),'disjoint species identities')
    if production:need(len(q['domains']['mouse_loo']['unit_ids'])==202,'published central 202-unit roster; reconcile any source-QC mismatch before production')
    return q

def probability(v):
    need(type(v) is list and len(v)==5,'five probabilities')
    for x in v:number(x);need(0<=x<=1,'probability in [0,1]')
    need(abs(math.fsum(v)-1)<=1e-8,'normalized probabilities');return v

def submission(s,q):
    exact(s,('schema','task_id','query_sha256','information_arm','method_description','predictions'))
    need(s['schema']=='c4_predictions_v1' and s['task_id']==TASK and s['query_sha256']==digest(q),'submission identity')
    need(s['information_arm'] in ARMS,'information arm');need(type(s['method_description']) is str and 1<=len(s['method_description'])<=4000,'method description')
    exact(s['predictions'],METHODS)
    for method in METHODS:
        exact(s['predictions'][method],DOMAINS)
        for dom in DOMAINS:
            rows=s['predictions'][method][dom];want=q['domains'][dom]['unit_ids'];need(type(rows) is list and len(rows)==len(want),'full roster')
            for r,u in zip(rows,want):
                exact(r,('unit_id','probabilities'));need(r['unit_id']==u,'exact ordered unit identity')
                need(type(r['probabilities']) is list and len(r['probabilities'])==10,'ten independent instantiations')
                for v in r['probabilities']:probability(v)
    return s

def target(t,q):
    exact(t,('schema','query_sha256','labels','groups'))
    need(t['schema']=='c4_target_v1' and t['query_sha256']==digest(q),'private target identity');exact(t['labels'],DOMAINS);exact(t['groups'],DOMAINS)
    for dom in DOMAINS:
        want=q['domains'][dom]['unit_ids'];need(type(t['labels'][dom]) is list and len(t['labels'][dom])==len(want),'complete labels')
        need(all(type(v) is str and v in CLASSES for v in t['labels'][dom]),'class labels')
        need(type(t['groups'][dom]) is list and len(t['groups'][dom])==len(want),'complete source groups')
        for row in t['groups'][dom]:
            exact(row,('animal','session','lab'))
            for v in row.values():ident(v)
    return t
