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
