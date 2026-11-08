"""Source-only exact native collection contracts. No input body is read at import."""
import hashlib
import json
import math
import re
from pathlib import PurePosixPath,Path

RUNTIME_FILES=('CONTRACT.json','PUBLIC_CONVENTIONS.json','QUALIFICATION.json','protocol.py','capture.py','dispatch.py','entry.py',
  'native-capture/build_capture.py','native-capture/CAPTURE_CONTRACT.json',
  'native-capture/CAPTURE_SCHEMA.json','native-capture/ach_native_capture.m','native-capture/ach_native_capture_state.m')

class Refusal(ValueError): pass
def need(ok, message):
    if not ok: raise Refusal(message)
def natural(x, name, zero=False):
    need(type(x) is int and x >= (0 if zero else 1), name+': exact natural required')
    return x
def sha(x):
    need(type(x) is str and re.fullmatch('[0-9a-f]{64}',x) is not None,'SHA256 required');return x
def plain(x):
    if x is None or type(x) in (str,int,bool):return
    if type(x) is float:need(math.isfinite(x),'finite JSON');return
    if type(x) is list:
        for v in x:plain(v)
        return
    if type(x) is dict:
        need(all(type(k) is str for k in x),'string JSON keys')
        for v in x.values():plain(v)
        return
    raise Refusal('plain JSON required')
def encode(x):
    plain(x);return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def digest(x):return hashlib.sha256(encode(x)).hexdigest()
def body_pin(b):
    need(type(b) is bytes,'bytes required');return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def decode(b,cap):
    need(type(b) is bytes and len(b)<=cap,'bounded metadata bytes')
    def pairs(rows):
        d={}
        for k,v in rows:need(k not in d,'duplicate key');d[k]=v
        return d
    def bad(v):raise Refusal('nonfinite JSON')
    x=json.loads(b.decode('utf-8','strict'),object_pairs_hook=pairs,parse_constant=bad);plain(x);return x
def path(x):
    need(type(x) is str and len(x)<=1024 and not x.startswith('/') and '\\' not in x
         and PurePosixPath(x).as_posix()==x and all(p not in ('','..','.') for p in x.split('/')),'canonical relative path')
    return x
def descriptor(x):
    need(type(x) is dict and set(x)=={'path','bytes','sha256'},'exact descriptor')
    path(x['path']);natural(x['bytes'],'extent',True);sha(x['sha256']);return x
def verify(b,d):
    descriptor(d);need(body_pin(b)=={k:d[k] for k in ('bytes','sha256')},'body identity mismatch');return b

def source_fingerprint(budget):
    """Fixed required production closure, never a candidate-controlled file list."""
    root=Path(__file__).resolve().parent;pins=[];bodies={};total=0
    for name in RUNTIME_FILES:
        p=root/name;need(p.is_file() and not p.is_symlink(),'ordinary installed source member')
        extent=p.stat().st_size;total+=extent;need(0<=extent<=262144 and total<=1048576,'bounded production source closure')
        budget.charge('read_bytes',extent+1)
        with p.open('rb') as stream:b=stream.read(extent+1)
        need(len(b)==extent,'installed source changed extent');pins.append(dict(path=name,**body_pin(b)));bodies[name]=b
    return digest(pins),bodies
def canonical_contract(c):
    need(c['canonical_id']=='PAPER-ROOT-ADD-019' and c['root_count']==37 and len(c['roots'])==37,'all37 original roots')
    need(len({r['id'] for r in c['roots']})==37 and c['native_jobs']==111,'original full native scope')
    need(len(c['original_source_members'])==64 and len(c['original_input_members'])==394,'complete original rosters')
    need(len(c['processed_epoch_recompute_roots'])==8,'all8 recomputations')
    need(c['qualification'] is False and c['full_paper_complete'] is False and c['new_task_count']==0,'no promotion')
    return c

