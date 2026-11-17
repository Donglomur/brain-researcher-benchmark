"""Independent outer cleanup of exact durable candidate and scorer ownership."""
from pathlib import Path
import json,stat,subprocess,time
from engine import DOCKER,ENV
from absence import absence

def bounded_json(path,cap=65536):
    p=Path(path);s=p.lstat()
    if p.is_symlink()or not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or not 0<s.st_size<=cap:raise ValueError('Bounded operator journal required')
    return json.loads(p.read_text())

def valid_name(name,prefix):return type(name)is str and name.startswith(prefix)and len(name)==len(prefix)+32 and all(c in'0123456789abcdef'for c in name[len(prefix):])

def owned(attempt):
    attempt=Path(attempt);rows=[];score=attempt/'score.json.ownership.json'
    if score.exists():
        v=bounded_json(score);name=v['owned_container']
        if v.get('attempted_before_dispatch')is not True or not valid_name(name,'dmfc-timing-score-'):raise ValueError('Exact owned scorer identity')
        rows.append(('container',name))
    journal=attempt/'resource_ownership.json'
    if journal.exists():
        v=bounded_json(journal);original=v['owned']
        if type(original)is not list or len(original)>3:raise ValueError('At most three explicit candidate resources')
        for row in reversed(original):
            kind,name=row['kind'],row['name'];prefixes=('dmfc-prog-volume-',)if kind=='volume'else('dmfc-prog-holder-','dmfc-prog-worker-')if kind=='container'else()
            if row.get('attempted_before_dispatch')is not True or not any(valid_name(name,p)for p in prefixes):raise ValueError('Exact owned program resource')
            rows.append((kind,name))
    if len(set(rows))!=len(rows):raise ValueError('Duplicate resource ownership')
    return rows

def recover(attempt,end):
    result=[]
    for kind,name in owned(attempt):
        row={'kind':kind,'name':name,'absence_verified':False,'commands':[]};result.append(row)
        for argv in (['volume','rm',name]if kind=='volume'else['rm','--force',name],['volume','inspect',name]if kind=='volume'else['inspect','--type','container',name]):
            try:
                remaining=end-time.monotonic()
                if remaining<=0:raise TimeoutError('Reserved cleanup deadline')
                p=subprocess.run([DOCKER,*argv],env=ENV,capture_output=True,timeout=min(2,remaining));full=len(p.stdout)<=4096 and len(p.stderr)<=4096
                event={'argv':argv,'returncode':p.returncode,'stdout':p.stdout[:4096].decode(errors='replace'),'stderr':p.stderr[:4096].decode(errors='replace'),'untruncated':full};row['commands'].append(event)
                if 'inspect'in argv:row['absence_verified']=full and absence(p.returncode,event['stdout'],event['stderr'],kind,name)
            except Exception as e:row.setdefault('errors',[]).append(repr(e))
    return result
