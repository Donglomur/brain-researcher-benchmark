"""One arbitrary programme, fresh owned outer folds, complete immutable roster.

This is an additive prospective agent condition. The fixed P1 three-model
programme, including its inner-tuning choices, is not modified by this module.
"""
from dataclasses import dataclass, asdict
from pathlib import PurePosixPath
import hashlib
import math
import struct
import time
from n074.maps import MapValue
from n074.splits import outer_folds
from n074.evaluation import _map_envelope
from .host_contract import (Carrier, Programme, HostPolicy, OwnerAdmission,
                            FoldRequest, OwnerReceipt)
from .owned_io import (Pin, Tree, require, integer, text, digest, json_bytes,
                       create_tree, separated, canonical_path, strict_json)
from .selection import TrainingReader


def prospective_separated(path, *existing):
    canonical_path(path, True)
    selected = PurePosixPath(path)
    for root in existing:
        canonical_path(root, True)
        other = PurePosixPath(root)
        require(selected != other and selected not in other.parents and other not in selected.parents,
                'Prospective destination overlaps an admitted custody root')
        # Parent exists because create_tree creates only one fresh leaf. Compare
        # inode ancestry too, including case-insensitive filesystem aliases.
        parent = Tree(str(selected.parent))
        existing_tree = Tree(root)
        require(existing_tree.identity[:2] not in parent.ancestors,
                'Prospective destination has an admitted custody ancestor inode')


def content_pin(body):
    return Pin(len(body), hashlib.sha256(body).hexdigest())


def identity(doc, maximum=1048576):
    return content_pin(json_bytes(doc, maximum)).sha256


def programme_identity(programme_pin, method_pin):
    return identity({'programme': programme_pin.document(), 'method': method_pin.document()})


def validate_policy(policy):
    require(type(policy) is HostPolicy, 'Exact independently selected HostPolicy required')
    for k in ('identity', 'owner_source_identity', 'image_identity', 'qualification_identity'):
        text(getattr(policy, k), k)
    for k in HostPolicy.__dataclass_fields__:
        if k not in ('identity', 'owner_source_identity', 'image_identity', 'qualification_identity'):
            integer(getattr(policy, k), k)
    require(policy.cleanup_seconds < policy.wall_seconds, 'Cleanup reserve must fit inside whole native lifetime')
    require(policy.identity == identity({k: v for k, v in asdict(policy).items()
            if k not in ('identity', 'qualification_identity')}), 'Host policy content identity mismatch')
    digest(policy.qualification_identity)
    return policy


def admit_programme(programme, policy, budget):
    require(type(programme) is Programme, 'Exact fixed programme submission required')
    for carrier, maximum in ((programme.programme, policy.maximum_programme_bytes),
                              (programme.method, policy.maximum_method_bytes)):
        require(type(carrier) is Carrier and type(carrier.pin) is Pin, 'Exact immutable carrier')
        carrier.pin.validate()
        require(0 < carrier.pin.bytes <= maximum, 'Submission exceeds its admitted extent')
        raw = Tree(carrier.root).capture(carrier.path, carrier.pin, budget)
        require(bool(raw.decode('utf-8').strip()), 'Empty or non-UTF8 submission')
    require(programme.identity == programme_identity(programme.programme.pin, programme.method.pin),
            'Programme identity must bind both fixed content pins')


@dataclass(frozen=True)
class AgentPrediction:
    person: str
    family: str
    endpoint: str
    status: str
    value: MapValue | None
    reason: str | None


@dataclass(frozen=True)
class CandidatePanel:
    selection_identity: str
    programme_identity: str
    policy_identity: str
    predictions: tuple
    receipts: tuple
    completion: str


class CandidateFailure(RuntimeError):
    def __init__(self, partial, original, rejected=None):
        self.partial, self.original, self.rejected = partial, original, rejected
        super().__init__('Candidate panel aborted; no target evaluation is admitted')


def finite_map(raw):
    require(type(raw) is bytes and len(raw) % 8 == 0,
            'Immutable little-endian float64 map extent')
    require(all(math.isfinite(v[0]) for v in struct.iter_unpack('<d', raw)), 'Nonfinite candidate/training map')



def fold_document(selection, fold):
    permitted = set(fold.training_endpoints) | set(fold.query_endpoints)
    return {'schema': 'n074-agent-fold-v1', 'selection_identity': selection.identity,
           'held_person': fold.held_person, 'held_family': fold.held_family,
           'support_identity': selection.support.support_identity,
           'map_length': selection.support.map_length, 'dtype': '<f8',
           'training': [{'person': person, 'endpoint': endpoint, 'map': 'train-%06d.f64' % index}
                        for index, (person, endpoint) in enumerate((p, e) for p in fold.training_people
                                                                 for e in fold.training_endpoints)], 'queries': list(fold.query_endpoints),
           'endpoints': [asdict(e) for e in selection.population.endpoints if e.identity in permitted],
           'designs': [asdict(d) for d in selection.designs if d.endpoint in permitted],
           'output': {'path': 'predictions.f64', 'row_order': list(fold.query_endpoints),
                      'dtype': '<f8', 'columns': selection.support.map_length}}

