"""Create-only complete-panel commitment; separate pinned evaluation phase.

Only the final COMMIT carrier returned after all writes/close/fsync successes is
eligible for independent evaluator selection. A leftover file from a failed
publication is not a successfully issued commitment. Old attempts are retained.
"""
from dataclasses import asdict
from n074.contracts import FitConfig
from n074.maps import MapValue
from n074.programme import ProgrammeResult, Prediction, run as run_fixed_programme
from n074.evaluation import result_digest
from .candidate import CandidatePanel, AgentPrediction, prospective_separated, validate_evidence
from .host_contract import Carrier, FoldRequest, OwnerReceipt
from .selection import Selection, TrainingReader, ProtectedOwner, exact_keys, record
from .owned_io import (Pin, Tree, require, integer, json_bytes, strict_json,
                       create_tree, separated)
from .panel import SelectionAuthority, preflight, evaluate, summarize


def run_references(selection, training_reader):
    """The original prospective fixed three-algorithm pipeline, unchanged."""
    require(type(selection) is Selection and type(training_reader) is TrainingReader and
            training_reader.selection is selection, 'Exact independently selected reference reader')
    return run_fixed_programme(selection.population, selection.designs, selection.protocol,
                               training_reader, selection.maximum_map_bytes)


def _frozen(value):
    return tuple(_frozen(v) for v in value) if type(value) is list else value


def commit_packet(selection, candidate, references, programme, policy, destination,
                  forbidden_roots, budget, maximum_metadata_bytes):
    """No protected reader is accepted here. Every declared row precedes COMMIT."""
    require(type(selection) is Selection and type(forbidden_roots) is tuple and forbidden_roots,
            'Frozen selection and complete operator-selected custody exclusion roots')
    integer(maximum_metadata_bytes, 'maximum_metadata_bytes')
    prospective_separated(destination, programme.programme.root, programme.method.root, *forbidden_roots)
    preflight(selection, candidate, references, programme, policy, SelectionAuthority(selection))
    packet = create_tree(destination, budget)
    total, ordinal = 0, 0
    def store_value(value):
        nonlocal total, ordinal
        if value is None:
            return None
        total += len(value.values)
        require(total <= selection.maximum_panel_prediction_bytes, 'Whole-panel retained prediction byte cap')
        path = 'prediction-%06d.f64' % ordinal
        ordinal += 1
        pin = packet.write_once(path, value.values, budget)
        return {'source_identity': value.source_identity, 'support_identity': value.support_identity,
                'length': value.length, 'path': path, 'pin': pin.document()}
    def prediction(row):
        return {'person': row.person, 'family': row.family, 'endpoint': row.endpoint,
                'status': row.status, 'reason': row.reason, 'value': store_value(row.value)}
    agent_rows = [prediction(row) for row in candidate.predictions]
    reference_rows = []
    for row in references.predictions:
        doc = prediction(row); doc['arm'] = row.arm; reference_rows.append(doc)
    reference_document = {key: getattr(references, key) for key in
        ('protocol_identity', 'taxonomy_identity', 'eligibility_identity', 'support_identity',
         'fit_events', 'native_observation', 'stage_events', 'completion')}
    reference_document['predictions'] = reference_rows
    reference_document['selected_configurations'] = [
        [key, arm, index, asdict(config)] for key, arm, index, config in references.selected_configurations]
    agent_document = {'selection_identity': candidate.selection_identity,
                      'programme_identity': candidate.programme_identity,
                      'policy_identity': candidate.policy_identity, 'completion': candidate.completion,
                      'predictions': agent_rows,
                      'receipts': [[asdict(request), asdict(receipt)] for request, receipt in candidate.receipts]}
    evidence_documents = []
    for index, (request, receipt) in enumerate(candidate.receipts):
        evidence_tree = Tree(receipt.evidence.root)
        separated(packet, evidence_tree)
        raw = evidence_tree.capture(receipt.evidence.path, receipt.evidence.pin, budget)
        validate_evidence(raw, receipt)
        path = 'owner-evidence-%06d.json' % index
        copied = packet.write_once(path, raw, budget)
        require(copied == receipt.evidence.pin, 'Exact native evidence preservation')
        evidence_documents.append({'path': path, 'pin': copied.document()})
    manifest = {'schema': 'n074-agent-reference-packet-v1', 'owner_evidence': evidence_documents, 'candidate': agent_document,
                'references': reference_document, 'selection_identity': selection.identity,
                'prediction_bytes': total, 'prediction_files': ordinal}
    manifest_pin = packet.write_once('PANEL.json', json_bytes(manifest, maximum_metadata_bytes), budget)
    commit = {'schema': 'n074-agent-reference-closed-commitment-v1',
              'selection_identity': selection.identity, 'programme_identity': programme.identity,
              'policy_identity': policy.identity, 'scientific_decisions_identity': selection.scientific_decisions_identity,
              'reference_digest': result_digest(references), 'manifest': manifest_pin.document(),
              'condition': 'prospective_arbitrary_agent_comparison', 'scientifically_qualified': False}
    commit_pin = packet.write_once('COMMIT.json', json_bytes(commit, maximum_metadata_bytes), budget)
    return Carrier(destination, 'COMMIT.json', commit_pin)


