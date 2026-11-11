"""Full N041 central/operator bridge; source-only until separately qualified.

--program is the exact signed whole-programme profile, not a participant module.
Only the independently selected operator supplies signature/key/clock/cap inputs.
The central registry cannot enable this route from source metadata alone.
"""
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,json,math,os,stat,time,types
from pathlib import Path

SOURCE_PINS={'actor_api.py': {'bytes': 2212, 'sha256': '91eaab0657e09927823080d64b04e8a17e53a92f4b36a46bfcd3d9bcfa872dc0'}, 'admission.py': {'bytes': 4286, 'sha256': '78a81f5d4f97ed0616a5ef2267d190a6c4f27bf98d936e1d0f615e0ba9f9e30f'}, 'bootstrap.py': {'bytes': 8488, 'sha256': '5c1ff4188b47acd60714a8e26a88a2b4601a674def6eeceb6a1c3443f655a218'}, 'campaign.py': {'bytes': 7495, 'sha256': '0dc4c2cebb6a5a4bea709580f6390dbc3fdc487cf7d789606d98d18a75ed71b7'}, 'core.py': {'bytes': 11691, 'sha256': '02121c9a375ab8eb67f9e7867d7579e4967f6ca8d0bcc674b4eac6bc041211df'}, 'custody.py': {'bytes': 2716, 'sha256': 'b9063fdae696f153583fca9f3293c0c58f79c4988c658cde0120494b0f9ec52b'}, 'engine.py': {'bytes': 22159, 'sha256': 'e33177c6a16c0071f90d8ce173a7dcf30acab55b77f7d5870e6fcb2db6de002a'}, 'entry.py': {'bytes': 3390, 'sha256': '2a8d414ca311785d5073fa7fbfade42236992aba6d8118dfe8dfdafc37b8fcf4'}, 'epoch_io.py': {'bytes': 2545, 'sha256': '6adbc42353bca185777c3f207385f24921fc4bf9b10ed53f5982a72ed4a4d6e0'}, 'fixed_decoder.py': {'bytes': 1057, 'sha256': 'c3e365efdcadc98febea24f1c63f4f82475426e8924e6c592361156064b6f86e'}, 'launcher.py': {'bytes': 4384, 'sha256': '79d805e7aa7b9247e5f5dcdf71b4bea7e16a7178c288e0a1b31001b1cc4ed040'}, 'nwb.py': {'bytes': 7534, 'sha256': '1daa6403655cee43590220f3a7a3872a7367d54341757990d4acdf6640970964'}, 'preparation.py': {'bytes': 15150, 'sha256': 'dd3c81c29d0ab2147321aa8925ede64272a56976b0c0fd3d6ccdf22e2c496fda'}, 'preparation_worker.py': {'bytes': 1840, 'sha256': 'fd293e0fc3f404eeaa9c9cc660e10e7cf901963bb90d2db7f8466219e44aae00'}, 'projection.py': {'bytes': 2533, 'sha256': '4a402a148f95a4ed7916bafbda01b9b6c7256af0aba5c88dafae75dfc5f58ae0'}, 'reasoning.py': {'bytes': 1056, 'sha256': 'c88d20d39007a0a0b3fb2579c3acd63b04944ce76ba75bbc186e7f62ea9bb872'}, 'reference.py': {'bytes': 5820, 'sha256': '553adb5c94ca973f0409300c084df8a6e9f2284abb364d87684d3f2cf554a18c'}, 'roster.py': {'bytes': 1555, 'sha256': 'd00682c6f34ebff59e3e0009746d8d202f672235d1c86b47a7653bf441b3161e'}, 'schema.py': {'bytes': 5228, 'sha256': '79f40b9b5c1aa75d8f855413f06117566e8b92887d72deef02cc0b852cc33198'}, 'score.py': {'bytes': 1818, 'sha256': '5ef6889680db1569d4dd9fde8da523c0ebc14ebe7c8a1faf5542226e796afa60'}, 'score_check.py': {'bytes': 1307, 'sha256': '50e8d7efe761654ae2f2b97088b1032c7744a0e4108622bb5d6f84fd470ebf2a'}, 'transport.py': {'bytes': 8703, 'sha256': 'c8ae151e0021bdb16876fb4b561863082f9c076ca636f5d64848804edec08d8d'}, 'uncertainty.py': {'bytes': 1872, 'sha256': '3304a87ec77ecdb42c1dc36e2522857fa65e61be3546125bb35b675f86a0bc9f'}, 'worker.py': {'bytes': 4044, 'sha256': 'e26301e3752d1883eda3e87050580936252fe828ef7bb8af2420fb73973114d7'}}
TASK='NEURAL-041'
SOURCE_ROOT=Path(__file__).absolute().parent/'runtime/source'
ONE=1048576
FAMILIES=tuple(m+'/'+a for m in ('frozen_program','case_adaptive_equal_inputs_tools_compute') for a in ('numeric','decoder_only','agent_plus_decoder'))+tuple('reference/'+r for r in ('prior','availability_only','rate_only','power_only','combined'))
LAST_OWNER=None

