"""Trusted full-domain export splitting into explicit phase-specific trees."""
from dataclasses import dataclass, asdict
import hashlib
import math
from ..admission.export import CandidateExport, ExportPlan, PublicArtifact, eligible_tool_names
from ..admission.catalogue import canonical_json
from ..core.custody import VerifiedAuthority, digest, decode_json
from ..process_guard.contracts import MemberPin, PublicMount, validate_mounts
from .filesystem import (ContextIOError,ContextIOFailure,IOLimits,IOCounter,TreeWriter,
                         absolute_path,token)


@dataclass(frozen=True)
class CapsuleReceipt:
    root: str
    arm: str
    condition: str
    domain: str
    context_digest: str
    plan_bindings: tuple
    role_members: tuple
    counters: tuple
    authority_digest: str
    io_binding_digest: str

    def to_dict(self):
        return {'schema':'n073-public-capsules-v1','root':self.root,'arm':self.arm,
                'condition':self.condition,'domain':self.domain,'context_digest':self.context_digest,
                'plan_bindings':dict(self.plan_bindings),
                'roles':{role:[asdict(m) for m in members] for role,members in self.role_members},
                'counters':dict(self.counters),'authority_digest':self.authority_digest,
                'io_binding_digest':self.io_binding_digest,
                'backing_mount_qualified':False,
                'cost_scope':'logical payload/read/write calls; excludes OS cache, metadata physical I/O, producer RAM and filesystem allocation'}

    @property
    def receipt_digest(self):return digest(self.to_dict())

    def mounts(self,phase,*,reference_tools=None,frozen_program=None):
        """Assemble actual paths; guard validation rejects Mac home paths/phase errors.

        This never relocates a tree or certifies a read-only backing mount. Caller
        must qualify actual native backing mounts and complete guard admission.
        """
        if phase not in ('prequery','query'):raise ContextIOError('unknown phase')
        roots={'knowledge':'common','training':'training','query':'query'}
        members=dict(self.role_members);result=[]
        for role in ('knowledge','training','query'):
            if role=='query' and phase=='prequery':continue
            destination={'knowledge':'/knowledge','training':'/data/training','query':'/data/query'}[role]
            rows=members[role]
            result.append(PublicMount(role,self.root+'/'+roots[role],destination,rows,
                                     digest([asdict(p) for p in rows]),self.receipt_digest))
        for extra,role in ((reference_tools,'reference_tools'),(frozen_program,'frozen_program')):
            if extra is not None:
                if type(extra) is not PublicMount or extra.role!=role:raise ContextIOError('wrong additional public mount role')
                result.append(extra)
        return validate_mounts(tuple(result),phase=phase,arm=self.arm)


def capsule_io_bindings(plan,parent_path,name,limits):
    if type(plan) is not ExportPlan:raise ContextIOError('exact issued ExportPlan required')
    plan.require_issued();absolute_path(parent_path);token(name);limits.validate()
    return {**plan.bindings,'capsule_io_digest':digest({'parent':parent_path,'name':name,
            'limits':asdict(limits),'schema':'n073-capsule-io-v1'})}


def _expected_interface(plan):
    return {'schema':'n073-candidate-export-v1','execution_domain':plan.authority_domain,
            'arm':plan.context.arm,'condition':plan.context.condition,'label_order':list(plan.label_order),
            'query_is_one_held_person':True,'allowed_cardinality_side_information':True,
            'training_rows':len(plan.training_map),'query_rows':len(plan.query_map),
            'required_tools':list(eligible_tool_names(plan.context.condition))}


def _validate_rows(body,role,plan,export,neural):
    if type(body) is not bytes or not body.endswith(b'\n'):raise ContextIOError('complete newline-terminated public rows required')
    entries=plan.training_map if role=='training' else plan.query_map
    lines=body.splitlines()
    if len(lines)!=len(entries):raise ContextIOError('full issued row count required')
    for line,entry in zip(lines,entries):
        row=decode_json(line,limit=len(line));cid,rid=entry[:2]
        required={'case_id','C'}|({'label_index','person_group'} if role=='training' else set())|({'array_file'} if neural else set())
        if not isinstance(row,dict) or set(row)!=required or row['case_id']!=cid:
            raise ContextIOError('public row schema/order differs from issued plan')
        if (type(row['C']) is not list or len(row['C'])!=105
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in row['C'])
            or tuple(row['C'])!=export._descriptors[rid].values):
            raise ContextIOError('C must equal exact original bound descriptor')
        if role=='training' and (type(row['label_index']) is not int or row['label_index']!=entry[2] or row['person_group']!=entry[3]):
            raise ContextIOError('training label/group differs from issued plan')
        if neural and row['array_file']!='arrays/'+cid+'.f64':raise ContextIOError('array identity differs from issued plan')


