"""Candidate parameter transport only; no target, model or fitted-roster reads."""
import hashlib,json,math,os,stat
from pathlib import Path
MAX_BYTES=16*1024*1024
PARTICIPANTS=('p01','p02','p05','p06','p07','p08','p09','p10','p11')
SIGNALS=('corrected_alpha','broadband','raw_alpha','low_broadband')
class InvalidSubmission(ValueError):pass
class InvalidRoster(ValueError):pass

def _fields(d,keys,error=InvalidSubmission):
    if not isinstance(d,dict) or set(d)!=set(keys):raise error('Exact object fields required')

def _sha(x):return isinstance(x,str) and len(x)==64 and all(c in '0123456789abcdef' for c in x)

def validate_roster(rows):
    if not isinstance(rows,list) or not 1<=len(rows)<=100000:raise InvalidRoster('Explicit nonempty bounded roster required; no synthesized fitted cohort')
    seen=set()
    for row in rows:
        _fields(row,('case_id','participant','electrode_id','signal','model','allow_negative_gain'),InvalidRoster)
        for k in ('case_id','electrode_id'):
            if not isinstance(row[k],str) or not row[k] or len(row[k])>512:raise InvalidRoster('Explicit bounded case/electrode identity')
        if row['case_id'] in seen or row['participant'] not in PARTICIPANTS or row['signal'] not in SIGNALS or row['model'] not in ('GS','OG') or type(row['allow_negative_gain']) is not bool:raise InvalidRoster('Roster identity/model policy')
        seen.add(row['case_id'])
    return rows

def _parameters(values,row):
    if not isinstance(values,list) or len(values)!=5 or any(type(v) not in (int,float) for v in values):raise InvalidSubmission('Exactly five numeric parameters; booleans refused')
    try:
        if not all(math.isfinite(v) for v in values):raise InvalidSubmission('Finite parameters required')
    except OverflowError as e:raise InvalidSubmission('Unrepresentable number') from e
    r,c,s,g,gr=values
    if not (-49<=r<=150 and -49<=c<=150 and s>=0 and 0<=gr<=1):raise InvalidSubmission('Source geometry parameter bounds')
    if not row['allow_negative_gain'] and g<0:raise InvalidSubmission('Negative gain not allowed by trusted case')
    if row['model']=='OG' and gr!=0:raise InvalidSubmission('OG must have GR exactly zero')
    # S=0 and GR=1 intentionally survive admission; scorer must report unsupported
    # model/numeric evaluation explicitly rather than deleting this case.
    return list(values)

def validate_submission(value,roster_rows,roster_sha256):
    rows=validate_roster(roster_rows)
    if not _sha(roster_sha256):raise InvalidRoster('Caller-authenticated roster SHA256 required')
    _fields(value,('schema','roster_sha256','cases'))
    if value['schema']!='visual_alpha_parameters_v1' or value['roster_sha256']!=roster_sha256:raise InvalidSubmission('Submission schema/roster identity')
    entries=value['cases']
    if not isinstance(entries,list) or len(entries)!=len(rows):raise InvalidSubmission('Every roster case required')
    expected={r['case_id']:r for r in rows};by={}
    for e in entries:
        _fields(e,('case_id','full','train_first','train_second'))
        ident=e['case_id']
        if not isinstance(ident,str) or ident not in expected or ident in by:raise InvalidSubmission('Case bijection: unknown/duplicate identity')
        by[ident]={'case_id':ident,**{k:_parameters(e[k],expected[ident]) for k in ('full','train_first','train_second')}}
    return {'schema':'visual_alpha_parameters_v1','roster_sha256':roster_sha256,'cases':[by[r['case_id']] for r in rows]}

def _parse(body):
    text=body.decode('utf-8');depth=0;quoted=False;escape=False
    for c in text:
        if quoted:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c=='"':quoted=False
        elif c=='"':quoted=True
        elif c in '[{':
            depth+=1
            if depth>12:raise InvalidSubmission('JSON nesting bound')
        elif c in ']}':depth-=1
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise InvalidSubmission('Duplicate JSON key')
            d[k]=v
        return d
    def integer(s):
        if len(s)>18:raise InvalidSubmission('Integer text bound')
        return int(s)
    def number(s):
        v=float(s)
        if not math.isfinite(v):raise InvalidSubmission('Nonfinite JSON number')
        return v
    def bad(s):raise InvalidSubmission('Nonfinite JSON constant')
    return json.loads(text,object_pairs_hook=pairs,parse_int=integer,parse_float=number,parse_constant=bad)

def capture_submission(path,roster_rows,roster_sha256):
    # Roster errors stay distinct from candidate transport failures.
    validate_roster(roster_rows)
    if not _sha(roster_sha256):raise InvalidRoster('Caller-authenticated roster SHA256 required')
    p=Path(path).absolute();fd=None
    try:
        if any(q.is_symlink() for q in (p,*p.parents)):raise InvalidSubmission('Linked candidate path refused')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or not 0<a.st_size<=MAX_BYTES:raise InvalidSubmission('Bounded regular single-link candidate file required')
        with os.fdopen(fd,'rb',closefd=False) as f:body=f.read(MAX_BYTES+1)
        b=os.fstat(fd);c=os.lstat(p)
        identity=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
        if len(body)!=a.st_size or identity(a)!=identity(b) or identity(a)!=identity(c):raise InvalidSubmission('Candidate changed during same-open capture')
        value=validate_submission(_parse(body),roster_rows,roster_sha256)
        return {'submission':value,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
    except (OSError,UnicodeError,json.JSONDecodeError,RecursionError,OverflowError,TypeError) as e:raise InvalidSubmission(str(e)) from e
    finally:
        if fd is not None:os.close(fd)
