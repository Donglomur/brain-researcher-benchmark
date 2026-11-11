"""Actual full-census assembly after both original arm source captures.

The original census validator is called through the same admitted SourceSession.
BUILD controls keep that scientific leaf inert; this module supplies no stand-in.
"""
from .common import need, encode, parse, pin, bounded_size
from .backend_capture import CaptureAttempt
from .precommit_records import CONDITIONS, validate_type
from .programme_capture import ProgrammeCaptureHandle

_ASSEMBLY=object()
_SCIENTIFIC=object()


class CapturedScientificRecord:
    __slots__=('_raw','_pin','owner','kind','attempt')
    def __init__(self,token,raw,descriptor,owner,kind,attempt):
        need(token is _SCIENTIFIC,'fixed completed original-encoding publication')
        self._raw=raw;self._pin=dict(descriptor);self.owner=owner;self.kind=kind;self.attempt=attempt
    @property
    def raw(self):return self._raw
    @property
    def pin(self):return dict(self._pin)
    @property
    def body(self):return parse(self._raw,len(self._raw))


class ProgrammeAssemblyHandle:
    def __init__(self,token,capture):
        need(token is _ASSEMBLY and type(capture) is ProgrammeCaptureHandle,
             'fixed original programme assembly constructor')
        need(capture.assembly is None,'one assembly attempt on the same capture')
        self.capture=capture;self.owner=capture.owner;self.raw_first=None;self.raw_secondaries=[]
        self.attempts={};self.final_census=None;self.receipt=None;self.binding=None;self.policy=None
        self.phase='registered';self.complete=False;self.cost_before=None;self.started_ns=None
        capture.assembly=self  # Register before P12 validation, clock or IO.

    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.complete=False;self.phase='failed';self.capture.retain(error,'ProgrammeAssembler.assemble_v3')

    def scientific_capture(self,name,kind,body):
        p=self.capture.publisher
        need(name not in self.attempts,'one actual original-encoding publication slot')
        attempt=CaptureAttempt(name,kind);self.attempts[name]=attempt
        try:
            key=(str(p.outputs.root),name)
            need(key not in p.parent.canonical_publications and
                 len(p.parent.canonical_publications)<p.maximum_members,'whole original publication count')
            p.parent.canonical_publications[key]=attempt
            bound=bounded_size(body)
            p.meter.charge('work_units',bound);p.meter.charge('retained_bytes',bound)
            if kind!='OriginalScientificCensus':validate_type(kind,body)
            raw=encode(body);attempt.raw=raw
            need(len(raw)<=self.capture.metadata_cap,'complete original-encoding member cap')
            # Same structural domain, without changing the scientific encoder.
            from .backend_json import parse as closed_parse
            closed_parse(raw,self.capture.metadata_cap,maximum_depth=self.capture.depth,
                         maximum_members=p.maximum_members,maximum_string_bytes=self.capture.metadata_cap)
            attempt.write_entered=True
            expected=p.outputs.write(name,raw);attempt.provisional=expected
            p.meter.charge('retained_bytes',len(raw)+1);attempt.readback_entered=True
            need(p.outputs.read(expected,self.capture.metadata_cap,metadata=True)==raw,
                 'exact original scientific encoding write/close/readback')
            result=CapturedScientificRecord(_SCIENTIFIC,raw,expected,self.owner,kind,attempt)
            attempt.complete=result;self.owner.parent.known_records.append(expected)
            return result
        except BaseException as error:attempt.retain(error);self.retain(error);raise


