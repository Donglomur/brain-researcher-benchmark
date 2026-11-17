"""Closed issuance joins. Historical completion is never replaced by PID lookup."""
import copy
import os
import stat
from pathlib import PurePosixPath
from nb079_launch_contract import require,fields,canonical,pin,root_reference
from nb079_authority_io import integer,check_pin,descriptor,absolute,relative,decode
from n079_role_binding import ROLE_ORDER,role_map,validate_identity_slots,binding_contract

SERVICES=ROLE_ORDER[:4]
ONE_SHOTS=ROLE_ORDER[4:]


def process_environment(raw):
    require(type(raw) is bytes and (not raw or raw.endswith(b'\x00')),'whole actual environment terminator')
    out={}
    for part in ([] if not raw else raw[:-1].split(b'\x00')):
        key,value=part.decode('utf-8').split('=',1)
        require(key and key not in out,'unique actual environment key, no collapsed duplicate');out[key]=value
    return out


def process_argv(raw):
    require(type(raw) is bytes and raw.endswith(b'\x00'),'whole actual argv terminator')
    return [part.decode('utf-8') for part in raw[:-1].split(b'\x00')]


def projection(config):
    value=copy.deepcopy(config);context=value['context']
    require('source_admission' in context and 'issuer_evidence' in context['effect_admission'],'two exact role-admission exceptions')
    del context['source_admission'];del context['effect_admission']['issuer_evidence'];return value


def require_time(value,clock,phase):
    integer(value);require(clock['origin']<=value<clock[phase],'original observation within selected phase')


def completed(row,role,H,source,clock):
    require(type(row) is dict and row['schema']=='n079_outer_actual_role_observation_v1' and row['role']==role and
        row['source_pin']==source and row['process_identity']==H[role],'actual original role/source identity')
    w=row['wait']
    require(type(w['pid']) is int and w['pid']==H[role]['pid'] and type(w['code']) is int and w['code']==os.CLD_EXITED and
        type(w['status']) is int and w['status']==0 and type(w['popen_returncode']) is int and w['popen_returncode']==0 and
        w['natural_zero'] is True,'original waitid/Popen natural integer success')
    phase='scientific' if role in ONE_SHOTS else 'closeout';require_time(w['observed_ns'],clock,phase)
    require(set(row['streams'])=={role+'/stdout',role+'/stderr'},'both full original streams')
    for stream in row['streams'].values():
        require(stream['eof'] is True and stream['durable'] is True and type(stream['bytes']) is int and stream['bytes']>=0 and
            stream['bytes']==stream['retained_bytes'] and stream['sha256']==stream['retained_sha256'] and
            stream['pending_block_base64'] is None and stream['pending_block_retained_bytes']==0,'whole durable EOF including empty files')
        check_pin({k:stream[k] for k in ('bytes','sha256')})
    terminal=row['terminal'];require(terminal['schema']=='n079_actual_role_return_v1' and terminal['role']==role and
        terminal['status']=='complete' and terminal['source_pin']==source,'actual source-owned complete terminal')
    for name in ('population_before','population_after'):
        item=row[name];raw=item['raw_ascii'].encode('ascii');require(pin(raw)==item['pin'],'exact original quiescence raw')
        values={}
        for line in raw.decode('ascii').splitlines():
            key,value=line.split();require(key not in values and value.isdecimal(),'exact quiescence fields');values[key]=int(value)
        require(values.get('populated')==0,'original role-descendant quiescence');require_time(item['observed_ns'],clock,phase)
    if role in ONE_SHOTS:
        products=row['products'];require(type(products) is list and len({p['path'] for p in products})==len(products),'complete unique product inventory')
        index=row['index']['descriptor'];require(index==terminal['result']['index'],'original returned index')
        require(any({k:p[k] for k in ('path','bytes','sha256')}==index for p in products),'actual complete inventory includes returned index')
        for p in products:relative(p['path']);check_pin({k:p[k] for k in ('bytes','sha256')})
    else:require(row['products'] is None and row['index'] is None,'service has no invented producer index')
    return row


def observe_completion(capture,row,role,H,source,T,phase='scientific',record_is_published=True):
    completed(row,role,H,source,capture.r['original_clock'])
    # A producer's previous actual observation was written by the authenticated
    # original finalizer after wait/EOF/full inventory, under exclusive custody.
    if record_is_published:
        item={'path':T['report_root']['path']+'/'+role+'-OBSERVATION.json','pin':pin(canonical(row))}
        require(decode(capture.io.read(item,phase,owner=H['finalizer']['uid']),capture.io.encoding)==row,'fresh entire original source-owned observation')
    for name,stream in row['streams'].items():
        require(stream['path']==T['stream_root']['path']+'/'+name.replace('/','-')+'.log','fixed actual full-stream path')
        raw=capture.io.read({'path':stream['path'],'pin':{k:stream[k] for k in ('bytes','sha256')}},phase,owner=H['finalizer']['uid'])
        if name.endswith('/stdout'):
            require(raw.endswith(b'\n') and decode(raw.splitlines()[-1],capture.io.encoding)==row['terminal'],'actual last source return line in whole captured stream')
    if role in ONE_SHOTS:
        root=T['output_roots'][role];root_reference(root)
        require(len(row['products'])<=root['maximum_files'] and sum(p['bytes'] for p in row['products'])<=root['maximum_bytes'],'full admitted product counts/bytes')
        index=row['index']['descriptor'];path=root['path']+'/'+relative(index['path'])
        require(decode(capture.io.read({'path':path,'pin':{k:index[k] for k in ('bytes','sha256')}},phase,owner=H[role]['uid']),capture.io.encoding)==row['index']['body'],
            'fresh actual complete producer index body; numeric backing remains attributed original full inventory')
    return row