def need(value,message):
    if not value:raise ValueError(message)

def encode(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':'))+'\n').encode()

def parse(raw):
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'duplicate operator profile key');out[k]=v
        return out
    return json.loads(raw.decode('utf8'),object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError('nonfinite profile JSON')))

def canonical(value):
    need(type(value)is str and value.startswith('/') and not value.startswith('//') and '\\' not in value and '\0' not in value,'canonical absolute operator path')
    need(value=='/' or not value.endswith('/') and all(x not in ('','.','..') for x in value.split('/')[1:]),'canonical operator spelling')
    return Path(value)

class Owner:
    def __init__(self):
        self.first=None;self.errors=[];self.events=[];self.owned=[];self.captures=[];self.publications=[]
        self.read_reserved=0;self.write_reserved=0;self.read_returned=0;self.write_returned=0
        self.status='created';self.source_returned=False;self.result=None;self.args=None
    def error(self,stage,error):
        if self.first is None:self.first=error
        self.errors.append((stage,error));self.status='failed'
    def propagated(self,stage,error):
        self.events.append((stage,error))
        if not any(error is e for _,e in self.errors):self.error(stage,error)
    def tick(self):
        now=time.monotonic()
        need(self.args.origin<=now<self.args.deadline,'same original central/bootstrap clock')
    def reserve(self,kind,count):
        self.tick();need(type(count)is int and count>=0,'nonnegative explicit reservation')
        attr=kind+'_reserved';cap=getattr(self.args,'bridge_'+kind+'_bytes')
        need(getattr(self,attr)+count<=cap,'explicit bridge capacity before effects')
        setattr(self,attr,getattr(self,attr)+count)
    def summary(self):
        return {'schema':'n041_central_owner_v1','status':self.status,'source_returned':self.source_returned,
            'raw_first_retained':self.first is not None,
            'error_occurrences':[{'stage':s,'type':type(e).__name__} for s,e in self.errors],
            'captures':self.captures,'publications':self.publications,
            'bridge_read_reserved':self.read_reserved,'bridge_write_reserved':self.write_reserved,
            'bridge_read_returned':self.read_returned,'bridge_write_returned':self.write_returned,
            'original_task_host_read_cap':None if self.args is None else self.args.host_read_bytes,
            'explicit_total_host_read_reservation':None if self.args is None else self.args.host_read_bytes+self.args.bridge_read_bytes,
            'same_origin_and_deadline':True,'unknown_physical_startup_native_and_terminal_io':True}

