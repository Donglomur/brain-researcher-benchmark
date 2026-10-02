"""Source-only GRADIENT oracle. Import-safe, offline, complete keyed evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import time
import warnings

import numpy as np

import core
import source_reader as source

require = core.require


def disjoint(left, right):
    return left != right and left not in right.parents and right not in left.parents


def prepare_destinations(output, private, report, protected):
    output = source.safe_path(output)
    private = source.safe_path(private) if private else None
    report = source.safe_path(report) if report else None
    targets = [v for v in (output, private, report) if v is not None]
    for i, target in enumerate(targets):
        require(not os.path.lexists(target), 'fresh destination required')
        require(all(disjoint(target, source.safe_path(p)) for p in protected), 'destination overlaps protected input')
        require(all(disjoint(target, other) for other in targets[i + 1:]), 'output/private/report overlap')
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    if private:
        private.mkdir()
    return output, private, report


def write_json(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def write_csv(path, rows):
    require(bool(rows), 'nonempty complete public table')
    keys = list(rows[0])
    require(all(set(row) == set(keys) for row in rows), 'consistent table fields')
    with path.open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_npz(path, arrays):
    require(all(np.asarray(value).dtype.kind != 'O' for value in arrays.values()), 'no object arrays')
    with path.open('xb') as handle:
        np.savez_compressed(handle, **arrays)


def finite_or_null(value):
    return float(value) if np.isfinite(value) else None


def quantity_status(embedding):
    if not embedding['embedding_valid']:
        return 'source_incomplete' if not embedding['operator_valid'] else 'multiscale_singular'
    return embedding['principal_status']


def analyze(ids, persons, labels, configurations):
    n = len(ids)
    require(n == 20 and len(persons) == n and len(labels) == 400, 'complete20x400 analysis')
    parcel_ids = np.array([r['parcel_id'] for r in labels], dtype=np.int64)
    networks = np.array([r['network'] for r in labels])
    require(list(parcel_ids) == list(range(1, 401)), 'canonical source parcel order')
    arrays = dict(participant_ids=np.array(ids), source_positions=np.arange(n, dtype=np.int64),
                  frame_indices=np.arange(core.N_FRAMES, dtype=np.int64), parcel_ids=parcel_ids,
                  arm_ids=np.array(['nobp', 'bp']), configuration_ids=np.array(core.CONFIGS))
    for key in ('raw_means', 'geometry_valid', 'raw_sample_sd', 'cleaned_series',
                'clean_centered_l2', 'activity_threshold', 'person_parcel_active', 'fc'):
        arrays[key] = np.stack([person[key] for person in persons])
    membership = np.zeros((4, n), dtype=bool)
    config_fcs, config_active, config_defined = [], [], []
    for k, config in enumerate(configurations):
        require(config['id'] == core.CONFIGS[k], 'public configuration order')
        positions = config['positions']
        membership[k, positions] = True
        arm = int(config['bandpass'])
        fc, active = core.mean_fc(arrays['fc'][positions, arm], arrays['person_parcel_active'][positions, arm])
        config_fcs.append(fc)
        config_active.append(active)
        config_defined.append(int(np.all(arrays['person_parcel_active'][positions, arm], axis=1).sum()))
    arrays.update(configuration_membership=membership, configuration_fc=np.stack(config_fcs),
                  configuration_parcel_active=np.stack(config_active))
    embeddings = [core.embedding(arrays['fc'][i, 0], parcel_ids) for i in range(n)]
    embeddings += [core.embedding(fc, parcel_ids) for fc in config_fcs]
    arrays['embedding_ids'] = np.array(['subject:' + pid for pid in ids] +
                                      ['configuration:' + name for name in core.CONFIGS])
    for key in ('operator_valid', 'embedding_valid', 'principal_valid', 'retained_span_valid',
                'eigenvalues', 'eigenvectors', 'raw_diffusion'):
        arrays[key] = np.array([e[key] for e in embeddings])
    reference = embeddings[n]
    gpa = None
    if all(e['retained_span_valid'] for e in embeddings[:n]) and reference['retained_span_valid']:
        gpa = core.align(arrays['raw_diffusion'][:n], reference['raw_diffusion'])
        arrays.update({k: np.asarray(v) for k, v in gpa.items() if k != 'termination'})
        gpa_status = dict(status='ok', n_iterations=gpa['gpa_n_iterations'], termination=gpa['termination'])
    else:
        arrays.update(gpa_n_iterations=np.array(0, dtype=np.int64),
                      gpa_rotations=np.empty((0, n, 10, 10)), gpa_reference_history=np.empty((0, 400, 10)),
                      gpa_distances=np.empty(0), aligned_gradients=np.full((n, 400, 10), np.nan))
        gpa_status = dict(status='alignment_undefined', n_iterations=0, termination='undefined')
    quantities = []
    for e in embeddings[n:]:
        quantities.append(core.display(e['raw_diffusion'], networks, e['principal_valid'], e['plane_valid']))
    aligned_mean = (np.mean(arrays['aligned_gradients'], axis=0, dtype=np.float64) if gpa else
                    np.full((400, 10), np.nan))
    quantities.append(core.display(aligned_mean, networks, bool(gpa and reference['principal_valid']),
                                   bool(gpa and reference['plane_valid']), orient_all=True))
    arrays.update(quantity_ids=np.array(list(core.CONFIGS) + ['aligned_mean']),
                  display_signs=np.stack([q['signs'] for q in quantities]),
                  display_coordinates=np.stack([q['coordinates'] for q in quantities]),
                  display_valid=np.stack([q['valid'] for q in quantities]))
    pairs, correlations, valid = core.pair_consistency(ids, embeddings[:n], gpa, reference['principal_valid'])
    arrays.update(pair_participant_ids=pairs, signed_pair_consistency=correlations,
                  pair_consistency_valid=valid)
    aggregates = [core.complete_mean([float(v) if okay else None for v, okay in
                                     zip(correlations[:, a], valid[:, a])]) for a in range(2)]
    subjects = []
    for i, (pid, e) in enumerate(zip(ids, embeddings)):
        own_pairs = np.any(pairs == pid, axis=1)
        own = [core.complete_mean([float(v) if okay else None for v, okay in
                                  zip(correlations[own_pairs, a], valid[own_pairs, a])]) for a in range(2)]
        subjects.append(dict(participant_id=pid, embedding_status=e['embedding_status'],
                             principal_status=e['principal_status'], retained_span_status=e['retained_span_status'],
                             unaligned_signed=own[0]['value'], aligned_signed=own[1]['value'],
                             n_partners_expected=n - 1, unaligned_n_defined=own[0]['n_defined'],
                             aligned_n_defined=own[1]['n_defined'], nuisance_rank=persons[i]['nuisance_rank'],
                             raw_principal_gap=e['principal_gap'], retained_boundary_gap=e['retained_boundary_gap']))
    rows, summaries = [], []
    for k, (name, q) in enumerate(zip(list(core.CONFIGS) + ['aligned_mean'], quantities)):
        e = embeddings[n + k] if k < 4 else reference
        status = quantity_status(e) if k < 4 or gpa else 'alignment_undefined'
        if status == 'ok' and q['constant_g1']:
            status = 'constant_coordinate'
        if not q['valid'][:2].all() and not e['plane_valid']:
            q['between_within_status'] = ('alignment_undefined' if k == 4 and not gpa else
                                         'source_incomplete' if not e['operator_valid'] else
                                         'multiscale_singular' if not e['embedding_valid'] else 'plane_degenerate')
        if k == 4 and not gpa:
            q['between_within_status'] = 'alignment_undefined'
        expected = int(membership[k].sum()) if k < 4 else n
        defined = config_defined[k] if k < 4 else n if gpa else 0
        for j, network in enumerate(core.NETWORKS):
            row = dict(quantity=name, network=network, n_subjects_expected=expected,
                       n_subjects_defined=defined, n_parcels=int((networks == network).sum()), status=status)
            row.update({'mean_g' + str(c + 1): finite_or_null(q['means'][j, c]) for c in range(10)})
            row.update(apex_network=q['apex_network'], bottom_network=q['bottom_network'],
                       between_within=q['between_within'], between_within_status=q['between_within_status'],
                       principal_gap=e['principal_gap'], retained_boundary_gap=e['retained_boundary_gap'])
            rows.append(row)
        if k < 4:
            summaries.append(dict(config=name, subject_ids=[pid for i, pid in enumerate(ids) if membership[k, i]],
                                  bandpass=configurations[k]['bandpass'], embedding_status=e['embedding_status'],
                                  principal_status=e['principal_status'], retained_span_status=e['retained_span_status'],
                                  apex_network=q['apex_network'], bottom_network=q['bottom_network'],
                                  between_within=q['between_within'], between_within_status=q['between_within_status'],
                                  principal_gap=e['principal_gap'], retained_boundary_gap=e['retained_boundary_gap']))
        else:
            aligned_summary = dict(quantity=name, status=status, n_subjects_expected=n, n_subjects_defined=defined,
                                   apex_network=q['apex_network'], bottom_network=q['bottom_network'],
                                   between_within=q['between_within'], between_within_status=q['between_within_status'],
                                   principal_gap=e['principal_gap'], retained_boundary_gap=e['retained_boundary_gap'])
    apexes = [q['apex_network'] for q in quantities[:4]]
    robust = len(set(apexes)) == 1 if all(v is not None for v in apexes) else None
    results = dict(schema_version='gradient-results-v2', status='ok', n_subjects=n, n_parcels=400,
                   n_components=10, n_frames=168, unaligned_signed=aggregates[0], aligned_signed=aggregates[1],
                   configuration_summaries=summaries, aligned_mean_summary=aligned_summary,
                   principal_gradient_identity_robust=robust,
                   robustness_status='ok' if robust is not None else 'incomplete_configuration_support',
                   apex_networks_observed=[name for name in core.NETWORKS if name in apexes],
                   gpa=gpa_status, claim_scope='descriptive method control')
    return arrays, subjects, rows, results


def software_versions():
    versions = {'python': platform.python_version()}
    for name in ('numpy', 'scipy', 'nibabel'):
        versions[name] = importlib.metadata.version(name)
    versions.update(nilearn='not_used', brainspace='not_used')
    return versions


def public_header(header, atlas=False):
    keys = ('shape', 'affine', 'source_dtype', 'spatial_units',
            'effective_scaling_slope', 'effective_scaling_intercept')
    if not atlas:
        keys += ('temporal_units', 'raw_TR', 'raw_toffset')
    return {key: header[key] for key in keys}


def run(args):
    started = time.monotonic()
    code = source.safe_path(Path(__file__).absolute().parent)
    task = code.parent
    protected = [args.data_dir, args.contract_path, args.schema_path, code]
    if (task / 'task.toml').is_file():
        protected.append(task)
    output, private, report = prepare_destinations(args.output_dir, args.private_dir, args.report, protected)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            inputs = source.authenticate(args.data_dir, args.contract_path, args.schema_path)
            common = source.load_common(inputs)
            ids = inputs['method']['source']['participant_ids']
            persons = [source.load_person(inputs, common, pid) for pid in ids]
            arrays, subject_rows, configuration_rows, results = analyze(ids, persons, common['labels'],
                                                                       inputs['method']['configurations'])
        observed = dict(participant_ids=ids, source_order=ids, participant_column_names=common['participant_columns'],
                        confound_column_names={pid: p['confound_columns'] for pid, p in zip(ids, persons)},
                        headers={pid: public_header(p['header']) for pid, p in zip(ids, persons)},
                        atlas_header=public_header(common['atlas_header'], atlas=True),
                        atlas_labels=[{k: row[k] for k in ('parcel_id', 'label', 'network')} for row in common['labels']],
                        voxel_support_by_subject={pid: p['support_metadata'] for pid, p in zip(ids, persons)},
                        frame_alignment='released_frame_index_only_no_measured_movie_onset',
                        raw_clock_metadata={pid: {k: p['header'][k] for k in
                                                  ('raw_TR', 'raw_toffset', 'temporal_units')}
                                            for pid, p in zip(ids, persons)},
                        effective_TR_s=2, effective_origin_s=0)
        metadata = dict(schema_version='gradient-metadata-v2', status='ok', task_id='GRADIENT-001',
                        **inputs['identity'],
                        source_files=[{k: r.get(k) for k in ('path', 'role', 'participant_id', 'size_bytes', 'sha256')}
                                      for r in inputs['manifest']['files']],
                        source_observed=observed, software_versions=software_versions(),
                        numerical_method_amendments=(
                            'symmetric diffusion operator; largest-algebraic nontrivial modes instead of largest magnitude; '
                            'exact40 signedrowretention; explicit float64 source means; public raw-scale nuisance-residual activity guard'),
                        warnings=[{'category': w.category.__name__, 'message': str(w.message)} for w in caught])
        write_csv(output / 'cohort.csv', [p['cohort'] for p in persons])
        write_csv(output / 'parcels.csv', [r for p in persons for r in p['parcel_rows']])
        write_npz(output / 'gradient_arrays.npz', arrays)
        write_csv(output / 'configurations.csv', configuration_rows)
        write_csv(output / 'per_subject.csv', subject_rows)
        write_json(output / 'results.json', results)
        write_json(output / 'run_metadata.json', metadata)
        lines = ['# Fixed-cohort connectivity gradients', '',
                 'Four predeclared configurations; no required stable/fragile result.',
                 'Raw signed pair mean: ' + str(results['unaligned_signed']['value']) +
                 '; aligned signed pair mean: ' + str(results['aligned_signed']['value']) + '.',
                 'Apex agreement across four defined configurations: ' + str(results['principal_gradient_identity_robust']) + '.']
        for row in results['configuration_summaries']:
            lines.append(row['config'] + ': apex=' + str(row['apex_network']) + ', status=' + row['principal_status'] + '.')
        lines += ['', 'These are descriptive measurements of fixed movie data and an operational cross-template mask transfer.',
                  'The age-confounded ordered halves are not independent replication; no adult-HCP paper, population, causal or difficulty claim.',
                  'Canonical source inputs and spectral/GPA certificates define computation; near-tie endpoint stability is not guaranteed.']
        with (output / 'findings.md').open('x', encoding='utf-8') as handle:
            handle.write('\n'.join(lines) + '\n')
        require({p.name for p in output.iterdir()} == set(inputs['schema']['files']), 'complete eight artifacts')
        if private:
            extras = {}
            for i, person in enumerate(persons):
                extras['confounds_' + str(i)] = person['original_confounds']
                extras['voxel_offsets_' + str(i)] = np.concatenate(([0], np.cumsum([len(x) for x in person['support_indices']])))
                extras['voxel_indices_' + str(i)] = np.concatenate(person['support_indices'])
            write_npz(private / 'source_receipts.npz', extras)
        receipt = dict(status='ok', elapsed_seconds=time.monotonic() - started, n_subjects=len(ids),
                       n_frames=168, n_parcels=400, n_operators=int(arrays['operator_valid'].sum()),
                       n_embeddings=int(arrays['embedding_valid'].sum()), gpa=results['gpa'], warnings=metadata['warnings'],
                       **inputs['identity'],
                       output_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())})
        if report:
            write_json(report, receipt)
        print(json.dumps(receipt, sort_keys=True, allow_nan=False))
        return receipt
    except Exception as exc:
        failure = dict(status='failed_precondition', reason=type(exc).__name__ + ': ' + str(exc),
                       elapsed_seconds=time.monotonic() - started)
        write_json(output / 'failure_report.json', failure)
        if report and not os.path.lexists(report):
            write_json(report, failure)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=os.environ.get('DATA_DIR', '/app/data/gradient'))
    parser.add_argument('--contract-path', default=os.environ.get('METHOD_CONTRACT', '/app/method_contract.json'))
    parser.add_argument('--schema-path', default=os.environ.get('OUTPUT_SCHEMA', '/app/output_schema.json'))
    parser.add_argument('--output-dir', default=os.environ.get('OUTPUT_DIR', '/app/output'))
    parser.add_argument('--private-dir')
    parser.add_argument('--report')
    parser.add_argument('--print-contract', action='store_true')
    args = parser.parse_args()
    if args.print_contract:
        print(source.stable_bytes(args.contract_path, 1024 * 1024).decode('utf-8'), end='')
    else:
        run(args)


if __name__ == '__main__':
    main()