def required_live(role):
    require(role in ROLE_ORDER,'fixed release role');before=ROLE_ORDER[:ROLE_ORDER.index(role)]
    return tuple(dict.fromkeys(('finalizer',role)+tuple(r for r in SERVICES if r in before)))


def remote_fifo(capture,process,observation,selected,access):
    """Inspect a live process's actual FD metadata, never credential contents."""
    require(type(access) is int and access in (os.O_RDONLY,os.O_WRONLY),'exact integer OS access mode, no bool')
    fields(observation,('fd','device','inode','owner_uid','mode','access_mode','nonblocking','observed_ns'))
    capture.identity.verify(process);integer(observation['fd'],3)
    fd=observation['fd'];path='/proc/%d/fd/%d'%(process['pid'],fd)
    st=os.stat(path);raw=capture.identity.proc('/proc/%d/fdinfo/%d'%(process['pid'],fd),'scientific')
    rows=dict(line.split(':',1) for line in raw.decode('ascii').splitlines() if ':' in line)
    flags=int(rows['flags'].strip(),8)
    require(stat.S_ISFIFO(st.st_mode) and {'device':st.st_dev,'inode':st.st_ino}==selected['identity'] and
        st.st_uid==selected['owner_uid'] and stat.S_IMODE(st.st_mode)==selected['mode'] and
        selected['mode']&0o022==0 and flags&os.O_ACCMODE==access and flags&os.O_NONBLOCK,'actual live selected opaque FIFO FD flags/inode')
    require(observation['device']==st.st_dev and observation['inode']==st.st_ino and observation['owner_uid']==st.st_uid and
        observation['mode']==stat.S_IMODE(st.st_mode) and type(observation['access_mode']) is int and observation['access_mode']==access and
        observation['nonblocking'] is True,'published FD observation matches actual retained process descriptor')
    require_time(observation['observed_ns'],capture.r['original_clock'],'scientific')
    return {'identity':process,'fd':fd,'fifo_identity':selected['identity'],'access_mode':observation['access_mode'],'observed_ns':capture.clock.tick()}


def validate_issuer(body,roles,base,profile,clock):
    fields(body,('schema','source_manifest_pin','profile_pin','environment_pin','custody_pin','history_pin',
        'origin_ns','scientific_ns','closeout_ns','outer_ns','roles'))
    require(body['schema']=='ach_typed_deployment_issuer_v1' and body['roles']==roles and
        body['source_manifest_pin']==base['source_manifest_pin'] and body['profile_pin']==pin(canonical(profile)) and
        body['environment_pin']==base['source_environment_receipt']['pin'] and body['custody_pin']==base['custody_receipt']['pin'] and
        body['history_pin']==base['history_receipt']['pin'] and
        all(body[k+'_ns']==clock[k] for k in ('origin','scientific','closeout','outer')),'complete actual issuer source/profile/base custody/history/original clocks/full roles')
    return body


def validate_baseline(baseline,T,clock):
    fields(baseline,('storage_baseline','raw_pin','scope_identity','observed_ns','raw_ascii'))
    require(baseline['scope_identity']==T['reader_admission']['scope_identity'] and pin(baseline['raw_ascii'].encode('ascii'))==baseline['raw_pin'],'same actual common baseline raw/scope')
    require_time(baseline['observed_ns'],clock,'scientific')
    # Parse exact admitted storage fields, no content-free success flag.
    actual={}
    for line in baseline['raw_ascii'].splitlines():
        parts=line.split();require(parts and parts[0] not in actual,'unique baseline device')
        fields_raw={}
        for token in parts[1:]:
            key,value=token.split('=',1);require(key not in fields_raw and value.isdecimal(),'unique nonnegative baseline fields');fields_raw[key]=value
        require('rbytes' in fields_raw and 'wbytes' in fields_raw,'actual baseline byte fields')
        actual[parts[0]]={'read_bytes':int(fields_raw['rbytes']),'write_bytes':int(fields_raw['wbytes'])}
    require(actual==baseline['storage_baseline'],'exact original baseline native counters')
    return baseline


