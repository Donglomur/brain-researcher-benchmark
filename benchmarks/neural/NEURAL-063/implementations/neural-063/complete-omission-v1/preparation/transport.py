"""Future authorized version-specific HTTPS transport; never called on import."""
import hashlib
import os
from pathlib import Path
import stat
import urllib.parse
import urllib.request
from owner.io import Artifact, ContractError, canonical, identity, ordinary
from .native import authenticated
from .source import locator

HEADER_BOUND = 7_000_000  # worst stdlib HTTP parser bound, reserved before request
CHUNK = 8 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ContractError('versioned provider redirects forbidden')


def address(row):
    locator(row)
    return row['url']+'?'+urllib.parse.urlencode({'versionId':row['version_id']})


def request(ctx,row,method):
    ctx.require_scientific()
    # Do not consume proxy/environment credentials or ambient URL handlers.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    req=urllib.request.Request(address(row),method=method,headers={'Accept-Encoding':'identity'})
    return opener.open(req,timeout=20 if method=='HEAD' else 60)


def response_identity(response,row):
    headers=list(response.headers.items())
    data=canonical(headers)
    if len(data)>HEADER_BOUND or response.status!=200:
        raise ContractError('provider status/header bound mismatch')
    for key in ('Content-Length','x-amz-version-id'):
        values=response.headers.get_all(key)
        if values is None or len(values)!=1: raise ContractError('unique exact transport header required')
    if response.headers['x-amz-version-id']!=row['version_id'] or response.headers.get('Content-Encoding','identity')!='identity':
        raise ContractError('wrong transport version/encoding')
    raw=response.headers['Content-Length']
    if not raw.isdigit() or int(raw)<=0: raise ContractError('positive source byte count required')
    return int(raw),len(data),headers


def allocation(ctx,name):
    value=ctx.parameters.get(name)
    if type(value) is not int or value<=0: raise ContractError('positive selected allocation required: '+name)
    return value


def filesystem_bytes(root):
    """Account every existing retained file under this isolated output root."""
    ordinary(root,directory=True); total=0; inodes=set()
    for current,dirs,files in os.walk(root,followlinks=False):
        for name in dirs: ordinary(Path(current)/name,directory=True)
        for name in files:
            path=ordinary(Path(current)/name); s=path.stat(); key=(s.st_dev,s.st_ino)
            if key in inodes: raise ContractError('retained file alias in storage census')
            inodes.add(key); total+=s.st_size
    return total,inodes


