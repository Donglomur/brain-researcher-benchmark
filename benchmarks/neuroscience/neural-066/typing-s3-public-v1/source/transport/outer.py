"""Root-selected concrete original-clock controller observation and owned recovery.

No operation is selected by importing this module. This standalone entry loads
only authenticated source through a private import table; no sys.path or global
module alias is installed. Authentic execution requires independent root gates.
"""
import argparse,builtins,copy,hashlib,importlib.util,json,math,os,re,signal,stat,sys,time,types
from pathlib import Path

# BEGIN IDENTICAL RAW FAILURE OWNER
import sys as _failure_sys
import json as _failure_json
from itertools import islice as _failure_islice

# Source-owned process-local state. Keys are builtin integer identities; values
# retain the actual errors, so an identity cannot be recycled while in custody.
# Bootstrap explicitly supplies this store to the captured central/runtime
# modules before work; the separate native process owns its own store.
_FAILURE_RECORDS={}

def _failure_record(error):
    record=_FAILURE_RECORDS.get(id(error))
    return record if record is not None and record['error'] is error else None

def failure_store():
    return _FAILURE_RECORDS

def bind_failure_store(store):
    """Source-only bootstrap binding; no exception attributes or peer callbacks."""
    global _FAILURE_RECORDS
    if type(store) is not dict:raise RuntimeError('Failure store must be source-owned builtin dict')
    if store is _FAILURE_RECORDS:return
    # Both stores are created by this exact captured primitive. Validate primitive
    # containers before accessing keys; never inspect the held exception objects.
    for key,record in store.items():
        if type(key) is not int or type(record) is not dict or not all(type(k) is str for k in record):
            raise RuntimeError('Invalid source failure store')
        if not all(k in record for k in ('error','traceback','raw','metadata')):
            raise RuntimeError('Incomplete source failure record')
        if type(record['raw']) is not list or type(record['metadata']) is not dict:
            raise RuntimeError('Invalid source failure containers')
    for key,record in _FAILURE_RECORDS.items():
        if key in store and store[key] is not record:
            raise RuntimeError('Failure store identity collision; original stores retained')
        store[key]=record
    _FAILURE_RECORDS=store

def failure_metadata(error,name,default=None):
    if type(name) is not str:return default
    record=_failure_record(error)
    return default if record is None else record['metadata'].get(name,default)

def failure_owner(error):
    record=_failure_record(error)
    return None if record is None else record['metadata'].get('source_owner')

def remember_failure_metadata(error,name,value):
    if type(name) is not str:raise RuntimeError('Source diagnostic key must be exact text')
    record=_failure_record(error)
    if record is None:
        active=_failure_sys.exc_info()
        record={'error':error,'traceback':active[2] if active[1] is error else None,
                'raw':[],'metadata':{}}
        _FAILURE_RECORDS[id(error)]=record
    record['metadata'][name]=value

def _diagnostic_text(value,limit=4096):
    # Exact builtin str only: no __str__, repr, encoding override or user slice.
    if type(value) is not str:return '<diagnostic unavailable; raw value retained>'
    return value[:limit].encode('ascii','backslashreplace').decode('ascii')

def safe_metadata(value,depth=0):
    """Bounded exact builtin containers; unknown types use a constant fallback."""
    if depth>8:return '<diagnostic depth limit>'
    kind=type(value)
    if value is None or kind is bool:return value
    if kind is int:return value if value.bit_length()<=256 else '<large integer retained>'
    if kind is float:return value if value==value and value!=float('inf') and value!=float('-inf') else '<nonfinite diagnostic>'
    if kind is str:return _diagnostic_text(value)
    if kind is list or kind is tuple:return [safe_metadata(x,depth+1) for x in value[:128]]
    if kind is dict:
        return {_diagnostic_text(k,256):safe_metadata(v,depth+1)
                for k,v in _failure_islice(value.items(),128) if type(k) is str}
    return '<diagnostic unavailable; raw value retained>'

def diagnostic_bytes(value):
    return (_failure_json.dumps(safe_metadata(value),ensure_ascii=True,sort_keys=True,
             separators=(',',':'),allow_nan=False)+'\n').encode('ascii')

def describe_failure(error):
    record=_failure_record(error)
    typed=None if record is None else record['metadata'].get('typed_error')
    if type(typed) is dict:
        return {'type':'BenchError','message':_diagnostic_text(typed['message'],2048)}
    # Never inspect an exception's class attributes, args, __dict__ or slots.
    # Raw objects remain available in the owned record; unknown classes need no
    # executable formatting to preserve first-error identity.
    kind=type(error);label='UnknownException'
    for cls,name in ((BaseException,'BaseException'),(Exception,'Exception'),(OSError,'OSError'),
        (RuntimeError,'RuntimeError'),(ValueError,'ValueError'),(TypeError,'TypeError'),
        (KeyError,'KeyError'),(AssertionError,'AssertionError'),(TimeoutError,'TimeoutError'),
        (UnicodeError,'UnicodeError'),(UnicodeEncodeError,'UnicodeEncodeError'),
        (UnicodeDecodeError,'UnicodeDecodeError'),(SystemExit,'SystemExit')):
        if kind is cls:label=name;break
    return {'type':label,'message':'<original exception retained; executable description not invoked>'}

class FailureOwner:
    """Strong original and ordered secondary custody before diagnostic work."""
    def __init__(self):
        self.primary=None;self.traceback=None;self.raw=[];self.descriptions={}
    def hold(self,error,stage):
        # sys.exc_info reads interpreter state, not exception descriptors.
        active=_failure_sys.exc_info()
        observed_tb=active[2] if active[1] is error else None
        previous=_failure_record(error)
        prior=[] if previous is None else previous['raw']
        if self.primary is None:
            self.primary=prior[0][1] if prior else error
            self.traceback=prior[0][2] if prior else observed_tb
        if previous is not None and previous['traceback'] is None:
            previous['traceback']=observed_tb
        if self.primary is error and self.traceback is None:self.traceback=observed_tb
        for label,item,tb in tuple(prior):
            if not any(item is old for _,old,_ in self.raw):self.raw.append((label,item,tb))
        if not any(error is old for _,old,_ in self.raw):
            self.raw.append((stage,error,observed_tb))
        if previous is None:
            previous={'error':error,'traceback':observed_tb,'raw':self.raw,'metadata':{}}
            _FAILURE_RECORDS[id(error)]=previous
        if observed_tb is not None:
            self.raw[:]=[(label,item,observed_tb if item is error and tb is None else tb)
                         for label,item,tb in self.raw]
        previous['raw']=self.raw
        # Make subsequent owners see the cumulative raw list, including errors
        # first held by a subordinate ledger. No arbitrary object is inspected.
        for _,item,tb in self.raw:
            r=_failure_record(item)
            if r is None:
                r={'error':item,'traceback':tb,'raw':self.raw,'metadata':{}}
                _FAILURE_RECORDS[id(item)]=r
            r['raw']=self.raw
        remember_failure_metadata(self.primary,'source_owner',self)
        return error
    def attempt(self,stage,fn,*args,**kwargs):
        try:return fn(*args,**kwargs)
        except BaseException as error:self.hold(error,stage);return None
        finally:
            if self.primary is not None:self.hold(self.primary,stage)
    def describe(self,error):
        value=describe_failure(error);self.descriptions[id(error)]=value;return value
    def projection(self):
        if self.primary is None:return {'primary':None,'secondary':[]}
        return {'primary':self.describe(self.primary),
                'secondary':[dict(stage=_diagnostic_text(stage),**self.describe(error))
                    for stage,error,_ in self.raw if error is not self.primary],
                'raw_errors_retained':len(self.raw)}
    def attach(self,name,value):
        if self.primary is not None:remember_failure_metadata(self.primary,name,value)
    def raise_first(self):
        if self.primary is not None:
            self.attach('benchmark_failure_projection',self.projection())
            raise BaseException.with_traceback(self.primary,self.traceback)
# END IDENTICAL RAW FAILURE OWNER

def hold(error,stage='caught'):
    owner=failure_owner(error)
    if owner is None:owner=FailureOwner()
    owner.hold(error,stage);return owner

def kind(error):
    hold(error);return describe_failure(error)['type']

def describe(error):
    hold(error);return describe_failure(error)['message']

def evidence(error,key,default=None):return failure_metadata(error,key,default)
def remember(error,key,value):hold(error);remember_failure_metadata(error,key,value)

def note(primary,text):
    owner=hold(primary,'original')
    active=_failure_sys.exc_info()
    if active[1] is not None and active[1] is not primary:owner.hold(active[1],'secondary')
    owner.attach('last_source_note',safe_metadata(text))

def cleanup(primary,stage,error):
    owner=hold(primary,'original');owner.hold(error,stage)
    owner.attach('cleanup_errors',[dict(action=safe_metadata(s),**describe_failure(e))for s,e,_ in owner.raw if e is not owner.primary])