def read_owned(owner,path,pin,receipt):
    """Reservation precedes this call; retain actual bytes and independent close."""
    fd=None;first=None;raw=None
    try:
        owner.tick();p=canonical(str(path))
        for parent in reversed(p.parents):need(stat.S_ISDIR(os.lstat(parent).st_mode),'ordinary source/profile parents')
        receipt['attempted']=True
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);receipt['fd_acquired']=True
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==pin['bytes'] and not before.st_mode&0o222,'exact sealed source/profile')
        chunks=[];left=pin['bytes']
        while left:
            owner.tick();b=os.read(fd,min(left,65536))
            owner.read_returned+=len(b);receipt['returned_bytes']+=len(b)
            need(bool(b),'short source/profile');chunks.append(b);left-=len(b)
        extra=os.read(fd,1);owner.read_returned+=len(extra);receipt['returned_bytes']+=len(extra)
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(not extra and stamp(before)==stamp(os.fstat(fd))==stamp(os.lstat(p)),'source/profile changed')
        raw=b''.join(chunks);need(hashlib.sha256(raw).hexdigest()==pin['sha256'],'exact source/profile pin')
        receipt['verified']=True
    except BaseException as error:first=error;owner.error('bridge_capture',error)
    finally:
        if fd is not None:
            receipt['close']='unknown'
            try:os.close(fd);receipt['close']='closed'
            except BaseException as error:
                owner.error('bridge_capture_close',error)
                if first is None:first=error
    if first is not None:raise first
    receipt['returned']=True;return raw

def publish_owned(owner,path,raw):
    need(type(raw)is bytes and len(raw)<=ONE,'bounded central terminal record')
    owner.reserve('write',len(raw))
    row={'path':str(path),'requested_bytes':len(raw),'attempted':False,'returned_bytes':0,'close':'not_acquired','returned':False}
    owner.publications.append(row);fd=None;first=None
    try:
        p=canonical(str(path))
        for parent in reversed(p.parents):need(stat.S_ISDIR(os.lstat(parent).st_mode),'ordinary report parents')
        row['attempted']=True;fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        view=memoryview(raw)
        while view:
            owner.tick();n=os.write(fd,view);need(n>0,'short central record write')
            owner.write_returned+=n;row['returned_bytes']+=n;view=view[n:]
        os.fchmod(fd,0o444);os.fsync(fd)
    except BaseException as error:first=error;owner.error('central_record',error)
    finally:
        if fd is not None:
            row['close']='unknown'
            try:os.close(fd);row['close']='closed'
            except BaseException as error:
                owner.error('central_record_close',error)
                if first is None:first=error
    if first is not None:raise first
    row['returned']=True

def precheck_profile(profile,args):
    """Pin and path checks only; original bootstrap owns signature/authority."""
    need(type(profile)is dict and profile.get('task')==TASK,'exact complete N041 profile')
    need(profile['source']==SOURCE_PINS,'all24 exact accepted source modules, no substitutions')
    need(canonical(profile['source_root'])==SOURCE_ROOT,'fixed installed source root')
    need(canonical(profile['report_root'])==canonical(args.output),'central output is actual original report root')
    need(type(profile['host_read_bytes'])is int and profile['host_read_bytes']==args.host_read_bytes,'unchanged original host-read equality')
    decoder=profile['fixed_decoder']
    need(decoder['pin']==SOURCE_PINS['fixed_decoder.py'] and canonical(decoder['path'])==SOURCE_ROOT/'fixed_decoder.py','exact original decoder source')
    # No signature, key, capacity or qualification is selected from this profile.
    return profile

