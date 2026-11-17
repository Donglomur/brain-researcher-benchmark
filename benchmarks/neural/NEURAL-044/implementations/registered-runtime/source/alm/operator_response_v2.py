"""Versioned target-last operator binding the paired NEURAL-044 endpoint.

No participant runner, source admission or native isolation is supplied here.
The original investigation grader remains a separate numerical check.
"""
from .contracts import require
from .operator import Operator, ARMS
from . import experiment, programme, grading
from .response_comparison_v2 import prepare_response_comparison, score_response_comparison


class ResponseComparisonOperator(Operator):
    def __init__(self):
        super().__init__('NEURAL-044')
        self._comparison = None

    def prepare_perturbation(self, root, manifest, mappings, budget, protocol,
                             private_key, limits, public_root, private_root,
                             truth_path, comparison_path, source_digest, receipt_path,
                             artifact_cap):
        def operation():
            self._begin('NEURAL-044', artifact_cap)
            self._root_geometry([public_root], [private_root],
                                [truth_path, comparison_path, receipt_path])
            records, population = self._call('load_population', programme.load_population,
                                            root, manifest, mappings, budget)
            construction = self._call('construct_perturbation', programme.construct_perturbation,
                                       records, protocol)
            mice = sorted({r['mouse'] for r in manifest['recordings']})
            packets = self._call('prepare_response_comparison', prepare_response_comparison,
                                 construction, mice, private_key, limits, source_digest)
            publication = self._publish(packets, public_root, private_root)
            comparison_pin = self._write(comparison_path, packets['cohort'])
            self._comparison = (comparison_path, comparison_pin)
            truth = self._call('investigation_truth', experiment.investigation_truth,
                               construction, source_digest)
            truth_pin = self._write(truth_path, truth)
            self._truth = (truth_path, truth_pin)
            self._write(receipt_path, {'task': self.task, 'publication': publication,
                'truth_pin': truth_pin, 'comparison_pin': comparison_pin,
                'source_only': True, 'provider_verified': False})
            self.state = 'prepared'
            return {'task': self.task, 'population': population, 'construction': construction,
                'publication': publication, 'truth_pin': truth_pin,
                'comparison_pin': comparison_pin, 'source_only': True, 'provider_verified': False}
        return self._call('prepare_perturbation_v2', operation)

    def evaluate_perturbation(self, submissions, commits, tolerances):
        def operation():
            require(self._truth is not None and self._comparison is not None,
                    'prepared investigation and paired comparison')
            ids = [r['public']['case_id'] for r in self._packets]
            require('investigation' not in ids, 'reserved investigation channel')
            found, pins = self._commit_all(submissions, commits, ids + ['investigation'])
            public = {r['public']['case_id']: r['public'] for r in self._packets}
            private = {case_id: self._private(r['private_path'], r['private_pin'])
                       for case_id, r in zip(ids, self._publications)}
            cohort = self._private(*self._comparison)
            truth = self._private(*self._truth)
            scores = {}
            for arm in ARMS:
                scores[arm] = {
                    'held_response': self._call('score_response_comparison', score_response_comparison,
                        {k: found[arm][k] for k in ids}, public, private, cohort),
                    'investigation': self._call('grade_investigation', grading.grade_investigation,
                        found[arm]['investigation'], truth, tolerances)}
            self.state = 'scored'
            return {'task': self.task, 'scores': scores, 'commitments': pins,
                    'scientific_qualification': False, 'provider_verified': False}
        return self._call('evaluate_perturbation_v2', operation)
