"""Closed metadata primitives for the ACh controller, never scientific authority."""
import hashlib
import json
import math
import os
import stat

class Refusal(ValueError):pass

def need(value,message):
    if not value:raise Refusal(message)

def integer(value,minimum=0):
    need(type(value) is int and value>=minimum,'exact nonnegative integer')
    return value

def finite(value):
    need(type(value) in (int,float) and math.isfinite(value),'finite numeric value')
    return float(value)

def token(value):
    need(type(value) is str and 0<len(value)<=256 and all(c.isalnum() or c in '_-.' for c in value),'opaque token')
    return value

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()

def pin_bytes(value):
    need(type(value) is bytes,'exact bytes')
    return {'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}

def pin(value):return pin_bytes(encode(value))

def require_pin(value):
    need(type(value) is dict and set(value)=={'bytes','sha256'},'exact body pin')
    integer(value['bytes']);s=value['sha256']
    need(type(s) is str and len(s)==64 and all(c in '0123456789abcdef' for c in s),'SHA256')
    return value

def decode(body,maximum):
    need(type(body) is bytes and len(body)<=integer(maximum),'bounded JSON body')
    def pairs(rows):
        result={}
        for k,v in rows:
            need(k not in result,'duplicate JSON key');result[k]=v
        return result
    def bad(value):raise Refusal('nonfinite JSON')
    result=json.loads(body.decode('utf-8','strict'),object_pairs_hook=pairs,parse_constant=bad)
    encode(result)
    return result

def read_exact(path,expected,maximum,ledger=None):
    """No-follow ordinary single-link body read; ancestor custody is external."""
    require_pin(expected);need(expected['bytes']<=maximum,'extent admitted before read')
    if ledger is not None:ledger.reserve({'read_bytes':expected['bytes']+1},'captured-source/read')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0));primary=None
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],
             'ordinary exact single-link source')
        parts=[];left=expected['bytes']+1
        while left:
            block=os.read(fd,min(left,65536))
            if not block:break
            parts.append(block);left-=len(block)
        body=b''.join(parts)
        after=os.fstat(fd)
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
             (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'source changed during read')
        need(pin_bytes(body)==expected,'exact source/body identity')
        return body
    except BaseException as error:primary=error;raise
    finally:finish_owned([('source descriptor close',lambda:os.close(fd))],primary)

def exact_fields(value,names,message):
    need(type(value) is dict and set(value)==set(names),message)
    return value

def retain_secondary(primary,error,phase):
    """Keep original exception identity and ordered bounded cleanup diagnostics."""
    record={'phase':str(phase)[:192],'type':type(error).__name__}
    try:
        records=list(getattr(primary,'ach_secondary_errors',[]));records.append(record)
        setattr(primary,'ach_secondary_errors',records)
    except BaseException:
        # External failure capture remains mandatory if memory is exhausted.
        try:primary.add_note('Secondary owned cleanup failure: '+record['phase']+' '+record['type'])
        except BaseException:pass
    return record

def finish_owned(operations,primary=None):
    """Attempt every owned cleanup once in the given deterministic order.

    When called during an exception handler/finally, pass that original error;
    it remains in flight. With no prior failure, raise the first cleanup error
    after all remaining cleanup attempts, retaining ordered secondary failures.
    """
    first=primary;secondary=[]
    for phase,operation in operations:
        try:operation()
        except BaseException as error:
            if first is None:
                first=error
                try:setattr(first,'ach_primary_cleanup_phase',phase)
                except BaseException:pass
            else:secondary.append(retain_secondary(first,error,phase))
    if primary is None and first is not None:raise first
    return secondary