def size_census(ctx,selection):
    attempts=[]; entries=[]; header_used=0
    cap=allocation(ctx,'header_transport_bytes')
    for row in selection['experiments']:
        item=None
        for attempt in range(1,4):
            if header_used+HEADER_BOUND>cap: raise ContractError('full size census header allowance exhausted')
            # Charge the conservative parser reservation even when response
            # parsing fails; measured decoded header bytes are separate.
            header_used+=HEADER_BOUND
            rec={'schema':'neural063_transport_attempt_v2','experiment':row['ophys_experiment_id'],'attempt':attempt,'method':'HEAD',
                 'reserved_header_bytes':HEADER_BOUND,'decoded_header_bytes':None}
            try:
                with request(ctx,row,'HEAD') as response:
                    size,used,headers=response_identity(response,row)
                    rec.update(status='success',decoded_header_bytes=used,headers=headers)
                    item={'experiment':row['ophys_experiment_id'],'bytes':size,
                          'version_id':row['version_id'],'url':row['url'],'blake2b_512':row['blake2b_512']}
            except Exception as exc:
                rec.update(status='failed',failure_class=type(exc).__name__,failure=str(exc)[:2048])
            finally:
                attempts.append(rec)
                ctx.write_json('head_'+row['ophys_experiment_id']+'_'+str(attempt)+'.json',rec,role='source_transport_attempt')
            if item is not None: break
        if item is None: raise ContractError('version-specific size census exhausted three attempts')
        entries.append(item)
    if len(entries)!=1936 or len({e['experiment'] for e in entries})!=1936:
        raise ContractError('full exact size census required')
    total=sum(e['bytes'] for e in entries)
    existing,inodes=filesystem_bytes(ctx.store.root)
    reuse_bytes=0
    for value in selection['reuse_sources'].values():
        ref=Artifact.parse(value); p=ordinary(ref.path); s=p.stat()
        if s.st_size!=ref.bytes: raise ContractError('reuse descriptor size changed')
        if (s.st_dev,s.st_ino) not in inodes:
            existing+=s.st_size; inodes.add((s.st_dev,s.st_ino))
        reuse_bytes+=s.st_size
    reserve=allocation(ctx,'working_reserve_bytes')+allocation(ctx,'receipt_reserve_bytes')
    # Full worst-case retained failures, never silently delete failed partials.
    required=existing+3*total+reserve
    retained_cap=allocation(ctx,'retained_storage_bytes')
    statfs=os.statvfs(ctx.store.root); available=statfs.f_bavail*statfs.f_frsize
    if required>retained_cap or 3*total+reserve>available:
        raise ContractError('complete source plus failed partial/work/receipt storage not admitted')
    return {'schema':'neural063_source_sizes_v2','entries':entries,'total_bytes':total,
            'source_selection_sha256':ctx.inputs['source_selection'].sha256,
            'attempts':attempts,'header_reservation_bytes':header_used,
            'storage':{'existing_retained_bytes':existing,'existing_source_bytes':reuse_bytes,
                       'worst_case_source_and_partial_bytes':3*total,'work_and_receipt_reserve_bytes':reserve,
                       'required_retained_ceiling_bytes':required,'selected_retained_ceiling_bytes':retained_cap,
                       'observed_available_bytes':available},'body_bytes_read':0}