def prepare_fold(selection, fold, programme, policy, training_reader, input_root, output_root, budget):
    """Build only this fold's inputs; no reader or operator Python object reaches candidate."""
    require(fold.eligible, 'Ineligible folds cannot create candidate inputs')
    expected_map_bytes = 8 * selection.support.map_length
    train_count = len(fold.training_people) * len(fold.training_endpoints)
    require(train_count * expected_map_bytes + policy.maximum_metadata_bytes <= policy.maximum_input_bytes,
            'Entire fold input upper bound exceeds selected native input allowance')
    require(len(fold.query_endpoints) * expected_map_bytes <= policy.maximum_output_bytes,
            'Complete fold output exceeds selected output allowance')
    tree = create_tree(input_root, budget)
    cases = {(c.person, c.endpoint): c for c in selection.population.cases}
    training, inputs = [], []
    for person in fold.training_people:
        require(person != fold.held_person, 'Global held person leaked to training')
        for endpoint in fold.training_endpoints:
            endpoint_row = next(e for e in selection.population.endpoints if e.identity == endpoint)
            require(endpoint_row.family != fold.held_family, 'Global held family leaked to training')
            c = cases[person, endpoint]
            value = training_reader.read_training_map(person, endpoint, c.source_identity)
            _map_envelope(value, c.source_identity, selection.support.support_identity,
                          selection.support.map_length, selection.maximum_map_bytes)
            finite_map(value.values)
            path = 'train-%06d.f64' % len(training)
            pin = tree.write_once(path, value.values, budget)
            inputs.append((path, pin))
            training.append({'person': person, 'endpoint': endpoint, 'map': path})
    doc = fold_document(selection, fold)
    raw = json_bytes(doc, policy.maximum_metadata_bytes)
    manifest = tree.write_once('fold.json', raw, budget)
    inputs.append(('fold.json', manifest))
    require(sum(p.bytes for _, p in inputs) <= policy.maximum_input_bytes, 'Fold total input bytes')
    fold_identity = identity({'selection': selection.identity, 'person': fold.held_person,
                              'family': fold.held_family, 'input_manifest': manifest.document(),
                              'inputs': [(name, pin.document()) for name, pin in inputs]})
    return FoldRequest(fold_identity, selection.identity, fold.held_person, fold.held_family,
                       programme.identity, input_root, manifest, tuple(inputs), output_root,
                       fold.query_endpoints, selection.support.map_length)


def validate_receipt(receipt, request, programme, policy, seen_contexts):
    require(type(receipt) is OwnerReceipt, 'Exact independently owned native receipt required')
    require((receipt.request_identity, receipt.programme_identity, receipt.policy_identity,
             receipt.owner_source_identity, receipt.image_identity, receipt.qualification_identity,
             receipt.input_manifest, receipt.output_root) ==
            (request.identity, programme.identity, policy.identity, policy.owner_source_identity,
             policy.image_identity, policy.qualification_identity, request.input_manifest, request.output_root),
            'Native owner receipt differs from the admitted request/policy')
    text(receipt.context_identity, 'fresh owned context identity')
    require(receipt.context_identity not in seen_contexts, 'Cross-fold context reuse is forbidden')
    require(receipt.producers_closed is True and receipt.all_owned_absent is True,
            'All owned producers must be retired before accepting any candidate output')
    require(receipt.status in ('completed', 'candidate_failed', 'timed_out', 'invalid_output'),
            'Unknown native disposition')
    if receipt.status == 'completed':
        require(receipt.reason is None and type(receipt.output) is Pin, 'Completed output receipt')
        receipt.output.validate()
        require(receipt.output.bytes == len(request.query_endpoints) * request.map_length * 8 <= policy.maximum_output_bytes,
                'Native output must cover the complete selected fold exactly')
    else:
        text(receipt.reason, 'failed native disposition reason')
        require(receipt.output is None, 'Failed native disposition cannot submit partial predictions')
    require(type(receipt.evidence) is Carrier and type(receipt.evidence.pin) is Pin,
            'Exact independently owned native evidence carrier')
    receipt.evidence.pin.validate()
    require(0 < receipt.evidence.pin.bytes <= policy.maximum_metadata_bytes, 'Native evidence metadata cap')
    canonical_path(receipt.evidence.root, True); canonical_path(receipt.evidence.path, False)
    seen_contexts.add(receipt.context_identity)



def validate_evidence(body, receipt):
    """Authenticate critical joins; native proof verification remains the owner responsibility."""
    doc = strict_json(body)
    require(type(doc) is dict and set(doc) == {'schema', 'request_identity', 'programme_identity',
        'policy_identity', 'owner_source_identity', 'image_identity', 'qualification_identity',
        'context_identity', 'output_root', 'input_manifest', 'producers_closed', 'all_owned_absent',
        'status', 'output', 'native'} and type(doc['native']) is dict and
        doc.get('schema') == 'n074-native-owner-evidence-v1',
            'Actual native owner evidence schema required')
    for key in ('request_identity', 'programme_identity', 'policy_identity', 'owner_source_identity',
                'image_identity', 'qualification_identity', 'context_identity', 'output_root',
                'producers_closed', 'all_owned_absent', 'status'):
        require(type(doc.get(key)) is type(getattr(receipt, key)) and doc[key] == getattr(receipt, key),
                'Native evidence/receipt disagreement: ' + key)
    require(doc.get('input_manifest') == receipt.input_manifest.document() and
            doc.get('output') == (None if receipt.output is None else receipt.output.document()),
            'Native evidence input/output pin disagreement')
    return doc

