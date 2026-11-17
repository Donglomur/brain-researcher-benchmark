"""NEURAL-073 numerical estimators; importing this package performs no fitting."""
from ._common import EstimatorError, NumericBudget, FrozenArray
from .svm import (GapCertificate, SVMState, fit_svm, fit_svm_primitive,
                  predict_svm, solve_binary_primitive, training_gamma)
from .trees import (ExtraTreesState, fit_extra_trees, fit_extra_trees_primitive,
                    predict_extra_trees, eligible_selection, exact_threshold)


def predict_raw(state, X, budget):
    if type(state) is SVMState:
        return predict_svm(state, X, budget)
    if type(state) is ExtraTreesState:
        return predict_extra_trees(state, X, budget)
    raise EstimatorError('unsupported_estimator_state')


def from_dict(value, budget, *, max_elements, max_nodes):
    if type(value) is not dict:
        raise EstimatorError('invalid_estimator_state')
    if value.get('schema') == 'n073_svm_state_v2':
        return SVMState.from_dict(value, budget, max_elements=max_elements)
    if value.get('schema') == 'n073_extra_trees_state_v1':
        return ExtraTreesState.from_dict(value, budget, max_nodes=max_nodes)
    raise EstimatorError('unsupported_estimator_schema')

from .kernel_bank import KernelBank, build_kernel_bank, validate_kernel_bank