def acquire(ctx,selection,sizes):
    entries={e['experiment']:e for e in sizes['entries']}
    if (len(sizes['entries'])!=1936 or len(entries)!=1936
            or set(entries)!={r['ophys_experiment_id'] for r in selection['experiments']}
            or any(type(e['bytes']) is not int or e['bytes']<=0 for e in entries.values())):
        raise ContractError('full size selection positive byte identities required')
    total=sum(e['bytes'] for e in entries.values())
    if total!=sizes['total_bytes'] or sizes['source_selection_sha256']!=ctx.inputs['source_selection'].sha256:
        raise ContractError('size binding/total mismatch')
    transport_cap=allocation(ctx,'body_transport_bytes')
    header_cap=allocation(ctx,'header_transport_bytes')
    if transport_cap<3*total or header_cap<1936*3*HEADER_BOUND:
        raise ContractError('finite complete worst-case retry transport not allocated')
    # Recheck current physical capacity at acquisition, not stale S01 free space.
    work=allocation(ctx,'working_reserve_bytes')+allocation(ctx,'receipt_reserve_bytes')
    existing,inodes=filesystem_bytes(ctx.store.root)
    for value in selection['reuse_sources'].values():
        ref=Artifact.parse(value); path=ordinary(ref.path); stat_result=path.stat()
        if stat_result.st_size!=ref.bytes: raise ContractError('reuse object size changed before acquisition')
        inode=(stat_result.st_dev,stat_result.st_ino)
        if inode not in inodes:
            existing+=stat_result.st_size; inodes.add(inode)
    free=os.statvfs(ctx.store.root)
    if 3*total+work>free.f_bavail*free.f_frsize or existing+3*total+work>allocation(ctx,'retained_storage_bytes'):
        raise ContractError('current complete acquisition storage unavailable')
    files=[]; spent=0; reserved_headers=0
    for row in selection['experiments']:
        eid=row['ophys_experiment_id']; planned=entries[eid]
        if (planned['url'],planned['version_id'],planned['blake2b_512'])!=locator(row):
            raise ContractError('source identity changed between stages')
        expected=planned['bytes']; completed=None
        if eid in selection['reuse_sources']:
            ref=Artifact.parse(selection['reuse_sources'][eid])
            if ref.bytes!=expected: raise ContractError('reuse byte census mismatch')
            with authenticated(ctx,ref,row['blake2b_512']): pass
            completed={'experiment':eid,'source':ref.object(),'version_id':row['version_id'],
                       'blake2b_512':row['blake2b_512'],'disposition':'authenticated_existing'}
        else:
            for attempt in range(1,4):
                reserved_headers+=HEADER_BOUND
                if reserved_headers>header_cap: raise ContractError('header retry allowance exhausted')
                name='source_'+eid+'_attempt_'+str(attempt)+'.nwb'
                path=ctx.store.path(ctx.stage+'/'+name)
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
                count=0; sha=hashlib.sha256(); blake=hashlib.blake2b()
                rec={'schema':'neural063_transport_attempt_v2','experiment':eid,'attempt':attempt,'method':'GET','path':str(path),'decoded_header_bytes':None}
                write_failed=False
                try:
                    with os.fdopen(fd,'wb') as stream,request(ctx,row,'GET') as response:
                        got,used,headers=response_identity(response,row)
                        rec.update(decoded_header_bytes=used,headers=headers)
                        if got!=expected: raise ContractError('GET length differs from exact version HEAD')
                        while count<expected:
                            amount=min(CHUNK,expected-count)
                            if spent+amount>transport_cap: raise ContractError('aggregate body allowance exhausted')
                            body=response.read(amount)
                            spent+=len(body); count+=len(body)
                            if not body: raise ContractError('truncated complete source body')
                            ctx.store.meter.write(len(body))
                            try:
                                if stream.write(body)!=len(body):
                                    raise OSError('short native object write')
                            except OSError:
                                write_failed=True; raise
                            sha.update(body); blake.update(body)
                        # HTTPResponse enforces the exact Content-Length; no
                        # extra byte is fetched outside the finite 3*B budget.
                        try:
                            stream.flush(); os.fsync(stream.fileno())
                        except OSError:
                            write_failed=True; raise
                    if count!=expected or blake.hexdigest()!=row['blake2b_512']:
                        raise ContractError('complete provider BLAKE2b/size mismatch')
                    ref=Artifact(str(path),count,sha.hexdigest(),'native_source','operator',ctx.stage,'application/x-nwb')
                    ctx.record_streamed(name,ref)
                    completed={'experiment':eid,'source':ref.object(),'version_id':row['version_id'],
                               'blake2b_512':blake.hexdigest(),'disposition':'acquired_authenticated'}
                    rec['status']='success'
                except Exception as exc:
                    rec.update(status='failed',failure_class=type(exc).__name__,failure=str(exc)[:2048])
                finally:
                    # A normally closed failed transport has a known streamed
                    # partial digest. Write/flush uncertainty remains unbound
                    # and aborts this stage; never fabricate its content hash.
                    retained=path.stat().st_size
                    if completed is None and not write_failed and retained==count:
                        partial=Artifact(str(path),retained,sha.hexdigest(),'source_partial','operator',ctx.stage,'application/octet-stream')
                        ctx.record_streamed(name,partial)
                    rec.update(retained_file_bytes=retained,body_bytes=count,body_sha256=sha.hexdigest(),body_blake2b_512=blake.hexdigest(),
                               aggregate_body_bytes=spent,partial_retained=True)
                    ctx.write_json('get_'+eid+'_'+str(attempt)+'.json',rec,role='source_transport_attempt')
                if write_failed or (completed is None and path.stat().st_size!=count):
                    raise ContractError('partial native write custody uncertain; retained without repair/retry')
                if completed: break
        if completed is None: raise ContractError('full-object acquisition exhausted three attempts')
        files.append(completed)
    if len({f['source']['sha256'] for f in files})!=1936:
        raise ContractError('authenticated duplicate/aliased source bodies across experiments')
    return {'schema':'neural063_source_inventory_v2','files':files,'total_bytes':total,
            'source_sizes_sha256':ctx.inputs['source_sizes'].sha256,
            'source_selection_sha256':ctx.inputs['source_selection'].sha256,
            'body_transport_bytes':spent,'reserved_header_bytes':reserved_headers}