def projection(error):
    owner=hold(error);return {**describe_failure(error),'cleanup_errors':safe_metadata(failure_metadata(error,'cleanup_errors',[])),'raw_custody':owner.projection()}

failures=types.SimpleNamespace(hold=hold,kind=kind,describe=describe,evidence=evidence,remember=remember,note=note,cleanup=cleanup,projection=projection)

def need(ok, message):
    if not ok:
        raise ValueError(message)
ENCODING_METER = None

def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if ENCODING_METER is not None:
        ENCODING_METER(len(raw))
    return raw

def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def error(exc):
    return {'type': failures.kind(exc), 'message': failures.describe(exc)[:2000], 'cleanup_errors': failures.evidence(exc, 'cleanup_errors', [])}

def parse(raw):

    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate outer metadata key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'Nonfinite metadata'))

def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and (type(value['bytes']) is int) and (value['bytes'] >= 0) and (type(value['sha256']) is str) and re.fullmatch('[a-f0-9]{64}', value['sha256']), 'Exact outer descriptor')
    return value

def relative(name):
    need(type(name) is str and name and (not Path(name).is_absolute()) and ('\\' not in name) and all((x not in ('', '.', '..') for x in name.split('/'))), 'Canonical relative source/receipt path')
    return name

def capture(path, expected, cap):
    """Bootstrap read: stable named regular file with prospective explicit pin."""
    path = Path(path)
    descriptor(expected)
    need(path.is_absolute() and '..' not in path.parts and (not any((p.is_symlink() for p in (path, *path.parents)))), 'Ordinary exact outer source path')
    need(expected['bytes'] <= cap, 'Bootstrap file cap')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    primary = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and (before.st_size == expected['bytes']), 'Exact bootstrap extent')
        parts = []
        n = 0
        while True:
            raw = os.read(fd, min(65536, expected['bytes'] + 1 - n))
            if not raw:
                break
            n += len(raw)
            need(n <= expected['bytes'], 'No bootstrap growth')
            parts.append(raw)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        sig = lambda x: tuple((getattr(x, k) for k in fields))
        need(sig(before) == sig(os.fstat(fd)) == sig(path.lstat()), 'Stable complete named source')
        body = b''.join(parts)
        need(pin(body) == expected, 'Exact captured bytes/SHA')
        return body
    except BaseException as exc:
        failures.hold(exc, 'caught')
        primary = exc
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as exc:
            failures.hold(exc, 'caught')
            if primary is None:
                raise
            failures.note(primary, 'Bootstrap close uncertainty: ' + failures.kind(exc))

class Captured:
    """Private exact source loader; ordinary stdlib imports remain isolated."""

    def __init__(self, root, bodies):
        self.root = Path(root)
        self.bodies = bodies
        self.cache = {}
        self.names = {}
        for path in bodies:
            if path.endswith('.py'):
                name = path[:-3].replace('/', '.')
                if name.endswith('.__init__'):
                    name = name[:-9]
                self.names[name] = path

    def load(self, name):
        if name in self.cache:
            return self.cache[name]
        need(name in self.names, 'Complete captured source dependency: ' + name)
        parent, _, leaf = name.rpartition('.')
        if parent:
            self.load(parent)
        file = self.names[name]
        module = types.ModuleType(name)
        module.__file__ = str(self.root / file)
        module.__package__ = name if file.endswith('/__init__.py') else parent
        if file.endswith('/__init__.py'):
            module.__path__ = [str((self.root / file).parent)]

        def importing(target, globals=None, locals=None, fromlist=(), level=0):
            fromlist = () if fromlist is None else fromlist
            absolute = importlib.util.resolve_name('.' * level + target, globals['__package__']) if level else target
            top = absolute.split('.')[0]
            captured_top = any((n == top or n.startswith(top + '.') for n in self.names))
            if not captured_top:
                return builtins.__import__(target, globals, locals, fromlist, level)
            result = self.load(absolute)
            for item in fromlist:
                child = absolute + '.' + item
                if item != '*' and child in self.names and (not hasattr(result, item)):
                    setattr(result, item, self.load(child))
            return result if fromlist else self.load(top)
        module.__dict__['__builtins__'] = {**vars(builtins), '__import__': importing}
        self.cache[name] = module
        try:
            exec(compile(self.bodies[file], module.__file__, 'exec'), module.__dict__)
        except BaseException:
            self.cache.pop(name, None)
            raise
        if parent:
            setattr(self.cache[parent], leaf, module)
        return module