def load_committed(selection, expected_commitment, programme, policy, budget, maximum_metadata_bytes):
    """Expected carrier must be independently selected after successful publication.

    The carrier cannot come from a submitted programme, target-derived search or
    merely finding a COMMIT filename. Target authority belongs to another phase.
    """
    require(type(expected_commitment) is Carrier and type(expected_commitment.pin) is Pin,
            'Independently selected closed commitment carrier required')
    integer(maximum_metadata_bytes, 'maximum_metadata_bytes')
    require(expected_commitment.path == 'COMMIT.json' and expected_commitment.pin.bytes <= maximum_metadata_bytes,
            'Exact bounded final commitment')
    packet = Tree(expected_commitment.root)
    commit = strict_json(packet.capture(expected_commitment.path, expected_commitment.pin, budget))
    exact_keys(commit, ('schema', 'selection_identity', 'programme_identity', 'policy_identity',
                       'scientific_decisions_identity', 'reference_digest', 'manifest', 'condition',
                       'scientifically_qualified'))
    require(commit['schema'] == 'n074-agent-reference-closed-commitment-v1' and
            (commit['selection_identity'], commit['programme_identity'], commit['policy_identity'],
             commit['scientific_decisions_identity']) ==
            (selection.identity, programme.identity, policy.identity, selection.scientific_decisions_identity),
            'Commitment differs from independent selection/submission/policy')
    require(commit['condition'] == 'prospective_arbitrary_agent_comparison' and
            commit['scientifically_qualified'] is False, 'Commitment overclaims scientific qualification')
    manifest_pin = Pin.parse(commit['manifest'])
    require(manifest_pin.bytes <= maximum_metadata_bytes, 'Complete manifest metadata cap')
    doc = strict_json(packet.capture('PANEL.json', manifest_pin, budget))
    exact_keys(doc, ('schema', 'candidate', 'references', 'selection_identity', 'prediction_bytes', 'prediction_files', 'owner_evidence'))
    require(doc['schema'] == 'n074-agent-reference-packet-v1' and doc['selection_identity'] == selection.identity,
            'Wrong complete-panel manifest')
    expected_bytes = integer(doc['prediction_bytes'], 'prediction_bytes', 0)
    expected_files = integer(doc['prediction_files'], 'prediction_files', 0)
    require(expected_bytes <= selection.maximum_panel_prediction_bytes and
            expected_files <= 4 * len(selection.population.cases), 'Full-panel input cap')
    total, names = 0, set()
    def value(row):
        nonlocal total
        if row is None:
            return None
        exact_keys(row, ('source_identity', 'support_identity', 'length', 'path', 'pin'))
        pin = Pin.parse(row['pin'])
        require(row['length'] == selection.support.map_length and
                pin.bytes == 8 * selection.support.map_length <= selection.maximum_map_bytes,
                'Prediction geometry must match independent selection before capture')
        require(type(row['path']) is str and row['path'] not in names, 'Unique prediction carrier required')
        names.add(row['path']); total += pin.bytes
        require(total <= expected_bytes and len(names) <= expected_files, 'Cumulative declared prediction cap')
        raw = packet.capture(row['path'], pin, budget)
        return MapValue(row['source_identity'], row['support_identity'], raw, row['length'], pin.sha256)
    agent = doc['candidate']
    exact_keys(agent, ('selection_identity', 'programme_identity', 'policy_identity', 'completion', 'predictions', 'receipts'))
    require(type(agent['predictions']) is list and len(agent['predictions']) == len(selection.population.cases),
            'Full candidate roster before map captures')
    rows = []
    for row in agent['predictions']:
        exact_keys(row, ('person', 'family', 'endpoint', 'status', 'reason', 'value'))
        rows.append(AgentPrediction(row['person'], row['family'], row['endpoint'], row['status'], value(row['value']), row['reason']))
    require(type(agent['receipts']) is list and len(agent['receipts']) <= len(selection.population.cases),
            'Finite native receipt count')
    receipts = []
    for pair in agent['receipts']:
        require(type(pair) is list and len(pair) == 2, 'Closed native request/receipt pair')
        request, receipt = pair
        exact_keys(request, tuple(FoldRequest.__dataclass_fields__))
        exact_keys(receipt, tuple(OwnerReceipt.__dataclass_fields__))
        require(type(request['inputs']) is list, 'Input carrier list')
        request = dict(request)
        request['input_manifest'] = Pin.parse(request['input_manifest'])
        request['inputs'] = tuple((name, Pin.parse(pin)) for name, pin in request['inputs'])
        request['query_endpoints'] = tuple(request['query_endpoints'])
        receipt = dict(receipt)
        receipt['input_manifest'] = Pin.parse(receipt['input_manifest'])
        receipt['output'] = None if receipt['output'] is None else Pin.parse(receipt['output'])
        evidence = receipt['evidence']
        exact_keys(evidence, ('root', 'path', 'pin'))
        receipt['evidence'] = Carrier(evidence['root'], evidence['path'], Pin.parse(evidence['pin']))
        receipts.append((FoldRequest(**request), OwnerReceipt(**receipt)))
    require(type(doc['owner_evidence']) is list and len(doc['owner_evidence']) == len(receipts),
            'Complete independently owned evidence copies required')
    evidence_names = set()
    for evidence, (_, receipt) in zip(doc['owner_evidence'], receipts):
        exact_keys(evidence, ('path', 'pin'))
        pin = Pin.parse(evidence['pin'])
        require(pin == receipt.evidence.pin and pin.bytes <= policy.maximum_metadata_bytes and
                evidence['path'] not in evidence_names, 'Exact bounded unique owner evidence copy')
        evidence_names.add(evidence['path'])
        raw = packet.capture(evidence['path'], pin, budget)
        validate_evidence(raw, receipt)
    candidate = CandidatePanel(agent['selection_identity'], agent['programme_identity'], agent['policy_identity'],
                               tuple(rows), tuple(receipts), agent['completion'])
    ref = doc['references']
    exact_keys(ref, tuple(ProgrammeResult.__dataclass_fields__))
    require(type(ref['predictions']) is list and len(ref['predictions']) == 3 * len(selection.population.cases),
            'Full exact-three-arm reference roster')
    predictions = []
    for row in ref['predictions']:
        exact_keys(row, ('person', 'family', 'endpoint', 'arm', 'status', 'reason', 'value'))
        predictions.append(Prediction(row['person'], row['family'], row['endpoint'], row['arm'],
                                      row['status'], value(row['value']), row['reason']))
    require(type(ref['selected_configurations']) is list, 'Selected reference configurations')
    configs = tuple((_frozen(key), arm, index, record(config, FitConfig))
                    for key, arm, index, config in ref['selected_configurations'])
    references = ProgrammeResult(ref['protocol_identity'], ref['taxonomy_identity'], ref['eligibility_identity'],
        ref['support_identity'], tuple(predictions), _frozen(ref['fit_events']), configs,
        ref['native_observation'], _frozen(ref['stage_events']), ref['completion'])
    require((total, len(names)) == (expected_bytes, expected_files), 'Complete prediction extent required')
    require(result_digest(references) == commit['reference_digest'], 'Fixed-reference commitment differs')
    preflight(selection, candidate, references, programme, policy, SelectionAuthority(selection))
    return candidate, references


def evaluate_committed(selection, expected_commitment, programme, policy, protected_owner,
                       budget, maximum_metadata_bytes):
    """Public target-consuming entry: load/verify all committed predictions first."""
    require(type(protected_owner) is ProtectedOwner and protected_owner.selection is selection,
            'Protected target owner must authenticate this exact frozen selection')
    require(protected_owner.budget is budget, 'Packet and protected target reads require one shared evaluation budget')
    candidate, references = load_committed(selection, expected_commitment, programme, policy,
                                           budget, maximum_metadata_bytes)
    comparisons = evaluate(selection, candidate, references, programme, policy, protected_owner)
    summary = summarize(comparisons, selection.population)
    budget.check()
    return {'commitment': asdict(expected_commitment), 'comparisons': comparisons, 'summary': summary}
