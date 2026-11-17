"""Fixed original-pair programme capture, full inventory and two-seal barrier."""
import time
from .common import need, same, encode, parse, pin, integer, relative, bounded_size
from .backend_json import parse as parse_canonical, canonical
from .backend_capture import CanonicalPublisher, CapturedRecord
from .development_handles import PairCompletionHandle
from .precommit_records import CONDITIONS, validate_type
from .programme_workspace import WorkspaceReader, capture_source_file

_CAPTURE=object()


class ProgrammeCaptureHandle:
    def __init__(self,token,pair_completion):
        need(token is _CAPTURE and type(pair_completion) is PairCompletionHandle,
             'fixed original pair capture constructor')
        self.pair_completion=pair_completion;self.pair=pair_completion.pair;self.owner=self.pair.owner
        need(not hasattr(self.pair,'programme_capture'),'one original pair capture including failed attempts')
        self.raw_first=None;self.raw_secondaries=[];self.promoted=False;self.assembly=None
        self.started_ns=None;self.cost_before=None;self.readers={};self.manifests={}
        self.manifest_captures={};self.file_attempts={};self.parent_handles=[]
        self.captured_files={};self.source_manifests={};self.receipts={};self.seals={}
        self.inventories={};self.partitions={};self.phase='registered'
        self.pair.programme_capture=self  # Before all later validation/clock/IO.

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.promoted=False;self.phase='failed'
        try:self.owner.parent.retain(error,'source_capture','publication_failure',site)
        except BaseException as later:self.raw_secondaries.append(later)

    def clock(self):
        self.owner.check();now=time.monotonic_ns();integer(now)
        need(now<self.owner.parent.original_deadline,'same original H evidence deadline')
        return now

    def require_promoted(self):
        need(self.pair.programme_capture is self and self.promoted and self.raw_first is None and
             self.owner.parent.first_raw is None and set(self.seals)==set(CONDITIONS) and
             set(self.receipts)==set(CONDITIONS),'same actual fully promoted two-arm source capture')
        self.pair_completion.require_original()
        return self

    def publish(self,name,kind,body):
        # The original finite parser/member domain applies to produced records
        # too, before the first write. Publisher retains once-only raw custody.
        self.owner.host.charge('work_units',bounded_size(body))
        raw=canonical(body,self.metadata_cap,maximum_depth=self.depth)
        self.owner.host.charge('retained_bytes',16*len(raw)+4096)
        parse_canonical(raw,self.metadata_cap,maximum_depth=self.depth,
            maximum_members=self.owner.plan['maximum_members'],maximum_string_bytes=self.metadata_cap)
        result=self.publisher.capture(name,kind,body)
        self.owner.parent.known_records.append(result.pin)
        return result


def _preflight(capture):
    owner=capture.owner;M=capture.metadata_cap;S=capture.source_cap;F=capture.files
    bounds={'read_bytes':14*(M+1)+4*F*(S+1),'write_bytes':12*M+2*F*S}
    # This admits the full original route's conservative source/metadata
    # envelope. Actual operations still charge the original owner separately;
    # no reservations, physical errors or pre-existing costs are erased.
    for key,amount in bounds.items():
        limit=owner.partitions['host'][key]-owner.terminal_reserve[key]
        need(owner.used['host'][key]+amount<=limit,'whole paired output route fits same original H reserve')
        need(owner.parent.share.spent[key]+amount<=owner.parent.share.limits[key],
             'whole paired output route fits original aggregate envelope')
    need(len(capture.publisher.parent.canonical_publications)+12+2*F<=
         capture.publisher.maximum_members,'whole paired publication/file capacity before capture effects')


def _same_earlier_products(capture):
    pair=capture.pair;construction=pair.construction;contract=pair.contract
    need(construction.owner is capture.owner and construction is
         contract.admitted_open.issuance.construction,'same actual full creator/contract chain')
    selection=contract.admitted_open.issuance.result.product
    result={}
    for name in ('public_interface','public_ABI','paired_views_manifest'):
        item=construction.attempts[name]
        need(item.complete,'actual earlier completed public creator')
        raw=pair.outputs.read(item.output_pin,capture.metadata_cap,metadata=True)
        expected=item.product if name=='paired_views_manifest' else item.product.body
        need(raw==encode(expected),'exact original scientific/public canonical bytes')
        result[name]=(item.output_pin,expected)
    need(result['public_interface'][0]==selection['public_interface'] and
         result['public_ABI'][0]==selection['public_ABI'] and
         result['paired_views_manifest'][0]==selection['paired_views'],
         'actual earlier public products are exactly the selected originals')
    need(pair.inputs.read(contract.programme_abi_pin,capture.metadata_cap,metadata=True)==contract.programme_abi_raw,
         'exact same earlier static capture ABI readback')
    validate_type('ProgrammeCaptureABI',contract.programme_abi)
    need(contract.programme_abi_pin==contract.policy['programme_capture_ABI'],
         'ABI selected by the actual original AgentPolicy')
    return result


