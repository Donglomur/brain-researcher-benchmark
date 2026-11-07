#!/usr/bin/env python3
"""Join bounded source audits without changing candidate or execution status."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/neuroscience-benchmarks/build'
AUDITS = ROOT / 'authoring/neural-source-audits'


def read(p):
    return json.loads(p.read_text())


def pin(p):
    return {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}


SOURCES = {
    'boldmoments-v1': ('BOLDMoments', 'Choose main-paper A versus revised B processing; resolve stimulus rights and a bounded input representation.'),
    'narratives-v1': ('Narratives', 'Reconcile derivative identities, participant membership and story/scanner clock before linguistic modeling.'),
    'ibc-v1': ('Individual Brain Charting', 'Freeze the map release and person/task split; the inspected classifier does not enforce person holdout.'),
    'generic-object-decoding-v1': ('Generic Object Decoding', 'Separate private category aggregation from prediction; resolve preprocessing version, legacy scorer and feature exposure.'),
    'eegmoments-v1': ('EEGMoments', 'Resolve raw-preprocessing defect versus published derivatives and target-dependent normalization; join eye/EEG trials explicitly.'),
    'openbmi-v1': ('OpenBMI', 'Revise cue-independent imagery/covert-attention claims; pin actual file identities and calibrated/native split contracts.'),
    'microns-v1': ('MICrONS', 'A separate BossDB v1 pickle route matches the older paper code; the later Feather route remains unresolved. Raw-neural tasks still need a version-consistent structural/functional bridge and eligible pair universe; cleft volume is not physiological strength.'),
    'libribrain-v1': ('LibriBrain', 'Choose phoneme versus word edition and verify reduced-file loader coverage, timing and adaptation policy.'),
    'allen-visual-coding-v1': ('Allen Visual Coding Neuropixels', 'Separate new-stimulus prediction in calibrated units from new-mouse prediction; resolve covariates and distribution terms.'),
    'dmfc-v1': ('DMFC Ready–Set–Go', 'Training metadata inspection completed: two early Go responses block the predeclared Set+200 ms policy, and ts/tp semantics remain unresolved. The exact 800 ms prior overlap occurs in all 12 recorded groups; no spike values, model or scientific reference was evaluated.'),
    'cogitate-v1': ('COGITATE', 'Resolve access and a category-hidden prediction interface; true-label pseudo-trial averages are not a matched single-trial predictor.'),
    'garcia-v1': ('Garcia auditory pathways', 'Bridge released NWBs to source timing/laminar definitions; available MATLAB scripts do not implement the full response analysis.'),
}


def main():
    roster_path = OUT / 'neural_100.json'
    roster = read(roster_path)['tasks']
    legacy_path = OUT / 'discovery_audit_four.json'
    legacy = read(legacy_path)
    entries = []
    pins = {str(p.relative_to(ROOT)): pin(p) for p in (
        roster_path, legacy_path, OUT / 'DISCOVERY_AUDIT_FOUR.md', Path(__file__).resolve())}
    for row in legacy['collections']:
        entries.append({
            'source_id': row['source_id'], 'name': row['name'],
            'assignment_ids': row['assignment_ids'], 'checked_on': legacy['checked_on'],
            'audit_path': str(legacy_path.relative_to(ROOT)),
            'narrative_path': 'docs/neuroscience-benchmarks/build/DISCOVERY_AUDIT_FOUR.md',
            'audit_scope': row['audit_conclusion'], 'remaining_gates': row['remaining_gates'],
            'roster_status_changed': False, 'reference_executed': False, 'scientific_admission': False,
        })
    byte_total = attempts = 0
    request_seconds = 0.0
    for folder, (name, implication) in SOURCES.items():
        base = AUDITS / folder
        path = base / 'audit.json'
        audit = read(path)
        sid = audit.get('source_id', audit.get('source'))
        ids = sorted(r['id'] for r in roster if sid in r['source_ids'])
        if len(ids) != 2:
            raise ValueError(f'Unexpected assignment mapping for {sid}: {ids}')
        declared = audit.get('assignment_ids', audit.get('task_ids', audit.get('roster_ids')))
        if declared is not None and sorted(declared) != ids:
            raise ValueError(f'Audit/roster task mismatch: {sid}')
        # Preserve actual filename case even on a case-insensitive authoring host.
        report = next(p for p in base.iterdir() if p.name.casefold() == 'audit.md')
        receipt = audit.get('resource_accounting', audit.get('resource_scope', audit.get('receipt')))
        if isinstance(receipt, str):
            receipt = read(base / receipt)
        bytes_read = receipt.get('direct_consumed_body_bytes', receipt.get('response_payload_bytes', receipt.get('response_body_bytes')))
        n = receipt.get('request_attempts', receipt.get('attempts', receipt.get('requests')))
        seconds = receipt.get('direct_request_wall_seconds_sum', receipt.get('request_wall_seconds_sum', receipt.get('request_wall_seconds')))
        if not isinstance(bytes_read, int) or bytes_read > 2_000_000:
            raise ValueError(f'Missing/excess source byte receipt: {sid}')
        byte_total += bytes_read
        attempts += n
        request_seconds += seconds
        gates = next((audit[k] for k in ('remaining_gates', 'next_gates', 'gates', 'next_gate', 'next_actions') if k in audit), None)
        if gates is None:
            raise ValueError(f'No next gates: {sid}')
        for p in (path, report, *[p for p in (base / 'FREEZE.json', base / 'evidence_freeze.json', base / 'payload_pins.json', base / 'receipt.json', base / 'transfer_ledger.json') if p.exists()]):
            pins[str(p.relative_to(ROOT))] = pin(p)
        entries.append({
            'source_id': sid, 'name': name, 'assignment_ids': ids,
            'checked_on': '2026-10-30', 'audit_path': str(path.relative_to(ROOT)),
            'narrative_path': str(report.relative_to(ROOT)),
            'audit_scope': 'Source, archive metadata and code inspection only; no recording or model payload and no scientific execution.',
            'construction_implication': implication, 'remaining_gates': gates,
            'explicit_response_body_bytes': bytes_read, 'request_attempts': n,
            'request_wall_seconds_sum': seconds, 'independent_source_cap_bytes': 2_000_000,
            'roster_status_changed': False, 'reference_executed': False, 'scientific_admission': False,
        })
        if folder == 'microns-v1':
            route_path = ROOT / 'authoring/paper-construction-audit/microns-route-reconciliation.json'
            route = read(route_path)
            if (route['paper']['id'] != 'PAPER-FIND-020'
                    or route['relationship']['catalog_source_id'] != sid
                    or sorted(route['relationship']['neural_task_ids']) != ids):
                raise ValueError('MICrONS reconciliation identity mismatch')
            # Pin the reconciliation and recheck its exact saved evidence. Do not
            # replace the immutable original audit or treat HEAD as payload proof.
            pins[str(route_path.relative_to(ROOT))] = pin(route_path)
            for item in route['evidence_pins']:
                observed = pin(ROOT / item['path'])
                if observed != {k: item[k] for k in ('bytes', 'sha256')}:
                    raise ValueError(f"Stale MICrONS reconciliation evidence: {item['path']}")
                pins[item['path']] = observed
            entries[-1]['route_reconciliation'] = {
                'path': str(route_path.relative_to(ROOT)),
                'paper_id': route['paper']['id'],
                'conclusion': route['conclusion'],
                'pickle_source_commit': route['older_source_route']['commit'],
                'feather_source_commit': route['later_source_route']['commit'],
                'observed_pickle_head_bytes': route['older_source_route']['combined_head_length_bytes'],
                'payload_checksum_or_schema_qualified': False,
                'raw_neural_input_bridge_qualified': False,
                'original_audit_and_gates_preserved': True,
                'remaining_route_gates': route['remaining_gates'],
            }
        if folder == 'dmfc-v1':
            summary_path = ROOT / 'authoring/dmfc-timing/schema-v2/RESULT_SUMMARY.json'
            review_path = ROOT / 'authoring/dmfc-timing/schema-v2-review-v1/audit.json'
            execution_path = ROOT / 'authoring/dmfc-timing/schema-v2-review-v1/execution.json'
            summary, review, execution = read(summary_path), read(review_path), read(execution_path)
            if (sorted(summary['candidate_ids']) != ids
                    or summary['primary_cutoff_ms'] != 200
                    or summary['early_response_count'] != 2
                    or summary['cutoff_substituted'] is not False
                    or summary['trials_excluded_to_rescue'] is not False
                    or summary['spike_values_decoded'] is not False
                    or summary['test_asset_accessed'] is not False
                    or summary['models_run'] != 0
                    or summary['reference_executed'] is not False
                    or summary['common_recorded_prior_interval_ms'] != 800
                    or review['findings']['support_groups'] != 12
                    or review['status'] != 'saved_metadata_audit_passed'
                    or execution['returncode'] != 0
                    or review['independent_empirical_recomputation'] is not False):
                raise ValueError('DMFC saved follow-up evidence changed; review the overlay')
            followup_paths = [summary_path, review_path, execution_path,
                ROOT / 'authoring/dmfc-timing/schema-v2/RESULTS.md',
                ROOT / 'authoring/dmfc-timing/schema-v2-review-v1/RESULTS.md']
            for p in followup_paths:
                pins[str(p.relative_to(ROOT))] = pin(p)
            for source_path, expected_pin in summary['pins'].items():
                observed_pin = pin(ROOT / source_path)
                if observed_pin != expected_pin:
                    raise ValueError(f'Stale DMFC summary evidence: {source_path}')
                pins[source_path] = observed_pin
            entries[-1]['input_metadata_followup'] = {
                'summary_path': str(summary_path.relative_to(ROOT)),
                'narrative_path': 'authoring/dmfc-timing/schema-v2/RESULTS.md',
                'independent_saved_metadata_review': str(review_path.relative_to(ROOT)),
                'review_execution_receipt': str(execution_path.relative_to(ROOT)),
                'status': summary['status'],
                'metadata_inspection_executed': True,
                'training_asset_bytes_acquired_in_separate_intake': summary['training_asset_bytes'],
                'training_asset_sha256': summary['training_asset_sha256'],
                'trial_count': summary['trial_count'],
                'split_counts': summary['split_counts'],
                'primary_cutoff_ms': summary['primary_cutoff_ms'],
                'primary_feasibility_status': summary['primary_feasibility_status'],
                'early_response_count': summary['early_response_count'],
                'cutoff_substituted': False, 'trials_excluded_to_rescue': False,
                'ts_tp_semantics_resolved': False,
                'tp_min_ms': summary['tp_min_ms'],
                'max_tp_event_residual_ms': summary['max_tp_event_residual_ms'],
                'shared_recorded_prior_interval_ms': summary['common_recorded_prior_interval_ms'],
                'support_groups': review['findings']['support_groups'],
                'common_support_counts_before_eligibility': summary['common_support_counts_before_eligibility'],
                'common_support_is_qualified_scientific_contrast': False,
                'spike_values_decoded': summary['spike_values_decoded'],
                'test_asset_accessed': summary['test_asset_accessed'],
                'models_run': summary['models_run'],
                'reference_executed': summary['reference_executed'],
                'independent_empirical_recomputation': False,
                'original_source_audit_and_gates_preserved': True,
                'remaining_gate': 'Resolve trial/event/target semantics and missingness, censoring and eligibility before a new observation contract. Do not infer the early-response/outlier intersection from aggregate counts or replace the failed primary with a sensitivity cutoff.',
                'accounting_scope': 'Separate training-file intake and metadata reader; the full file includes spike bytes but no spike values were decoded. The original source-audit transfer totals and zero scientific-reference counts remain unchanged.',
                'conservative_cumulative_seconds': summary['conservative_cumulative_seconds'],
                'cumulative_limit_seconds': summary['cumulative_limit_seconds'],
            }
    entries.sort(key=lambda x: x['assignment_ids'][0])
    covered = sorted(i for e in entries for i in e['assignment_ids'])
    expected = sorted(r['id'] for r in roster if r['status'] == 'discovery_candidate')
    if covered != expected or len(entries) != 16 or len(set(covered)) != 32:
        raise ValueError('Audit coverage must be exactly the 32 existing discovery assignments')
    result = {
        'schema_version': 2, 'updated_on': '2026-10-30',
        'purpose': 'Current construction evidence overlay, not an execution or admission promotion.',
        'original_roster': str(roster_path.relative_to(ROOT)),
        'audited_source_collections': 16, 'existing_discovery_assignments_covered': 32,
        'new_source_audits': 12, 'new_audit_response_body_bytes': byte_total,
        'new_audit_request_attempts': attempts, 'new_audit_request_wall_seconds_sum': request_seconds,
        'accounting_scope': 'Explicit application-consumed HTTP body bytes, including retained failures/partial responses. Web-tool views, headers and transport buffering are unmetered. Earlier four-source accounting remains separate in discovery_audit_four.json.',
        'new_audit_recording_or_model_bytes': 0, 'new_audit_scientific_executions': 0,
        'roster_statuses_changed': False, 'collections': entries, 'source_pins': pins,
    }
    (OUT / 'construction_audit_index.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# Source audits for the 32 discovery assignments', '',
        '**16 collections now have bounded construction audits covering all 32 existing discovery assignments.** The roster remains 100 paper projects plus 100 neural assignments. These audits do not create new tasks or establish runnable references.', '',
        'The earlier four-source pass included selected real headers and tiny event/QC arrays. The twelve additional audits inspected code and metadata only: no recordings, model weights, fitting or candidate execution. Their explicit response bodies total ' + f'**{byte_total:,} bytes across {attempts} attempts**. Each collection stayed within its separate 2 MB source allowance; this is not total network traffic.', '',
        '| Assignments | Collection | Construction implication |', '|---|---|---|']
    for e in entries:
        link = '../../..' + '/' + e['narrative_path']
        # This file is docs/neuroscience-benchmarks/build: three levels to repository root.
        detail = e.get('construction_implication', e['audit_scope'])
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        lines.append(f"| {', '.join(e['assignment_ids'])} | [{e['name']}]({link}) | {detail.replace('|', '/')} |")
    lines += ['', '## What becomes executable next', '',
        'MICrONS has a separately documented processed-data option: BossDB v1 node/edge pickles match older paper code, while the later inspected release expects an unresolved Feather file. The [version reconciliation](../../../authoring/paper-construction-audit/microns-route-reconciliation.json) retains both contracts. HEAD lengths do not qualify payload integrity, schema or format equivalence; this option does not establish the raw-neural feature/mapping path for NEURAL-087/088.', '',
        'The separate [DMFC training-metadata follow-up](../../../authoring/dmfc-timing/schema-v2/RESULTS.md) has completed, with an [independent saved-metadata review](../../../authoring/dmfc-timing/schema-v2-review-v1/RESULTS.md). Two early Go responses block the predeclared Set+200 ms observation policy; no trials were removed and no shorter sensitivity cutoff substituted. The ts/tp event semantics remain unresolved. Recorded short/long-prior supports share exactly 800 ms in all 12 split/modality/direction groups, before eligibility, but this is not a qualified scientific contrast. The complete 14,119,912-byte training file was acquired in that separate intake; only allowlisted metadata was decoded, with no spike values, test asset, model or scientific reference evaluated. Its cumulative ledger is 89.070619/90 seconds. Original source-audit counts and statuses remain unchanged.', '',
        'ERP CORE and the Garcia recording components offer subsequent bounded input inspections once their time bases, event definitions and subject identities are frozen. IBC needs map-version and invalid-flag resolution first. The larger fMRI/MEG collections need compact, provenance-preserving exports or additional storage; a small file alone is not an adequate scientific cohort.', '',
        'For every task, freeze the allowed observations, unit of generalization, reference and nuisance controls, signed metric, private scoring boundary and resource allowance before fitting. Public historical test labels do not become an unseen assessment merely because a local packet omits them. Preserve null, undefined and failed outcomes.', '',
        '[Machine-readable gates and source pins](construction_audit_index.json) · [Exposure review](EXPOSURE_AUDIT.md) · [Live build status](../BUILD_STATUS.md)', '']
    (OUT / 'CONSTRUCTION_SOURCE_AUDITS.md').write_text('\n'.join(lines))
    print(json.dumps({k: result[k] for k in ('audited_source_collections', 'existing_discovery_assignments_covered', 'new_audit_response_body_bytes', 'new_audit_request_attempts')}))


if __name__ == '__main__':
    main()