CHILD_BOOTSTRAP = '\nimport hashlib,json,os,stat,sys,time,types\nfrom pathlib import Path\n\n# BEGIN IDENTICAL RAW FAILURE OWNER\nimport sys as _failure_sys\nimport json as _failure_json\nfrom itertools import islice as _failure_islice\n\n# Source-owned process-local state. Keys are builtin integer identities; values\n# retain the actual errors, so an identity cannot be recycled while in custody.\n# Bootstrap explicitly supplies this store to the captured central/runtime\n# modules before work; the separate native process owns its own store.\n_FAILURE_RECORDS={}\n\ndef _failure_record(error):\n    record=_FAILURE_RECORDS.get(id(error))\n    return record if record is not None and record[\'error\'] is error else None\n\ndef failure_store():\n    return _FAILURE_RECORDS\n\ndef bind_failure_store(store):\n    """Source-only bootstrap binding; no exception attributes or peer callbacks."""\n    global _FAILURE_RECORDS\n    if type(store) is not dict:raise RuntimeError(\'Failure store must be source-owned builtin dict\')\n    if store is _FAILURE_RECORDS:return\n    # Both stores are created by this exact captured primitive. Validate primitive\n    # containers before accessing keys; never inspect the held exception objects.\n    for key,record in store.items():\n        if type(key) is not int or type(record) is not dict or not all(type(k) is str for k in record):\n            raise RuntimeError(\'Invalid source failure store\')\n        if not all(k in record for k in (\'error\',\'traceback\',\'raw\',\'metadata\')):\n            raise RuntimeError(\'Incomplete source failure record\')\n        if type(record[\'raw\']) is not list or type(record[\'metadata\']) is not dict:\n            raise RuntimeError(\'Invalid source failure containers\')\n    for key,record in _FAILURE_RECORDS.items():\n        if key in store and store[key] is not record:\n            raise RuntimeError(\'Failure store identity collision; original stores retained\')\n        store[key]=record\n    _FAILURE_RECORDS=store\n\ndef failure_metadata(error,name,default=None):\n    if type(name) is not str:return default\n    record=_failure_record(error)\n    return default if record is None else record[\'metadata\'].get(name,default)\n\ndef failure_owner(error):\n    record=_failure_record(error)\n    return None if record is None else record[\'metadata\'].get(\'source_owner\')\n\ndef remember_failure_metadata(error,name,value):\n    if type(name) is not str:raise RuntimeError(\'Source diagnostic key must be exact text\')\n    record=_failure_record(error)\n    if record is None:\n        active=_failure_sys.exc_info()\n        record={\'error\':error,\'traceback\':active[2] if active[1] is error else None,\n                \'raw\':[],\'metadata\':{}}\n        _FAILURE_RECORDS[id(error)]=record\n    record[\'metadata\'][name]=value\n\ndef _diagnostic_text(value,limit=4096):\n    # Exact builtin str only: no __str__, repr, encoding override or user slice.\n    if type(value) is not str:return \'<diagnostic unavailable; raw value retained>\'\n    return value[:limit].encode(\'ascii\',\'backslashreplace\').decode(\'ascii\')\n\ndef safe_metadata(value,depth=0):\n    """Bounded exact builtin containers; unknown types use a constant fallback."""\n    if depth>8:return \'<diagnostic depth limit>\'\n    kind=type(value)\n    if value is None or kind is bool:return value\n    if kind is int:return value if value.bit_length()<=256 else \'<large integer retained>\'\n    if kind is float:return value if value==value and value!=float(\'inf\') and value!=float(\'-inf\') else \'<nonfinite diagnostic>\'\n    if kind is str:return _diagnostic_text(value)\n    if kind is list or kind is tuple:return [safe_metadata(x,depth+1) for x in value[:128]]\n    if kind is dict:\n        return {_diagnostic_text(k,256):safe_metadata(v,depth+1)\n                for k,v in _failure_islice(value.items(),128) if type(k) is str}\n    return \'<diagnostic unavailable; raw value retained>\'\n\ndef diagnostic_bytes(value):\n    return (_failure_json.dumps(safe_metadata(value),ensure_ascii=True,sort_keys=True,\n             separators=(\',\',\':\'),allow_nan=False)+\'\\n\').encode(\'ascii\')\n\ndef describe_failure(error):\n    record=_failure_record(error)\n    typed=None if record is None else record[\'metadata\'].get(\'typed_error\')\n    if type(typed) is dict:\n        return {\'type\':\'BenchError\',\'message\':_diagnostic_text(typed[\'message\'],2048)}\n    # Never inspect an exception\'s class attributes, args, __dict__ or slots.\n    # Raw objects remain available in the owned record; unknown classes need no\n    # executable formatting to preserve first-error identity.\n    kind=type(error);label=\'UnknownException\'\n    for cls,name in ((BaseException,\'BaseException\'),(Exception,\'Exception\'),(OSError,\'OSError\'),\n        (RuntimeError,\'RuntimeError\'),(ValueError,\'ValueError\'),(TypeError,\'TypeError\'),\n        (KeyError,\'KeyError\'),(AssertionError,\'AssertionError\'),(TimeoutError,\'TimeoutError\'),\n        (UnicodeError,\'UnicodeError\'),(UnicodeEncodeError,\'UnicodeEncodeError\'),\n        (UnicodeDecodeError,\'UnicodeDecodeError\'),(SystemExit,\'SystemExit\')):\n        if kind is cls:label=name;break\n    return {\'type\':label,\'message\':\'<original exception retained; executable description not invoked>\'}\n\nclass FailureOwner:\n    """Strong original and ordered secondary custody before diagnostic work."""\n    def __init__(self):\n        self.primary=None;self.traceback=None;self.raw=[];self.descriptions={}\n    def hold(self,error,stage):\n        # sys.exc_info reads interpreter state, not exception descriptors.\n        active=_failure_sys.exc_info()\n        observed_tb=active[2] if active[1] is error else None\n        previous=_failure_record(error)\n        prior=[] if previous is None else previous[\'raw\']\n        if self.primary is None:\n            self.primary=prior[0][1] if prior else error\n            self.traceback=prior[0][2] if prior else observed_tb\n        if previous is not None and previous[\'traceback\'] is None:\n            previous[\'traceback\']=observed_tb\n        if self.primary is error and self.traceback is None:self.traceback=observed_tb\n        for label,item,tb in tuple(prior):\n            if not any(item is old for _,old,_ in self.raw):self.raw.append((label,item,tb))\n        if not any(error is old for _,old,_ in self.raw):\n            self.raw.append((stage,error,observed_tb))\n        if previous is None:\n            previous={\'error\':error,\'traceback\':observed_tb,\'raw\':self.raw,\'metadata\':{}}\n            _FAILURE_RECORDS[id(error)]=previous\n        if observed_tb is not None:\n            self.raw[:]=[(label,item,observed_tb if item is error and tb is None else tb)\n                         for label,item,tb in self.raw]\n        previous[\'raw\']=self.raw\n        # Make subsequent owners see the cumulative raw list, including errors\n        # first held by a subordinate ledger. No arbitrary object is inspected.\n        for _,item,tb in self.raw:\n            r=_failure_record(item)\n            if r is None:\n                r={\'error\':item,\'traceback\':tb,\'raw\':self.raw,\'metadata\':{}}\n                _FAILURE_RECORDS[id(item)]=r\n            r[\'raw\']=self.raw\n        remember_failure_metadata(self.primary,\'source_owner\',self)\n        return error\n    def attempt(self,stage,fn,*args,**kwargs):\n        try:return fn(*args,**kwargs)\n        except BaseException as error:self.hold(error,stage);return None\n        finally:\n            if self.primary is not None:self.hold(self.primary,stage)\n    def describe(self,error):\n        value=describe_failure(error);self.descriptions[id(error)]=value;return value\n    def projection(self):\n        if self.primary is None:return {\'primary\':None,\'secondary\':[]}\n        return {\'primary\':self.describe(self.primary),\n                \'secondary\':[dict(stage=_diagnostic_text(stage),**self.describe(error))\n                    for stage,error,_ in self.raw if error is not self.primary],\n                \'raw_errors_retained\':len(self.raw)}\n    def attach(self,name,value):\n        if self.primary is not None:remember_failure_metadata(self.primary,name,value)\n    def raise_first(self):\n        if self.primary is not None:\n            self.attach(\'benchmark_failure_projection\',self.projection())\n            raise BaseException.with_traceback(self.primary,self.traceback)\n# END IDENTICAL RAW FAILURE OWNER\n\ndef hold(error,stage=\'caught\'):\n    owner=failure_owner(error)\n    if owner is None:owner=FailureOwner()\n    owner.hold(error,stage);return owner\n\ndef kind(error):\n    hold(error);return describe_failure(error)[\'type\']\n\ndef describe(error):\n    hold(error);return describe_failure(error)[\'message\']\n\ndef evidence(error,key,default=None):return failure_metadata(error,key,default)\ndef remember(error,key,value):hold(error);remember_failure_metadata(error,key,value)\n\ndef note(primary,text):\n    owner=hold(primary,\'original\')\n    active=_failure_sys.exc_info()\n    if active[1] is not None and active[1] is not primary:owner.hold(active[1],\'secondary\')\n    owner.attach(\'last_source_note\',safe_metadata(text))\n\ndef cleanup(primary,stage,error):\n    owner=hold(primary,\'original\');owner.hold(error,stage)\n    owner.attach(\'cleanup_errors\',[dict(action=safe_metadata(s),**describe_failure(e))for s,e,_ in owner.raw if e is not owner.primary])\n\ndef projection(error):\n    owner=hold(error);return {**describe_failure(error),\'cleanup_errors\':safe_metadata(failure_metadata(error,\'cleanup_errors\',[])),\'raw_custody\':owner.projection()}\n\nfailures=types.SimpleNamespace(hold=hold,kind=kind,describe=describe,evidence=evidence,remember=remember,note=note,cleanup=cleanup,projection=projection)\ndef require(ok,message):\n    if not ok:raise ValueError(message)\ndef pairs(rows):\n    value={}\n    for key,item in rows:\n        require(key not in value,\'Duplicate child binding\');value[key]=item\n    return value\nrequire(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode,\'Isolated source-only child bootstrap\')\nrequire(len(sys.argv)==2 and len(sys.argv[1].encode())<=131072,\'Bounded exact child binding\')\nbinding=json.loads(sys.argv[1],object_pairs_hook=pairs,parse_constant=lambda x:require(False,\'Finite binding\'))\nproof=binding[\'proof\'];require(proof[\'origin\']<=time.monotonic()<proof[\'work_deadline\']<proof[\'deadline\'],\'Original child cutoff before entry capture\')\nexpected=binding[\'outer_source_pin\'];require(set(expected)=={\'bytes\',\'sha256\'} and type(expected[\'bytes\'])is int and 0<expected[\'bytes\']<=8388608,\'Exact bounded captured entry extent\')\npath=Path(binding[\'source_root\'])/\'transport/outer.py\';require(path.is_absolute() and \'..\'not in path.parts and not any(p.is_symlink()for p in(path,*path.parents)),\'Exact ordinary entry path\')\nfd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None\ntry:\n    before=os.fstat(fd);require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected[\'bytes\'],\'Complete entry source\')\n    parts=[];size=0\n    while True:\n        require(time.monotonic()<proof[\'work_deadline\'],\'Original entry capture deadline\')\n        raw=os.read(fd,min(65536,expected[\'bytes\']+1-size))\n        if not raw:break\n        size+=len(raw);require(size<=expected[\'bytes\'],\'No entry growth\');parts.append(raw)\n    fields=(\'st_dev\',\'st_ino\',\'st_size\',\'st_mode\',\'st_nlink\',\'st_mtime_ns\',\'st_ctime_ns\');stamp=lambda s:tuple(getattr(s,k)for k in fields)\n    require(stamp(before)==stamp(os.fstat(fd))==stamp(path.lstat()),\'Stable named entry source\')\n    raw=b\'\'.join(parts);require(len(raw)==expected[\'bytes\'] and hashlib.sha256(raw).hexdigest()==expected[\'sha256\'],\'Exact captured entry hash\')\nexcept BaseException as exc:primary=exc;raise\nfinally:\n    try:os.close(fd)\n    except BaseException as exc:\n        if primary is None:raise\n        bootstrap_secondary=exc  # raw secondary retained until process exit; no executable diagnostics\nmodule=types.ModuleType(\'neural066_captured_outer_child\');module.__file__=str(path)\nexec(compile(raw,str(path),\'exec\'),module.__dict__)\nraise SystemExit(module.child_main(binding,raw))\n'

def bootstrap_proof(files, operation_pin, authority_pin, manifest_pin, child_pin, source_root, origin, end, work_deadline):
    for d in (*files.values(), operation_pin, authority_pin, manifest_pin, child_pin):
        descriptor(d)
    extent = sum((d['bytes'] + 1 for d in files.values())) + sum((d['bytes'] + 1 for d in (operation_pin, authority_pin, manifest_pin, child_pin)))
    return {'schema': 'neural066_captured_controller_bootstrap_v1', 'source_root': str(source_root), 'operation_pin': operation_pin, 'authority_pin': authority_pin, 'source_manifest_pin': manifest_pin, 'child_limits_pin': child_pin, 'origin': origin, 'deadline': end, 'work_deadline': work_deadline, 'read_charge': 2 * extent + files['transport/outer.py']['bytes'] + 1, 'postcheck_write_reserve': 8192}

