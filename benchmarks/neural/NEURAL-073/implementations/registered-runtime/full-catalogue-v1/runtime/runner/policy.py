"""Public analysis opportunity and closed action protocol; no model or I/O calls."""
from dataclasses import dataclass
from ..core.custody import CustodyError, canonical, digest
from ..core.inference import InferencePolicy, require_applied_inference

TASK = '''Recover the 25 declared protocol labels for every case in the one held-person query batch.
Training cases, person groups, their labels, original nuisance-enriched C descriptors,
permitted neural arrays, and inspectable fitted reference tools are available.
The original and spatial-scrambled conditions expose N, C and NC tools; C-only exposes
only C tools. C is always computed from the original array. Train your own models,
inspect reference parameters, run analyses, and use the entire allowed batch.
Full training/query cardinality and grouping are permitted side information. Avoid
source lookup: network and private source identities are not available. No query
answers, scores or correctness feedback are supplied during this study.
Return one JSON line per query case: {"case_id":"opaque ID","probabilities":[25 numbers]}.
Numbers must be finite, nonnegative, with sum within1e-6 of1. Missing/duplicate/invalid
rows are retained as failures. Supply all rows, with no prose. The selected resource
ceilings are shared across both phases and every tool/model call; no retries/reset.
Use exec with a shell-free argv list to run Python or other admitted runtime tools.
If shell syntax is needed invoke an admitted shell explicitly; its entire process
runs in the same isolated sandbox. To preserve a program, write an executable under
/work with an admitted interpreter shebang. No package/network installation exists.
F authors a complete program before query, then returns seal with its relative path
under /work and fixed argv suffix. The complete work/tmp state is frozen. After seal
F receives no model calls and that frozen executable runs once on the query batch.
I may open_query then continue analyses/model calls, and finishes with submit naming
its complete output file under /work. Both arms get the same data/tools/resources.
Reference CLI: /tools/reference_cli.py inspect NAME; /tools/reference_cli.py predict
NAME /data/training|/data/query [CASE_ID...]. Predict emits calibrated probabilities.
The common interface and geometry are in /knowledge; row JSONL and arrays belong to
phase-specific /data/training and /data/query. Query is absent before it opens.
'''


def _string(value,name,maximum=4096):
    if not isinstance(value,str) or not value or len(value.encode('utf-8'))>maximum or '\x00' in value:
        raise CustodyError('invalid action '+name)
    return value


def relative_work_path(value):
    import posixpath
    _string(value,'work path')
    if value.startswith('/') or posixpath.normpath(value)!=value or value in ('.','..') or value.startswith('../'):
        raise CustodyError('canonical relative work path required')
    return value


@dataclass(frozen=True)
class Policy:
    policy_id: str
    max_response_tokens: int
    source_digest: str
    inference_policy: InferencePolicy

    def __post_init__(self):
        from ..core.custody import require_digest
        _string(self.policy_id,'policy ID');require_digest(self.source_digest)
        if type(self.inference_policy) is not InferencePolicy:
            raise CustodyError('typed fixed inference policy required')
        if type(self.max_response_tokens) is not int or not 1<=self.max_response_tokens<=131072:
            raise CustodyError('response maximum must lie within the shared output allowance')

    @property
    def binding_digest(self):
        return digest({'id':self.policy_id,'max_response_tokens':self.max_response_tokens,
                       'source_digest':self.source_digest,'task':TASK,
                        'inference_policy':self.inference_policy.to_dict()})

    def require_adapter(self,admission,context):
        from ..provider_transport.protocol import AdapterAdmission
        if type(admission) is not AdapterAdmission:
            raise CustodyError('typed adapter admission required for matched inference')
        admission.validate()
        if admission.context_id!=context.context_id or admission.repetition!=context.repetition:
            raise CustodyError('adapter context/repetition differs from candidate context')
        return require_applied_inference(admission.inference_binding,
            self.inference_policy.binding_for(context.repetition))

    def initial(self,public_context):
        if set(public_context)!= {'context_id','condition','arm','repetition'}:
            raise CustodyError('closed public context required')
        self.inference_policy.binding_for(public_context['repetition'])
        return {'task':TASK,'context':dict(public_context),'policy_id':self.policy_id,
                'messages':[],'action_schema':'n073_candidate_action_v1'}


def parse_action(value, *, arm, phase):
    """Responses contain exactly one action, not executable trusted-host code."""
    if type(value) is not dict or value.get('schema')!='n073_candidate_action_v1':
        raise CustodyError('candidate action schema')
    kind=value.get('action')
    if kind=='exec':
        if set(value)!={'schema','action','argv','observation_offset','observation_bytes'}:
            raise CustodyError('exec action fields')
        argv=value['argv']
        if type(argv) is not list or not argv or len(argv)>4096:
            raise CustodyError('explicit nonempty bounded argv list required')
        for arg in argv:_string(arg,'argument',1048576)
        if not argv[0].startswith('/'):
            raise CustodyError('explicit admitted sandbox executable path required')
        for key in ('observation_offset','observation_bytes'):
            if type(value[key]) is not int or value[key]<0:
                raise CustodyError('nonnegative observation bounds')
        if value['observation_bytes']==0:raise CustodyError('positive observation window')
    elif kind=='seal':
        if arm!='F' or phase!='authoring' or set(value)!={'schema','action','entry','argv_suffix'}:
            raise CustodyError('seal only in F authoring')
        relative_work_path(value['entry'])
        if type(value['argv_suffix']) is not list or len(value['argv_suffix'])>4096:
            raise CustodyError('frozen argument vector')
        for arg in value['argv_suffix']:_string(arg,'frozen argument',1048576)
    elif kind=='open_query':
        if arm!='I' or phase!='authoring' or set(value)!={'schema','action'}:
            raise CustodyError('open_query only in I authoring')
    elif kind=='submit':
        if arm!='I' or phase!='query_open' or set(value)!={'schema','action','output'}:
            raise CustodyError('submit only in I query')
        relative_work_path(value['output'])
    else:raise CustodyError('unknown action')
    canonical(value)
    return dict(value)
