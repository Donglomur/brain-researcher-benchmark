"""Fixed, source-authenticated composition of the current BaRISTA operator methods.

This API does not authorize scientific work. The task remains inactive; the sole
CLI is inspect. Caller inputs/checkpoints and process isolation need separate
admission. No module/function/callback is selected by an operator request.
"""
import hashlib,importlib,json,os,stat,sys
from pathlib import Path,PurePosixPath
from .pins import SOURCE_MANIFEST_SHA256,OFFICIAL_DESCRIPTOR_SHA256

CAP=1048576
BATCH=16*CAP
MEMBERS=2048
FLAT={
 'arrays':'source/classification/public/arrays.py',
 'io_contract':'source/classification/public/io_contract.py',
 'protocol':'source/classification/public/protocol.py',
 'design':'source/classification/private/design.py',
 'intervals':'source/classification/private/intervals.py',
 'metrics':'source/classification/private/metrics.py',
 'prepare':'source/classification/private/prepare.py',
 'stage':'source/classification/private/stage.py',
 'bind_gold':'source/classification/private/bind_gold.py',
 'score':'source/classification/private/score.py',
 'source_provision':'source/classification/private/source_provision.py',
}
PACKAGES={'barista_reference':'source/reference/source/barista_reference',
          'barista_reconstruction':'source/reconstruction/source/barista_reconstruction'}

def _relative(value):
    if not isinstance(value,str) or not value or '\\' in value or any(ord(c)<32 for c in value):raise ValueError('Ordinary relative source path')
    p=PurePosixPath(value)
    if p.is_absolute() or str(p)!=value or any(c in ('.','..','.git') for c in p.parts):raise ValueError('Nontraversing source path')
    return p.parts