def validate_blocked_observation(capture,body,Qc,actual,argv,template,credential_fd,fifo):
    """Bind historical readiness/EOF; inspect only the still-live release FD."""
    b=body['blocked_observation']
    fields(b,('schema','identity','initial_argv','argv_template','source_pin','request_pin','original_clock',
        'ready_byte','ready_eof','observed_ns','process_observation','placement','credential_fd','credential_observation',
        'credential_content_read','pipe_observations'))
    require(b['schema']=='nb079_actual_blocked_finalizer_v1' and b['identity']==actual==body['actual_blocked_identity'] and
        b['initial_argv']==argv==body['actual_initial_argv'] and b['argv_template']==template==Qc['argv_template'] and
        b['source_pin']==Qc['source_pin'] and b['request_pin']==capture.request_descriptor['pin'] and
        b['original_clock']==capture.r['original_clock']==Qc['original_clock'],'whole actual original blocked source/request/process/argv/clock joins')
    require(b['ready_byte']=='R' and b['ready_eof'] is True and b['credential_content_read'] is False,'historical actual R plus EOF without credential read')
    require_time(b['observed_ns'],capture.r['original_clock'],'scientific')
    require(b['observed_ns']<=capture.clock.tick(),'readiness observation precedes actual issuance')
    integer(b['credential_fd'],3);require(b['credential_fd']==credential_fd,'same inherited credential FD number')
    inherited=body['inherited_fifo_observation'];observed=b['credential_observation']
    fields(observed,('fd','device','inode','owner_uid','mode','access_mode','nonblocking','observed_ns'))
    require(type(observed['access_mode']) is int and observed['access_mode']==os.O_RDONLY and observed['nonblocking'] is True and
        {k:v for k,v in observed.items() if k!='observed_ns'}=={k:v for k,v in inherited.items() if k!='observed_ns'},'same complete credential FD metadata across distinct actual observations')
    require_time(inherited['observed_ns'],capture.r['original_clock'],'scientific');require_time(observed['observed_ns'],capture.r['original_clock'],'scientific')
    require(inherited['observed_ns']<=observed['observed_ns']<=b['observed_ns'],'original ordered reader/observer credential/readiness timestamps')
    process=b['process_observation'];fields(process,('argv_pin','environment_observed_equal'))
    require(process['argv_pin']==pin(b'\x00'.join(x.encode('utf-8') for x in argv)+b'\x00') and process['environment_observed_equal'] is True,'exact source-emitted argv/environment observation ABI')
    placement=b['placement'];fields(placement,('before','selected_scope','pid_write_bytes','P_write_bytes','after','scope_write_complete','prelude_gate_complete'))
    before=placement['before'];after=placement['after']
    require(after==actual and set(before)==set(actual) and before['cgroup']==Qc['central_expected']['cgroup'] and
        all(before[k]==actual[k] for k in actual if k!='cgroup') and placement['selected_scope']==Qc['roots']['finalizer_scope'],
        'original same-process placement from central to selected finalizer scope')
    integer(placement['pid_write_bytes']);integer(placement['P_write_bytes'])
    require(placement['pid_write_bytes']==len((str(actual['pid'])+'\n').encode('ascii')) and placement['P_write_bytes']==1 and
        placement['scope_write_complete'] is True and placement['prelude_gate_complete'] is True,'actual complete PID placement and P byte before readiness')
    pipes=b['pipe_observations'];fields(pipes,('release','ready'))
    for name,marker in (('release','@RELEASE_FD@'),('ready','@READY_FD@')):
        row=pipes[name];fields(row,('child_fd','device','inode'));integer(row['child_fd'],3);integer(row['device']);integer(row['inode'])
        require(template.count(marker)==1 and argv[template.index(marker)]==str(row['child_fd']),'retained original pipe FD matches exact literal launch operand')
    release,ready=pipes['release'],pipes['ready']
    require(len({release['child_fd'],ready['child_fd'],credential_fd})==3 and
        len({(release['device'],release['inode']),(ready['device'],ready['inode']),(fifo['identity']['device'],fifo['identity']['inode'])})==3,
        'two original pipe identities and credential FIFO/FD are disjoint')
    # Ready has already reached EOF and was closed. Its numeric FD may now be
    # absent or reused; no ready stat/fdinfo lookup is valid here.
    capture.identity.verify(actual)
    live=os.stat('/proc/%d/fd/%d'%(actual['pid'],release['child_fd']))
    info=capture.identity.proc('/proc/%d/fdinfo/%d'%(actual['pid'],release['child_fd']),'scientific')
    rows={}
    for line in info.decode('ascii').splitlines():
        key,value=line.split(':',1);require(key not in rows,'unique live release fdinfo field');rows[key]=value.strip()
    flags=int(rows['flags'],8)
    require(stat.S_ISFIFO(live.st_mode) and live.st_dev==release['device'] and live.st_ino==release['inode'] and
        flags&os.O_ACCMODE==os.O_RDONLY and bool(flags&os.O_NONBLOCK),'actual still-live original release FIFO/inode/read-only/nonblocking flags')
    capture.identity.verify(actual)
    return b