class ProgrammeAssembler:
    @staticmethod
    def assemble_v3(capture):
        result=ProgrammeAssemblyHandle(_ASSEMBLY,capture)
        try:
            capture.require_promoted();pair=capture.pair;construction=pair.construction
            session=construction.session;public=construction.public;template=construction.template
            need(type(template) is public.ScientificTemplateAdmission and template.scope is construction.scope and
                 template is construction.attempts['public_interface'].product.template and not session.closed,
                 'same actual full original template admission and source session')
            result.cost_before=result.owner.cost_prefix();result.started_ns=capture.clock()
            result.phase='complete_scientific_projection'
            result.owner.host.charge('work_units',bounded_size(template.body))
            result.owner.host.charge('retained_bytes',bounded_size(template.body)*2)
            census=parse(encode(template.body['census_body']),capture.metadata_cap)
            abi=pair.contract.programme_abi
            for job in census['jobs']:
                if job['operation']=='candidate':
                    need('command' not in job and 'command_source_pins' not in job,
                         'only original missing candidate dispatch fields are added')
                    job['command']=list(abi['dispatcher_argv'])
                    job['command_source_pins']=[dict(row) for row in abi['dispatcher_source']]
            raw=encode(census);expected={'path':'programme_FINAL_CENSUS.json',**pin(raw)}
            public.require_final_scientific_projection(template,census,expected,meter=result.owner.host)
            # The fixed original full validator remains the sole authority for
            # scientific census requirements. No new callback or partial test.
            original=session.module('census')
            original.validate(construction.scope,census)
            original.require_executable(census)
            result.final_census=result.scientific_capture(expected['path'],'OriginalScientificCensus',census)
            result.phase='assembly_receipt'
            seals={c:capture.seals[c].pin for c in CONDITIONS}
            body={'schema':'ci_programme_assembly_receipt_v1','ABI':pair.contract.programme_abi_pin,
                  'agent_policy':pair.contract.policy_pin,'assembler_source':abi['assembler_source'],
                  'capture_receipts':{c:capture.receipts[c].pin for c in CONDITIONS},
                  'cost_before':result.cost_before,'cost_before_receipt':result.owner.cost_prefix(),
                  'development_contract':pair.contract.identity_pin,
                  'dispatcher_argv':list(abi['dispatcher_argv']),'dispatcher_source':list(abi['dispatcher_source']),
                  'early_selection':pair.contract.admitted_open.selection_pin,'final_census':result.final_census.pin,
                  'finished_ns':capture.clock(),'owner_binding':result.owner.parent.binding_pin,
                  'projected_template_census_sha256':pin(encode(template.body['census_body']))['sha256'],
                  'public_ABI':capture.public['public_ABI'][0],'public_interface':capture.public['public_interface'][0],
                  'scientific_template':template.descriptor,'seals':seals,
                  'source_manifests':{c:capture.source_manifests[c].pin for c in CONDITIONS},
                  'started_ns':result.started_ns,'status':'complete'}
            result.receipt=capture.publish('programme_ASSEMBLY_RECEIPT.json','ProgrammeAssemblyReceipt',body)
            result.phase='binding'
            binding={'schema':'ci_executionbinding_v1','agent_policy':pair.contract.policy_pin,
                     'assembler_receipt':result.receipt.pin,'campaign_id':result.owner.parent.clock['campaign_id'],
                     'dispatcher_argv':list(abi['dispatcher_argv']),'dispatcher_source':list(abi['dispatcher_source']),
                     'early_selection':body['early_selection'],'final_census':result.final_census.pin,
                     'public_ABI':body['public_ABI'],'public_interface':body['public_interface'],
                     'scientific_template':template.descriptor,'seals':seals}
            result.binding=result.scientific_capture('programme_EXECUTION_BINDING.json','ExecutionBinding',binding)
            result.phase='paired_policy'
            policy={'schema':'critical_init_paired_candidate_policy_v4','census':result.final_census.pin,
                    'conditions':list(CONDITIONS),'execution_binding':result.binding.pin,
                    'jobs':[{'job_id':job['id'],'command':job['command'],'command_source_pins':job['command_source_pins']}
                            for job in census['jobs'] if job['operation']=='candidate'],
                    'paired_view_manifest':capture.public['paired_views_manifest'][0],'programme_seals':seals,
                    'report_ABI':body['public_ABI'],'same_agent_policy':pair.contract.policy_pin}
            result.policy=result.scientific_capture('programme_PAIRED_POLICY.json','PairedPolicy',policy)
            capture.clock();capture.require_promoted()
            result.phase='complete';result.complete=True
            return result
        except BaseException as error:result.retain(error);raise

