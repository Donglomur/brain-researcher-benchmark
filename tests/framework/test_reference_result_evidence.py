"""Selected A/B/G public aggregate controls; never execute a scientific workload."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location('reference_result_' + name, ROOT / 'src/neurobench' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


evidence = module('evidence')
PUBLIC = (evidence.LANGUAGE_REFERENCE, evidence.LANGUAGE_REFERENCE_PROVENANCE,
          evidence.LANGUAGE_REFERENCE_NARRATIVE, evidence.UMBRAE_RESCORE,
          evidence.UMBRAE_RESCORE_NARRATIVE, evidence.ANNOTATION_PROVENANCE,
          evidence.ANNOTATION_NARRATIVE)
TASKS = {'PAPER-ROOT-ADD-001', 'PAPER-paper-method-042', 'PAPER-paper-method-013'}


class ReferenceResultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        for name in PUBLIC:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())

    def document(self, name):
        return json.loads((ROOT / name).read_text())

    def install(self, name, doc):
        (self.root / name).write_text(json.dumps(doc, indent=2) + '\n')

    def rows(self):
        return {row['category']: row for rows in evidence.load(self.root, TASKS)['records'].values() for row in rows}

    def refuses(self, name, mutations):
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                doc = self.document(name)
                mutate(doc)
                self.install(name, doc)
                with self.assertRaises(ValueError):
                    evidence.load(self.root, TASKS)
        (self.root / name).write_bytes((ROOT / name).read_bytes())

    def test_three_scopes_have_separate_counts_and_no_solver_qualification(self):
        result = evidence.load(self.root, TASKS)
        counts = result['counts']
        self.assertEqual(counts['public_reports'], 3)
        self.assertEqual(counts['tasks_with_recorded_evidence'], 3)
        self.assertEqual(counts['trusted_operator_reference_execution_attempts'], 3)
        self.assertEqual(counts['trusted_operator_reference_estimator_fits'], 5685)
        self.assertEqual(counts['trusted_operator_reference_complete_endpoints'], 1)
        self.assertEqual(counts['released_output_rescore_subject_query_evaluations'], 9676)
        self.assertEqual(counts['annotation_provenance_pair_conditions'], 32)
        for key in ('pilot_attempts', 'direct_interpretation_attempts', 'author_model_inference_probes',
                    'author_reference_calibration_arms', 'historical_reference_rescore_operations'):
            self.assertEqual(counts[key], 0)
        for row in self.rows().values():
            self.assertEqual(row['qualification_effect'], 'none')
            self.assertEqual(row['solver_attempts_recorded'], 0)
            self.assertFalse(row['full_task_completed'])
            self.assertNotIn('scientific_readiness', row)

    def test_language_keeps_preworker_failures_and_paired_reduction(self):
        row = self.rows()['trusted_operator_reference']
        self.assertEqual([attempt['estimator_fits'] for attempt in row['attempts']], [0, 0, 5685])
        self.assertEqual([attempt['status'] for attempt in row['attempts']],
                         ['failed_before_container', 'failed_before_worker', 'complete_trusted_reference'])
        self.assertEqual([row['coverage'][key] for key in ('people', 'sessions', 'cells')], [8, 14, 42])
        score = row['metrics'][0]
        self.assertEqual(score['value'], score['comparators']['provided_author_reference'])
        self.assertLess(row['comparison']['equal_session_paired_mean_delta'], 0)
        self.assertFalse(row['comparison']['new_acceptance_tolerance_or_improvement_margin'])
        self.assertTrue(row['reference_read_after_all_fits'])
        self.assertFalse(row['participant_provider_qualified'])
        self.assertEqual({item['path'] for item in row['attachments']},
                         {evidence.LANGUAGE_REFERENCE_PROVENANCE, evidence.LANGUAGE_REFERENCE_NARRATIVE})

    def test_language_scope_units_and_qualification_contradictions_refuse(self):
        self.refuses(evidence.LANGUAGE_REFERENCE, {
            'fit-count': lambda d: d['scope'].update(fresh_Ridge_fits=42),
            'incomplete-cell': lambda d: d.update(cell_receipts_verified=41),
            'boolean-count': lambda d: d['scope'].update(people=True),
            'wrong-endpoint': lambda d: d['scope'].update(lag_indices=[16, 17, 18]),
            'participant-promotion': lambda d: d['claims'].update(participant_NativeProvider_qualified=True),
            'AI-promotion': lambda d: d['claims'].update(AI_result=True),
            'pearson-units': lambda d: d.update(fresh_reference_equal_session_mean=4.512),
            'paired-exceeds-cells': lambda d: d.update(equal_session_paired_mean_delta=.1),
            'closure': lambda d: d['completion'].update(owned_container_removed_and_absent=False),
        })

    def test_language_provenance_is_required_and_custody_is_not_inferred(self):
        self.refuses(evidence.LANGUAGE_REFERENCE_PROVENANCE, {
            'missing-failed-attempt': lambda d: d['attempt_history'].pop(0),
            'failed-attempt-read': lambda d: d['attempt_history'][0].update(authentic_scientific_input_body_reads=1),
            'failed-attempt-fit': lambda d: d['attempt_history'][1].update(fits=1),
            'unclosed-owner': lambda d: d['attempt_history'][2].update(all_spawned_process_scopes_closed=False),
            'reference-fed-to-predictor': lambda d: d['provided_author_reference'].update(read_into_predictor=True),
            'reference-read-early': lambda d: d['provided_author_reference'].update(read_only_after_all5685fits=False),
            'retuned-source': lambda d: d['attempt_history'][2].update(scientific_source_retuned=True),
            'runtime-replaced': lambda d: d['numerical_runtime'].update(python='3.12.12'),
        })
        (self.root / evidence.LANGUAGE_REFERENCE_PROVENANCE).unlink()
        with self.assertRaisesRegex(ValueError, 'provenance is missing'):
            evidence.load(self.root)

    def test_umbrae_preserves_full_denominators_and_precision_scope(self):
        row = self.rows()['released_output_scoring_reference']
        self.assertEqual(row['coverage']['query_identities_per_subject'], 2419)
        self.assertEqual(row['coverage']['subject_query_evaluations'], 4 * 2419)
        self.assertEqual(row['coverage']['source_metric_cells_across_passes'], 160)
        self.assertEqual(row['coverage']['keyed_metric_cells'], 80)
        self.assertEqual(row['diagnostics']['source_accuracy_cells_compared'], 60)
        self.assertGreater(row['diagnostics']['maximum_source_seed_mean_iou_difference'], 0)
        self.assertFalse(row['diagnostics']['all_80_cells_bit_identical'])
        self.assertFalse(row['diagnostics']['universal_scorer_equivalence'])
        self.assertEqual(row['diagnostics']['empty_answers_by_subject'], {'S1': 8, 'S2': 1, 'S5': 2, 'S7': 1})
        self.assertEqual(row['new_model_inference_runs'], 0)
        self.assertEqual(row['reference_fits'], 0)
        self.assertEqual([round(metric['value'], 2) for metric in row['metrics']], [18.93, 18.27, 18.19, 16.74])
        self.assertTrue(row['narrative']['path'].endswith('20261124.md'))

    def test_umbrae_missing_panels_units_and_denominators_refuse(self):
        self.refuses(evidence.UMBRAE_RESCORE, {
            'missing-seed': lambda d: d['source_panels'].pop('1'),
            'missing-subject': lambda d: d['canonical_keyed_float64_panel'].pop('S7'),
            'missing-overlap-group': lambda d: d['source_panels']['0']['S1'].pop('Salient Objects'),
            'reduced-denominator': lambda d: d['source_panels']['0']['S1']['All'].update(query_count=2411),
            'fraction-as-percent': lambda d: d['recovered_primary_percent_by_seed']['0'].update(S1=.18933443571723854),
            'percent-as-fraction': lambda d: d['source_panels']['0']['S1']['All']['accuracy'].update({'0.5': 18.93}),
            'empty-answer-dropped': lambda d: d['canonical_keyed_float64_panel']['S1']['All'].update(missing_or_invalid=0),
            'whole-history-claimed': lambda d: d['runtime'].update(historical_runtime_authenticated=True),
        })

    def test_umbrae_alignment_mean_and_precision_contradictions_refuse(self):
        self.refuses(evidence.UMBRAE_RESCORE, {
            'pairing': lambda d: d['canonical_keyed_float32_diagnostics']['S1']['All'].update(source_positional_pairing_compatible=False),
            'threshold-change': lambda d: d['canonical_keyed_float32_diagnostics']['S1']['All']['threshold_decision_disagreements_float32_vs_float64'].update({'0.5': 1}),
            'accuracy-disagreement': lambda d: d['canonical_keyed_float64_panel']['S1']['All']['accuracy'].update({'0.5': .19}),
            'mean-summary': lambda d: d['ordering_and_precision_comparison'].update(maximum_source_seed_mean_iou_difference=0),
            'keyed-mean-summary': lambda d: d['ordering_and_precision_comparison'].update(maximum_source_seed0_vs_keyed64_mean_iou_difference=0),
            'precision-summary': lambda d: d['ordering_and_precision_comparison'].update(maximum_individual_iou_float32_vs_float64_difference=0),
            'status-denominator': lambda d: d['canonical_keyed_float32_diagnostics']['S1']['All']['keyed_prediction_status_counts'].update(valid=2419),
        })

    def test_umbrae_accuracy_cannot_credit_empty_answers(self):
        ceiling = (2419 - 8) / 2419

        def synchronized_accuracy(value):
            doc = self.document(evidence.UMBRAE_RESCORE)
            values = {key: value for key in ('0.3', '0.5', '0.7')}
            for seed in ('0', '1'):
                doc['source_panels'][seed]['S1']['All']['accuracy'] = dict(values)
                doc['recovered_primary_percent_by_seed'][seed]['S1'] = 100 * value
            doc['canonical_keyed_float64_panel']['S1']['All']['accuracy'] = dict(values)
            doc['canonical_keyed_float32_diagnostics']['S1']['All']['keyed_float32_accuracy'] = dict(values)
            doc['published_v2_primary_percent']['S1'] = round(100 * value, 2)
            self.install(evidence.UMBRAE_RESCORE, doc)

        # All four accuracy views and both percentage summaries agree. Only the
        # eight retained empty answers make these claimed accuracies impossible.
        serialized_ceiling = math.nextafter(ceiling, math.inf)
        for value in (1.0, math.nextafter(serialized_ceiling, math.inf)):
            with self.subTest(rejected_accuracy=value):
                synchronized_accuracy(value)
                with self.assertRaisesRegex(ValueError, 'nonempty-answer denominator'):
                    evidence.load(self.root, TASKS)
        for value in (ceiling, serialized_ceiling):
            with self.subTest(accepted_accuracy=value):
                synchronized_accuracy(value)
                row = self.rows()['released_output_scoring_reference']
                self.assertEqual(row['metrics'][0]['value'], 100 * value)
                self.assertEqual(row['diagnostics']['empty_answers_by_subject']['S1'], 8)
                self.assertEqual(row['qualification_effect'], 'none')

    def test_annotation_all_conditions_are_provenance_without_model_metrics(self):
        row = self.rows()['annotation_representation_provenance']
        self.assertEqual(row['coverage']['recording_pairs'], 4)
        self.assertEqual(row['coverage']['ROIs_per_source'], 1050)
        self.assertEqual(row['coverage']['pair_conditions'], 32)
        self.assertEqual(len(row['conditions']), 8)
        matches = [item for item in row['conditions'] if item['ordered_exact_matches']]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['orientation'], 'spatial_axes_swapped')
        self.assertEqual(matches[0]['zero_padding_offset'], [0, 0])
        self.assertEqual(matches[0]['ordered_exact_matches'], 1050)
        self.assertEqual(row['metrics'], [])
        self.assertFalse(row['model_performance_assessed'])
        self.assertFalse(row['causal_lineage_established'])

    def test_annotation_missing_duplicate_and_changed_conditions_refuse(self):
        self.refuses(evidence.ANNOTATION_PROVENANCE, {
            'missing-cohort-condition': lambda d: d['prespecified_conditions'].pop(),
            'duplicate-cohort-condition': lambda d: d['prespecified_conditions'].__setitem__(1, copy.deepcopy(d['prespecified_conditions'][0])),
            'missing-pair': lambda d: d['complete_per_recording_conditions'].pop(),
            'duplicate-pair': lambda d: d['complete_per_recording_conditions'].__setitem__(1, copy.deepcopy(d['complete_per_recording_conditions'][0])),
            'missing-pair-condition': lambda d: d['complete_per_recording_conditions'][0]['conditions'].pop(),
            'boolean-offset': lambda d: d['complete_per_recording_conditions'][0]['conditions'][0].update(zero_padding_offset=[False, 0]),
            'unselected-condition': lambda d: d['prespecified_conditions'][0].update(zero_padding_offset=[2, 0]),
        })

    def test_annotation_multiplicity_sums_and_qualification_refuse(self):
        self.refuses(evidence.ANNOTATION_PROVENANCE, {
            'duplicate-masks': lambda d: d['complete_per_recording_conditions'][0]['conditions'][4]['deep_duplicates'].update(duplicate_excess_count=1),
            'unmatched-roi': lambda d: d['complete_per_recording_conditions'][0]['conditions'][4].update(ordered_matching_roi_count=236),
            'cohort-sum': lambda d: d['prespecified_conditions'][4].update(ordered_exact_matches=1049),
            'equality-flag': lambda d: d['prespecified_conditions'][0].update(whole_cohort_ordered_equal=True),
            'full-original-cohort': lambda d: d['population'].update(full_original_paper_cohort_qualified=True),
            'performance-claim': lambda d: d.update(reproduction_or_improvement_success=True),
            'readiness': lambda d: d.update(benchmark_ready_increment=1),
        })

    def test_fixed_public_attachments_bind_without_following_embedded_paths(self):
        doc = self.document(evidence.LANGUAGE_REFERENCE_PROVENANCE)
        doc['provided_author_reference']['path'] = '/private-sentinel/raw-author-output.npy'
        self.install(evidence.LANGUAGE_REFERENCE_PROVENANCE, doc)
        original = Path.open
        observed = []
        def guarded(path, *args, **kwargs):
            relative = path.relative_to(self.root).as_posix()
            self.assertIn(relative, PUBLIC)
            observed.append(relative)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            result = evidence.load(self.root)
        self.assertEqual(set(observed), set(PUBLIC))
        self.assertNotIn('private-sentinel', json.dumps(result))
        for name in (evidence.LANGUAGE_REFERENCE_NARRATIVE, evidence.UMBRAE_RESCORE_NARRATIVE, evidence.ANNOTATION_NARRATIVE):
            with self.subTest(name=name):
                path = self.root / name
                path.unlink()
                with self.assertRaisesRegex(ValueError, 'narrative is missing'):
                    evidence.load(self.root)
                path.write_text('Unbound replacement narrative.\n')
                with self.assertRaisesRegex(ValueError, 'narrative pin mismatch'):
                    evidence.load(self.root)
                path.write_bytes((ROOT / name).read_bytes())

    def test_catalog_status_and_registration_keep_the_three_claim_scopes(self):
        result = evidence.load(self.root, TASKS)
        rendered = module('catalog').evidence_text({'recorded_evidence': result})
        for phrase in ('5685 fresh Ridge fits', '2 source-seed panels', 'mean-IoU differences remain',
                       '1050 ROIs per source', 'raw-movie lineage, segmentation performance'):
            self.assertIn(phrase, rendered)
        status = (ROOT / 'docs/status/README.md').read_text()
        for relative in (evidence.LANGUAGE_REFERENCE_NARRATIVE, evidence.UMBRAE_RESCORE_NARRATIVE, evidence.ANNOTATION_NARRATIVE):
            self.assertIn(relative, status)
        with self.assertRaisesRegex(ValueError, 'unregistered task'):
            evidence.load(self.root, TASKS - {'PAPER-paper-method-013'})
        self.assertEqual(len(evidence.PUBLIC_REPORTS), 22)
        self.assertEqual(len(evidence.PUBLIC_ATTACHMENTS), 9)
        self.assertNotIn(evidence.LANGUAGE_REFERENCE_PROVENANCE, evidence.PUBLIC_REPORTS)

    def test_json_provenance_attachment_uses_strict_decoder_and_allowlist(self):
        path = self.root / evidence.LANGUAGE_REFERENCE_PROVENANCE
        for raw in ('{"same":1,"same":2}', '{"value":NaN}', '[]', '{"value":Infinity}', 'not JSON'):
            with self.subTest(raw=raw):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    evidence.load(self.root)
        with self.assertRaisesRegex(ValueError, 'not allowlisted'):
            evidence.read_json_attachment(self.root, evidence.LANGUAGE_REFERENCE)
        with self.assertRaisesRegex(ValueError, 'not allowlisted'):
            evidence.read(self.root, evidence.LANGUAGE_REFERENCE_PROVENANCE)


    def install_nested(self):
        for name in (evidence.LANGUAGE_NESTED, evidence.LANGUAGE_NESTED_PROVENANCE, evidence.LANGUAGE_NESTED_NARRATIVE):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())

    def test_nested_negative_result_preserves_delta_units_and_reuses_A3(self):
        self.install_nested()
        result = evidence.load(self.root, TASKS)
        row = self.rows()['trusted_operator_candidate_comparison']
        self.assertEqual(result['counts']['public_reports'], 4)
        self.assertEqual(result['counts']['tasks_with_recorded_evidence'], 3)
        self.assertEqual(result['counts']['trusted_operator_reference_estimator_fits'], 5685)
        self.assertEqual(result['counts']['trusted_operator_reference_execution_attempts'], 3)
        self.assertEqual(result['counts']['trusted_operator_candidate_executions'], 1)
        self.assertEqual(result['counts']['trusted_operator_candidate_estimator_fits'], 90960)
        self.assertEqual(result['counts']['trusted_operator_candidate_inner_fits'], 85275)
        self.assertEqual(result['counts']['trusted_operator_candidate_outer_refits'], 5685)
        self.assertEqual(result['counts']['trusted_operator_candidate_new_reference_fits'], 0)
        self.assertEqual(result['counts']['trusted_operator_candidate_non_improving_comparisons'], 1)
        metric = row['metrics'][0]
        delta = row['comparison']['paired_equal_session_mean_delta']
        self.assertEqual(metric['value'], .04498980902383724)
        self.assertEqual(metric['comparators']['fresh_A3_reference'], .04512071156679768)
        self.assertEqual(delta, -.00013090254296041978)
        self.assertNotEqual(delta, metric['value'] - metric['comparators']['fresh_A3_reference'])
        self.assertEqual(row['comparison']['reference']['path'], evidence.LANGUAGE_REFERENCE)
        self.assertFalse(row['comparison']['inferential_superiority_or_meaningful_effect_criterion_selected'])
        self.assertEqual(row['AI_attempts_recorded'], 0)
        self.assertFalse(row['participant_provider_qualified'])
        self.assertEqual(row['qualification_effect'], 'none')

    def test_nested_incomplete_fits_units_and_positive_claims_refuse(self):
        self.install_nested()
        self.refuses(evidence.LANGUAGE_NESTED, {
            'incomplete-fits': lambda d: d['scope'].update(fresh_estimator_fits=85275),
            'requests-as-fits': lambda d: d['fit_observation'].update(fit_returns=5685),
            'missing-person': lambda d: d['scope'].update(people=7),
            'positive-delta': lambda d: d.update(paired_equal_session_mean_delta=.00013090254296041978),
            'contradictory-negative': lambda d: d.update(paired_equal_session_mean_delta=-.1),
            'percent-as-Pearson': lambda d: d.update(candidate_equal_session_mean=4.4989809),
            'AI-improvement': lambda d: d['claims'].update(AI_improvement=True),
            'participant-promotion': lambda d: d['claims'].update(participant_NativeProvider_qualification=True),
            'retuning': lambda d: d['claims'].update(post_result_tuning=True),
            'changed-weighting': lambda d: d.update(original_primary_endpoint='equal mean eight people'),
            'incomplete-closure': lambda d: d['closure'].update(container_removed_and_absence_verified=False),
        })

    def test_nested_requires_actual_A3_dependency_and_complete_pairing(self):
        self.install_nested()
        self.refuses(evidence.LANGUAGE_NESTED, {
            'wrong-reference-mean': lambda d: d.update(fresh_reference_equal_session_mean=.05),
            'missing-target-join': lambda d: d['pairing_verification'].update(all42fresh_reference_target_support_qid_time_row_and_fold_identities_match=False),
            'early-reference-read': lambda d: d['pairing_verification'].update(fresh_reference_read_after_all_candidate_fits=False),
            'dropped-support': lambda d: d['pairing_verification'].update(no_original_rows_folds_cells_sessions_dropped=False),
        })
        baseline = self.document(evidence.LANGUAGE_REFERENCE)
        baseline.update(fresh_reference_equal_session_mean=.06, provided_author_equal_session_mean=.06)
        self.install(evidence.LANGUAGE_REFERENCE, baseline)
        with self.assertRaisesRegex(ValueError, 'fresh-reference comparison'):
            evidence.load(self.root)
        (self.root / evidence.LANGUAGE_REFERENCE).unlink()
        with self.assertRaisesRegex(ValueError, 'captured fresh A3 reference'):
            evidence.load(self.root)

    def test_nested_provenance_binds_frozen_method_no_retry_and_no_second_baseline(self):
        self.install_nested()
        self.refuses(evidence.LANGUAGE_NESTED_PROVENANCE, {
            'changed-grid': lambda d: d['method'].update(alphas=[.01, .1, 1, 10, 100]),
            'boolean-grid': lambda d: d['method'].update(alphas=[.001, .01, .1, True, 10]),
            'changed-inner-folds': lambda d: d['method'].update(inner_training_sentence_folds=2),
            'changed-selection': lambda d: d['method'].update(selection_metric='mean of fold correlations'),
            'retuned-source': lambda d: d['candidate_unchanged'].update(sha256='a' * 64),
            'recomputed-baseline': lambda d: d['fresh_reference'].update(no_duplicate_reference_execution=False),
            'early-baseline-load': lambda d: d['fresh_reference'].update(only_read_after_candidate_completion=False),
            'unbound-reference': lambda d: d['fresh_reference'].update(public_aggregate='another/RESULT.json'),
            'retry': lambda d: d['single_actual_attempt'].update(no_retry=False),
            'unclosed-attempt': lambda d: d['single_actual_attempt'].update(allprocess_and_container_scopes_closed=False),
            'new-runtime': lambda d: d['runtime'].update(python='3.12.12'),
        })

    def test_nested_all_direction_rosters_retained_without_p2_subsetting(self):
        self.install_nested()
        row = self.rows()['trusted_operator_candidate_comparison']
        self.assertEqual(row['direction_counts']['cells']['negative'], 26)
        self.assertEqual(row['direction_counts']['sessions']['negative'], 10)
        self.assertEqual(row['direction_counts']['people_mean_diagnostic']['negative'], 5)
        self.assertEqual(row['direction_counts']['leave_one_person_out']['negative'], 7)
        self.assertEqual(len(row['session_directions']), 14)
        self.assertEqual(len(row['person_directions']), 8)
        positive = [item['person'] for item in row['person_directions']
                    if item['leave_one_person_out_primary_delta_direction'] == 'positive']
        self.assertEqual(positive, ['p2'])
        self.refuses(evidence.LANGUAGE_NESTED, {
            'drop-p2': lambda d: d['person_directions'].pop(1),
            'drop-session': lambda d: d['session_directions'].pop(2),
            'duplicate-person': lambda d: d['person_directions'].__setitem__(1, copy.deepcopy(d['person_directions'][0])),
            'changed-person-weight': lambda d: d['person_directions'][3].update(session_count=2),
            'hide-sensitivity': lambda d: d['person_directions'][1].update(leave_one_person_out_primary_delta_direction='negative'),
            'changed-session-direction': lambda d: d['session_directions'][2].update(direction='positive'),
            'contradictory-counts': lambda d: d['direction_counts']['cells'].update(negative=25),
        })

    def test_nested_public_bindings_render_negative_result_without_private_reads(self):
        self.install_nested()
        doc = self.document(evidence.LANGUAGE_NESTED_PROVENANCE)
        doc['evidence_identities']['private_complete_result']['path'] = '/private-sentinel/RESULT.json'
        self.install(evidence.LANGUAGE_NESTED_PROVENANCE, doc)
        result_doc = self.document(evidence.LANGUAGE_NESTED)
        result_doc['person_directions'][0]['unselected_payload'] = '/private-sentinel/person-data'
        result_doc['session_directions'][0]['unselected_payload'] = '/private-sentinel/session-data'
        self.install(evidence.LANGUAGE_NESTED, result_doc)
        allowed = set(PUBLIC) | {evidence.LANGUAGE_NESTED, evidence.LANGUAGE_NESTED_PROVENANCE, evidence.LANGUAGE_NESTED_NARRATIVE}
        original = Path.open
        observed = []
        def guarded(path, *args, **kwargs):
            relative = path.relative_to(self.root).as_posix()
            self.assertIn(relative, allowed)
            observed.append(relative)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            result = evidence.load(self.root)
        self.assertEqual(set(observed), allowed)
        self.assertNotIn('private-sentinel', json.dumps(result))
        rendered = module('catalog').evidence_text({'recorded_evidence': result})
        for phrase in ('90960 fits', '−0.00013090254296041978', 'reused without new reference fits', 'without retuning or dropping p2'):
            self.assertIn(phrase, rendered)
        # The catalog must render the accepted projection, not a second metric literal.
        alternate = self.document(evidence.LANGUAGE_NESTED)
        alternate['candidate_equal_session_mean'] = alternate['fresh_reference_equal_session_mean'] - .001
        alternate['paired_equal_session_mean_delta'] = -.001
        self.install(evidence.LANGUAGE_NESTED, alternate)
        changed = module('catalog').evidence_text({'recorded_evidence': evidence.load(self.root)})
        self.assertIn('negative paired equal-session delta of −0.001 ', changed)
        self.assertNotIn('−0.00013090254296041978', changed)
        self.install(evidence.LANGUAGE_NESTED, result_doc)
        self.assertIn(evidence.LANGUAGE_NESTED_NARRATIVE, (ROOT / 'docs/status/README.md').read_text())
        path = self.root / evidence.LANGUAGE_NESTED_NARRATIVE
        path.write_text('Unbound replacement narrative.\n')
        with self.assertRaisesRegex(ValueError, 'narrative pin mismatch'):
            evidence.load(self.root)
        path.write_bytes((ROOT / evidence.LANGUAGE_NESTED_NARRATIVE).read_bytes())
        path = self.root / evidence.LANGUAGE_NESTED_PROVENANCE
        path.write_text('{"same":1,"same":2}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            evidence.load(self.root)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'nested-Ridge provenance is missing'):
            evidence.load(self.root)


if __name__ == '__main__':
    unittest.main()
