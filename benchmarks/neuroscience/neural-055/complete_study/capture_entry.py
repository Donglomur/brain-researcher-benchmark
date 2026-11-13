"""Trusted bounded opaque capture, including failures, after actor retirement.

No model/header deserialization. The CLI has a fixed /capture root and fixed ABI
caps. capture() accepts an explicit root solely for owned engineering fixtures.
"""
import base64,hashlib,json,os,stat,sys,time,re
from pathlib import Path
from n055.common import diagnostic_type
CAPS={'fit':{'model.bin':268435456,'selected_method.json':8388608,'operations.json':8388608},'infer':{'prediction.json':4194304,'operations.json':8388608}}

def require(value,message):
    if not value:raise ValueError(message)
def stamp(s):return(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def capture(root,kind):
    require(kind in CAPS,'literal original capture kind');root=Path(root);names=CAPS[kind];result={};errors=[];entries=[];directory=None
    try:
        directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);original=os.fstat(directory)
        require(stat.S_ISDIR(original.st_mode),'ordinary original capture root')
        # Bounded namespace inspection, never follow unexpected entries.
        with os.scandir(directory) as scan:
            for row in scan:
                if len(entries)>=32:errors.append({'kind':'namespace_entry_cap','remaining_names_unobserved':True});break
                entries.append(row.name)
        if set(entries)!=set(names):errors.append({'kind':'declared_namespace_mismatch','observed_names':entries})
        for name,cap in names.items():
            row={'status':'unobserved','observed_bytes':0,'bytes':0,'sha256':hashlib.sha256(b'').hexdigest(),'base64':'','source_size':None,'complete':False,'errors':[]};result[name]=row;fd=None;body=bytearray();before=None
            try:
                before=os.stat(name,dir_fd=directory,follow_symlinks=False);row['source_size']=before.st_size
                require(stat.S_ISREG(before.st_mode)and before.st_nlink==1,'ordinary single-link original output')
                fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory);require(stamp(os.fstat(fd))==stamp(before),'same original output handle')
                while len(body)<min(before.st_size,cap):
                    chunk=os.read(fd,min(65536,min(before.st_size,cap)-len(body)));body.extend(chunk)
                    require(bool(chunk),'original output truncated')
                after=os.fstat(fd);named=os.stat(name,dir_fd=directory,follow_symlinks=False)
                require(stamp(before)==stamp(after)==stamp(named),'stable complete original output identity')
                require(before.st_size<=cap,'original output exceeds fixed ABI cap')
                require(len(body)==before.st_size and len(body)>0,'complete nonempty original output')
                row['complete']=True;row['status']='complete'
            except FileNotFoundError as exc:row['status']='missing';row['errors'].append({'type':diagnostic_type(exc)})
            except BaseException as exc:row['status']='partial_or_invalid';row['errors'].append({'type':diagnostic_type(exc)})
            finally:
                if fd is not None:
                    try:os.close(fd)
                    except BaseException as exc:row['complete']=False;row['status']='close_failed';row['errors'].append({'type':diagnostic_type(exc),'phase':'close'})
                # Every actually returned prefix precedes fallible final encoding.
                row.update(bytes=len(body),observed_bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),base64=base64.b64encode(body).decode('ascii'))
        require(stamp(os.fstat(directory))==stamp(original)==stamp(root.lstat()),'same final capture directory')
    except BaseException as exc:errors.append({'type':diagnostic_type(exc),'phase':'capture_namespace'})
    finally:
        if directory is not None:
            try:os.close(directory)
            except BaseException as exc:errors.append({'type':diagnostic_type(exc),'phase':'capture_directory_close'})
    return {'schema':'n055-phase-capture-v3','kind':kind,'files':result,'namespace':entries,'errors':errors,'complete':not errors and set(result)==set(names)and all(r['complete']for r in result.values()),'partial_bytes_are_not_valid_outputs':True}

def request_capture(root,sequence):
    require(type(sequence)is int and 0<=sequence<100000000,'finite original request sequence')
    root=Path(root);result={'schema':'n055-broker-request-capture-v3','sequence':sequence,'status':'pending','pin':None,'base64':'','errors':[],'partial_names':[],'observed_names':[]}
    directory=None;fd=None;body=bytearray();original=None
    try:
        directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);original=os.fstat(directory)
        require(stat.S_ISDIR(original.st_mode),'ordinary original request directory')
        with os.scandir(directory) as entries:
            for entry in entries:
                require(len(result['observed_names'])<4096,'bounded original request namespace')
                name=entry.name;result['observed_names'].append(name)
                require(re.fullmatch(r'[0-9]{8}\.(json|partial)',name),'only request protocol entries')
                number=int(name[:8]);require(number<=sequence,'no unadmitted future request')
                if name.endswith('.partial'):
                    require(number==sequence,'no abandoned previous partial request');result['partial_names'].append(name)
        name=f'{sequence:08d}.json'
        if name in result['observed_names']:
            require(not result['partial_names'],'atomic complete request without competing partial')
            before=os.stat(name,dir_fd=directory,follow_symlinks=False)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=1048576,'bounded ordinary one-link original request')
            fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory);require(stamp(os.fstat(fd))==stamp(before),'same original request handle')
            while len(body)<before.st_size:
                chunk=os.read(fd,min(65536,before.st_size-len(body)));body.extend(chunk);require(bool(chunk),'original request truncated')
            require(stamp(os.fstat(fd))==stamp(before)==stamp(os.stat(name,dir_fd=directory,follow_symlinks=False)),'stable original request')
            result['status']='complete'
        # The actor may atomically publish its one current request concurrently;
        # that is observed on the next poll. Directory identity, not timestamps,
        # must still name the same owned mount.
        after=os.fstat(directory);named=root.lstat()
        require((original.st_dev,original.st_ino)==(after.st_dev,after.st_ino)==(named.st_dev,named.st_ino),'same original request namespace')
    except BaseException as exc:
        result['status']='partial_or_invalid';result['errors'].append({'type':diagnostic_type(exc)})
    finally:
        for descriptor in (fd,directory):
            if descriptor is not None:
                try:os.close(descriptor)
                except BaseException as exc:result['status']='close_failed';result['errors'].append({'type':diagnostic_type(exc)})
        result['pin']={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()};result['base64']=base64.b64encode(body).decode('ascii')
    return result

def main():
    if len(sys.argv)==3 and sys.argv[1]=='request':
        require(re.fullmatch('[0-9]{1,8}',sys.argv[2]),'literal bounded sequence operand')
        result=request_capture('/requests',int(sys.argv[2]))
    else:
        require(len(sys.argv)==3 and sys.argv[1]in('hold','capture')and sys.argv[2]in CAPS,'literal capture role')
        if sys.argv[1]=='hold':
            while True:time.sleep(1)
        result=capture('/capture',sys.argv[2])
    raw=json.dumps(result,separators=(',',':'),allow_nan=False).encode()+b'\n';offset=0
    while offset<len(raw):
        n=os.write(1,memoryview(raw)[offset:]);require(type(n)is int and 0<n<=len(raw)-offset,'capture transport progress');offset+=n
if __name__=='__main__':main()
