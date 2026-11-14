"""Closed operator records and charged ordinary source/metadata IO."""
from __future__ import annotations
import hashlib,json,math,os,re,stat
from pathlib import Path
from tms_figure.contract import (Budget,Refusal,require,keys,pin,strict_int,
    metadata,digest,json_body,read_pinned)

def exact_budget(value):
    require(type(value) is Budget,'exact inherited cumulative Budget')
    value.charge()

def positive(value):
    require(type(value) in (int,float) and math.isfinite(value) and value>0,'positive finite operand')

def integer(value, minimum=1, maximum=None):
    require(strict_int(value,minimum) and (maximum is None or value<=maximum),'integer operand')

def canonical(value):
    def visit(x,depth=0):
        require(depth<=32,'JSON depth')
        if x is None or type(x) in (str,bool,int):return
        if type(x) is float:require(math.isfinite(x),'finite JSON');return
        require(type(x) in (dict,list),'JSON type')
        if type(x) is dict:
            require(all(type(k) is str for k in x),'JSON string keys')
            for v in x.values():visit(v,depth+1)
        else:
            for v in x:visit(v,depth+1)
    visit(value)
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode()

def body_pin(body):return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def bounded_json(value,cap):
    """Prevent complete encoding allocation beyond the selected byte cap."""
    integer(cap);active=set();nodes=0
    def extent(x,depth=0):
        nonlocal nodes
        nodes+=1;require(depth<=32 and nodes<=cap,'finite JSON structure')
        if type(x) in (str,int,float,bool) or x is None:
            if type(x) is str:
                require(len(x)<=cap and all(not 0xD800<=ord(c)<=0xDFFF for c in x),'bounded Unicode scalar text')
                n=2
                for c in x:
                    n+=2 if c in '\\"\b\f\n\r\t' else 6 if ord(c)<32 else len(c.encode('utf-8'))
                    require(n<=cap,'bounded escaped text')
                return n
            b=canonical(x);require(len(b)<=cap,'bounded scalar');return len(b)
        require(type(x) in (dict,list) and id(x) not in active,'noncyclic JSON structure');active.add(id(x))
        try:
            n=2;first=True
            for k,v in (x.items() if type(x) is dict else enumerate(x)):
                if not first:n+=1
                first=False
                if type(x) is dict:require(type(k) is str,'JSON key');n+=extent(k,depth+1)+1
                n+=extent(v,depth+1);require(n<=cap,'bounded complete JSON')
            return n
        finally:active.remove(id(x))
    n=extent(value);require(n<=cap,'bounded JSON');body=canonical(value);require(len(body)==n,'encoded JSON extent');return body

def load(path,expected,budget,cap=1048576):
    exact_budget(budget);pin(expected);require(expected['bytes']<=cap,'selected metadata cap')
    body=ordinary_body(path,expected,budget,cap);budget.charge(read=len(body),write=len(body))
    return json_body(body)

def ordinary_body(path,expected,budget,cap=1048576):
    """Finite metadata/source reader; a FIFO refuses before any blocking read."""
    pin(expected);require(expected['bytes']<=cap,'ordinary source/metadata extent')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);require(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==expected['bytes'],'ordinary pinned metadata/source')
        chunks=[];remaining=a.st_size
        while remaining:
            n=min(65536,remaining);budget.charge(read=n,write=n);b=os.read(fd,n)
            require(len(b)==n,'complete metadata/source read');chunks.append(b);remaining-=n
        budget.charge(read=a.st_size,write=a.st_size);body=b''.join(chunks)
        b=os.fstat(fd)
        require((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns),'stable metadata/source')
        require(hashlib.sha256(body).hexdigest()==expected['sha256'],'metadata/source body pin')
        return body
    finally:os.close(fd)

def save(path,value,budget,cap=1048576):
    exact_budget(budget)
    cap=min(cap,(budget.write_limit-budget.writes)//2)
    body=bounded_json(value,cap)
    budget.charge(write=2*len(body)) # encoded buffer and persistent body
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False) as stream:
            stream.write(body);stream.flush();os.fsync(fd)
    finally:os.close(fd)
    return body_pin(body)

def directory(path):
    p=Path(path).absolute()
    require(p==Path(os.path.normpath(p)),'normalized absolute path')
    for node in [p,*p.parents]:
        if node.exists():require(not node.is_symlink(),'no symlink directory ancestor')
    st=p.lstat();require(stat.S_ISDIR(st.st_mode),'ordinary directory')
    return p

def fresh_directory(path):
    p=Path(path).absolute();directory(p.parent)
    p.mkdir(mode=0o700);p.chmod(0o700)
    return p