def run_candidate(selection, programme, policy, training_reader, owner, workspace_root, budget):
    """Run through a required native owner; no candidate is imported in this process.

    A concrete separately reviewed backend and actual native qualification are
    required. An unissued host never becomes runnable by setting a status field.
    """
    validate_policy(policy)
    require(type(training_reader) is TrainingReader and training_reader.selection is selection,
            'Training reader must be owned by this exact frozen selection')
    require(training_reader.budget is budget, 'Candidate preparation and source reads require one shared operation budget')
    prospective_separated(workspace_root, programme.programme.root, programme.method.root, training_reader.tree.root)
    admit_programme(programme, policy, budget)
    admission = owner.authenticate_selected_owner()  # no candidate-supplied arguments
    require(type(admission) is OwnerAdmission and admission == OwnerAdmission(
        policy.identity, policy.owner_source_identity, policy.image_identity, policy.qualification_identity),
        'Independent native owner admission differs from selected policy')
    workspace = create_tree(workspace_root, budget)
    separated(workspace, Tree(programme.programme.root), training_reader.tree)
    # The method may share programme root; neither may live under the fold workspace.
    separated(workspace, Tree(programme.method.root))
    endpoints = {e.identity: e for e in selection.population.endpoints}
    rows = {(c.person, c.endpoint): AgentPrediction(c.person, endpoints[c.endpoint].family,
            c.endpoint, 'not_attempted', None, 'Panel has not reached this declared case')
            for c in selection.population.cases}
    receipts, seen = [], set()
    active_fold, rejected = None, None
    def snapshot(completion):
        return CandidatePanel(selection.identity, programme.identity, policy.identity,
                              tuple(rows[c.person, c.endpoint] for c in selection.population.cases),
                              tuple(receipts), completion)
    try:
        for ordinal, fold in enumerate(outer_folds(selection.population)):
            active_fold, rejected = fold, None
            if not fold.eligible:
                for endpoint in fold.query_endpoints:
                    rows[fold.held_person, endpoint] = AgentPrediction(fold.held_person, fold.held_family,
                        endpoint, 'ineligible_support', None, 'Complete selected training/query support is unavailable')
                continue
            request = prepare_fold(selection, fold, programme, policy, training_reader,
                workspace_root + '/input-%06d' % ordinal, workspace_root + '/output-%06d' % ordinal, budget)
            budget.check()
            require(policy.wall_seconds <= budget.deadline - time.monotonic(),
                    'Remaining cooperative operation budget cannot cover the whole native invocation')
            rejected = (request, None)  # Retain the exact dispatched request even if owner raises.
            receipt = owner.run_fresh(programme, request, policy)
            rejected = (request, receipt)  # Preserve exact rejected ownership evidence on failure.
            validate_receipt(receipt, request, programme, policy, seen)
            evidence_tree = Tree(receipt.evidence.root)
            separated(evidence_tree, Tree(request.input_root), Tree(request.output_root))
            separated(evidence_tree, Tree(programme.programme.root), training_reader.tree)
            separated(evidence_tree, Tree(programme.method.root))
            evidence = evidence_tree.capture(receipt.evidence.path, receipt.evidence.pin, budget)
            validate_evidence(evidence, receipt)
            receipts.append((request, receipt))
            if receipt.status != 'completed':
                for endpoint in fold.query_endpoints:
                    rows[fold.held_person, endpoint] = AgentPrediction(fold.held_person, fold.held_family,
                        endpoint, 'candidate_failed', None, receipt.status + ': ' + receipt.reason)
                continue
            raw = Tree(receipt.output_root).capture('predictions.f64', receipt.output, budget)
            finite_map(raw)  # all rows, before retaining any row from this fold
            extent = selection.support.map_length * 8
            for index, endpoint in enumerate(fold.query_endpoints):
                values = raw[index * extent:(index + 1) * extent]
                value = MapValue('P1_AGENT:' + fold.held_person + ':' + endpoint,
                    selection.support.support_identity, values, selection.support.map_length,
                    hashlib.sha256(values).hexdigest())
                rows[fold.held_person, endpoint] = AgentPrediction(fold.held_person, fold.held_family,
                                                                 endpoint, 'predicted', value, None)
        budget.check()
        return snapshot('complete_source_attempt')
    except BaseException as error:
        if active_fold is not None:
            for endpoint in active_fold.query_endpoints:
                rows[active_fold.held_person, endpoint] = AgentPrediction(active_fold.held_person, active_fold.held_family,
                    endpoint, 'candidate_failed', None, 'Aborted attempted fold: ' + type(error).__name__)
        raise CandidateFailure(snapshot('aborted'), error, rejected) from error