def run(args):
    """Trusted operator supplies args; untrusted {program} supplies no authority."""
    global LAST_OWNER
    owner=Owner();LAST_OWNER=owner;owner.args=args;owner.owned.append(args)
    args.n041_central_owner=owner
    try:
        for name in ('host_read_bytes','bridge_read_bytes','bridge_write_bytes','bridge_live_bytes','profile_bytes'):
            value=getattr(args,name);need(type(value)is int and value>=0,'explicit operator capacities')
        need(0<args.profile_bytes<=ONE,'bounded full profile')
        need(type(args.origin) in (int,float) and type(args.deadline) in (int,float) and math.isfinite(args.origin) and math.isfinite(args.deadline) and args.origin<args.deadline,'original finite operator clock')
        for name in ('profile_sha','signature_sha','trust_key_sha'):
            value=getattr(args,name);need(type(value)is str and len(value)==64 and all(c in '0123456789abcdef' for c in value),'exact operator input SHA')
        program=canonical(args.program);output=canonical(args.output)
        canonical(args.signature);canonical(args.trust_key)
        need(program!=output and output not in program.parents and program not in output.parents,'separate selected profile and output')
        pins=[('bootstrap',SOURCE_ROOT/'bootstrap.py',SOURCE_PINS['bootstrap.py']),
              ('profile',program,{'bytes':args.profile_bytes,'sha256':args.profile_sha})]
        total=sum(p['bytes']+1 for _,_,p in pins)
        need(8*sum(p['bytes'] for _,_,p in pins)<=args.bridge_live_bytes,'whole bridge retention capacity before capture')
        owner.reserve('read',total)
        captured={}
        for label,path,pin in pins:
            owner.captures.append({'role':label,'path':str(path),'pin':pin,'attempted':False,'returned_bytes':0,'fd_acquired':False,'verified':False,'close':'not_acquired','returned':False})
        for (label,path,pin),row in zip(pins,owner.captures):
            captured[label]=read_owned(owner,path,pin,row)
        precheck_profile(parse(captured['profile']),args)
        ns={'__name__':'_n041_original_operator_bootstrap','__file__':str(SOURCE_ROOT/'bootstrap.py')}
        exec(compile(captured['bootstrap'],ns['__file__'],'exec',dont_inherit=True),ns)
        owner.owned.append(ns)
        original=argparse.Namespace(profile=str(program),profile_bytes=args.profile_bytes,profile_sha=args.profile_sha,
            signature=args.signature,signature_sha=args.signature_sha,trust_key=args.trust_key,trust_key_sha=args.trust_key_sha,
            origin=args.origin,deadline=args.deadline,host_read_bytes=args.host_read_bytes)
        owner.owned.append(original)
        # The exact original run anchors its live owner on this original Namespace
        # before any signature/key/source read. No metadata substitute is accepted.
        result=ns['run'](original);owner.source_returned=True;owner.result=result
        need(type(result)is dict and result.get('schema')=='n041_complete_report_v1' and result.get('task')==TASK and result.get('complete_cells')==396,'normal full programme return')
        need(set(result['scores'])==set(FAMILIES),'all six participant and five reference families')
        owner.tick();owner.status='source_complete_before_central_record'
        marker={'schema':'n041_central_complete_v1','task':TASK,'profile':{'bytes':args.profile_bytes,'sha256':args.profile_sha},
            'complete_cells':396,'planned_native_operations':864,'source_normal_return':True,
            'operator_source':SOURCE_PINS,'known_bridge_prefix':owner.summary(),
            'cutoff':'before this marker publication and final clock; original normal outer return is mandatory',
            'marker_alone_is_success_authority':False,'scientific_qualification_not_created':True}
        publish_owned(owner,output/'CENTRAL_COMPLETE.json',encode(marker))
        owner.tick();owner.status='complete'
        return result
    except BaseException as error:
        owner.propagated('central_invocation',error)
    # Genuine source/bootstrap owners remain on original Namespace in owned.
    # Files and known prefixes survive failures; no rollback, retry or rescoring.
    raise owner.first

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('program','output','profile-sha','signature','signature-sha','trust-key','trust-key-sha'):p.add_argument('--'+n,required=True)
    for n in ('profile-bytes','host-read-bytes','bridge-read-bytes','bridge-write-bytes','bridge-live-bytes'):p.add_argument('--'+n,type=int,required=True)
    for n in ('origin','deadline'):p.add_argument('--'+n,type=float,required=True)
    args=p.parse_args()
    try:
        run(args)
        print(json.dumps({'status':'N041_COMPLETE_ORIGINAL_RETURN','task':TASK,'owner':LAST_OWNER.summary()},sort_keys=True))
    except BaseException as error:
        if LAST_OWNER is not None:
            LAST_OWNER.propagated('central_cli',error)
            try:print(json.dumps({'status':'FAILED_NO_SUCCESS_AUTHORITY','task':TASK,'owner':LAST_OWNER.summary()},sort_keys=True),file=sys.stderr)
            except BaseException as later:LAST_OWNER.error('terminal_diagnostic',later)
            raise LAST_OWNER.first
        raise
if __name__=='__main__':main()