def child_main(binding, entry_raw):
    """Authenticated argv-bound bootstrap calls only captured controller.main."""
    required = {'schema', 'operation_path', 'authority_path', 'source_root', 'source_manifest_path', 'root', 'child_limits_path', 'proof', 'outer_source_pin'}
    need(type(binding) is dict and set(binding) == required and (binding['schema'] == 'neural066_controller_child_binding_v1'), 'Exact captured child binding')
    proof = binding['proof']
    need(type(proof) is dict and set(proof) == {'schema', 'source_root', 'operation_pin', 'authority_pin', 'source_manifest_pin', 'child_limits_pin', 'origin', 'deadline', 'work_deadline', 'read_charge', 'postcheck_write_reserve'}, 'Exact original bootstrap accounting proof')
    origin, end, work = (proof['origin'], proof['deadline'], proof['work_deadline'])
    last = origin
    need(all((type(x) in (int, float) and math.isfinite(x) for x in (origin, end, work))) and origin < work < end, 'Original child clock')

    def tick(cutoff):
        nonlocal last
        now = time.monotonic()
        need(last <= now < cutoff, 'Original captured-child clock without rollback')
        last = now
        return now
    tick(work)
    need(pin(entry_raw) == binding['outer_source_pin'], 'Fixed bootstrap captured this exact entry')
    source_root = Path(binding['source_root'])
    need(str(source_root) == proof['source_root'], 'Exact bootstrap source root')
    captures = []
    known_read_charge = binding['outer_source_pin']['bytes'] + 1

    def read(path, d, cap=8388608):
        nonlocal known_read_charge
        descriptor(d)
        known_read_charge += d['bytes'] + 1
        need(known_read_charge <= proof['read_charge'], 'Pre-reserved complete child source read charge')
        tick(work)
        raw = capture(Path(path), d, cap)
        tick(work)
        return raw
    for key, pinkey in (('operation_path', 'operation_pin'), ('authority_path', 'authority_pin'), ('source_manifest_path', 'source_manifest_pin'), ('child_limits_path', 'child_limits_pin')):
        raw = read(binding[key], proof[pinkey])
        captures.append((Path(binding[key]), proof[pinkey], raw))
    op, authority, manifest, limits = (parse(v[2]) for v in captures)
    need(op['source_root'] == str(source_root) and op['source_manifest'] == {'path': binding['source_manifest_path'], **proof['source_manifest_pin']} and (op['source_lock'] == proof['source_manifest_pin'] == authority['source_lock']), 'Original operation/authority/source closure')
    need(authority['actual_operation_selected'] is True and authority['selected_operation_sha256'] == pin(encoded(op))['sha256'] and (authority['public_export_selected'] is False), 'Exact root-selected operation')
    need(limits == op['controller_limits'] and end == origin + limits['wall_seconds'] and (work == end - op['cleanup_seconds'] - op['host_finish_seconds']), 'Unchanged child partition and original work clock')
    files = manifest['files']
    need(type(files) is dict and 0 < len(files) <= 512, 'Full bounded captured source map')
    need(files['transport/outer.py'] == binding['outer_source_pin'] and proof == bootstrap_proof(files, proof['operation_pin'], proof['authority_pin'], proof['source_manifest_pin'], proof['child_limits_pin'], source_root, origin, end, work), 'Exact source-derived both-pass reservation')
    bodies = {}
    for name, d in sorted(files.items()):
        relative(name)
        bodies[name] = read(source_root / name, d)
    need(bodies['transport/outer.py'] == entry_raw, 'Same pinned entry and private source inventory')
    modules = Captured(source_root, bodies)
    modules.load('failures').bind_failure_store(failure_store())
    controller = modules.load('controller')
    io = modules.load('transport.io')
    argv = ['--operation', binding['operation_path'], '--authority', binding['authority_path'], '--root', binding['root'], '--origin', repr(origin), '--deadline', repr(end), '--work-deadline', repr(work), '--child-limits', binding['child_limits_path']]

    class Publication:

        def __init__(self):
            self.write_charge = 0
            self.cutoff = work

        def tick(self):
            return tick(self.cutoff)

        def write(self, n):
            self.tick()
            need(type(n) is int and n >= 0 and (self.write_charge + n <= proof['postcheck_write_reserve']), 'Complete precharged child postcheck publication reserve')
            self.write_charge += n
    publication = Publication()
    controller_code = None
    try:
        tick(work)
        controller_code = controller.main(argv, bootstrap_proof=copy.deepcopy(proof))
        need(type(controller_code) is int, 'Literal controller exit disposition')
        cutoff = work if controller_code == 0 else end
        publication.cutoff = cutoff
        for name, d in files.items():
            known_read_charge += d['bytes'] + 1
            need(known_read_charge <= proof['read_charge'], 'Full post-source reservation')
            tick(cutoff)
            need(capture(source_root / name, d, 8388608) == bodies[name], 'Child source unchanged after controller')
            tick(cutoff)
        for path, d, raw in captures:
            known_read_charge += d['bytes'] + 1
            need(known_read_charge <= proof['read_charge'], 'Full post-metadata reservation')
            tick(cutoff)
            need(capture(path, d, 8388608) == raw, 'Child operation/authority/source/partition unchanged')
            tick(cutoff)
        need(known_read_charge == proof['read_charge'], 'Complete charged pre/post source coverage')
        close = {'schema': 'neural066_captured_controller_bootstrap_close_v1', 'proof': proof, 'controller_exit_code': controller_code, 'status': 'complete' if controller_code == 0 else 'incomplete', 'source_postchecked': True, 'source_read_charge': known_read_charge, 'read_charge_is_conservative_upper': True, 'finished_before_publication': tick(cutoff), 'scientific_qualification': False}
        io.publish(Path(binding['root']) / 'CHILD_BOOTSTRAP_CLOSE.json', encoded(close), publication)
        tick(cutoff)
        return controller_code
    except BaseException as primary:
        failures.hold(primary, 'caught')
        publication.cutoff = end
        try:
            doc = {'schema': 'neural066_child_bootstrap_invalidated_v1', 'complete': False, 'proof': proof, 'controller_exit_code': controller_code, 'known_source_read_charge': known_read_charge, 'error': error(primary)}
            io.publish(Path(binding['root']) / 'CHILD_BOOTSTRAP_INVALIDATED.json', encoded(doc), publication)
        except BaseException as secondary:
            failures.hold(secondary, 'caught')
            failures.note(primary, 'Child bootstrap invalidation unavailable: ' + failures.kind(secondary))
        raise

def partitions(op):
    fields = {'wall_seconds', 'read_bytes', 'write_bytes', 'retained_bytes'}
    global_limits = op['limits']
    for name in ('outer_limits', 'controller_limits'):
        value = op[name]
        need(type(value) is dict and set(value) == fields, 'Complete disjoint ' + name)
        need(value['wall_seconds'] == global_limits['wall_seconds'], 'One shared original wall clock, not summed/reset clocks')
        for key in ('read_bytes', 'write_bytes', 'retained_bytes'):
            need(type(value[key]) is int and value[key] > 0, 'Finite positive budget partition')
    for key in ('read_bytes', 'write_bytes', 'retained_bytes'):
        need(op['outer_limits'][key] + op['controller_limits'][key] <= global_limits[key], 'Disjoint parent+child global ' + key)
    a = op['outer']
    required = {'metadata_bytes', 'controller_return_bytes', 'log_bytes', 'max_events', 'event_bytes', 'cleanup_seconds', 'finish_seconds', 'grace_seconds', 'host_memory_bytes', 'recovery_limits'}
    need(type(a) is dict and set(a) == required, 'Exact complete outer profile')
    for key in required - {'recovery_limits'}:
        need(type(a[key]) is int and a[key] > 0, 'Positive outer ' + key)
    need(a['cleanup_seconds'] <= op['cleanup_seconds'] and a['finish_seconds'] <= op['host_finish_seconds'] and (a['grace_seconds'] <= a['cleanup_seconds']), 'Outer closure uses only original reserved windows')
    need(a['host_memory_bytes'] >= op['host_memory_bytes'], 'Independent outer-enforced controller memory permits original programme')
    return a

