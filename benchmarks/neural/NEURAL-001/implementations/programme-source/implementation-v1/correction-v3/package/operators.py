"""Concrete reference/assembly/full-panel grading composition after trusted gates.

These functions never establish actual execution authority. The source controller
must admit the exact full input/environment and independent method/process gates
before invoking them. Pure invented controls do not call scientific entrypoints.
"""
import numpy as np
from .protocol import PEOPLE, panels, require
from .reference.reference_engine import Epoch, train_reference, predict_reference
from .support import packets, uncertainty, score_core


def epoch_inputs(training, subject, family):
    """Join all admitted epoch identities/run roles/lengths, with no silent subset."""
    ids = tuple(training['interval_ids'].tolist())
    runs = tuple(training['run_ids'].tolist())
    offsets = training['offsets']
    require(ids == subject.epoch_ids and runs == subject.epoch_runs, 'exact original epoch/run join')
    require(tuple(int(b-a) for a,b in zip(offsets,offsets[1:])) == subject.epoch_lengths,
            'exact native-retained epoch lengths required')
    require(len(offsets) == len(ids)+1 and offsets[0] == 0
            and offsets[-1] == len(training['envelope']), 'complete calibration support')
    rows = []
    for ident, run, a, b in zip(ids, runs, offsets, offsets[1:]):
        meg = None if family == 'R0' else training['meg'][a:b]
        rows.append(Epoch(run, ident, meg, training['envelope'][a:b]))
    return tuple(rows)


def reference_training(training, subject, family, channel_kinds, progress):
    """Dispatch actual complete person reference; not called by engineering tests."""
    epochs = epoch_inputs(training, subject, family)
    return train_reference(subject.public_alias, epochs, subject.run_ids,
                           subject.epoch_ids, subject.epoch_runs, subject.epoch_lengths,
                           tuple(channel_kinds), family, stage='person_training', progress=progress)


def reference_prediction(state, already_transformed_query, progress):
    # Support owns the one-and-only shift. No target/sample trimming or state update.
    view=already_transformed_query
    if state.family=='R0':
        # The pure engine admits its stored sensor-schema provenance before its
        # R0 branch. Supply that constant operator metadata locally; never read
        # or add MEG, nor change the public no-neural view.
        view=dict(view,channel_kinds=state.channel_kinds)
    return predict_reference(state, view, progress=progress)


def assemble(predictions_by_opaque_id, subject):
    return packets.assemble_person(predictions_by_opaque_id, subject.support())


def comparisons():
    rows = [('adaptive_minus_frozen', 'candidate/adaptive_case/neural',
             'candidate/frozen_program/neural')]
    for mode in ('frozen_program', 'adaptive_case'):
        actual = f'candidate/{mode}/neural'
        for family in ('R1', 'R2'):
            rows.append((f'{mode}_minus_{family}', actual, f'reference/{family}/neural'))
        rows.append((f'{mode}_neural_minus_prior', actual, f'candidate/{mode}/no_neural'))
        rows.append((f'{mode}_neural_minus_shift', actual, f'candidate/{mode}/within_query_half_shift'))
    return rows


def grade_all(submissions_by_panel, subjects, target_loader, group_loader, *, progress):
    """All264 submissions validate before the FIRST target or private group load.

    A caller must reserve complete target/uncertainty costs beforehand. Target and
    group loaders are trusted protected-store capabilities, not candidate callbacks.
    Their actual identities/custody are separately authenticated by deployment.
    """
    require(set(submissions_by_panel) == set(panels()), 'all11 independent panels required')
    manifest = [s.support() for s in subjects]
    require(tuple(s.canonical_id for s in subjects) == PEOPLE, 'all24 canonical people required')
    predictions = {}
    for panel in panels():
        progress({'operation': 'validate_panel', 'panel': panel, 'target_reads': 0})
        predictions[panel] = packets.validate_all_submissions(submissions_by_panel[panel], manifest)
    # No target or identity body can be read above this line.
    targets = {}
    for s in subjects:
        progress({'operation': 'load_protected_target', 'person': s.canonical_id})
        value = target_loader(s.canonical_id)
        require(type(value) is np.ndarray and value.dtype == np.dtype('<f8')
                and value.shape == (sum(s.query_lengths),) and np.isfinite(value).all(),
                'complete finite protected target vector required')
        offsets = s.support()['query_offsets']
        require(all(not np.all(value[a:b] == value[a]) for a,b in zip(offsets, offsets[1:])),
                'constant target invalidates complete operator packet')
        targets[s.canonical_id] = value
    progress({'operation': 'load_protected_groups', 'target_packets': 24})
    groups = group_loader()
    scores = {}
    z = {}
    offsets = {s.canonical_id: s.support()['query_offsets'] for s in subjects}
    ids = {s.canonical_id: list(s.query_ids) for s in subjects}
    for panel in panels():
        progress({'operation': 'score_complete_panel', 'panel': panel})
        scores[panel] = score_core.score_people(predictions[panel], targets, offsets, ids)
        z[panel] = np.asarray([[r['fisher_z_spearman']
                               for r in scores[panel]['persons'][s.canonical_id]['per_sentence']]
                              for s in subjects], dtype='<f8')
    progress({'operation': 'paired_uncertainty', 'draws': 10000})
    intervals = uncertainty.paired_uncertainty(z, groups, [(a, b) for _, a, b in comparisons()])
    return {'task_id': 'NEURAL-001', 'panels': scores, 'uncertainty': intervals,
            'comparison_estimand': 'combined_training_and_case_investigation',
            'half_shift_interpretation': {'kind':'disclosed_transform_robustness',
                'inversion_or_realignment_allowed':True,
                'evidence_of_absent_alignment_or_neural_information':False,
                'causal_or_alignment_null_control':False,
                'reference_panels':'fixed reference without automatic realignment; descriptive sensitivity'},
            'neural_information_comparison':'matched neural versus no_neural with all original limitations',
            'all264_validated_before_targets': True,
            'status': 'protected_provisional_report_pending_outer_natural_zero',
            'scientific_qualification': False, 'submission_ready': False}
