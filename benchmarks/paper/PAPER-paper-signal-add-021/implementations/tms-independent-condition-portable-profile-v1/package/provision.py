"""Import an authorized, already accepted full projection without transforming it.

This command does not create references, fetch assets or convert a raw MAT file.
Its only scientific bytes are the complete two-file original-input projection.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import signal
import sys
import time

def portable_bootstrap(source, lock_sha, config_path, config_sha):
    # Only this authenticated owner source is imported; never participant code.
    import importlib.util
    def take(p, cap):
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd)
            if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or not 0<a.st_size<=cap:
                raise ValueError('bounded portable source')
            parts=[];left=a.st_size
            while left:
                b=os.read(fd,min(left,65536))
                if not b:raise ValueError('short portable source')
                parts.append(b);left-=len(b)
            z=os.fstat(fd);n=Path(p).lstat()
            fields=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
            if any(getattr(a,k)!=getattr(z,k) or getattr(a,k)!=getattr(n,k) for k in fields):
                raise ValueError('unstable portable source')
            return b''.join(parts)
        finally:os.close(fd)
    raw=take(source/'PORTABLE_SOURCE_LOCK.json',65536)
    if hashlib.sha256(raw).hexdigest()!=lock_sha:raise ValueError('portable source lock identity')
    lock=json.loads(raw);entry=lock['members']['portable_config.py']
    body=take(source/'portable_config.py',1048576)
    if (len(body),hashlib.sha256(body).hexdigest())!=(entry['bytes'],entry['sha256']):
        raise ValueError('portable configuration source identity')
    if 'portable_config' in sys.modules:raise ValueError('fresh portable configuration namespace')
    spec=importlib.util.spec_from_file_location('portable_config',source/'portable_config.py')
    mod=importlib.util.module_from_spec(spec);sys.modules['portable_config']=mod
    exec(compile(body,str(source/'portable_config.py'),'exec'),mod.__dict__)
    bodies,total=mod.load_source(str(source),lock_sha)
    cfg=mod.load(config_path,config_sha,source_bodies=bodies)
    mod.state()['source_lock_sha256']=lock_sha
    return mod,cfg,bodies,total+len(raw)+len(body)+mod.state()['config_bytes']

def main():
    start=time.monotonic()
    def timeout(*unused):raise TimeoutError('original120second provisioning deadline')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,120)
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--config-sha256',required=True)
    parser.add_argument('--source-lock-sha256',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    source=Path(__file__).absolute().parent
    pc,cfg,bodies,source_bytes=portable_bootstrap(source,args.source_lock_sha256,args.config,args.config_sha256)
    for name in ('common','source_projection'):
        if name in sys.modules:raise ValueError('fresh provisioning module namespace')
        spec=importlib.util.spec_from_file_location(name,source/(name+'.py'))
        mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod
        exec(compile(bodies[name+'.py'],str(source/(name+'.py')),'exec'),mod.__dict__)
    out=pc.path(args.output)
    pc.need(not out.exists(),'provision output must be a fresh absent directory')
    inp=out/'input'
    assets=cfg['assets']
    original_input=pc.path(assets['input_manifest']['path']).parent
    reference_root=pc.path(cfg['reference']['root'])
    pc.need(not out.is_relative_to(original_input) and not original_input.is_relative_to(out)
            and not out.is_relative_to(reference_root) and not reference_root.is_relative_to(out),
            'provision output must be disjoint from original inputs and protected reference')
    # Owner-selected projection receipt ties both full pins to source-only
    # provenance. No protected reference or private review body is read here.
    receipt=pc.decode(pc.read(assets['projection_receipt'],1048576))
    for role,key in [('input_manifest','manifest'),('input_values','values')]:
        pc.need({k:receipt[key][k] for k in ('bytes','sha256')}==
                {k:assets[role][k] for k in ('bytes','sha256')},
                'accepted projection receipt does not bind '+role)
    pc.need(receipt.get('schema')=='tms_original_projection_owner_receipt_v1'
            and receipt.get('source_closed') is True
            and receipt.get('input_origin')=='original_source_only'
            and type(receipt.get('reference_reads')) is int and receipt['reference_reads']==0,
            'accepted source-only projection receipt required')
    raw=pc.read(assets['input_manifest'],65536,0o400)
    manifest=pc.decode(raw)
    sp=sys.modules['source_projection']
    pc.need(manifest.get('shape')==list(sp.SHAPE) and manifest.get('original_source')==sp.SOURCE_PIN
            and manifest.get('values')=={k:assets['input_values'][k] for k in ('bytes','sha256')}
            and manifest.get('contains_reference_or_derived_target_fields') is False,
            'complete original projection schema required')
    values=pc.read(assets['input_values'],sp.BYTES,0o400)
    out.mkdir(mode=0o700);inp.mkdir(mode=0o700)
    budget=sys.modules['common'].Budget(start+120,1<<20,16<<20)
    rows={}
    try:
        for name,body in [('INPUT.json',raw),('values.f64',values)]:
            rows[name]=sys.modules['common'].write(inp/name,body,budget)
        os.chmod(inp,0o500)
        result={'schema':'tms_portable_projection_import_v1','input':rows,
                'source_config_sha256':args.config_sha256,
                'source_lock_sha256':args.source_lock_sha256,
                'all_values_preserved_without_transformation':True,
                'reference_bodies_read':0,'acquisition_or_MAT_conversion':False,
                'body_read_bytes':source_bytes+len(raw)+len(values)+assets['projection_receipt']['bytes'],
                'public_redistribution_permission_claimed':False}
        sys.modules['common'].write(out/'PROVISIONING.private.json',
                                    sys.modules['common'].encode(result),budget)
        os.chmod(out,0o500)
        print(json.dumps({'status':'IMPORTED_PENDING_OWNER_ADMISSION','files':2,
                          'value_bytes':len(values),'reference_reads':0}))
    except BaseException:
        # Exclusive partial output is preserved. Never remove or retry it.
        raise
    pc.need(time.monotonic()<start+120,'original provisioning deadline')
    signal.setitimer(signal.ITIMER_REAL,0)
    return 0

if __name__=='__main__':
    os.umask(0o077)
    raise SystemExit(main())
