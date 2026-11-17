"""Accepted public method-field parser, extracted without prerequisite receipts.

Consumers inject json, need and decode; this file is not an execution grant.
"""

METHOD_FIELDS = ('estimator_family', 'cue_feature_map', 'neural_feature_map',
                 'training_preprocessing', 'hyperparameter_candidates', 'selection_folds',
                 'selection_loss', 'tie_rule', 'constant_or_missing_group_policy',
                 'training_random_seed', 'allowed_view_specific_changes',
                 'query_transduction_policy')

def read_method(body):
    need(type(body) is bytes and 0 < len(body) <= 32768, 'Bounded method declaration')
    value = decode(body)
    need(type(value) is dict and value.get('candidate_id') == 'NEURAL-095' and
         type(value.get('schema_version')) is int and value['schema_version'] == 1 and
         all(k in value for k in METHOD_FIELDS), 'Complete public method declaration')
    json.dumps(value, allow_nan=False)
    for key in METHOD_FIELDS:
        if key not in ('training_random_seed', 'hyperparameter_candidates'):
            need(type(value[key]) is str and 0 < len(value[key]) <= 4096,
                 'Nonempty bounded procedure description: ' + key)
    need(value['training_random_seed'] is None or type(value['training_random_seed']) is int,
         'Declared integer seed or deterministic null')
    need(type(value['hyperparameter_candidates']) in (list, dict, str), 'Explicit selection grid or no-selection declaration')
    return value