class Budget:
    """Cumulative logical accounting. Physical enforcement belongs to qualified observer."""
    def __init__(self,profile,origin,clock):
        need(type(profile) is dict and set(profile)=={'duration_ns','read_bytes','write_bytes','retained_bytes','live_bytes','max_jobs','capture_limits'},'exact profile')
        for k in ('duration_ns','read_bytes','write_bytes','retained_bytes','live_bytes','max_jobs'):natural(profile[k],k)
        need(profile['max_jobs']==111,'complete111 jobs required')
        natural(origin,'original origin');self.origin=origin;self.end=origin+profile['duration_ns'];self.clock=clock;self.p=profile
        self.cost=dict(read_bytes=0,write_bytes=0,retained_bytes=0,live_bytes=0);self.unknown=[];self.tick()
    def tick(self):
        t=self.clock();need(type(t) is int and self.origin<=t<self.end,'original strict clock');return t
    def charge(self,kind,n):
        natural(n,kind,True)
        self.cost[kind]=max(self.cost[kind],n) if kind=='live_bytes' else self.cost[kind]+n
        need(self.cost[kind]<=self.p[kind],'cumulative '+kind+' exceeded');self.tick()
    def receipt_cost(self,r,label='external'):
        # Validate the entire measurement before mutation. Missing/malformed
        # dimensions remain unknown, never reported as measured zero.
        if not (type(r) is dict and set(r)==set(self.cost) and
                all(type(v) is int and v>=0 for v in r.values())):
            self.unknown.append(label+': missing or malformed resource measurement')
            raise Refusal('exact complete typed independent resource counters')
        measured={k:(max(self.cost[k],v) if k=='live_bytes' else self.cost[k]+v) for k,v in r.items()}
        self.cost.update(measured) # Preserve all measured dimensions on overrun.
        exceeded=[k for k,v in self.cost.items() if v>self.p[k]]
        need(not exceeded,'complete measured resource overrun: '+','.join(exceeded))
        self.tick()

def qualify(q,c,verify_authority):
    """This executes before bundle/inputs/provider factories or user operands."""
    canonical_contract(c)
    need(type(q) is dict and q.get('execution_enabled') is True,'native operation is not independently qualified')
    need(q.get('scope')=='native_collection_only' and q.get('scientific_qualification') is False
         and q.get('whole_paper_complete') is False,'component scope is not scientific admission')
    need(q.get('contract_sha256')==hashlib.sha256((json.dumps(c,indent=2,sort_keys=True)+'\n').encode()).hexdigest(),'installed contract pin')
    sha(q.get('source_digest'));sha(q.get('authority_digest'))
    need(callable(verify_authority) and verify_authority(q,c) is True,'separate trusted qualification authority required')
    return q['source_digest']