def materialize_capsules(export,plan,*,authority,parent_path,name,limits,counter=None):
    """No filesystem effect until concrete export, issued plan and authority match.

    No input path is opened. Export producer receives all record operands through
    its authenticated explicit mapping; this component only consumes its one-pass
    allowlisted bytes. Memory/capacity for that producer remains separately gated.
    """
    if type(export) is not CandidateExport or type(plan) is not ExportPlan or export._plan is not plan:
        raise ContextIOError('concrete CandidateExport and identical issued plan required')
    if type(authority) is not VerifiedAuthority:raise ContextIOError('verified export authority required')
    bindings=capsule_io_bindings(plan,parent_path,name,limits)
    authority_digest=authority.require(role='export',domain=plan.authority_domain,bindings=bindings)
    if export._used:raise ContextIOError('export already consumed')
    work=IOCounter() if counter is None else counter
    if type(work) is not IOCounter:raise ContextIOError('concrete logical counter required')
    neural=plan.context.condition!='C_only'
    expected={'interface.json':'common','training.jsonl':'training','query.jsonl':'query'}
    if neural:
        expected['geometry.json']='common'
        for role,rows in (('training',plan.training_map),('query',plan.query_map)):
            for row in rows:
                key='arrays/'+row[0]+'.f64'
                if key in expected:raise ContextIOError('public opaque case collision')
                expected[key]=role
    if len(expected)>limits.max_files:raise ContextIOError('full export file count exceeds explicit cap')
    if neural:
        array_bytes=8*export._assessment.geometry.voxels
        if array_bytes>limits.max_file_bytes or array_bytes*(len(expected)-4)>limits.max_total_bytes:
            raise ContextIOError('full numeric export exceeds explicit capacity')
    writer=None;seen=set()
    try:
        writer=TreeWriter(parent_path,name,limits,work)
        for role in ('common','training','query'):writer.mkdir(role)
        for artifact in export.iter_public_files():
            if type(artifact) is not PublicArtifact or type(artifact.body) is not bytes:
                raise ContextIOError('exact source-owned public byte artifact required')
            path=artifact.relative_name
            if path not in expected or path in seen:raise ContextIOError('extra/duplicate public artifact')
            body=artifact.body;work.export_bytes_received+=len(body)
            if len(body)>limits.max_file_bytes:raise ContextIOError('public file exceeds capacity')
            if path=='interface.json':
                if artifact.media_type!='application/json' or body!=canonical_json(_expected_interface(plan))+b'\n':
                    raise ContextIOError('interface differs from public allowlist')
            elif path=='geometry.json':
                if artifact.media_type!='application/json' or body!=canonical_json(export._assessment.geometry.public_descriptor())+b'\n':
                    raise ContextIOError('shared geometry differs from admitted geometry')
            elif path.endswith('.jsonl'):
                if artifact.media_type!='application/x-ndjson':raise ContextIOError('wrong public row encoding')
                _validate_rows(body,path[:-6],plan,export,neural)
            elif artifact.media_type!='application/octet-stream' or len(body)!=array_bytes:
                raise ContextIOError('canonical array extent/encoding mismatch')
            writer.write_bytes(expected[path]+'/'+path,body);seen.add(path)
        if seen!=set(expected):raise ContextIOError('full public export is incomplete')
        pins=writer.finish();roles=[]
        for role,folder in (('knowledge','common'),('training','training'),('query','query')):
            rows=tuple(MemberPin(p.path[len(folder)+1:],p.bytes,p.sha256,p.mode) for p in pins if p.path.startswith(folder+'/'))
            roles.append((role,rows))
        return CapsuleReceipt(writer.path,plan.context.arm,plan.context.condition,plan.authority_domain,
            plan.context.fingerprint,tuple(sorted(plan.bindings.items())),tuple(roles),
            tuple(sorted(work.to_dict().items())),authority_digest,bindings['capsule_io_digest'])
    except Exception as exc:
        raise ContextIOFailure(exc,counter=work,partial_root=parent_path+'/'+name) from exc
    finally:
        if writer is not None:writer.close()
