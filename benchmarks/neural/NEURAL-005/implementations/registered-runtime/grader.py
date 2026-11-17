"""Trusted numerical grader. Strict public validation precedes private decode."""
import hashlib,json,math,os,stat,sys
from pathlib import Path
sys.path.insert(0,'/source')
from probability_metrics import calculate


def need(ok,msg):
    if not ok:raise ValueError(msg)

def unique(pairs):
    obj={}
    for k,v in pairs:need(k not in obj,'duplicate JSON field');obj[k]=v
    return obj

def reject_constant(value):raise ValueError('nonfinite JSON constant:'+value)

def decode(body):return json.loads(body,object_pairs_hook=unique,parse_constant=reject_constant)

def read_pinned(path,pin):
    need(type(pin['bytes'])is int and 0<=pin['bytes']<=1000000,'bounded pinned input size')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==pin['bytes'],'ordinary exact-size pinned input')
        chunks=[];remaining=before.st_size
        while remaining:
            b=os.read(fd,min(65536,remaining));need(bool(b),'truncated input');chunks.append(b);remaining-=len(b)
        after=os.fstat(fd);need(not os.read(fd,1)and all(getattr(before,k)==getattr(after,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')),'input mutated while reading')
        body=b''.join(chunks);need(hashlib.sha256(body).hexdigest()==pin['sha256'],'pinned bytes changed');return body
    finally:os.close(fd)

def main():
    private=False
    try:
        assets=decode(Path('/source/operator_assets.json').read_bytes());inv=decode(Path('/source/invocation.json').read_bytes())
        panel=decode(read_pinned('/public/cases.json',assets['public_panel']));ids=[(r['participant'],r['case_id'])for r in panel['cases']]
        need(len(ids)==816 and len(set(ids))==816 and len({p for p,c in ids})==7,'canonical panel')
        try:
            b=read_pinned('/submission/probabilities.json',inv['submission']);need(len(b)<=assets['max_submission_bytes'],'submission cap');obj=decode(b)
            need(type(obj)is dict and set(obj)=={'schema_version','probabilities'}and type(obj['schema_version'])is int and obj['schema_version']==1,'exact submission schema')
            values=obj['probabilities'];need(type(values)is list and len(values)==len(ids),'exact case count');got={}
            for row in values:
                need(type(row)is dict and set(row)=={'participant','case_id','probability'},'exact probability fields')
                need(type(row['participant'])is str and type(row['case_id'])is str and 0<len(row['participant'])<=32 and 0<len(row['case_id'])<=64,'typed case identifiers')
                key=(row['participant'],row['case_id']);need(key not in got,'duplicate case');p=row['probability'];need(type(p)in(int,float)and math.isfinite(p)and 0<=p<=1,'finite numeric probability in[0,1]');got[key]=p
            need(set(got)==set(ids),'exact complete participant/case identities')
        except Exception as exc:
            print(json.dumps({'status':'invalid_submission','score':None,'reason':str(exc),'private_targets_decoded':False,'private_reference_probabilities_decoded':False,'candidate_chronology_verified':False}),flush=True);return 2
        # Only after every public candidate field validates may private payloads decode.
        truth=decode(read_pinned('/private/development_private.json',assets['private_targets']));private=True;refs=read_pinned('/private/reference_predictions.jsonl',assets['private_references'])
        target={}
        for r in truth['cases']:
            key=(r['request']['participant'],r['request']['case_id']);need(key not in target and type(r['target'])is int and r['target']in(0,1),'private target identity');target[key]=r['target']
        reference={}
        for line in refs.splitlines():
            r=decode(line)['prediction'];key=(r['participant'],r['case_id']);need(key not in reference and set(r['probabilities'])=={'history','prestimulus','all_erp'},'reference identity')
            need(all(type(p)in(int,float)and math.isfinite(p)and 0<=p<=1 for p in r['probabilities'].values()),'reference probability');reference[key]=r['probabilities']
        need(set(target)==set(reference)==set(ids)and set(truth['participant_ids'])=={x[0]for x in ids},'private/public panel join')
        rows=[{'participant':p,'case_id':c,'target':target[p,c],'probabilities':dict(reference[p,c],candidate=got[p,c])}for p,c in ids];result=calculate(rows)
        result.update(status='scored',score=result['equal_participant_arms']['candidate']['log_loss'],metric='equal_participant_log_loss',direction='lower',scientific_success_threshold=None,scientific_success=None,private_targets_decoded=True,private_reference_probabilities_decoded=True,candidate_chronology_verified=False,candidate_code_executed=False,coverage=truth['coverage'],scope='Static completed probability-file scoring on7development people; does not establish prefix access or source trial alignment',independent_ERP_trial_identity_verified=False,positive_gain_required=False,full_contract_qualified=False)
        b=json.dumps(result,allow_nan=False);need(len(b.encode())<=120000,'bounded result');print(b,flush=True);return 0
    except Exception as exc:
        print(json.dumps({'status':'operator_error','score':None,'reason':str(exc),'private_targets_decoded':private}),flush=True);return 1

if __name__=='__main__':raise SystemExit(main())