def observe_return(returned, operation_pin, authority_pin, source_pin, child_pin, origin, end, work_deadline, child_limits):
    required = {'schema', 'operation_pin', 'authority_pin', 'source_manifest_pin', 'origin', 'deadline', 'work_deadline', 'child_limits_pin', 'status', 'custody', 'roster', 'costs', 'score_pins', 'runtime_qualified', 'scientific_qualified'}
    need(type(returned) is dict and set(returned) == required and (returned['schema'] == 'neural066_controller_return_v1'), 'Exact bounded controller return schema')
    for key, value in (('operation_pin', operation_pin), ('authority_pin', authority_pin), ('source_manifest_pin', source_pin), ('child_limits_pin', child_pin), ('origin', origin), ('deadline', end), ('work_deadline', work_deadline)):
        need(type(returned[key]) is type(value) and returned[key] == value, 'Exact original controller ' + key)
    need(returned['status'] in ('complete', 'incomplete') and returned['runtime_qualified'] is False and (returned['scientific_qualified'] is False), 'Typed outcome with no qualification promotion')
    custody = returned['custody']
    need(type(custody) is dict and set(custody) == {'all_worker_phases_closed', 'all_model_sessions_closed', 'all_owned_views_retired', 'unknown_external_activity'} and all((type(v) is bool for v in custody.values())), 'Typed complete custody fields')
    roster = returned['roster']
    need(type(roster) is dict and set(roster) == {'expected', 'complete', 'failed', 'not_started', 'ledger_pin'}, 'Complete original roster summary')
    need(type(roster['expected']) is int and roster['expected'] == 11306 and all((type(roster[k]) is int and roster[k] >= 0 for k in ('complete', 'failed', 'not_started'))) and (sum((roster[k] for k in ('complete', 'failed', 'not_started'))) == 11306), 'All11306 dispositions preserved')
    costs = returned['costs']
    need(costs['origin'] == origin and costs['deadline'] == end and (type(costs['observed']) in (int, float)) and math.isfinite(costs['observed']) and (origin <= costs['observed'] < end), 'Original child cost clock')
    for key, limit in (('logical_read_charge', 'read_bytes'), ('logical_write_charge', 'write_bytes'), ('retained_charge', 'retained_bytes')):
        need(type(costs[key]) is int and 0 <= costs[key] <= child_limits[limit], 'Child full cost partition')
    if returned['status'] == 'complete':
        need(costs['observed'] < work_deadline and roster['complete'] == 11306 and all((custody[k] is True for k in ('all_worker_phases_closed', 'all_model_sessions_closed', 'all_owned_views_retired'))) and (custody['unknown_external_activity'] is False), 'Complete all phases/models/views and no unknown activity')
    return returned

def read_named(root, desc, budget, cap):
    need(type(desc) is dict and set(desc) == {'path', 'bytes', 'sha256'}, 'Exact bounded private metadata descriptor')
    relative(desc['path'])
    d = {k: desc[k] for k in ('bytes', 'sha256')}
    descriptor(d)
    need(d['bytes'] <= cap, 'Complete private metadata cap')
    budget.read(d['bytes'] + 1)
    raw = capture(Path(root) / desc['path'], d, cap)
    budget.file_reads += len(raw)
    return raw

def join_ledger(doc, planned, summary):
    need(type(doc) is dict and doc.get('schema') == 'neural066_controller_phase_ledger_v1' and (type(doc.get('rows')) is list), 'Full private controller ledger')
    expected = {row['phase_id']: row for row in planned}
    need(len(expected) == 11306, 'Unchanged complete source roster')
    got = {}
    counts = {k: 0 for k in ('complete', 'failed', 'not_started')}
    for row in doc['rows']:
        job = row['job']
        key = job['phase_id']
        need(key not in got and expected.get(key) == job, 'Every exact planned job once, no subset/duplicate')
        need(row['status'] in counts, 'Explicit complete/failed/not-started disposition')
        got[key] = True
        counts[row['status']] += 1
    need(got.keys() == expected.keys() and counts == {k: summary[k] for k in counts}, 'All original status rows join returned summary')
    return {'planned': len(expected), 'counts': counts, 'full_membership_joined': True}

def capture_score(desc, root, quarantine, budget, cap):
    need(type(desc) is dict and set(desc) == {'source_path', 'bytes', 'sha256'}, 'Exact protected score source descriptor')
    path = Path(desc['source_path'])
    need(path.is_absolute() and '..' not in path.parts and any((path.is_relative_to(Path(base)) for base in (root, quarantine))), 'Private score within selected owned output roots')
    d = {k: desc[k] for k in ('bytes', 'sha256')}
    descriptor(d)
    need(d['bytes'] <= cap, 'Complete protected score extent')
    budget.read(d['bytes'] + 1)
    raw = capture(path, d, cap)
    budget.file_reads += len(raw)
    return pin(raw)

def framed_return(result, budget):
    """Include this single publication in its counters without a hash cycle."""
    need('outer_costs' in result, 'Cost snapshot before final framing')
    base = (budget.writes, budget.retained, budget.file_writes)
    last = None
    for _ in range(16):
        raw = encoded(result)
        n = len(raw)
        if n == last:
            return raw
        last = n
        result['outer_costs'].update(logical_write_charge=base[0] + n, retained_charge=base[1] + n, successfully_published_host_file_write_bytes=base[2] + n)
    raise ValueError('Finite exact outer self-publication cost')

class Dispositions:
    """One-pass exact source roster join; no outcome inferred from absence."""

    def __init__(self, planned):
        self.rows = [{'job': copy.deepcopy(j), 'status': 'not_started', 'evidence': None} for j in planned]
        self.byid = {r['job']['phase_id']: r for r in self.rows}
        need(len(self.byid) == len(self.rows), 'Unique complete planned identities')
        self.next = 0
        self.active = None
        self.pending = None
        self.stopped = False
        self.history_error = None

    def accept(self, event, event_pin):
        kind = event.get('kind')
        if kind not in ('logical_start', 'logical_complete', 'logical_failed'):
            return
        if kind == 'logical_start':
            job = event['job']
            need(not self.stopped and self.active is None and (self.next < len(self.rows)) and (self.rows[self.next]['job'] == job), 'Exact sequential planned start, no dispatch after failure')
            if self.pending is not None:
                self.pending['status'] = 'complete'
                self.pending = None
            self.active = self.rows[self.next]
            self.next += 1
            self.active.update(status='unknown', evidence=event_pin)
        elif kind == 'logical_complete':
            need(self.active is not None and self.active['job']['phase_id'] == event['phase_id'], 'Terminal event has exact durable prior start')
            self.pending = self.active
            self.pending.update(status='unknown', evidence=event_pin)
            self.active = None
        else:
            job = event['job']
            row = self.active if self.active is not None else self.pending
            need(row is not None and row['job'] == job and (type(event['unknown_external_activity']) is bool), 'Exact failure or late terminal invalidation')
            row.update(status='failed', evidence=event_pin)
            self.active = None
            self.pending = None
            self.stopped = True

    def corrupt(self, exc):
        self.history_error = error(exc)
        for row in self.rows:
            if row['status'] == 'not_started':
                row['status'] = 'unknown'

    def document(self, journal, invalidated):
        counts = {k: sum((r['status'] == k for r in self.rows)) for k in ('complete', 'failed', 'unknown', 'not_started')}
        return {'schema': 'neural066_outer_phase_dispositions_v1', 'expected': len(self.rows), 'counts': counts, 'rows': self.rows, 'journal': journal, 'history_error': self.history_error, 'return_invalidated': invalidated, 'programme_complete': False, 'latest_unconfirmed_terminal_is_unknown': True, 'scientific_qualification': False}

def child_events(root, budget, origin, end, profile, io):
    directory = Path(root) / 'controller-journal'
    need(directory.is_dir() and (not directory.is_symlink()), 'Original exclusively owned child journal')
    names = []
    total = 0
    last = origin
    for q in directory.iterdir():
        need(len(names) < profile['max_events'] and re.fullmatch('[0-9]{7}\\.json', q.name), 'Bounded exact child event membership')
        names.append(q.name)
    for index, name in enumerate(sorted(names)):
        need(name == f'{index:07d}.json', 'Complete contiguous original child event sequence')
        raw = io.capture(directory / name, cap=profile['event_bytes'], meter=budget)
        total += len(raw)
        need(total <= profile['recovery_limits']['max_metadata_bytes'], 'Complete cumulative child-journal cap')
        event = parse(raw)
        clock = event['ledger_clock']
        observed = clock['observed']
        need(event['index'] == index and clock['origin'] == origin and (clock['deadline'] == end) and (type(observed) in (int, float)) and math.isfinite(observed) and (last <= observed <= end), 'Original immutable event index/clock')
        last = observed
        yield (event, pin(raw))