def separate(paths):
    values=[Path(x).absolute() for x in paths]
    require(len(set(values))==len(values),'distinct locations')
    for i,a in enumerate(values):
        for b in values[i+1:]:require(not a.is_relative_to(b) and not b.is_relative_to(a),'nonoverlapping locations')

def source_members(root,budget):
    """Finite source inventory before any source body is admitted."""
    pending=[Path(root)];members=set();entries=0
    while pending:
        budget.charge()
        parent=pending.pop()
        with os.scandir(parent) as stream:
            for entry in stream:
                budget.charge();entries+=1
                require(entries<=2048,'complete source entry cap, including directories')
                path=parent/entry.name;relative=path.relative_to(root)
                require(len(relative.parts)<=64 and not entry.is_symlink(),'finite ordinary source ancestry')
                if entry.is_dir(follow_symlinks=False):pending.append(path)
                else:members.add(relative.as_posix())
    return members

def slug(value):
    require(type(value) is str and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',value),'plain unique run identifier')

LIMIT_KEYS={'cpu','ram_bytes','pids','seconds','cleanup_seconds','work_bytes','output_bytes',
    'log_bytes','transfer_bytes','model_calls','model_input_tokens','model_output_tokens',
    'terminal_calls','terminal_seconds','terminal_output_bytes'}
def limits(value):
    keys(value,LIMIT_KEYS)
    for k in LIMIT_KEYS:
        if k in {'seconds','cleanup_seconds','terminal_seconds'}:positive(value[k])
        else:integer(value[k])
    require(value['terminal_seconds']<=value['seconds'],'terminal deadline within arm')
    require(value['terminal_output_bytes']<=value['transfer_bytes'],'tool capture within transfer')
    return value

def execution_plan(value):
    keys(value,{'schema','identity','trials','views','capsule','runtime','qualification','limits',
        'source_lock','operator_lock','absolute_tolerance','relative_tolerance','tolerance_justification'})
    require(value['schema']=='tms_figure2b_execution_plan_v1','execution plan schema')
    metadata(value['identity']);keys(value['trials'],{'A','B'});keys(value['views'],{'A','B'})
    for arm in ('A','B'):slug(value['trials'][arm]);pin(value['views'][arm])
    require(value['trials']['A']!=value['trials']['B'],'separate arm identities')
    for k in ('capsule','runtime','qualification','source_lock','operator_lock','tolerance_justification'):pin(value[k])
    limits(value['limits'])
    from tms_figure.compare import tolerance
    tolerance(value['absolute_tolerance'],value['relative_tolerance'])
    return value

def capsule(value):
    keys(value,{'schema','instruction','model','parameters','model_input_reservation',
        'max_request_bytes','max_response_bytes','max_items','http_timeout_seconds'})
    require(value['schema']=='tms_figure2b_responses_capsule_v1','fixed Responses capsule')
    require(type(value['instruction']) is str and 0<len(value['instruction'])<=65536,'complete matched instructions')
    instruction=value['instruction'];lines=instruction.split('\n');index=0
    canary=re.compile(r'^(<!--.*canary.*-->|#.*canary.*)$',re.IGNORECASE)
    while index<len(lines) and canary.match(lines[index].strip()):index+=1
    while index<len(lines) and lines[index].strip()=='':index+=1
    require('\r' not in instruction and '\n'.join(lines[index:])==instruction,'instruction must survive exact pinned Harbor newline/canary handling without normalization')
    require(type(value['model']) is str and re.fullmatch(r'[!-~]{1,256}',value['model']),'explicit exact model identifier')
    p=value['parameters'];require(type(p) is dict and 'max_output_tokens' in p and set(p)<={'max_output_tokens','temperature','top_p','reasoning','text'},'selected request parameters')
    integer(p['max_output_tokens'],1,2**31-1)
    for k,upper in [('temperature',2),('top_p',1)]:
        if k in p:require(type(p[k]) in (int,float) and math.isfinite(p[k]) and 0<=p[k]<=upper,'sampling operand')
    if 'reasoning' in p:
        require(type(p['reasoning']) is dict and set(p['reasoning'])<={'effort','summary','mode','context'} and all(type(v) is str and 0<len(v)<=64 for v in p['reasoning'].values()),'explicit reasoning options')
    if 'text' in p:
        keys(p['text'],{'format'});keys(p['text']['format'],{'type'});require(p['text']['format']['type']=='text','plain text')
    integer(value['model_input_reservation']);integer(value['max_request_bytes'],1,8*2**20)
    integer(value['max_response_bytes'],1,8*2**20);integer(value['max_items'],1,65536);positive(value['http_timeout_seconds'])
    return value