def _partition(capture,condition,manifest):
    arm=capture.pair.arms[condition];expected={}
    for row in arm.inventory.body['entries']:
        name=row['relative_path'];relative(name)
        need(name not in expected,'unique exact earlier inventory member')
        expected[name]={'kind':row['identity']['kind'],'identity':row['identity'],
                        'bytes':None if row['content'] is None else row['content']['bytes'],
                        'class':'inherited'}
    name=capture.pair.contract.programme_abi['manifest_path']
    need(name not in expected,'manifest cannot overwrite an original inherited member')
    expected[name]={'kind':'regular_file','class':'manifest'}
    for row in manifest['sources']:
        name=row['relative_path'];relative(name)
        need(name not in expected,'new source cannot overwrite original workspace/control/source')
        expected[name]={'kind':'regular_file','bytes':row['bytes'],'class':'source'}
        parts=name.split('/')
        for count in range(1,len(parts)):
            parent='/'.join(parts[:count])
            if parent in expected:need(expected[parent]['kind']=='directory','source ancestors are actual directories')
            else:expected[parent]={'kind':'directory','class':'source_ancestor'}
    need(len(expected)<=capture.files,'full workspace including inherited members fits original profile')
    return expected


def _project_jobs(capture,condition,manifest,files):
    pair=capture.pair;contract=pair.contract
    view=capture.public['paired_views_manifest'][1]
    inherited=view['common']+(view['author_code'] if condition==CONDITIONS[1] else [])
    expected_ids=[row['job_id'] for row in capture.public['public_interface'][1]['jobs']]
    need([row['job_id'] for row in manifest['jobs']]==expected_ids,'entire original job roster and order')
    jobs=[]
    for job in manifest['jobs']:
        need(job['argv'][0]['schema']=='ci_programme_tool_argument_v1','fixed earlier tool is argv zero')
        argv=[]
        for argument in job['argv']:
            kind=argument['schema']
            if kind=='ci_programme_literal_argument_v1':value=argument['value']
            elif kind=='ci_programme_source_argument_v1':value=files[argument['source_ordinal']]['captured']['path']
            elif kind=='ci_programme_inherited_argument_v1':
                ordinal=argument['view_member_ordinal']
                need(ordinal<len(inherited),'exact earlier permitted inherited-view ordinal')
                value=inherited[ordinal]['destination']
            else:
                need(kind=='ci_programme_tool_argument_v1' and argument['tool'] in contract.policy['tool_closure'],
                     'tool is in the earlier qualified exact command closure')
                from .operator_tool_commands import qualified_command_for_contract_v1
                value=qualified_command_for_contract_v1(contract,argument['tool'])
            need(type(value) is str and len(value)<=4096,'original bounded exact argv member')
            argv.append(value)
        jobs.append({'job_id':job['job_id'],'argv':argv,
                     'report_producer':files[job['report_source_ordinal']]['captured']})
    return jobs