def _root_fd(root):
    p=Path(root)
    if not p.is_absolute():p=Path.cwd()/p
    if '..' in p.parts:raise ValueError('No root traversal')
    fd=os.open(p.anchor,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in p.parts[1:]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
        return fd
    except BaseException:os.close(fd);raise

def _id(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def _capture(root,relative):
    parts=_relative(relative);fd=_root_fd(root);filefd=None
    try:
        for part in parts[:-1]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
        filefd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        before=os.fstat(filefd)
        if not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode)!=0o644 or before.st_nlink!=1 or not 0<=before.st_size<=CAP:raise ValueError('Bounded single-link ordinary0644 source required')
        chunks=[];left=before.st_size
        while left:
            b=os.read(filefd,min(left,65536))
            if not b:raise ValueError('Short source read')
            chunks.append(b);left-=len(b)
        if os.read(filefd,1):raise ValueError('Source grew')
        after=os.fstat(filefd);named=os.stat(parts[-1],dir_fd=fd,follow_symlinks=False)
        if _id(before)!=_id(after) or _id(after)!=_id(named):raise ValueError('Source changed during capture')
        b=b''.join(chunks);b.decode('utf-8')
        if b'\0' in b:raise ValueError('NUL source')
        return b
    finally:
        if filefd is not None:os.close(filefd)
        os.close(fd)

def _pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git_blob':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),'git_mode':'100644'}
def _json(body):
    def unique(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('Duplicate JSON field')
            out[k]=v
        return out
    return json.loads(body,object_pairs_hook=unique)

class Operator:
    def __init__(self,root):
        self.root=Path(root).absolute();self._owned_models={}

    def authenticate(self):
        body=_capture(self.root,'SOURCE_MANIFEST.json')
        if hashlib.sha256(body).hexdigest()!=SOURCE_MANIFEST_SHA256:raise ValueError('Pinned source manifest identity')
        manifest=_json(body)
        if manifest['schema']!='barista_inactive_source_manifest_v1' or manifest['current_functional_roles']!=85:raise ValueError('Complete current source manifest')
        rows=manifest['files']
        if len(rows)!=100 or len(rows)+1>MEMBERS or sum(x['bytes'] for x in rows)+len(body)>BATCH:raise ValueError('Complete bounded source inventory')
        names=[x['path'] for x in rows]
        if len(names)!=len(set(names)) or len(names)!=len({n.casefold() for n in names}):raise ValueError('Unique source paths')
        captured={}
        for x in rows:
            b=_capture(self.root,x['path'])
            if _pin(b)!={k:x[k] for k in _pin(b)}:raise ValueError('Current source body identity: '+x['path'])
            captured[x['path']]=b
        composition=_json(captured['COMPOSITION.json'])
        if composition['admission']!={'runnable':False,'research_qualified':False,'full_contract_complete':False,'source_complete':False,'scientifically_qualified':False,'submission_ready':False}:raise ValueError('Inactive admission is immutable')
        return manifest,composition

    def inspect(self):
        manifest,composition=self.authenticate()
        return {'id':composition['id'],'status':'source_only_inactive','admission':composition['admission'],
                'entrypoints':{'run':None,'score':None,'program_execution':None,'inspect':'operator.py inspect'},
                'scope':composition['scope'],'fixed_operator_apis':composition['fixed_operator_apis'],
                'holds':composition['holds'],'source_files':99,'current_functional_roles':85,
                'bundled_role_bodies':83,'external_role_bodies':2,'source_manifest_sha256':SOURCE_MANIFEST_SHA256,
                'execution_authorized':False}

    def _check_loaded(self,official_root=None):
        for name,rel in FLAT.items():
            if name in sys.modules and Path(getattr(sys.modules[name],'__file__','')).absolute()!=self.root/rel:raise RuntimeError('Foreign cached source module: '+name)
        for prefix,rel in PACKAGES.items():
            allowed=self.root/rel
            for name,module in tuple(sys.modules.items()):
                if name==prefix or name.startswith(prefix+'.'):
                    origin=getattr(module,'__file__',None)
                    if origin is None or not Path(origin).absolute().is_relative_to(allowed):raise RuntimeError('Foreign cached package: '+name)
        if official_root is not None:
            for name,module in tuple(sys.modules.items()):
                if name=='barista' or name.startswith('barista.'):
                    origin=getattr(module,'__file__',None)
                    locations=[Path(origin).absolute()] if origin else [Path(x).absolute() for x in getattr(module,'__path__',[])]
                    if not locations or any(not x.is_relative_to(Path(official_root).absolute()/'barista') for x in locations):raise RuntimeError('Foreign cached official source: '+name)

    def _module(self,name,official_root=None):
        # Fresh complete byte admission precedes any scientific-source import.
        self.authenticate();self._check_loaded(official_root)
        allowed=set(FLAT)|{'barista_reference.design','barista_reference.producer','barista_reference.training','barista_reference.export','barista_reconstruction.score'}
        if name not in allowed:raise ValueError('No arbitrary operator module dispatch')
        paths=[self.root/'source/classification/private',self.root/'source/classification/public',self.root/'source/reference/source',self.root/'source/reconstruction/source']
        if official_root is not None:paths.append(Path(official_root).absolute())
        old=list(sys.path)
        try:
            sys.path[:0]=[str(p) for p in paths];module=importlib.import_module(name);self._check_loaded(official_root);return module
        finally:sys.path[:]=old

    def provision_official(self,operator_source_root,out_path):
        m=self._module('source_provision')
        return m.provision(self.root/'source/classification/source',operator_source_root,
            self.root/'source/classification/source/OFFICIAL_SOURCE_ACCESS.json',OFFICIAL_DESCRIPTOR_SHA256,out_path)

    def classification_prepare(self,resolved_path,out_path,secret_path,max_output_bytes):
        return self._module('prepare').prepare(resolved_path,out_path,secret_path,max_output_bytes)

    def classification_stage(self,pool_path,context_id,model,arm,out_path,max_output_bytes,*,paper_path,official_source_root=None):
        return self._module('stage').stage(pool_path,context_id,model,arm,out_path,max_output_bytes,paper_path=paper_path,official_source_root=official_source_root)

    def classification_bind_gold(self,pool_path,public_path,baseline_path,out_path,max_output_bytes):
        return self._module('bind_gold').bind(pool_path,public_path,baseline_path,out_path,max_output_bytes)

    def classification_score(self,public_path,gold_path,submission_path):
        # Omit the legacy optional loader argument: the fixed real primitive reader is used.
        return self._module('score').grade(public_path,gold_path,submission_path)

    def reconstruction_cells(self,sessions):
        return self._module('barista_reference.design').programme_cells(sessions)

    def _official(self,root):
        sp=self._module('source_provision');dpath=self.root/'source/classification/source/OFFICIAL_SOURCE_ACCESS.json'
        doc=sp._descriptor(sp.load_descriptor(dpath,OFFICIAL_DESCRIPTOR_SHA256),OFFICIAL_DESCRIPTOR_SHA256)
        files=[]
        for row in doc['roles']+doc['notices']:
            sp.capture(root,row['destination'],row)
            files.append({'path':row['destination'],**{k:row[k] for k in sp.PIN_KEYS}})
        admission=_json(_capture(root,'ADMISSION_MANIFEST.json'))
        expected={'schema':'barista_offline_source_admission_v1','upstream_commit':sp.COMMIT,'descriptor_sha256':OFFICIAL_DESCRIPTOR_SHA256,'original_source_roles':32,'external_source_roles':2,'native_execution':False,'redistribution_grant':False,'files':files}
        if admission!=expected:raise ValueError('Complete original source assembly admission')
        return Path(root).absolute()

    def reconstruction_model(self,model_config,metadata,model_name,config,*,official_root,initialization,backbone_state=None,retained_h_state=None,retained_mask=None):
        root=self._official(official_root);m=self._module('barista_reference.producer',root)
        # The producer imports its native leaves inside the constructor. Keep the
        # already authenticated normal original package import root during that call.
        old=list(sys.path)
        try:
            sys.path.insert(0,str(root));model=m.make_reconstructor(model_config,metadata,model_name,config,initialization=initialization,backbone_state=backbone_state,retained_h_state=retained_h_state,retained_mask=retained_mask)
            self._check_loaded(root)
        finally:sys.path[:]=old
        self._owned_models[id(model)]=(model,root)
        return model

    def _owned(self,model):
        row=self._owned_models.get(id(model))
        if row is None or row[0] is not model:raise ValueError('Model must originate from this fixed operator constructor')
        self._official(row[1]);self._check_loaded(row[1]);return row[1]

    def reconstruction_fit(self,model,session,train_waveforms,train_segment_ids,*,arm):
        root=self._owned(model)
        return self._module('barista_reference.training',root).fit_cell(model,session,train_waveforms,train_segment_ids,arm=arm)

    def reconstruction_export(self,panel,request_id,model,session,observed_waveforms,observed_channel_ids,test_segment_ids,target_channel_id,out_path,*,arm,max_output_bytes,max_known_export_bytes):
        root=self._owned(model)
        return self._module('barista_reference.export',root).export_channel(panel,request_id,model,session,observed_waveforms,observed_channel_ids,test_segment_ids,target_channel_id,out_path,arm=arm,max_output_bytes=max_output_bytes,max_known_export_bytes=max_known_export_bytes)

    def reconstruction_score(self,public_path,gold_path,submission_path,limits):
        return self._module('barista_reconstruction.score').grade(public_path,gold_path,submission_path,limits)