def reconstruct(root, planned, budget, origin, end, profile, io, close, invalidated):
    reducer = Dispositions(planned)
    journal = {'captured_events': 0, 'captured_bytes': 0, 'complete_contiguous': False}
    try:
        need(close is not None and close.get('reaped') is True and (close.get('process_group_absent') is True), 'Stopped controller required before authoritative journal snapshot')
        for event, d in child_events(root, budget, origin, end, profile, io):
            reducer.accept(event, d)
            journal['captured_events'] += 1
            journal['captured_bytes'] += d['bytes']
        journal['complete_contiguous'] = True
    except BaseException as exc:
        failures.hold(exc, 'caught')
        reducer.corrupt(exc)
    return reducer.document(journal, invalidated is not None)

def retire_cli(token, end, budget, grace, engine):
    """Reopen only after birth-token comparison; never signal numeric PID/PGID."""
    result = {'identity': token, 'closed': False, 'signalled': False}
    fd = None

    def absent():
        try:
            os.killpg(token['pgid'], 0)
        except ProcessLookupError:
            return True
        return False
    try:
        budget.tick()
        if absent():
            result.update(closed=True, group_absent=True)
            return result
        fd = os.pidfd_open(token['pid'], 0)

        def reserve(n):
            budget.tick()
            need(budget.reads + n <= budget.limits['read_bytes'], 'Recovery identity reserve')
        fresh = engine.process_identity(token['pid'], end, budget.read, reserve)
        need(fresh == token, 'Exact captured UID/boot/start/PID/session before recovery signal')
        signal.pidfd_send_signal(fd, signal.SIGKILL, None, 0)
        result['signalled'] = True
        cutoff = min(end, time.monotonic() + grace)
        while time.monotonic() < cutoff:
            budget.tick()
            if absent():
                result.update(closed=True, group_absent=True)
                break
            time.sleep(min(0.01, max(0, cutoff - time.monotonic())))
    except BaseException as exc:
        failures.hold(exc, 'caught')
        result['error'] = error(exc)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as exc:
                failures.hold(exc, 'caught')
                result.update(closed=False, close_error=error(exc))
    budget.tick()
    return result

def recovery_ownership(root, budget, origin, end, profile):
    """Use only complete contiguous trusted controller events, never guess IDs."""
    found = {}
    for row, d in child_events(root, budget, origin, end, profile, profile['_io']):
        if row.get('event') != 'N065-TRANSPORT' or row.get('name') != 'OWNERSHIP':
            continue
        inner = row['value']['record']
        value = inner['value']
        ownership = value['ownership']
        phase = ownership['phase_id']
        need(inner['schema'] == 'osl_transport_journal_v1' and inner['event'] == 'OWNERSHIP' and (inner['phase_id'] == phase) and (inner['request_sha256'] == ownership['request_pin']['sha256']), 'Exact externally journaled native ownership')
        need(phase not in found and type(ownership['original_deadline']) in (int, float) and (origin < ownership['original_deadline'] <= end), 'Unique original per-phase/global-clock ownership')
        found[phase] = {'request_pin': ownership['request_pin'], 'ownership_pin': value['ownership_pin'], 'journal_pin': d, 'original_phase_deadline': ownership['original_deadline']}
    return found

def recover_native(op, root, origin, end, close, close_pin, budget, modules, profile):
    """Attempt bounded actual daemon recovery; outcome remains scientifically failed."""
    result = {'schema': 'neural066_outer_recovery_v1', 'native': [], 'model_sessions': 'unknown', 'recovered_result_claim': False, 'complete_custody': False}
    if not (close.get('reaped') is True and close.get('process_group_absent') is True):
        result['reason'] = 'independent_controller_custody_missing'
        return result
    limits = profile['recovery_limits']
    required = {'max_phases', 'max_records', 'max_record_bytes', 'max_metadata_bytes', 'max_cli_calls', 'max_cli_bytes', 'source_read_bytes', 'host_write_bytes'}
    need(set(limits) == required and all((type(v) is int and v > 0 for v in limits.values())), 'Complete finite original recovery allowance')
    cleanup_end = min(end - profile['finish_seconds'], budget.tick() + profile['cleanup_seconds'])
    need(cleanup_end > budget.tick(), 'Original bounded cleanup window remains')
    engine = modules.load('transport.vendor.engine')
    io = modules.load('transport.io')
    provider_module = modules.load('transport.vendor.provider')
    observed = []
    old_work_end = getattr(budget, 'work_end', None)
    budget.work_end = cleanup_end
    try:
        ownership = recovery_ownership(root, budget, origin, end, {**profile, '_io': io})
        need(len(ownership) <= limits['max_phases'], 'All known phases fit complete recovery envelope')
        c = op['native_transport']
        control = Path(c['control_root'])
        known = set(ownership)
        directories = []
        if control.exists():
            for q in control.iterdir():
                need(len(directories) < limits['max_phases'] and q.is_dir() and (not q.is_symlink()), 'Bounded original native control roots')
                directories.append(q.name)
        need(set(directories) == known, 'No unjournaled/missing native phase guessed closed')
        read_upper = limits['max_phases'] * limits['source_read_bytes']
        write_upper = limits['max_phases'] * limits['host_write_bytes']
        budget.reserve_producer('outer-owned-native-recovery', read_upper, write_upper, write_upper)
        provider = provider_module.Provider(c['control_root'], c['quarantine_root'], c['docker_binary'], c['docker_socket'], c['engine_source'], c['trusted_exposures'], read_upper, write_upper)
        for phase, row in sorted(ownership.items()):
            need(budget.tick() < cleanup_end, 'Original recovery cutoff')
            phase_root = control / phase
            names = []
            for q in phase_root.iterdir():
                need(len(names) < limits['max_records'] + 16, 'Bounded native control inventory')
                names.append(q.name)
            for name in sorted(names):
                if not re.fullmatch('[0-9]{6}-CLI-CHILD\\.json', name):
                    continue
                path = phase_root / name
                n = path.stat().st_size
                need(0 < n <= limits['max_record_bytes'], 'Complete CLI ownership cap')
                budget.read(n + 1)
                raw = io.capture(path, cap=limits['max_record_bytes'])
                item = parse(raw)
                need(item['schema'] == 'osl_transport_journal_v1' and item['phase_id'] == phase and (item['request_sha256'] == row['request_pin']['sha256']) and (item['event'] == 'CLI-CHILD') and (name == f"{item['index']:06d}-CLI-CHILD.json"), 'Exact phase/request CLI event')
                v = item['value']
                need(v['docker_exec_still_gated'] is True and v['independent_group'] is True and (v['pid'] == v['pgid'] == v['process_identity']['pid']), 'Recorded pre-exec CLI custody')
                cli = retire_cli(v['process_identity'], cleanup_end, budget, profile['grace_seconds'], engine)
                observed.append({'phase': phase, 'record': pin(raw), 'closure': cli})
                need(cli['closed'] is True, 'Unknown CLI group blocks daemon recovery')
            per = {k: limits[k] for k in required - {'max_phases'}}
            old_call, old_meter = (provider_module.Docker, provider_module.Meter)

            class RecoveryDocker(old_call):

                def __call__(self, args, deadline, kind, cap=131072):
                    return super().__call__(args, cleanup_end, kind, cap)

            class RecoveryMeter(old_meter):

                def __init__(self, reads, writes, deadline):
                    super().__init__(reads, writes, cleanup_end)
            provider_module.Docker, provider_module.Meter = (RecoveryDocker, RecoveryMeter)
            try:
                recovered = provider.recover(phase, row['request_pin'], row['ownership_pin'], row['original_phase_deadline'], lambda name, value: budget.event({'event': 'OUTER-RECOVERY', 'phase': phase, 'name': name, 'value': value}), per, close_pin)
            finally:
                provider_module.Docker, provider_module.Meter = (old_call, old_meter)
            result['native'].append(recovered)
            need(budget.tick() < cleanup_end, 'Recovery receipt before original cleanup cutoff')
        result['all_recorded_native_resources_closed'] = all((r['receipt']['all_resource_custody_closed'] is True for r in result['native']))
        result['recorded_cli'] = observed
    except BaseException as exc:
        failures.hold(exc, 'caught')
        result.update(error=error(exc), recorded_cli=observed, all_recorded_native_resources_closed=False)
    finally:
        if old_work_end is None:
            del budget.work_end
        else:
            budget.work_end = old_work_end
    return result

