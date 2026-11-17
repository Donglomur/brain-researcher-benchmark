"""Restricted XM prediction capability over prequalified fold/control artifacts.

The operator supplies externally verified artifact pins and qualification receipt;
this API cannot itself make a reference scientifically qualified. It exposes no
removed comparator, target, raw artifact, or alternate training data.
"""
import copy
from .base import require, digest
from .contracts import validate_model_tool, assert_endpoint_applicable
from .models import predict
from .trajectory import predict_native


class ModelTool:
    def __init__(self, public, descriptor, artifacts, operator_artifact_pins):
        assert_endpoint_applicable(public['cell_id'], public['task'], public['endpoint'])
        validate_model_tool(public['cell_id'], descriptor, digest(public['training']), public['task'])
        names = set(descriptor['model_names'])
        require(set(artifacts) == set(operator_artifact_pins) == names, 'model_tool_artifact_names')
        require(all(digest(artifacts[k]) == operator_artifact_pins[k] for k in names), 'model_tool_pin')
        permitted_features = set.intersection(*(set(r['features']) for r in public['training']))
        if public['task'] == 'NEURAL-045': permitted_features |= {'tau'}
        for name, artifact in artifacts.items():
            model = artifact['model'] if public['task'] == 'NEURAL-045' else artifact
            enc = model['encoder']
            used = set(enc['axes']) | set(enc['numeric']) | set(enc['categorical'])
            require(used <= permitted_features, 'model_tool_feature_backfill')
            require(set(model['training_animals']) <= {r['animal'] for r in public['training']}, 'tool_training_animal_leak')
        self.public = copy.deepcopy(public)
        self.artifacts = copy.deepcopy(artifacts)
        self.descriptor = copy.deepcopy(descriptor)

    def predict(self, name, case_ids):
        require(name in self.artifacts, 'model_api_removed_comparator')
        require(len(set(case_ids)) == len(case_ids) and case_ids, 'model_api_query_ids')
        query = {r['id']: r for r in self.public['query']}
        require(set(case_ids) <= set(query), 'model_api_unknown_query')
        rows = [query[k] for k in case_ids]
        values = (predict_native(self.artifacts[name], rows) if self.public['task'] == 'NEURAL-045'
                  else predict(self.artifacts[name], rows))
        return {'model': name, 'predictions': values, 'cell_id': self.public['cell_id'],
                'training_view_digest': self.descriptor['training_digest'],
                'new_target_access': False}
