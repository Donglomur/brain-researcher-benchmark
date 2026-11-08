"""Exact independent operator admission; inactive source never authorizes work."""
from pathlib import Path
from core import need, integer, finite, pin, encoded, capture, parse, disjoint, canonical, relative
from contracts import TASK, matched_panel_limits


def effective_selection(selection):
    # Qualification document locators are the only excluded edge, avoiding a
    # self-pin cycle. Every actual parameter/root/resource/source stays bound.
    need(type(selection)is dict,'complete selected operation')
    return {k:v for k,v in selection.items() if k!='qualifications'}


class Qualifications:
    """Root-selected external evidence, not candidate booleans or callbacks."""
    def __init__(self,selection,source_pin,budget):
        self.selection=selection;self.source=source_pin;self.budget=budget
        self.binding=pin(encoded(effective_selection(selection)));self.observed=[]

    def require(self,kind,subject=None):
        records=self.selection['qualifications']
        need(kind in records,'missing independent qualification: '+kind)
        row=records[kind];path=Path(self.selection['roots']['operator'])/relative(row['path'])
        raw,custody=capture(path,row['pin'],262144,self.budget,readonly=True)
        value=parse(raw)
        need(value.get('schema')=='neural058_independent_qualification_v1' and value.get('task')==TASK,
             'task-specific independent qualification schema')
        need(value.get('kind')==kind and value.get('status')=='ADMITTED' and value.get('independent_operator') is True,
             'explicit independent operator admission')
        need(value.get('source')==self.source and value.get('selection')==self.binding,
             'qualification binds complete actual source/selection, not generic booleans')
        need(value.get('subject')==(None if subject is None else pin(encoded(subject))),
             'exact original/role/method/model/projection subject')
        need(value.get('original_origin')==self.selection['origin']
             and value.get('original_deadline')==self.selection['deadline'],'unchanged original qualification clocks')
        now=self.budget.tick()
        need(self.selection['origin']<=finite(value['observed'])<=now
             and now<finite(value['valid_until'])<=self.selection['deadline'],'fresh nonfuture independent qualification')
        self.observed.append({'kind':kind,'source':row,'custody':custody,'subject':value['subject']})
        return True


def validate(selection,source_pin,budget):
    need(selection.get('schema')=='neural058_complete_selection_v1' and selection.get('task')==TASK
         and selection.get('selected') is True,'explicit selected complete NEURAL058 operation')
    need(selection['source']==source_pin,'actual complete runtime source pin')
    need(selection['origin']==budget.origin and selection['deadline']==budget.deadline,'inherited original clocks')
    need(selection.get('conditional_history') is False,'strict primary; secondary has separate unresolved admission')
    need(selection.get('grading',{}).get('selected') is False,'production cannot contain late grading/observation circular pins')
    roots=selection['roots'];required={'source','prepared','private','original','output','observation','operator','secrets'}
    need(set(roots)==required,'complete protected namespaces')
    names=sorted(roots)
    for i,a in enumerate(names):
        canonical(roots[a])
        for b in names[i+1:]: need(disjoint(roots[a],roots[b]),'qualified distinct host namespaces')
    matched_panel_limits(selection['panel_limits'])
    for profile in selection['panel_limits'].values():
        for key in ('per_response_tokens','request_bytes','response_bytes'):integer(profile[key],1)
        need(profile['concurrency']==1,'selected source controller is sequential')
    expected_profiles={'reference_ridge','reference_forest','reference_set','candidate_analysis','candidate_fit','candidate_features','candidate_infer'}
    need(set(selection['native_profiles'])==expected_profiles,'complete actual native phase profiles')
    for profile in selection['native_profiles'].values():
        for key in ('cpu_ns','cpu_rate_ns','memory_bytes','scratch_bytes','pids','worker_read_bytes','worker_write_bytes'):integer(profile[key],1)
        for key in ('wall_seconds','retirement_seconds','readback_seconds','qualified_enforcement_lag_seconds'):
            need(finite(profile[key])>0,'positive full native phase bounds')
    need(selection['engine']['output_root']==roots['output']
         and selection['engine']['whole_output_quota_root']==roots['output'],'hard quota covers every native attempt and all derived retention')
    need(canonical(roots['secrets']) in canonical(selection['provider']['credential_path']).parents,'provider credential stays in protected selected namespace')
    integer(selection['limits']['journal_event_bytes'],1,64<<20)
    need(selection['engine']['image_id'].startswith('sha256:') and len(selection['engine']['image_id'])==71,'immutable native image digest')
    need(selection['provider']['wire_protocol']=='neural058_chat_json_v1','exact selected typed provider protocol')
    need(selection['limits']['read_bytes']==budget.read_cap and selection['limits']['write_bytes']==budget.write_cap,
         'inherited whole-operation resource counters')
    review=Qualifications(selection,source_pin,budget)
    for kind in ('environment_and_physical_resources','source_and_input_custody','full_support_and_projection',
                 'units_sign_and_native_semantics','method_exposure_and_workflow','reference_numerical_parity',
                 'provider_protocol_account_and_costs','immutable_mount_and_namespace_isolation'):
        review.require(kind)
    return review


def forbid_protected_mounts(mounts,selection):
    roots=selection['roots']
    for row in mounts:
        src=canonical(row['source'])
        for key in ('private','original','operator','secrets','observation'):
            need(disjoint(src,roots[key]),'no protected operand/credential/observation mounted to native candidate')
        need(row['destination'].startswith(('/inputs/','/artifacts/')),'exact allowed native namespace')
    return True