class ProgrammeCapture:
    @staticmethod
    def capture_pair_v2(pair_completion):
        return ProgrammeCapture.capture_pair_v3(pair_completion)

    @staticmethod
    def capture_pair_v3(pair_completion):
        capture=ProgrammeCaptureHandle(_CAPTURE,pair_completion)
        try:
            pair_completion.require_original();pair=capture.pair;owner=capture.owner
            plan=owner.plan;profile=pair.contract.profile
            capture.metadata_cap=min(plan['maximum_input_bytes'],plan['maximum_output_bytes'],profile['maximum_metadata_bytes'])
            capture.source_cap=min(plan['maximum_input_bytes'],plan['maximum_output_bytes'])
            capture.files=min(8192,plan['maximum_members'],profile['maximum_files'])
            capture.depth=min(64,plan['maximum_depth'])
            for cap in (capture.metadata_cap,capture.source_cap,capture.files,capture.depth):integer(cap,1)
            capture.publisher=CanonicalPublisher(owner,pair.outputs,maximum_bytes=capture.metadata_cap,
                maximum_members=plan['maximum_members'],maximum_depth=capture.depth)
            _preflight(capture)
            capture.started_ns=capture.clock();capture.cost_before=owner.cost_prefix()
            capture.public=_same_earlier_products(capture)
            capture.phase='both_arm_preflight'
            # Both manifests and whole inventories pass before the first copied
            # source or new programme record. Partial reads remain original cost.
            for condition in CONDITIONS:
                reader=WorkspaceReader(capture,pair_completion.attempts[condition]);capture.readers[condition]=reader
                raw,before,after=reader.read(pair.contract.programme_abi['manifest_path'],capture.metadata_cap)
                body=parse_canonical(raw,capture.metadata_cap,maximum_depth=capture.depth,
                    maximum_members=plan['maximum_members'],maximum_string_bytes=capture.metadata_cap)
                validate_type('ProgrammeOutputManifest',body)
                need(canonical(body,capture.metadata_cap,maximum_depth=capture.depth)==raw,
                     'exact new-record canonical manifest, without alternate encodings')
                request=pair.arms[condition].request.body
                need(body['condition']==condition and body['public_interface']==request['public_interface']==capture.public['public_interface'][0]
                     and body['public_ABI']==request['public_ABI']==capture.public['public_ABI'][0],
                     'same earlier arm request/interface/ABI')
                need(len(body['sources'])<=capture.files and all(row['bytes']<=capture.source_cap for row in body['sources']),
                     'whole declared roster fits existing source/file extents')
                need([j['job_id'] for j in body['jobs']]==[j['job_id'] for j in capture.public['public_interface'][1]['jobs']],
                     'every original scientific job in exact order')
                capture.manifests[condition]=(body,raw,before,after)
                partition=_partition(capture,condition,body);capture.partitions[condition]=partition
                capture.inventories[condition]=reader.inventory(partition)
            for condition in CONDITIONS:
                capture.phase='capture_'+condition
                manifest,raw,_,_=capture.manifests[condition];reader=capture.readers[condition]
                manifest_capture=capture.publish('programme_'+condition+'_MANIFEST.json',
                                                            'ProgrammeOutputManifest',manifest)
                capture.manifest_captures[condition]=manifest_capture
                files=[];capture.captured_files[condition]=files
                for ordinal,declared in enumerate(manifest['sources']):
                    raw,before,after=reader.read(declared['relative_path'],capture.source_cap,declared=declared)
                    files.append(capture_source_file(capture,condition,ordinal,raw,declared,before,after))
                need(reader.inventory(capture.partitions[condition])==capture.inventories[condition],
                     'complete exact final inventory including all original member identities')
                jobs=_project_jobs(capture,condition,manifest,files)
                a=pair_completion.attempts[condition];arm=pair.arms[condition]
                body={'schema':'ci_captured_programme_source_manifest_v1','condition':condition,
                      'ABI':pair.contract.programme_abi_pin,'agent_policy':pair.contract.policy_pin,
                      'development':pair_completion.completions[condition].pin,'development_contract':pair.contract.identity_pin,
                      'files':files,'inherited_view_inventory':arm.inventory.pin,'jobs':jobs,
                      'original_attempt':a.prefix_capture.pin,'original_manifest':manifest_capture.pin,
                      'pair_closure':pair_completion.closure.pin,'public_ABI':capture.public['public_ABI'][0],
                      'public_interface':capture.public['public_interface'][0],'request':arm.request.pin,
                      'source_capture':pair.contract.programme_abi['source_capture'],
                      'source_closure':[row['captured'] for row in files],'workspace':arm.workspace_capture.pin}
                source=capture.publish('programme_'+condition+'_SOURCE_MANIFEST.json',
                                                 'CapturedProgrammeSourceManifest',body)
                capture.source_manifests[condition]=source
                receipt={'schema':'ci_programme_capture_receipt_v1','ABI':pair.contract.programme_abi_pin,
                         'captured_files':body['source_closure'],'condition':condition,'cost_before':capture.cost_before,
                         'cost_before_receipt':owner.cost_prefix(),'development':body['development'],
                         'development_contract':body['development_contract'],'finished_ns':capture.clock(),
                         'original_attempt':body['original_attempt'],'original_manifest':manifest_capture.pin,
                         'owner_binding':owner.parent.binding_pin,'pair_closure':body['pair_closure'],
                         'source_capture':body['source_capture'],'source_manifest':source.pin,
                         'started_ns':capture.started_ns,'status':'complete','workspace':body['workspace']}
                capture.receipts[condition]=capture.publish('programme_'+condition+'_CAPTURE_RECEIPT.json',
                                                                       'ProgrammeCaptureReceipt',receipt)
            need(set(capture.receipts)==set(CONDITIONS),'both original source receipts before either seal')
            capture.phase='both_arm_seals'
            for condition in CONDITIONS:
                source=capture.source_manifests[condition].body
                seal={'schema':'ci_programmeseal_v3','agent_policy':pair.contract.policy_pin,
                      'capture_receipt':capture.receipts[condition].pin,'condition':condition,
                      'development':pair_completion.completions[condition].pin,'environment':pair.contract.profile['environment'],
                      'exposure':pair.arms[condition].exposure.pin,'jobs':source['jobs'],
                      'pair_closure':pair_completion.closure.pin,'sealed_ns':capture.clock(),
                      'source_closure':source['source_closure'],'source_manifest':capture.source_manifests[condition].pin}
                capture.seals[condition]=capture.publish('programme_'+condition+'_SEAL.json','ProgrammeSeal',seal)
            capture.promoted=True;capture.phase='promoted'
            return capture.require_promoted()
        except BaseException as error:
            capture.retain(error,'ProgrammeCapture.capture_pair_v3');raise

