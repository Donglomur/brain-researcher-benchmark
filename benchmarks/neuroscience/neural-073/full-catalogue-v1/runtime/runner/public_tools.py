"""Authenticating selected fits and projecting an explicit public tool file set."""
from dataclasses import dataclass,asdict
import hashlib
from ..core.custody import VerifiedAuthority,CustodyError,canonical,digest,require_digest
from ..transforms.public_tools_v1 import project_transform
from ..public_models import model as pm
from ..admission.export import eligible_tool_names
from ..context_io.filesystem import TreeWriter,IOLimits,IOCounter,ContextIOFailure
from ..process_guard.contracts import PublicMount
from .reference import FittedReference

@dataclass(frozen=True)
class PublicSource:
    name:str
    body:bytes
    sha256:str
    mode:int

    def validate(self):
        if self.name not in ('reference_cli.py','public_transform.py','public_model.py') or type(self.body) is not bytes:
            raise CustodyError('exact standalone public source allowlist')
        if self.mode!=(0o555 if self.name=='reference_cli.py' else 0o444) or hashlib.sha256(self.body).hexdigest()!=self.sha256:
            raise CustodyError('public source byte/mode pin')

@dataclass(frozen=True)
class PublicToolSet:
    outer_person:str
    condition:str
    files:tuple
    model_limits:pm.PublicModelLimits
    private_bindings:tuple

    @property
    def files_digest(self):
        return digest([{'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'mode':m} for p,b,m in self.files])


def build_tool_set(results,*,condition,outer_person,source_files,model_limits,numeric_limits,authority,reference_completion_digest):
    results=tuple(results);require_digest(reference_completion_digest)
    if type(authority) is not VerifiedAuthority:raise CustodyError('verified fit projection authority required')
    expected=eligible_tool_names(condition)
    if any(type(r) is not FittedReference or r.condition!=condition or r.outer_person!=outer_person for r in results):
        raise CustodyError('only this condition/outer selected models can be public')
    names=tuple(r.view+':'+r.family for r in results)
    # Names follow the frozen exporter, not any private model path or fit ID.
    normalized=names
    if set(normalized)!=set(expected) or len(normalized)!=len(expected):
        raise CustodyError('full permitted model-tool set required')
    sources=tuple(source_files)
    if {s.name for s in sources}!= {'reference_cli.py','public_transform.py','public_model.py'} or len(sources)!=3:
        raise CustodyError('complete standalone public code closure')
    for s in sources:s.validate()
    bindings={'reference_completion_digest':reference_completion_digest,
        'selected_fits_digest':digest([r.private_descriptor() for r in results]),
        'public_sources_digest':digest([{'name':s.name,'sha256':s.sha256,'mode':s.mode} for s in sources]),
        'public_model_limits_digest':digest(asdict(model_limits))}
    authority.require(role='reference_predict',domain='authentic',bindings=bindings)
    files=[(s.name,s.body,s.mode) for s in sources];index={}
    for name,r in zip(normalized,results):
        t=project_transform(r.view_bank,r.family,pca_rank=r.configuration.get('pca_rank'),limits=numeric_limits)
        m=pm.project_fitted(r.model,limits=model_limits);md=m.to_dict(limits=model_limits)
        tool={'schema':'n073_public_reference_tool_v1','name':name,'transform':t.to_dict(limits=numeric_limits),
              'model':md,'temperature':r.calibration['temperature']}
        body=canonical(tool);path=name+'.json'
        index[name]={'file':path,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
                     'parameter_digest':pm.parameter_digest(md,limits=model_limits)}
        files.append((path,body,0o444))
    indexbody=canonical({'schema':'n073_public_reference_index_v1','condition':condition,
                          'tools':index,'model_limits':asdict(model_limits)})
    if len(indexbody)>1048576:raise CustodyError('public index extent')
    files.append(('index.json',indexbody,0o444))
    return PublicToolSet(outer_person,condition,tuple(files),model_limits,tuple(sorted(bindings.items())))


def tool_io_bindings(tools,parent_path,name,limits):
    if type(tools) is not PublicToolSet or type(limits) is not IOLimits:raise CustodyError('typed public tools and I/O limits')
    return {**dict(tools.private_bindings),'public_tool_files_digest':tools.files_digest,
            'public_tool_io_digest':digest({'parent':parent_path,'name':name,'limits':asdict(limits)})}


def materialize_tools(tools,*,authority,parent_path,name,limits,counter=None):
    if type(authority) is not VerifiedAuthority:raise CustodyError("verified export authority required before public tool I/O")
    bindings=tool_io_bindings(tools,parent_path,name,limits)
    authority.require(role='export',domain='authentic',bindings=bindings)
    work=IOCounter() if counter is None else counter
    if type(work) is not IOCounter:raise CustodyError("concrete original I/O counter required")
    writer=None
    try:
        writer=TreeWriter(parent_path,name,limits,work)
        for path,body,mode in tools.files:writer.write_bytes(path,body,mode)
        members=writer.finish()
    except BaseException as exc:
        # Original counters/root and exception survive even constructor failure.
        raise ContextIOFailure(exc,counter=work,partial_root=parent_path+"/"+name) from exc
    finally:
        if writer is not None:writer.close()
    mount=PublicMount('reference_tools',writer.path,'/tools',members,
                      digest([asdict(p) for p in members]),digest(bindings))
    mount.validate()
    return mount,{'files_digest':tools.files_digest,'counters':work.to_dict(),
                  'backing_mount_qualified':False,'source_of_models':'selected concrete fitted states'}


_TOOL_SEAL=object()

@dataclass(frozen=True)
class IssuedReferenceTools:
    outer_person:str
    condition:str
    reference_context_id:str
    mount:PublicMount
    files_digest:str
    binding_digest:str
    _seal:object

    def require_context(self,context):
        if self._seal is not _TOOL_SEAL or (self.outer_person,self.condition,self.reference_context_id)!=(context.outer_person,context.condition,context.reference_context_id):
            raise CustodyError('reference tool outer/condition/context custody mismatch')
        if self.mount.role!='reference_tools' or self.mount.destination!='/tools':
            raise CustodyError('exact reference tools role required')
        self.mount.validate();require_digest(self.files_digest);require_digest(self.binding_digest)


def tool_issue_bindings(tools,sealed,reference_context_id):
    from ..context_io.native_seal_v1 import SealedPublicExports
    if type(tools) is not PublicToolSet or type(sealed) is not SealedPublicExports or len(sealed.mounts)!=1:
        raise CustodyError('actual complete tool projection and native seal required')
    return {**dict(tools.private_bindings),'tool_files_digest':tools.files_digest,
        'outer_person_digest':digest(tools.outer_person),'condition_digest':digest(tools.condition),
        'reference_context_digest':digest(reference_context_id),
        'sealed_tool_mount_digest':digest(asdict(sealed.mounts[0])),'native_seal_digest':sealed.evidence_digest}


def issue_reference_tools(tools,sealed,reference_context_id,*,authority):
    bindings=tool_issue_bindings(tools,sealed,reference_context_id)
    if type(authority) is not VerifiedAuthority:raise CustodyError('verified complete tool identity custody required')
    authority.require(role='export',domain='authentic',bindings=bindings)
    return IssuedReferenceTools(tools.outer_person,tools.condition,reference_context_id,sealed.mounts[0],
                                tools.files_digest,digest(bindings),_TOOL_SEAL)
