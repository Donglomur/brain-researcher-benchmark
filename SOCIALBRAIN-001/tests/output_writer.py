"""Serialize source-derived SOCIALBRAIN artifacts without import-time I/O."""
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat

import numpy as np

FILES = ('signal_evidence.npz', 'network_connectivity.csv', 'age_effects.json',
         'run_metadata.json', 'findings.md')


def fresh_output(value, protected=()):
    raw = os.fspath(value)
    if not isinstance(raw, str) or not raw.startswith('/') or '\0' in raw \
            or any(x in ('.', '..') for x in raw.split('/')):
        raise ValueError('absolute_output_without_traversal_required')
    output = Path(raw)
    for node in (*reversed(output.parents), output):
        if os.path.lexists(node):
            if not stat.S_ISDIR(node.lstat().st_mode):
                raise ValueError('output_symlink_or_nondirectory')
    for item in (*protected, Path(__file__).absolute().parent):
        item = Path(item).absolute()
        if output == item or output in item.parents or item in output.parents:
            raise ValueError('output_protected_overlap')
    if output.exists():
        if any(output.iterdir()):
            raise ValueError('fresh_or_empty_output_required')
    else:
        if not output.parent.is_dir():
            raise ValueError('output_parent_required')
        output.mkdir()
    return output


def json_write(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def write_artifacts(reference, output, kernel, *, protected=()):
    """One accepted-clean replay; no CSV/JSON roundtrip into scientific inputs."""
    directory = fresh_output(output, protected)
    try:
        if reference.get('status') != 'complete':
            raise ValueError('complete_reference_required')
        ids = list(reference['subject_ids'])
        if ids != [f'sub-pixar{i:03d}' for i in range(1, 156)]:
            raise ValueError('fixed_cohort_required')
        persons = reference['persons']
        clean = {sid: persons[sid]['cleaned_roi'] for sid in ids}
        active = {sid: persons[sid]['canonical_active'] for sid in ids}
        result = kernel.analyze(clean, clean, active, reference['covariates'], ids)
        lengths = [len(persons[sid]['frame_indices']) for sid in ids]
        with (directory / FILES[0]).open('xb') as stream:
            np.savez_compressed(stream, subject_ids=np.asarray(ids),
                roi_ids=np.asarray(reference['roi_ids']), pipeline_ids=np.asarray(reference['pipeline_ids']),
                frame_subject_ids=np.concatenate([np.repeat(sid, length) for sid, length in zip(ids, lengths)]),
                frame_indices=np.concatenate([persons[sid]['frame_indices'] for sid in ids]),
                raw_roi=np.concatenate([persons[sid]['raw_roi'] for sid in ids]),
                global_signal=np.concatenate([persons[sid]['global_signal'] for sid in ids]),
                cleaned_roi=np.concatenate([clean[sid] for sid in ids]),
                canonical_active=np.stack([active[sid] for sid in ids]))
        columns = ['subject_id', 'age', 'group', 'mean_fd', *kernel.METRICS,
                   *(metric + '_status' for metric in kernel.METRICS)]
        with (directory / FILES[1]).open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader(); writer.writerows(result['participant_rows'])
        pins = reference['pins']
        shared = {key: pins[key] for key in
                  ('source_manifest_sha256', 'method_sha256', 'output_schema_sha256')}
        effects = dict(result['age_effects'], schema_version='socialbrain-results-v2',
                       task_id='SOCIALBRAIN-001', status='complete', **shared)
        json_write(directory / FILES[2], effects)
        observed = dict(reference['analysis_observed'])
        observed.update(result['analysis_observed'])
        software = {key: importlib.metadata.version(distribution) for key, distribution in
                    [('numpy', 'numpy'), ('scipy', 'scipy'), ('nibabel', 'nibabel'),
                     ('nilearn', 'nilearn'), ('scikit_learn', 'scikit-learn')]}
        software['python'] = platform.python_version()
        metadata = dict(schema_version='socialbrain-metadata-v2', task_id='SOCIALBRAIN-001',
            dataset_id='ds000228', status='complete', **shared,
            reporting_kernel_sha256=pins['reporting_kernel_sha256'],
            analysis_scope='Cross-sectional shared-movie ToM/pain GSR and motion sensitivity adaptation',
            cohort=reference['cohort'], roi_definitions=reference['roi_definitions'],
            source_files=reference['source_files'], source_observed=reference['source_observed'],
            analysis_observed=observed, software_versions=software, warnings=[])
        json_write(directory / FILES[3], metadata)
        lines = ['# ToM/pain connectivity sensitivity', '',
            'All 155 released participants are retained: 122 children and 33 adults. '
            'Network measurements are signed fixed-edge Fisher summaries; adult means '
            'weight participants equally. Child associations use their own unrounded '
            'measurements, with separate motion-rank-adjusted estimates.', '']
        for metric in kernel.METRICS:
            value = effects[metric]
            lines.append(f"{metric}: child r={value['r']}, p={value['p']} ({value['status']}); "
                         f"motion-adjusted r={value['motion_adjusted_rank_r']}, "
                         f"p={value['motion_adjusted_rank_p']} ({value['motion_adjusted_rank_status']}); "
                         f"adult mean={effects['adult_means'][metric]}.")
        lines.extend(['', 'This is a Richardson-derived public-data sensitivity application, '
            'not an exact reproduction of the paper’s primary-motor/artifact-adjusted pipeline. '
            'Cross-sectional age associations are not within-person developmental changes. '
            'Shared movie input, motion and preprocessing remain interpretive limits. '
            'GSR sensitivity alone establishes neither artifact removal nor neural specificity. '
            'Undefined endpoints retain all participant slots with explicit support and null status. '
            'No effect sign, significance, attenuation or model difficulty was required.'])
        with (directory / FILES[4]).open('x', encoding='utf-8') as stream:
            stream.write('\n'.join(lines) + '\n')
        if os.path.lexists(directory / 'failure_report.json'):
            raise ValueError('authoritative_failure_marker')
        return effects
    except BaseException as exc:
        marker = directory / 'failure_report.json'
        if not os.path.lexists(marker):
            json_write(marker, {'status': 'failed_precondition', 'error_type': type(exc).__name__,
                                'reason': 'artifact_serialization_failed'})
        raise