def run(operation_path, operation_pin, authority_path, authority_pin, source_root, source_manifest_path, source_manifest_pin, root, origin):
    """One source-qualified whole operation; actual root selection is mandatory."""
    need(not sys.flags.optimize, 'No disabled source assertions')
    need(type(origin) is float and math.isfinite(origin) and (0 <= origin <= time.monotonic()), 'Original outer origin before admission')
    operation_path = Path(operation_path)
    authority_path = Path(authority_path)
    source_root = Path(source_root)
    source_manifest_path = Path(source_manifest_path)
    root = Path(root)
    operation_raw = capture(operation_path, operation_pin, 8388608)
    authority_raw = capture(authority_path, authority_pin, 8388608)
    op = parse(operation_raw)
    authority = parse(authority_raw)
    need(op.get('schema') == 'neural066_complete_operation_v1' and authority.get('schema') == 'neural066_root_execution_authority_v1' and (authority.get('actual_operation_selected') is True) and (authority.get('public_export_selected') is False) and (authority.get('selected_operation_sha256') == pin(encoded(op))['sha256']), 'Explicit independent root operation selection before source/qualification operands')
    need(len(str(root).encode()) <= 4096, 'Bounded root path for exact entry response')
    profile = partitions(op)
    end = origin + op['limits']['wall_seconds']
    work_deadline = end - op['cleanup_seconds'] - op['host_finish_seconds']
    need(time.monotonic() < work_deadline < end, 'Unextended full original operation clock')
    need(source_root.is_absolute() and (not any((q.is_symlink() for q in (source_root, *source_root.parents)))) and (op['source_root'] == str(source_root)), 'Exact immutable source root')
    need(op['source_manifest'] == {'path': str(source_manifest_path), **source_manifest_pin} and op['source_lock'] == source_manifest_pin and (authority['source_lock'] == source_manifest_pin), 'Exact operation/root source-manifest binding')
    bootstrap_read = operation_pin['bytes'] + authority_pin['bytes'] + source_manifest_pin['bytes'] + 3
    need(bootstrap_read <= op['outer_limits']['read_bytes'], 'Source admission reservation before reads')
    manifest_raw = capture(source_manifest_path, source_manifest_pin, profile['metadata_bytes'])
    manifest = parse(manifest_raw)
    files = manifest['files']
    need(type(files) is dict and 0 < len(files) <= 512, 'Complete bounded source file map')
    required = {'controller.py', 'core.py', 'safe_io.py', 'budget.py', 'operation.py', 'transport/outer.py', 'transport/host.py', 'transport/io.py', 'transport/vendor/provider.py', 'transport/vendor/SOURCE_MANIFEST.json'}
    need(required <= set(files), 'Full concrete owner/controller/outer source closure')
    bodies = {}
    for name, d in sorted(files.items()):
        relative(name)
        descriptor(d)
        need(d['bytes'] <= 8388608, 'Bounded individual source member')
        bootstrap_read += d['bytes'] + 1
        need(bootstrap_read <= op['outer_limits']['read_bytes'], 'Full source read allocation')
        need(time.monotonic() < work_deadline, 'Source admission in original clock')
        bodies[name] = capture(source_root / name, d, 8388608)
    bootstrap_read += files['transport/outer.py']['bytes'] + 1
    need(bootstrap_read <= op['outer_limits']['read_bytes'], 'Executing-source reread reserved')
    need(Path(__file__).resolve() == (source_root / 'transport/outer.py').resolve() and pin(capture(Path(__file__).resolve(), files['transport/outer.py'], 8388608)) == files['transport/outer.py'], 'Executing exact outer source')
    modules = Captured(source_root, bodies)
    modules.load('failures').bind_failure_store(failure_store())
    budget_class = modules.load('budget').Budget
    operation = modules.load('operation')
    core = modules.load('core')
    io = modules.load('transport.io')
    host = modules.load('transport.host')
    bounds = modules.load('transport.vendor.bounds')
    need(root.is_absolute() and (not os.path.lexists(root)) and (not any((q.is_symlink() for q in root.parents))), 'Fresh exclusive outer/controller namespace')
    root.mkdir(mode=448)
    journal = root / 'outer-journal'
    journal.mkdir(mode=448)
    bounds.fsync_dir(root)
    bounds.fsync_dir(root.parent)
    budget = budget_class(op['outer_limits'], origin, journal)
    budget.max_events = profile['max_events']
    budget.max_event_bytes = profile['event_bytes']
    budget.read(bootstrap_read)
    budget.tick()
    reservation = operation.admit(op, authority, op['authority_root'],meter=budget)
    for kind, key in (('read', 'read_bytes'), ('write', 'write_bytes'), ('retained', 'retained_bytes')):
        need(op['controller_limits'][key] >= reservation[kind + '_upper'], 'Complete selected programme fits child ' + key)
    work_seconds = reservation['wall_upper'] - op['cleanup_seconds'] - op['host_finish_seconds']
    need(budget.tick() + work_seconds < work_deadline, 'Full unchanged programme wall allowance remains after source admission')

    class ReadAdapter:

        def tick(self):
            return budget.tick()

        def read(self, n):
            budget.read(n)

        def ensure_read(self, n):
            budget.tick()
            need(budget.reads + n <= budget.limits['read_bytes'], 'Complete stream read reserve')
    python = op['host_python']
    need(type(python) is dict and set(python) == {'path', 'bytes', 'sha256'}, 'Qualified exact host Python')
    bounds.body(python['path'], {k: python[k] for k in ('bytes', 'sha256')}, ReadAdapter(), python['bytes'], False)
    failure_ledger_upper = sum((len(encoded({'job': j, 'status': 'unknown', 'evidence': None})) + 500 for j in core.roster())) + 8192
    need(profile['metadata_bytes'] >= failure_ledger_upper, 'Complete all-11306 failure ledger admission before launch')
    need(budget.writes + failure_ledger_upper + profile['metadata_bytes'] <= budget.limits['write_bytes'] and budget.retained + failure_ledger_upper + profile['metadata_bytes'] <= budget.limits['retained_bytes'], 'Full failure ledger and terminal receipt headroom')
    child_raw = encoded(op['controller_limits'])
    child_pin = pin(child_raw)
    proof = bootstrap_proof(files, operation_pin, authority_pin, source_manifest_pin, child_pin, source_root, origin, end, work_deadline)
    need(op['controller_limits']['read_bytes'] >= reservation['read_upper'] + proof['read_charge'], 'Both full bootstrap source passes fit the original child partition')
    for key in ('write', 'retained'):
        need(op['controller_limits'][key + '_bytes'] >= reservation[key + '_upper'] + proof['postcheck_write_reserve'], 'Precharged child terminal/invalidation metadata fits complete original reservation')
    budget.save(root / 'CHILD_LIMITS.json', child_raw)
    binding = {'schema': 'neural066_controller_child_binding_v1', 'operation_path': str(operation_path), 'authority_path': str(authority_path), 'source_root': str(source_root), 'source_manifest_path': str(source_manifest_path), 'root': str(root), 'child_limits_path': str(root / 'CHILD_LIMITS.json'), 'proof': proof, 'outer_source_pin': files['transport/outer.py']}
    binding_raw = encoded(binding)
    need(len(binding_raw) <= 131072, 'Exact bounded observed child binding')
    argv = [python['path'], '-I', '-S', '-B', '-c', CHILD_BOOTSTRAP, binding_raw.decode()]
    budget.event({'event': 'OUTER-INTENT', 'argv': argv, 'operation_pin': operation_pin, 'authority_pin': authority_pin, 'source_manifest_pin': source_manifest_pin, 'child_limits_pin': child_pin, 'origin': origin, 'deadline': end, 'work_deadline': work_deadline})
    close = None
    close_pin = None
    returned = None
    returned_raw = None
    returned_pin = None
    recovery = None
    ledger = None
    scores = {}
    errors = []
    logs = {}
    status = 'incomplete'
    invalidation = None
    failure_ledger_pin = None
    bootstrap_close = None
    bootstrap_close_pin = None

    def failed(step, exc):
        errors.append({'step': step, **error(exc)})
    try:
        close = host.observe_controller(argv, root, {'origin': origin, 'deadline': end}, work_deadline, budget, profile['grace_seconds'], profile['log_bytes'], profile['host_memory_bytes'])
    except BaseException as exc:
        failures.hold(exc, 'caught')
        failed('controller_observation', exc)
    if close is not None:
        raw_logs = close.pop('logs_data', {})
        for name in ('stdout', 'stderr'):
            try:
                raw = raw_logs[name]
                need(type(raw) is bytes and len(raw) <= profile['log_bytes'] + 1 and (pin(raw) == close['logs'][name]), 'Exact actual complete or overflow-sentinel worker log')
                logs[name] = budget.save(root / ('controller.' + name + '.log'), raw)
            except BaseException as exc:
                failures.hold(exc, 'caught')
                failed('publish_' + name, exc)
        try:
            close_pin = budget.save(root / 'CONTROLLER_CLOSE.json', encoded(close))
        except BaseException as exc:
            failures.hold(exc, 'caught')
            failed('publish_controller_close', exc)
    try:
        path = root / 'CONTROLLER_RETURN.json'
        n = path.stat().st_size
        need(0 < n <= profile['controller_return_bytes'], 'Bounded complete controller return')
        budget.read(n + 1)
        returned_raw = io.capture(path, cap=profile['controller_return_bytes'])
        returned_pin = pin(returned_raw)
        returned = parse(returned_raw)
    except BaseException as exc:
        failures.hold(exc, 'caught')
        failed('capture_controller_return', exc)
    try:
        bootstrap_raw = io.capture(root / 'CHILD_BOOTSTRAP_CLOSE.json', cap=8192, meter=budget)
        bootstrap_close_pin = pin(bootstrap_raw)
        bootstrap_close = parse(bootstrap_raw)
    except BaseException as exc:
        failures.hold(exc, 'caught')
        failed('capture_child_bootstrap_close', exc)
    try:
        if os.path.lexists(root / 'CHILD_BOOTSTRAP_INVALIDATED.json'):
            raw = io.capture(root / 'CHILD_BOOTSTRAP_INVALIDATED.json', cap=8192, meter=budget)
            invalidation = {'pin': pin(raw), 'value': parse(raw)}
            raise ValueError('Captured child bootstrap invalidated its source/terminal check')
        if os.path.lexists(root / 'RETURN_INVALIDATED.json'):
            raw = io.capture(root / 'RETURN_INVALIDATED.json', cap=profile['metadata_bytes'], meter=budget)
            invalidation = {'pin': pin(raw), 'value': parse(raw)}
            raise ValueError('Controller published additive return invalidation')
        need(not errors and close_pin is not None and (close['natural_exit'] is True) and (close['forced'] is False) and (close['reaped'] is True) and (close['process_group_absent'] is True) and (close['error'] is None) and (close['cleanup_errors'] == []), 'Independent natural complete controller closure')
        need(close['argv'] == argv and close['origin'] == origin and (close['global_deadline'] == end) and (close['work_deadline'] == work_deadline) and (origin <= close['started'] <= close['finished'] <= budget.tick() < end), 'Fresh exact host closure and original clock')
        need(type(bootstrap_close) is dict and set(bootstrap_close) == {'schema', 'proof', 'controller_exit_code', 'status', 'source_postchecked', 'source_read_charge', 'read_charge_is_conservative_upper', 'finished_before_publication', 'scientific_qualification'} and (bootstrap_close['schema'] == 'neural066_captured_controller_bootstrap_close_v1'), 'Exact captured child source-close schema')
        need(bootstrap_close['proof'] == proof and type(bootstrap_close['controller_exit_code']) is int and (bootstrap_close['controller_exit_code'] == 0) and (bootstrap_close['status'] == 'complete') and (bootstrap_close['source_postchecked'] is True) and (bootstrap_close['source_read_charge'] == proof['read_charge']) and (bootstrap_close['read_charge_is_conservative_upper'] is True) and (bootstrap_close['scientific_qualification'] is False), 'All captured child source/clock/accounting commitments')
        need(origin <= bootstrap_close['finished_before_publication'] <= close['finished'] < work_deadline, 'Child postcheck publication and natural close inside original work cutoff')
        observe_return(returned, operation_pin, authority_pin, source_manifest_pin, child_pin, origin, end, work_deadline, op['controller_limits'])
        ledger_doc = parse(read_named(root, returned['roster']['ledger_pin'], budget, profile['metadata_bytes']))
        ledger = join_ledger(ledger_doc, core.roster(), returned['roster'])
        need(type(returned['score_pins']) is dict and set(returned['score_pins']) <= {'primary', 'independent'}, 'Only declared protected scorers')
        for name, d in returned['score_pins'].items():
            scores[name] = capture_score(d, root, op['native_transport']['quarantine_root'], budget, profile['metadata_bytes'])
        if returned['status'] == 'complete':
            need(set(scores) == {'primary', 'independent'}, 'Both complete original protected scorers required')
            status = 'complete'
    except BaseException as exc:
        failures.hold(exc, 'caught')
        failed('private_complete_join', exc)
    if status != 'complete':
        try:
            need(close is not None, 'Captured independent closure proof required for recovery')
            if close_pin is None:
                close_pin = budget.save(root / 'RECOVERY_CONTROLLER_CLOSE.json', encoded(close))
            recovery = recover_native(op, root, origin, end, close, close_pin, budget, modules, profile)
        except BaseException as exc:
            failures.hold(exc, 'caught')
            failed('bounded_native_recovery', exc)
    if status != 'complete':
        try:
            diagnosis = reconstruct(root, core.roster(), budget, origin, end, profile, io, close, invalidation)
            failure_raw = encoded(diagnosis)
            need(len(failure_raw) <= profile['metadata_bytes'], 'Full failure ledger within admitted extent')
            failure_ledger_pin = budget.save(root / 'OUTER_PHASE_LEDGER.json', failure_raw)
        except BaseException as exc:
            failures.hold(exc, 'caught')
            failed('full_failure_dispositions', exc)
    try:
        for name, d in files.items():
            budget.read(d['bytes'] + 1)
            need(capture(source_root / name, d, 8388608) == bodies[name], 'Source unchanged after complete controller lifecycle')
        for path, d, raw in ((operation_path, operation_pin, operation_raw), (authority_path, authority_pin, authority_raw), (source_manifest_path, source_manifest_pin, manifest_raw)):
            budget.read(d['bytes'] + 1)
            need(capture(path, d, max(8388608, d['bytes'])) == raw, 'Operation/authority/source manifest unchanged')
        budget.tick()
    except BaseException as exc:
        failures.hold(exc, 'caught')
        failed('final_source_clock', exc)
        status = 'incomplete'
    if errors:
        status = 'incomplete'
    result = {'schema': 'neural066_outer_return_v1', 'status': status, 'operation_pin': operation_pin, 'authority_pin': authority_pin, 'source_manifest_pin': source_manifest_pin, 'origin': origin, 'deadline': end, 'work_deadline': work_deadline, 'controller_close_pin': close_pin, 'controller_return_pin': returned_pin, 'unadmitted_controller_return': returned if status != 'complete' else None, 'controller_return_parseable': returned is not None, 'child_bootstrap_close_pin': bootstrap_close_pin, 'unadmitted_child_bootstrap_close': bootstrap_close if status != 'complete' else None, 'logs': logs, 'full_ledger_join': ledger, 'failure_ledger_pin': failure_ledger_pin, 'return_invalidation': invalidation, 'score_pins': scores, 'recovery': recovery, 'errors': errors, 'custody': 'joined_complete' if status == 'complete' else 'unknown', 'caller_custody_claim': False, 'scientific_qualified': False, 'runtime_qualified': False, 'partitions': {'outer': op['outer_limits'], 'controller': op['controller_limits']}, 'unknown_child_costs_never_refund_original_partition': True}
    try:
        budget.event({'event': 'OUTER-CLOSE', 'status': status, 'controller_close_pin': close_pin, 'controller_return_pin': returned_pin})
        budget.write(8192)
        result['entry_stdout_reserved_bytes'] = 8192
        result['outer_costs'] = budget.snapshot()
        budget.tick()
        raw = framed_return(result, budget)
        need(len(raw) <= profile['metadata_bytes'], 'Complete outer return extent')
        receipt = budget.save(root / 'OUTER_RETURN.json', raw)
        budget.tick()
        need(time.monotonic() < end, 'Fresh original clock after outer final publication')
        return {'receipt': receipt, 'path': str(root / 'OUTER_RETURN.json'), 'status': status, 'complete': status == 'complete', 'caller_custody_claim': False, 'final_outer_counters': budget.snapshot()}
    except BaseException as exc:
        failures.hold(exc, 'caught')
        failures.remember(exc, 'outer_unadmitted_result', result)
        failures.remember(exc, 'controller_return_raw', returned_raw)
        try:
            budget.save(root / 'OUTER_INVALIDATED.json', encoded({'schema': 'neural066_outer_invalidated_v1', 'complete': False, 'error': error(exc)}))
        except BaseException as secondary:
            failures.hold(secondary, 'caught')
            failures.note(exc, 'Outer invalidation publication uncertainty: ' + failures.kind(secondary))
        raise

def main(argv=None):
    origin = time.monotonic()
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('operation', 'authority', 'source-root', 'source-manifest', 'root'):
        p.add_argument('--' + key, required=True)
    for key in ('operation', 'authority', 'source-manifest'):
        p.add_argument('--' + key + '-bytes', required=True, type=int)
        p.add_argument('--' + key + '-sha256', required=True)
    args = p.parse_args(argv)
    need(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode, 'Root outer entry uses -I -S -B')
    result = run(args.operation, {'bytes': args.operation_bytes, 'sha256': args.operation_sha256}, args.authority, {'bytes': args.authority_bytes, 'sha256': args.authority_sha256}, args.source_root, args.source_manifest, {'bytes': args.source_manifest_bytes, 'sha256': args.source_manifest_sha256}, args.root, origin)
    reply = encoded({k: result[k] for k in ('receipt', 'path', 'status', 'complete', 'caller_custody_claim')})
    need(len(reply) <= 8192, 'Precharged exact bounded entry response')
    print(reply.decode(), end='')
    return 0 if result['complete'] else 1
if __name__ == '__main__':
    raise SystemExit(main())
