"""Fixed Figure 2 reporting selection after the accepted reference successor.

Metadata authentication only. Existing numerical reporters are unchanged and
never executed here. The scalar admission API and the endpoint batch are intact.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import types

TASK = 'PAPER-paper-method-029'
HOME = 'benchmarks/paper/' + TASK
REVISION_FILE = 'figure2-complete-successor.v1.json'
CURRENT_FILE = 'improvement.figure2-complete.v1.json'
PREVIOUS_MODULE_SHA256 = '98256a1ca02da2a4bad11ab6735d966a36011d638e9e7ecf35e0195a102daea5'
_SEAL = object()
_PREVIOUS = None


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _previous():
    global _PREVIOUS
    if _PREVIOUS is not None:
        return _PREVIOUS
    path = Path(__file__).with_name('paper_deeprecon_reference.py')
    _need(not path.is_symlink(), 'Deeprecon reference authenticator cannot be a symlink')
    with path.open('rb') as stream:
        raw = stream.read(65537)
    _need(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == PREVIOUS_MODULE_SHA256,
          'Deeprecon reference authenticator identity mismatch')
    module = types.ModuleType('_deeprecon_figure2_previous')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    _PREVIOUS = module
    return module


def approved_pin(name):
    return copy.deepcopy(_APPROVED[name]['pin']) if name in _APPROVED else _previous().approved_pin(name)


def _pin(selected, name):
    _need(type(selected) is dict and selected == approved_pin(name), 'Unreviewed Deeprecon Figure2 ' + name + ' selector')


def _is_new(revision):
    return type(revision) is dict and revision.get('path') == HOME + '/' + REVISION_FILE


def has_primary_successor(row):
    _need(row.get('id') == TASK and row.get('track') == 'paper', 'Unexpected Deeprecon Figure2 owner')
    declared = row.get('paper_outcomes')
    if declared is None:
        return False
    _need(type(declared) is dict, 'Deeprecon outcomes must be an object')
    if not _is_new(declared.get('primary_policy_revision')):
        return _previous().has_primary_successor(row)
    for field, name in (('primary_policy_revision', 'descriptor'),
                        ('primary_improvement_contract', 'improvement'), ('reproduction_contract', 'reproduction')):
        _pin(declared.get(field), name)
    return True


def _paths(before, after, prefix=''):
    if type(before) is not type(after):
        return [prefix]
    if type(before) is dict:
        if set(before) != set(after):
            return [prefix]
        return [path for key in before for path in _paths(before[key], after[key], prefix + '/' + key)]
    if type(before) is list:
        if len(before) != len(after):
            return [prefix]
        return [path for i in range(len(before)) for path in _paths(before[i], after[i], prefix + '/' + str(i))]
    return [] if before == after else [prefix]


def _project(previous_task, improvement):
    result = copy.deepcopy(previous_task)
    result['primary_outputs'][1] = ('Improvement: complete original Figure 2 content-loss-matched reporting '
        'for all 20 directed pairs, six ROIs and both axes, with complete brain-loss controls, under ' + CURRENT_FILE + '.')
    result['success_criteria'][0] = ('Assess reproduction and improvement independently under reproduction.v1.json and '
                                   + CURRENT_FILE + '; do not combine their scores.')
    result['evaluation']['contracts']['improvement'] = CURRENT_FILE
    result['episode']['improvement'] = copy.deepcopy(improvement['episode'])
    result['blocking_issues']['improvement'] = copy.deepcopy(improvement['blocking_issues'])
    result['holds']['preserved_limits']['task_specific'] = copy.deepcopy(improvement['blocking_issues'])
    result['holds']['interpretation'] = (
        'Source, observation, exposure and execution limits remain in force. Improvement-only criteria apply only to '
        'improvement; reproduction-specific gaps are declared in reproduction.v1.json. The selected ' + CURRENT_FILE
        + ' binds the complete original Figure 2 reporting panel and matching exposed published references. '
        'Both preceding improvement contracts and archived tasks retain their historical scope. This source binding '
        'does not qualify native execution, inferential superiority or either scientific outcome.')
    result['next_implementation_action']['improvement']['action'] = (
        improvement['disposition_reason'] + ' ' + ' '.join(improvement['blocking_issues']))
    return result


class _Authenticated:
    __slots__ = ('_payload', '_seal')

    def __init__(self, documents, seal):
        _need(seal is _SEAL, 'Authenticated Deeprecon Figure2 seal required')
        object.__setattr__(self, '_payload', _encode(documents))
        object.__setattr__(self, '_seal', seal)

    def __setattr__(self, name, value):
        raise AttributeError('Authenticated Deeprecon Figure2 is immutable')

    def __delattr__(self, name):
        raise AttributeError('Authenticated Deeprecon Figure2 is immutable')

    def snapshot(self):
        _need(self._seal is _SEAL, 'Authenticated Deeprecon Figure2 seal required')
        return json.loads(self._payload)

    @property
    def primary_improvement(self):
        return self.snapshot()['improvement']

    @property
    def retained_improvement(self):
        return self.snapshot()['previous']['retained_improvement']

    @property
    def descriptor_pin(self):
        return approved_pin('descriptor')

    @property
    def candidate_interface(self):
        return None

    @property
    def author_reproduction_routes(self):
        return None

    @property
    def members(self):
        old = _previous()
        return [old.approved_pin('descriptor'), old.approved_pin('improvement'),
                approved_pin('descriptor'), approved_pin('improvement')]

    @property
    def public_provenance(self):
        old = _previous()
        return {'published_reference': old.approved_pin('reference'),
                'previous_task': approved_pin('previous_task'),
                'previous_outcomes': approved_pin('previous_outcomes'),
                'retained_improvement': old.approved_pin('retained_improvement'),
                'reference_recovery_policy': old.approved_pin('improvement'),
                'reference_recovery_revision': old.approved_pin('descriptor'),
                'complete_figure2_binding': approved_pin('descriptor')}


def authenticate(*, task_id, revision_pin, primary_pin, reproduction_pin, previous_pin,
                 retained_improvement_pin, read_pin):
    _need(task_id == TASK, 'Unexpected Deeprecon Figure2 task')
    old = _previous()
    if not _is_new(revision_pin):
        return old.authenticate(task_id=task_id, revision_pin=revision_pin, primary_pin=primary_pin,
                                reproduction_pin=reproduction_pin, previous_pin=previous_pin,
                                retained_improvement_pin=retained_improvement_pin, read_pin=read_pin)
    for selected, name in ((revision_pin, 'descriptor'), (primary_pin, 'improvement'),
                           (reproduction_pin, 'reproduction'), (previous_pin, 'pre_outcomes'),
                           (retained_improvement_pin, 'retained_improvement')):
        _pin(selected, name)

    def archived_reader(pin, label):
        if pin == old.approved_pin('outcomes'):
            return read_pin(approved_pin('previous_outcomes'), label + ' (exact retained reference-stage bytes)')
        return read_pin(pin, label)

    historical = old.authenticate(task_id=TASK, revision_pin=old.approved_pin('descriptor'),
        primary_pin=old.approved_pin('improvement'), reproduction_pin=reproduction_pin,
        previous_pin=previous_pin, retained_improvement_pin=retained_improvement_pin, read_pin=archived_reader)
    prior = historical.snapshot()
    docs = {}
    for name, identity in _APPROVED.items():
        value = read_pin(copy.deepcopy(identity['pin']), 'Deeprecon Figure2 ' + name)
        _need(_digest(value) == identity['canonical'], 'Deeprecon Figure2 parsed identity mismatch: ' + name)
        docs[name] = value
    descriptor, improvement = docs['descriptor'], docs['improvement']
    _need(descriptor['schema_version'] == 'deeprecon-figure2-complete-successor/v1'
          and descriptor['task_id'] == TASK, 'Invalid Deeprecon Figure2 descriptor')
    _need(descriptor['panel_binding'] == _PANEL, 'Deeprecon Figure2 requires the exact complete original panel')
    _need(descriptor['previous_reference_revision'] == old.approved_pin('descriptor')
          and descriptor['previous_improvement'] == old.approved_pin('improvement')
          and descriptor['unchanged_reproduction'] == reproduction_pin, 'Deeprecon Figure2 predecessor identities differ')
    _need(old.project(prior['archived_task.json'], historical) == docs['previous_task'],
          'Deeprecon Figure2 requires the authenticated reference-stage task')
    _need(docs['previous_outcomes'] == prior['outcomes'], 'Deeprecon Figure2 archived outcomes differ')
    _need(improvement['same_task'] == prior['improvement']['same_task']
          and improvement['source_paper'] == prior['improvement']['source_paper'], 'Deeprecon Figure2 same-task anchors changed')
    _need(sorted(_paths(prior['improvement'], improvement)) == descriptor['improvement_changed_pointers'],
          'Deeprecon Figure2 improvement differs beyond accepted source bindings')
    _need(improvement['disposition'] == prior['improvement']['disposition'] == 'source_unresolved'
          and prior['reproduction']['eligibility'] == 'source_unresolved'
          and 'admission_policy' not in improvement, 'Deeprecon Figure2 cannot promote qualification')
    for key in ('minimum_effect', 'uncertainty', 'reproduced_author_baseline', 'current_sota'):
        _need(improvement['comparison'][key] == prior['improvement']['comparison'][key],
              'Deeprecon Figure2 changed unresolved inferential or calibration policy: ' + key)
    _need(improvement['comparison']['published_baseline']['status'] == 'unresolved'
          and improvement['comparison']['published_baseline']['value'] is None,
          'Deeprecon Figure2 cannot invent a combined scalar baseline')
    _need(improvement['episode']['access_budget'] is None and improvement['episode']['resource_budget'] is None,
          'Deeprecon Figure2 cannot instantiate episode budgets')
    expected_task = _project(docs['previous_task'], improvement)
    _need(expected_task == docs['task'], 'Deeprecon Figure2 current projection differs')
    _need(sorted(_paths(docs['previous_task'], docs['task'])) == descriptor['task_changed_pointers'],
          'Deeprecon Figure2 task differs beyond fixed projection')
    expected_outcomes = copy.deepcopy(docs['previous_outcomes'])
    expected_outcomes['original_task_sha256'] = approved_pin('task')['sha256']
    expected_outcomes['contracts']['improvement'] = _digest(improvement)
    expected_outcomes['pairing']['improvement']['rationale'] = _OUTCOME_RATIONALE
    _need(expected_outcomes == docs['outcomes'], 'Deeprecon Figure2 outcomes differ beyond binding and endpoint wording')
    _need(all(value['protocol'] is None and value['status'] == 'unresolved'
              for value in docs['outcomes']['pairing'].values()), 'Deeprecon Figure2 cannot instantiate pairing')
    docs['previous'] = prior
    return _Authenticated(docs, _SEAL)


def project(base_dual_task, authenticated):
    if type(authenticated) is not _Authenticated:
        # The original authenticator remains independently usable and checks its
        # own seal; unsupported objects cannot enter either projection.
        return _previous().project(base_dual_task, authenticated)
    _need(authenticated._seal is _SEAL, 'Authenticated Deeprecon Figure2 required')
    docs = authenticated.snapshot()
    _need(base_dual_task == docs['previous']['archived_task.json'],
          'Deeprecon Figure2 requires the exact deterministic predecessor projection')
    result = _project(docs['previous_task'], docs['improvement'])
    expected = approved_pin('task')
    raw = _encode(result)
    _need(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'],
          'Deeprecon Figure2 projection raw identity differs')
    return result

# Exact independently reviewable identities and panel semantics are appended by
# the bounded source builder, never derived from files occupying selected paths.

_APPROVED = {'descriptor': {'pin': {'path': 'benchmarks/paper/PAPER-paper-method-029/figure2-complete-successor.v1.json', 'bytes': 12990, 'sha256': '968a91bf54d1e33c5e077e159d75daa22498a7b7efd1d8da5553cb089da29c73'}, 'canonical': 'ba5e2a4eb16b1c4d4e8d18ef2898ddea9bd3c6bb8a12f01e80f581b1d1625744'}, 'improvement': {'pin': {'path': 'benchmarks/paper/PAPER-paper-method-029/improvement.figure2-complete.v1.json', 'bytes': 18101, 'sha256': '7b38e2298d01074e4141cdc911bdea89398a8ec6fe3dff1ccf14b04e795251fd'}, 'canonical': 'd64f9e415d0c55d085e09ab100332f99559d8eebc0daf5ab0f39ffbd83a4275b'}, 'task': {'pin': {'path': 'benchmarks/paper/PAPER-paper-method-029/task.json', 'bytes': 31093, 'sha256': '60d56b21b763b356fec9b5fb74ff171880f7c6578c3f6f418652a8bd7f017a37'}, 'canonical': 'b426f1b2fddc606dd352ccfe35e15fe16719ec96932e0851883409356e1e5c2b'}, 'outcomes': {'pin': {'path': 'benchmarks/paper/PAPER-paper-method-029/outcomes.v1.json', 'bytes': 1642, 'sha256': '937f70b104829d9533c825f5a97a75525d5fe7993a92d955a7ddc1e7b51e9151'}, 'canonical': 'b4366fb0065d51d1f3c98da29d928defdb8f757902c32883029f05aa8f5a1f0c'}, 'previous_task': {'pin': {'path': 'benchmarks/paper/PAPER-paper-method-029/docs/provenance/pre-figure2-complete-20261117/task.json', 'bytes': 29884, 'sha256': 'bf0a50c891e2654e310ede3e5e322283db064e990d925f54559b58bcc1ca1eeb'}, 'canonical': 'b642856be87ee133c1d909950b3339181d014c7b111d880efc257cb7f764a704'}, 'previous_outcomes': {'pin': {'path': 'benchmarks/paper/PAPER-paper-method-029/docs/provenance/pre-figure2-complete-20261117/outcomes.v1.json', 'bytes': 1559, 'sha256': '4ecaa3fe84077ff455079bb817edf5e7defb7a6e529f8bfd8eed6660f5364ecf'}, 'canonical': '53efdefec3715fbef026643f6f85bf0aafa3c45f51996fabd336565bcf80b773'}}
_PANEL = {'selection': 'complete_original_figure2_overlapping_training_condition', 'subjects': ['sub01', 'sub02', 'sub03', 'sub04', 'sub05'], 'directed_pairs': [['sub01', 'sub02'], ['sub01', 'sub03'], ['sub01', 'sub04'], ['sub01', 'sub05'], ['sub02', 'sub01'], ['sub02', 'sub03'], ['sub02', 'sub04'], ['sub02', 'sub05'], ['sub03', 'sub01'], ['sub03', 'sub02'], ['sub03', 'sub04'], ['sub03', 'sub05'], ['sub04', 'sub01'], ['sub04', 'sub02'], ['sub04', 'sub03'], ['sub04', 'sub05'], ['sub05', 'sub01'], ['sub05', 'sub02'], ['sub05', 'sub03'], ['sub05', 'sub04']], 'rois': ['VC', 'V1', 'V2', 'V3', 'V4', 'HVC'], 'axes': ['pattern', 'profile'], 'source_methods': ['brain_loss', 'content_loss'], 'images': 50, 'repeats': 24, 'training_samples': 6000, 'metric': 'noise_ceiling_normalized_Pearson_correlation', 'direction': 'higher', 'pattern': 'Average all 24-by-24 measured/predicted repeat correlations per image in target-normalized voxel space; normalize and mask/clip eligible per-image values before within-pair averaging.', 'profile': 'Restore target training-derived scaling; correlate across the 50-image axis for each voxel and every repeat combination; normalize and mask/clip eligible voxel values before within-pair averaging.', 'mask_clip': 'Use fixed source noise-ceiling/random-pair-threshold artifacts and exact author eligible-feature rule; divide by ceiling, clip each eligible feature to [-1,1], then average. Do not estimate or alter masks from candidate/test results.', 'source_support_holds': ['Native source and target ordered voxel/trial identities and training-derived scales remain unqualified.', 'Original noise-ceiling/threshold/mask arrays are not authenticated by this binding.', 'Existing refusal of undefined eligible replay values remains; source nan_to_num parity is an unresolved native verification issue.'], 'published_source': {'url': 'https://static-content.springer.com/esm/art%3A10.1038%2Fs43588-025-00826-5/MediaObjects/43588_2025_826_MOESM4_ESM.csv', 'bytes': 15637, 'sha256': 'f6beffbcad700f3e24208016daabe18d802805404f32a0585e2f9333fd4968fb', 'row_keys': ['Source', 'Target', 'ROI', 'Method'], 'axis_columns': {'pattern': 'pattern_mean', 'profile': 'profile_mean'}, 'rows': 240, 'pair_axis_values': 480, 'role': 'exposed_published_pair_means_not_computation_proof'}, 'primary_comparator': {'method_key': 'content_loss', 'pair_axis_values': 240, 'support': 'Every directed pair x ROI x axis in the explicit roster; exact keyed lookup in the pinned publisher CSV.', 'role': 'matching_main_original_paper_method_reference'}, 'required_control': {'method_key': 'brain_loss', 'pair_axis_values': 240, 'support': 'The identical complete directed pair x ROI x axis roster.', 'role': 'source_control_under_its_own_access_condition_not_main_comparator_substitution'}, 'continuous_reporting': {'implementation': {'path': 'benchmarks/paper/PAPER-paper-method-029/implementations/published-reference-continuous-v1/continuous.py', 'bytes': 6044, 'sha256': '199803a571931e4665fe8ae34e272716c21bcc4b86f87a0ab926f59f2110591b'}, 'predecessor_reader': {'path': 'benchmarks/paper/PAPER-paper-method-029/implementations/published-reference-v1/published_reference.py', 'bytes': 12446, 'sha256': '3e4d5d23fbd740999f60b8deaaa9689db72bc3821f07259639716b70d60263f8'}, 'api': 'compare_continuous(reference, replay)', 'result_schema': 'deeprecon_published_pair_discrepancies/v1', 'pair_rows': 480, 'roi_method_axis_groups': 24, 'summary_role': 'observed_equal_pair_mean_not_figure_bootstrap_mean', 'decision': 'not_made', 'candidate_or_native_authentication': 'not_provided_by_reporter', 'scientific_improvement': 'not_evaluated'}, 'bootstrap_companions': {'count': 72, 'finding_ids': ['fig2-pattern-vc-brain_loss-bootstrap_mean', 'fig2-pattern-vc-brain_loss-percentile_2_5', 'fig2-pattern-vc-brain_loss-percentile_97_5', 'fig2-pattern-vc-content_loss-bootstrap_mean', 'fig2-pattern-vc-content_loss-percentile_2_5', 'fig2-pattern-vc-content_loss-percentile_97_5', 'fig2-pattern-v1-brain_loss-bootstrap_mean', 'fig2-pattern-v1-brain_loss-percentile_2_5', 'fig2-pattern-v1-brain_loss-percentile_97_5', 'fig2-pattern-v1-content_loss-bootstrap_mean', 'fig2-pattern-v1-content_loss-percentile_2_5', 'fig2-pattern-v1-content_loss-percentile_97_5', 'fig2-pattern-v2-brain_loss-bootstrap_mean', 'fig2-pattern-v2-brain_loss-percentile_2_5', 'fig2-pattern-v2-brain_loss-percentile_97_5', 'fig2-pattern-v2-content_loss-bootstrap_mean', 'fig2-pattern-v2-content_loss-percentile_2_5', 'fig2-pattern-v2-content_loss-percentile_97_5', 'fig2-pattern-v3-brain_loss-bootstrap_mean', 'fig2-pattern-v3-brain_loss-percentile_2_5', 'fig2-pattern-v3-brain_loss-percentile_97_5', 'fig2-pattern-v3-content_loss-bootstrap_mean', 'fig2-pattern-v3-content_loss-percentile_2_5', 'fig2-pattern-v3-content_loss-percentile_97_5', 'fig2-pattern-v4-brain_loss-bootstrap_mean', 'fig2-pattern-v4-brain_loss-percentile_2_5', 'fig2-pattern-v4-brain_loss-percentile_97_5', 'fig2-pattern-v4-content_loss-bootstrap_mean', 'fig2-pattern-v4-content_loss-percentile_2_5', 'fig2-pattern-v4-content_loss-percentile_97_5', 'fig2-pattern-hvc-brain_loss-bootstrap_mean', 'fig2-pattern-hvc-brain_loss-percentile_2_5', 'fig2-pattern-hvc-brain_loss-percentile_97_5', 'fig2-pattern-hvc-content_loss-bootstrap_mean', 'fig2-pattern-hvc-content_loss-percentile_2_5', 'fig2-pattern-hvc-content_loss-percentile_97_5', 'fig2-profile-vc-brain_loss-bootstrap_mean', 'fig2-profile-vc-brain_loss-percentile_2_5', 'fig2-profile-vc-brain_loss-percentile_97_5', 'fig2-profile-vc-content_loss-bootstrap_mean', 'fig2-profile-vc-content_loss-percentile_2_5', 'fig2-profile-vc-content_loss-percentile_97_5', 'fig2-profile-v1-brain_loss-bootstrap_mean', 'fig2-profile-v1-brain_loss-percentile_2_5', 'fig2-profile-v1-brain_loss-percentile_97_5', 'fig2-profile-v1-content_loss-bootstrap_mean', 'fig2-profile-v1-content_loss-percentile_2_5', 'fig2-profile-v1-content_loss-percentile_97_5', 'fig2-profile-v2-brain_loss-bootstrap_mean', 'fig2-profile-v2-brain_loss-percentile_2_5', 'fig2-profile-v2-brain_loss-percentile_97_5', 'fig2-profile-v2-content_loss-bootstrap_mean', 'fig2-profile-v2-content_loss-percentile_2_5', 'fig2-profile-v2-content_loss-percentile_97_5', 'fig2-profile-v3-brain_loss-bootstrap_mean', 'fig2-profile-v3-brain_loss-percentile_2_5', 'fig2-profile-v3-brain_loss-percentile_97_5', 'fig2-profile-v3-content_loss-bootstrap_mean', 'fig2-profile-v3-content_loss-percentile_2_5', 'fig2-profile-v3-content_loss-percentile_97_5', 'fig2-profile-v4-brain_loss-bootstrap_mean', 'fig2-profile-v4-brain_loss-percentile_2_5', 'fig2-profile-v4-brain_loss-percentile_97_5', 'fig2-profile-v4-content_loss-bootstrap_mean', 'fig2-profile-v4-content_loss-percentile_2_5', 'fig2-profile-v4-content_loss-percentile_97_5', 'fig2-profile-hvc-brain_loss-bootstrap_mean', 'fig2-profile-hvc-brain_loss-percentile_2_5', 'fig2-profile-hvc-brain_loss-percentile_97_5', 'fig2-profile-hvc-content_loss-bootstrap_mean', 'fig2-profile-hvc-content_loss-percentile_2_5', 'fig2-profile-hvc-content_loss-percentile_97_5'], 'values_status': 'unresolved', 'source_statistic': 'Author plot_figure.py: seed42 reset per ROI/method group; 1000 replicates of20 accepted nonself source-target draws; replicate mean and2.5/97.5 percentiles, preserving exact subject order and random generator.', 'role': 'required_source_outputs_not_independent_subject_uncertainty'}, 'decision_policy': {'combined_scalar': None, 'binary_threshold': None, 'partial_panel_win': False, 'inferential_rule': None, 'scientific_outcomes': 'unknown'}}
_OUTCOME_RATIONALE = 'No authentic frozen common-input/identity/evaluator/exposure/cumulative-budget manifests or submitted-analysis/granular-verification protocol exist for the complete original Figure2 condition. Published source values and code pointers alone cannot supply these identities; author-code delivery is not pinned. The complete original Figure 2 panel and published vector references are selected, but improvement still lacks qualified native comparison, a calibrated matching source method, meaningful effect and dependence-aware uncertainty; source values do not establish an exceed result.'
