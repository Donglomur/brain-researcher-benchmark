"""Selected-later dependency-only CI handoff; reuse the existing native owner.

No invocation is authorized by the existence of this source. Never accepts
scientific assets, answer values, candidate text, credentials or owner keys.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import resource
import selectors
import subprocess
import types
import shutil
import signal
import stat
import sys
import tarfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

MIB=1048576
GIB=1073741824
SOURCE_LIMIT=MIB
IMAGE_LIMIT=2*GIB
ARTIFACT_LIMIT=2415919104
WHOLE_DISK_LIMIT=10*GIB


def need(ok,code):
    if not ok:raise ValueError(code)


def encoded(v):return (json.dumps(v,indent=2,allow_nan=False)+'\n').encode()


def plain(path):
    p=Path(path)
    need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'plain_path')
    return p


def body(p,maximum):
    p=plain(p);before=p.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=maximum,'bounded_regular_file')
    with p.open('rb') as f:b=f.read(maximum+1)
    after=p.stat()
    need(len(b)==before.st_size and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'stable_file')
    return b


def digest(p,maximum):
    p=plain(p);size=p.stat().st_size;need(size<=maximum,'file_digest_extent')
    h=hashlib.sha256();count=0
    with p.open('rb') as f:
        while True:
            chunk=f.read(MIB)
            if not chunk:break
            count+=len(chunk);need(count<=maximum,'file_grew');h.update(chunk)
    need(count==size==p.stat().st_size,'file_extent_changed')
    return {'bytes':count,'sha256':h.hexdigest()}


def save(p,v):
    with p.open('xb') as f:f.write(encoded(v))
    p.chmod(0o600)
    return {'path':str(p),**digest(p,MIB)}


def files(root):
    result=[]
    for p in root.rglob('*'):
        need(not p.is_symlink(),'output_symlink')
        if p.is_file():result.append(p)
        else:need(p.is_dir(),'output_special_file')
    need(len(result)<=4096,'output_member_count')
    return result


def extent(root):return sum(p.stat().st_size for p in files(root))


def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;exec(compile(body(p,MIB),str(p),'exec'),m.__dict__);return m


def capture_api(kit):
    """Reuse pinned recorder definitions without bootstrapping the owner twice."""
    # These are the unchanged production functions, not an alternative process
    # runner. The full source bodies were authenticated by the CI source lock
    # and source-kit transport before this private definition namespace exists.
    c=load('nider_hosted_capture_custody',kit/'runtime/custody.py')
    raw=body(kit/'runtime/protected_runner.py',MIB)
    tree=ast.parse(raw);wanted={'bounded_process','validate_outcome'}
    nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in wanted]
    need(len(nodes)==2 and {x.name for x in nodes}==wanted,'complete_capture_definitions')
    space={'os':os,'Path':Path,'selectors':selectors,'signal':signal,'subprocess':subprocess,
           'time':time,'need':c.need,'pin':c.pin,'plain':c.plain}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(kit/'runtime/protected_runner.py'),'exec'),space)
    need('configuration' not in sys.modules,'capture_did_not_bootstrap_owner')
    return types.SimpleNamespace(**{name:space[name] for name in wanted})


def retain_http_error(exc,logs,index):
    """Keep bounded available decoded response evidence; never admit as input."""
    prefix=logs/('archive-%03d'%index)
    result={'status':exc.code,'final_URL':exc.url,'reason':str(exc.reason),'response_available':True,
            'body_cap':65536,'header_representation_cap':16384,'wire_header_bytes_claimed':False}
    headerpath=Path(str(prefix)+'.http-headers');bodypath=Path(str(prefix)+'.http-body')
    # Preserve header fields in their available order and folding, explicitly
    # as a UTF-8 representation of the parser's decoded values, not raw wire.
    header=bytearray();observed=0
    if exc.headers is not None:
        for key,value in exc.headers.raw_items():
            chunk=(key+': '+value+'\r\n').encode('utf-8',errors='backslashreplace')
            observed+=len(chunk);header.extend(chunk[:max(0,16384-len(header))])
    with headerpath.open('xb') as out:out.write(header)
    result['headers']={**digest(headerpath,16384),'path':str(headerpath),'available':exc.headers is not None,
                       'representation_bytes_observed':observed,'truncated':observed>len(header)}
    retained=bytearray();read_count=0;read_failure=None
    try:
        while read_count<65537:
            chunk=exc.read(min(4096,65537-read_count))
            if not chunk:break
            read_count+=len(chunk);retained.extend(chunk[:max(0,65536-len(retained))])
    except BaseException as error:
        read_failure={'type':type(error).__name__,'message':str(error)}
    finally:
        try:exc.close()
        except BaseException as error:result['close_failure']={'type':type(error).__name__,'message':str(error)}
        with bodypath.open('xb') as out:out.write(retained)
    result['body']={**digest(bodypath,65536),'path':str(bodypath),'response_bytes_read':read_count,
                    'truncated':read_count>len(retained),'complete':read_failure is None and read_count<65537,
                    'read_failure':read_failure}
    return result


class LockedRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections=3
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        parsed=urllib.parse.urlparse(newurl)
        need(parsed.scheme=='https' and not parsed.username and not parsed.password,'HTTPS_redirect_only')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def acquire(plan,root,logs):
    """Exactly82 locked archives, one attempt each; no online fallback."""
    need(plan['schema']=='nider_hosted_exact_dependency_acquisition_v1' and
         len(plan['archives'])==plan['archive_count']==82 and
         sum(x['bytes'] for x in plan['archives'])==plan['archive_bytes']==74461530,'acquisition_plan')
    opener=urllib.request.build_opener(LockedRedirect());records=[];returned=0
    for index,entry in enumerate(plan['archives']):
        rel=PurePosixPath(entry['relative_path'])
        need(not rel.is_absolute() and '..' not in rel.parts and str(rel)==entry['relative_path'],'archive_relative_path')
        parsed=urllib.parse.urlparse(entry['url'])
        need(parsed.scheme=='https' and not parsed.username and not parsed.password,'archive_URL')
        dest=root/str(rel);dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        record={'index':index,'request':entry,'started_monotonic':time.monotonic(),'attempt':1,'complete':False}
        try:
            req=urllib.request.Request(entry['url'],headers={'User-Agent':'NIDER-dependency-construction/1','Accept-Encoding':'identity'})
            with opener.open(req,timeout=20) as response,dest.open('xb') as out:
                record.update({'HTTP_status':response.status,'final_URL':response.url,'content_type':response.headers.get('Content-Type'),'declared_length':response.headers.get('Content-Length')})
                need(response.status==200,'archive_HTTP_status')
                h=hashlib.sha256();size=0
                while True:
                    chunk=response.read(min(65536,entry['bytes']+1-size))
                    if not chunk:break
                    out.write(chunk);size+=len(chunk);returned+=len(chunk);h.update(chunk)
                    need(size<=entry['bytes'] and returned<=74461530,'archive_byte_limit')
                record.update({'received_bytes':size,'sha256':h.hexdigest()})
                need(size==entry['bytes'] and h.hexdigest()==entry['sha256'],'archive_identity')
                record['complete']=True
        except BaseException as exc:
            if isinstance(exc,urllib.error.HTTPError):
                try:record['HTTP_error_response']=retain_http_error(exc,logs,index)
                except BaseException as capture_error:record['HTTP_error_capture_failure']={'type':type(capture_error).__name__,'message':str(capture_error),'original_status':exc.code,'original_URL':exc.url}
            if dest.is_file():record['retained_partial_body']=digest(dest,entry['bytes']+1)
            record['failure']={'type':type(exc).__name__,'message':str(exc)}
            raise
        finally:
            record['elapsed_seconds']=time.monotonic()-record['started_monotonic'];records.append(record)
            save(logs/('archive-%03d.json'%index),record)
    need(returned==74461530,'complete_archive_extent')
    return {'archives':records,'complete':True,'received_bytes':returned,'retries':0}


def image_save_identity(path,image):
    """Preserve Docker's image-save format/config digest, not filesystem import."""
    pin=digest(path,IMAGE_LIMIT)
    with tarfile.open(path,'r:') as archive:
        members=archive.getmembers();need(len(members)<=256,'saved_image_member_count')
        for member in members:
            rel=PurePosixPath(member.name)
            need(not rel.is_absolute() and '..' not in rel.parts and not member.issym() and not member.islnk() and
                 (member.isfile() or member.isdir()),'saved_image_member_kind')
        need(len({x.name for x in members})==len(members),'saved_image_duplicate_member')
        manifest=archive.getmember('manifest.json');need(manifest.isfile() and manifest.size<=MIB,'saved_image_manifest_extent')
        values=json.loads(archive.extractfile(manifest).read())
        need(type(values) is list and len(values)==1,'one_saved_image')
        config=archive.getmember(values[0]['Config']);need(config.isfile() and config.size<=MIB,'saved_image_config_extent')
        raw=archive.extractfile(config).read()
        need('sha256:'+hashlib.sha256(raw).hexdigest()==image,'saved_image_config_identity')
        need(all(archive.getmember(x).isfile() for x in values[0]['Layers']),'saved_image_layers')
    return {**pin,'image_id':image,'format':'docker-image-save','members':len(members),'config_SHA256':image.removeprefix('sha256:')}


