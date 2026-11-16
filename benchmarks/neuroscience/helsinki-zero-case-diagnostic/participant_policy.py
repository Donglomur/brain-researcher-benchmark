"""Helsinki B-only policy and trusted kernel-evidence admission.

No qualification producer or accepted runtime is supplied by this source. All
proof bytes are trusted-owner operands bound before candidate material is read.
Candidate stdout and ordinary reference-worker observations cannot supply them.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from common import need, decode, pin, admit_pin

PROFILE = 'helsinki_arbitrary_frozen_program_participant_v1'
MIB = 1024 ** 2


def sha(value):
    return type(value) is str and len(value) == 64 and set(value) <= set('0123456789abcdef')


def validate_policy(p):
    need(type(p) is dict and set(p) == {'profile','image','runtime_manifest_sha256',
         'observer_source_sha256','source_closure_sha256','wall_seconds','cpu_seconds',
         'memory_bytes'}, 'closed_Helsinki_participant_policy')
    need(p['profile'] == PROFILE and type(p['image']) is str and
         p['image'].startswith('sha256:') and sha(p['image'][7:]), 'participant_image_policy')
    need(all(sha(p[k]) for k in ('runtime_manifest_sha256','observer_source_sha256',
         'source_closure_sha256')), 'source_runtime_observer_identity')
    need(type(p['wall_seconds']) is int and 1 <= p['wall_seconds'] <= 3600 and
         type(p['cpu_seconds']) is int and p['cpu_seconds'] == 120 and
         type(p['memory_bytes']) is int and p['memory_bytes'] == 1024 ** 3,
         'explicit_wall_and_unchanged_120CPU_1GiB')
    return p


_ADMITTED = object()


@dataclass(frozen=True)
class RuntimeAdmission:
    policy_json: bytes
    fact_sha256: str
    opinion_sha256: str
    token: object

    @property
    def policy(self):
        return json.loads(self.policy_json)


def _pinned_json(body, expected):
    admit_pin(expected, MIB)
    need(type(body) is bytes and pin(body) == expected, 'exact_selected_evidence_bytes')
    return decode(body, MIB)


def admit_runtime(policy, fact_body, fact_pin, opinion_body, opinion_pin):
    """Exact external facts, never a generated-control or trusted-worker flag.

    The trusted owner must select genuinely accepted original facts/opinions and
    independently authenticate the complete source closure. This parser cannot
    establish the truth of arbitrary assertions in a forged owner-supplied file.
    """
    validate_policy(policy)
    fact = _pinned_json(fact_body, fact_pin)
    opinion = _pinned_json(opinion_body, opinion_pin)
    need(type(fact) is dict and set(fact) == {'schema','policy','kind','observations',
         'input_scope','observer_mode','original_evidence_sha256'}, 'participant_runtime_fact_schema')
    need(fact['schema'] == PROFILE + '.FACT' and fact['policy'] == policy and
         fact['kind'] == 'independently_reviewed_actual_participant_qualification' and
         fact['observer_mode'] == 'trusted_in_process_no_child_observer' and
         fact['input_scope'] == 'current_public_case_and_frozen_same_fold_bundle_only' and
         sha(fact['original_evidence_sha256']), 'participant_specific_actual_fact_required')
    required = {'image_source_no_held_answers','read_only_exact_mounts','no_network_or_host_IPC',
                'unprivileged_capability_free','fresh_case_state','bounded_stdout_stderr',
                'full_container_cgroup_lifetime_accounting','empty_cgroup_final_observation',
                'owned_CID_and_client_closure','source_closure_authentication'}
    need(type(fact['observations']) is dict and set(fact['observations']) == required and
         all(type(v) is dict and set(v) == {'original_sha256','verdict'} and
             sha(v['original_sha256']) and v['verdict'] == 'accepted_actual_observation'
             for v in fact['observations'].values()), 'actual_original_observation_bindings')
    need(type(opinion) is dict and set(opinion) == {'schema','decision','fact_sha256',
         'source_closure_sha256','observer_source_sha256','image','kind'} and
         opinion == {'schema':PROFILE + '.WHOLE_OPINION','decision':'accepted',
             'fact_sha256':fact_pin['sha256'],'source_closure_sha256':policy['source_closure_sha256'],
             'observer_source_sha256':policy['observer_source_sha256'],'image':policy['image'],
             'kind':'independent_actual_participant_review'}, 'exact_independent_participant_opinion')
    return RuntimeAdmission(json.dumps(policy, sort_keys=True, separators=(',', ':')).encode(),
                            fact_pin['sha256'], opinion_pin['sha256'], _ADMITTED)


def require_runtime(value):
    need(type(value) is RuntimeAdmission and value.token is _ADMITTED, 'owner_admitted_runtime_capability')
    validate_policy(value.policy)
    return value


def _counter_table(text, names, label):
    need(type(text) is str and 0 < len(text.encode('ascii')) <= 8192 and text.endswith('\n'), label)
    rows = {}
    for line in text.splitlines():
        pieces = line.split(' ')
        need(len(pieces) == 2 and pieces[0] not in rows and pieces[0] in names and
             pieces[1].isdigit() and pieces[1].isascii(), label)
        rows[pieces[0]] = int(pieces[1])
    return rows


def validate_kernel_evidence(value, policy, *, cid, name):
    """Validate literal kernel counters from the selected trusted observer.

    Full cumulative CPU is used, without subtracting an inferred zero baseline.
    The external qualified observer must capture the final empty cgroup before
    Docker releases it. Missing such evidence is refusal, not zero resource use.
    """
    validate_policy(policy)
    need(type(value) is dict and set(value) == {'schema','cid','name','image','observer_source_sha256',
         'source','lifetime','capture_stage','cgroup_device','cgroup_inode','cgroup_path',
         'cpu_stat','memory_peak','cgroup_events','original_capture_sha256'}, 'closed_kernel_evidence')
    need(value['schema'] == PROFILE + '.KERNEL' and value['cid'] == cid and value['name'] == name and
         value['image'] == policy['image'] and value['observer_source_sha256'] == policy['observer_source_sha256'] and
         value['source'] == 'linux_cgroup_v2' and value['lifetime'] == 'entire_fresh_container_including_all_descendants' and
         value['capture_stage'] == 'all_tasks_exited_before_cgroup_release' and
         sha(value['original_capture_sha256']), 'kernel_scope_and_capture_identity')
    need(type(value['cgroup_device']) is int and value['cgroup_device'] >= 0 and
         type(value['cgroup_inode']) is int and value['cgroup_inode'] > 0 and
         type(value['cgroup_path']) is str and value['cgroup_path'].startswith('/') and
         '..' not in value['cgroup_path'].split('/') and
         all(32 <= ord(c) < 127 for c in value['cgroup_path']), 'exact_kernel_cgroup_identity')
    cpu = _counter_table(value['cpu_stat'], {'usage_usec','user_usec','system_usec','nr_periods',
        'nr_throttled','throttled_usec','nr_bursts','burst_usec'}, 'kernel_cpu_stat')
    need({'usage_usec','user_usec','system_usec'} <= set(cpu), 'complete_kernel_CPU')
    events = _counter_table(value['cgroup_events'], {'populated','frozen'}, 'kernel_cgroup_events')
    need(events.get('populated') == 0 and events.get('frozen') == 0, 'closed_empty_unfrozen_cgroup')
    peak = value['memory_peak']
    need(type(peak) is str and peak.endswith('\n') and peak[:-1].isdigit() and
         peak[:-1].isascii() and 0 < len(peak) <= 64, 'literal_kernel_memory_peak')
    peak = int(peak)
    need(0 <= cpu['usage_usec'] <= policy['cpu_seconds'] * 1000000 and
         cpu['user_usec'] <= cpu['usage_usec'] and cpu['system_usec'] <= cpu['usage_usec'] and
         0 < peak <= policy['memory_bytes'], 'aggregate_container_resource_limit')
    return {'kernel_original':dict(value),'CPU_seconds':cpu['usage_usec'] / 1000000,
            'peak_memory_bytes':peak,'accounting_scope':'complete_container_cgroup',
            'scientifically_qualified':False}


def validate_observer_closed(value, policy):
    need(type(value) is dict and set(value) == {'schema','observer_source_sha256',
         'close_status','original_close_sha256'} and
         value['schema'] == PROFILE + '.OBSERVER_CLOSED' and
         value['observer_source_sha256'] == policy['observer_source_sha256'] and
         value['close_status'] == 'all_owned_descriptors_closed_no_children_created' and
         sha(value['original_close_sha256']), 'trusted_observer_closure_required')
    return dict(value)