def bind(c,bundle,admission,profile,source_digest,authority):
    need(type(bundle) is dict and set(bundle)=={'programs','authoring_contexts','output_root','source_digest','admission_digest','profile_digest'},'exact bundle')
    need(bundle['source_digest']==source_digest and bundle['admission_digest']==digest(admission)
         and bundle['profile_digest']==digest(profile),'source/input/profile authority join')
    need(authority.get('bundle_digest')==digest(bundle) and authority.get('admission_digest')==digest(admission)
         and authority.get('profile_digest')==digest(profile),'independently selected exact operation operands')
    keys=set(c['candidate_program_keys'])
    need(set(bundle['programs'])==set(bundle['authoring_contexts'])==keys and len(keys)==4,'all4 policies before exposure')
    contexts=list(bundle['authoring_contexts'].values())
    need(all(type(x) is str and re.fullmatch('[A-Za-z0-9_.-]{1,96}',x) for x in contexts) and len(set(contexts))==4,'four distinct authoring contexts')
    for d in bundle['programs'].values():descriptor(d)
    need(len({d['path'] for d in bundle['programs'].values()})==4,'four independent immutable program paths')
    path(bundle['output_root'])
    expected={'original_inputs','processed_epoch_inputs','identity_clock_receipt','native_path_receipt','output_schemas','exposure_receipt','history_independence_receipt','environment_receipt','runtime_receipt','parser_route','matlab_command','candidate_commands','read_only_materials','native_compatibility'}
    need(type(admission) is dict and set(admission)==expected,'complete original-source/runtime admission')
    for k in ('identity_clock_receipt','native_path_receipt','exposure_receipt','history_independence_receipt','environment_receipt','runtime_receipt'):sha(admission[k])
    original={m['id']:m for m in c['original_input_members']}
    need(set(admission['original_inputs'])==set(original),'all394 namespace-qualified original inputs required')
    for key,d in admission['original_inputs'].items():
        descriptor(d);need(d['bytes']==original[key]['bytes'] and d['path']==original[key]['member'],'exact original full release-relative native path/extent')
    need(set(admission['processed_epoch_inputs'])==set(c['processed_epoch_recompute_roots']),'all8 authentic processed epoch/header joins required')
    for item in admission['processed_epoch_inputs'].values():
        need(type(item) is dict and set(item)=={'members','identity_clock_fields_receipt','full_cohort_support_receipt'},'complete processed input mapping')
        need(type(item['members']) is list and item['members'],'no fabricated empty processed epoch input')
        for d in item['members']:descriptor(d)
        sha(item['identity_clock_fields_receipt']);sha(item['full_cohort_support_receipt'])
    # Fresh root contexts may reuse identical bodies, but one native target
    # cannot silently resolve to two different source identities.
    for root in c['roots']:
        targets={}
        members=list(admission['original_inputs'].values())+admission['processed_epoch_inputs'].get(root['id'],{}).get('members',[])
        for d in members:
            identity=(d['bytes'],d['sha256'])
            old=targets.setdefault(d['path'],identity)
            need(old==identity,'contradictory native mount identity')
    compatibility=admission['native_compatibility']
    need(type(compatibility) is dict and set(compatibility)=={r['id'] for r in c['roots']},'all37 native path compatibility records')
    for root in c['roots']:
        v=compatibility[root['id']]
        need(type(v) is dict and set(v)=={'source_sha256','platform_receipt','complete_transitive_paths_receipt','aliases','handling','no_source_normalization'},'exact native compatibility evidence')
        need(v['source_sha256']==root['source']['sha256'] and v['handling'] in ('native_platform_path_semantics','independently_reviewed_readonly_aliases') and v['no_source_normalization'] is True,'explicit path successor, never silent normalization')
        sha(v['platform_receipt']);sha(v['complete_transitive_paths_receipt'])
        aliases=v['aliases'];need(type(aliases) is list,'explicit alias list')
        seen={}
        for a in aliases:
            need(type(a) is dict and set(a)=={'literal','canonical_target','source_membership_receipt'} and type(a['literal']) is str
                 and a['literal'] and not a['literal'].startswith('/') and '..' not in a['literal'].replace('\\','/').split('/'),'bounded original literal path')
            need(len(a['literal'])<=1024 and '\n' not in a['literal'] and '\r' not in a['literal'],'single original literal')
            path(a['canonical_target']);sha(a['source_membership_receipt'])
            need(a['literal'] not in seen,'unique literal alias');seen[a['literal']]=a['canonical_target']
        for a in root['path_compatibility_required']:
            need(seen.get(a['literal'])==a['proposed_canonical_target'],'unresolved original path discrepancy')
    need(admission['parser_route']=='all_required_S_fields_already_admitted','unselected conditional parser remains blocked')
    schemas=admission['output_schemas'];need(set(schemas)=={r['id'] for r in c['roots']},'all37 source-derived output schemas required')
    for root in c['roots']:
        s=schemas[root['id']]
        need(set(s)=={'shape_signature','coverage_receipt','original_source_sha256','obligation','selectors'} and s['original_source_sha256']==root['source']['sha256']
             and s['obligation']==root['output_obligation'],'independent complete output obligation join')
        sha(s['shape_signature']);sha(s['coverage_receipt'])
        need(type(s['selectors']) is list and s['selectors'] and all(type(p) is list and p and all(type(k) in (str,int) for k in p) for p in s['selectors']),'exact value-free projection selectors required')
    for name in ('matlab_command',):
        need(type(admission[name]) is list and admission[name] and all(type(t) is str and t for t in admission[name]),'qualified executable argv')
    need(set(admission['candidate_commands'])==keys,'four candidate command bindings')
    for key,cmd in admission['candidate_commands'].items():
        need(type(cmd) is list and cmd and all(type(t) is str and t for t in cmd)
             and cmd.count('{program}')==cmd.count('{request}')==cmd.count('{output}')==1,'literal candidate argv ABI')
    materials=admission['read_only_materials']
    need(set(materials)=={'common','B_author'} and materials['common']==[c['common_paper_descriptor'],c['common_scientific_conventions']],'identical clarified paper view')
    need(materials['B_author']==c['original_source_members'],'complete exact B author-code view')
    return digest({'bundle':bundle,'admission':admission})