def main():
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_AS,(2*GIB,2*GIB))
    resource.setrlimit(resource.RLIMIT_FSIZE,(IMAGE_LIMIT,IMAGE_LIMIT))
    need(len(sys.argv)==4,'source_root_lock_digest_fresh_owner_root')
    source=plain(sys.argv[1]);root=plain(sys.argv[3])
    lockraw=body(source/'ci/CI_SOURCE_LOCK.json',SOURCE_LIMIT)
    need(hashlib.sha256(lockraw).hexdigest()==sys.argv[2],'CI_source_lock_identity')
    lock=json.loads(lockraw);need(lock['schema']=='nider_hosted_setup_source_lock_v1' and len(lock['files'])==33,'CI_source_closure')
    count=0
    for row in lock['files']:
        rel=PurePosixPath(row['relative_path'])
        need(not rel.is_absolute() and '..' not in rel.parts and str(rel)==row['relative_path'],'CI_source_relative_path')
        raw=body(source/str(rel),MIB);count+=len(raw)
        need(len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'CI_source_identity')
    need(count<=SOURCE_LIMIT and not root.exists(),'CI_fresh_root_and_source_extent')
    root.mkdir(mode=0o700);public=root/'public_artifact';public.mkdir(mode=0o700)
    logs=root/'ci_logs';logs.mkdir(mode=0o700);started=time.monotonic();calls=[];failure=None;image=None;savepin=None
    cancellation_events=[]
    def requested(signum,_frame):
        cancellation_events.append({'signal':signum,'elapsed_seconds':time.monotonic()-started})
        raise InterruptedError('hosted_owner_cancelled')
    def noted(signum,_frame):
        cancellation_events.append({'signal':signum,'elapsed_seconds':time.monotonic()-started,'phase':'preservation'})
    signal.signal(signal.SIGTERM,requested);signal.signal(signal.SIGINT,requested)
    result={'schema':'nider_hosted_dependency_build_v1','attempts':1,'source_lock_sha256':sys.argv[2],
            'scientific_inputs':0,'scientific_calls':0,'model_calls':0,'candidate_calls':0,'failure':None}
    try:
        stager=load('nider_hosted_stager',source/'transport/source_kit.py')
        staged=stager.stage(source/'kit',root/'kit')
        save(root/'SOURCE_TRANSPORT.json',staged)
        kit=root/'kit';native=load('nider_hosted_native_setup',kit/'setup/native_setup.py')
        uid=os.geteuid();gid=os.getegid();native.validate_owner(uid,gid,uid,gid)
        need(platform.system()=='Linux' and platform.machine() in ('aarch64','arm64') and
             not any(k in os.environ for k in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH')),'CI_real_owner_platform')
        runner=capture_api(kit)
        def command(argv,seconds=30):
            prefix=logs/('command-%03d'%len(calls))
            save(Path(str(prefix)+'.intent.json'),{'argv':argv,'seconds':seconds})
            record=runner.bounded_process(argv,seconds,Path(str(prefix)+'.stdout'),Path(str(prefix)+'.stderr'))
            calls.append(record);save(Path(str(prefix)+'.outcome.json'),record)
            runner.validate_outcome(record);need(extent(logs)<=16*MIB,'CI_log_limit');return record
        def output(argv):return json.loads(body(Path(command(argv)['stdout']['path']),MIB))
        context=output(['docker','context','inspect']);info=output(['docker','info','--format','{{json .}}'])
        need(len(context)==1 and context[0]['Endpoints']['docker']=={'Host':'unix:///var/run/docker.sock','SkipTLSVerify':False},'CI_local_Docker_context')
        need(info['OSType']=='linux' and info['Architecture'] in ('aarch64','arm64') and info['NCPU']>=2 and
             info['MemTotal']>=8*GIB and not any('rootless' in x.lower() or 'userns' in x.lower() for x in info['SecurityOptions']),'CI_Docker_capacity_mapping')
        need(not body(Path(command(['docker','ps','-q'])['stdout']['path']),65536).strip(),'CI_no_competing_containers')
        dockerroot=plain(info['DockerRootDir']);free={'owner_root':shutil.disk_usage(root).free,'DockerRootDir':shutil.disk_usage(dockerroot).free}
        need(min(free.values())>=30*GIB,'CI_actual_filesystem_headroom')
        maps={name:Path('/proc/self/'+name).read_text() for name in ('uid_map','gid_map')}
        need(all(value.split()==['0','0','4294967295'] for value in maps.values()),'CI_identity_namespace_maps')
        save(root/'HOST.json',{'uid':uid,'gid':gid,'platform':platform.platform(),'maps':maps,'context':context,'docker':info,'free_bytes':free})
        plan=json.loads(body(source/'ci/ACQUISITION.json',MIB))
        def expired(*_):raise TimeoutError('dependency_acquisition600s')
        old=signal.signal(signal.SIGALRM,expired);signal.alarm(600)
        try:
            receipt=acquire(plan,root/'dependencies',logs)
            save(root/'ACQUISITION_RECEIPT.json',receipt)
            command(['docker','pull','--quiet','--platform=linux/arm64',plan['base']],180)
        finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)
        request=json.loads(body(source/'SETUP_REQUEST.template.json',MIB))
        request['owner_uid']=uid;request['owner_gid']=gid
        request['archive_paths']={name:str(root/'dependencies'/name) for name in request['archive_paths']}
        request['output_root']=str(root/'setup');request['name']='nider-clean-hosted-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
        request_pin=save(root/'SETUP_REQUEST.json',request)
        status=native.run(request,request_pin);need(status==0,'native_setup_did_not_qualify')
        completed=json.loads(body(root/'setup/RESULT.json',MIB));evidence=completed['image_evidence']
        raw=body(Path(evidence['path']),MIB);need(len(raw)==evidence['bytes'] and hashlib.sha256(raw).hexdigest()==evidence['sha256'],'CI_completed_evidence_identity')
        value=json.loads(raw);image=value['image']
        rp=sys.modules.get('runtime_policy')
        need(rp is not None and Path(rp.__file__)==kit/'runtime/runtime_policy.py','native_owned_runtime_module')
        rp.image_evidence(evidence,image)
        # The exact dependency-only image passed the existing complete content
        # audit before any image body enters the upload allowlist.
        target=public/'dependency-image.docker.tar'
        command(['docker','image','save','--output',str(target),image],180)
        savepin=image_save_identity(target,image)
        save(public/'IMAGE_SAVE.json',savepin)
        # Source provenance accompanies the new packages; only public locked
        # dependency archives are copied, never scientific owner operands.
        shutil.copyfile(source/'ci/ACQUISITION.json',public/'PACKAGE_SOURCE_MANIFEST.json')
        shutil.copyfile(kit/'setup/DEPENDENCIES.json',public/'DEPENDENCIES.json')
        timing=json.loads(body(root/'setup/POSTBUILD_TIMING.json',MIB))
        need(extent(root)+timing['base_size_bytes']<=WHOLE_DISK_LIMIT,'CI_whole_new_disk_limit')
        result['dependency_image_save_ready']=True
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        result['dependency_image_save_ready']=False
    finally:
        signal.signal(signal.SIGTERM,noted);signal.signal(signal.SIGINT,noted)
        # The complete owned setup cleanup is performed by native.run. This
        # handoff neither prunes Docker nor stops an unrelated resource.
        result.update({'failure':failure,'image_id':image,'image_save':savepin,'elapsed_seconds':time.monotonic()-started,
                       'calls':calls,'cancellation_events':cancellation_events,'automatic_retry':False,'scientific_qualification':False})
        # Only explicitly classified dependency-build metadata/logs are public.
        metadata=[]
        for prefix in ['ci_logs','setup/logs','setup/inventory']:
            directory=root/prefix
            if directory.is_dir():metadata.extend(files(directory))
        metadata.extend(x for x in root.glob('*.json') if x.is_file())
        if (root/'setup').is_dir():metadata.extend(x for x in (root/'setup').glob('*.json') if x.is_file())
        need(sum(x.stat().st_size for x in metadata)<=32*MIB,'safe_metadata_extent')
        for src in metadata:
            need(src.suffix in ('.json','.stdout','.stderr','.http-body','.http-headers'),'safe_metadata_extension')
            dest=public/'evidence'/src.relative_to(root);dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            shutil.copyfile(src,dest);dest.chmod(0o600)
        # Retain complete or partial exact public-package response bodies even
        # when acquisition/setup failed. They are evidence, not admitted inputs.
        dependencies=root/'dependencies'
        if dependencies.is_dir():
            archive_files=files(dependencies)
            need(len(archive_files)<=82 and sum(x.stat().st_size for x in archive_files)<=74461531,'archive_original_extent')
            for src in archive_files:
                dest=public/'dependency-acquisition-originals'/src.relative_to(dependencies)
                dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                shutil.copyfile(src,dest);dest.chmod(0o600)
        save(public/'CI_RESULT.json',result)
        need(extent(public)<=ARTIFACT_LIMIT,'public_artifact_extent')
        manifest=[{'relative_path':str(x.relative_to(public)),**digest(x,IMAGE_LIMIT)} for x in files(public)]
        save(public/'ARTIFACT_MANIFEST.json',{'schema':'nider_dependency_artifact_v1','members':manifest,'bytes':sum(x['bytes'] for x in manifest),
             'artifact_limit':ARTIFACT_LIMIT,'contains_scientific_operands':False,'image_ready':result['dependency_image_save_ready'],
             'next':'Owner downloads this exact run artifact, authenticates ZIP and all members, then separately selects docker image load and image_evidence admission. No filesystem import, retagged old image or automatic science run.'})
        need(extent(public)<=ARTIFACT_LIMIT,'public_artifact_final_extent')
        print(json.dumps({'status':'DEPENDENCY_IMAGE_SAVED' if failure is None else 'FAILED_PRESERVED','image':image,'artifact_root':str(public)}))
    return 0 if failure is None else 1


if __name__=='__main__':raise SystemExit(main())
