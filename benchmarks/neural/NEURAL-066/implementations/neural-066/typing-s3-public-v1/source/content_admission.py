"""Concrete bounded independent-operator content receipt channel.

Receipt authenticity derives from the root-selected operator-owned directory and
review authority. This is not a claim that AST/hash checks solve semantic leakage.
"""
import time
from pathlib import Path
from core import encoded, identity, need
from safe_io import capture, child, strict

def request_and_wait(root, context, phase, payload_pins, authority, budget, limits):
    request = {'schema': 'neural066_method_review_request_v1', 'context': context, 'phase': phase, 'payloads': payload_pins, 'fresh_final_state_required': True, 'query_label_or_other_case_access': False, 'source_lock': authority['source_lock']}
    token = identity(request)
    request_path = Path(root) / ('request-' + token + '.json')
    budget.save(request_path, encoded(request))
    response_path = Path(root) / ('response-' + token + '.json')
    end = min(budget.end, budget.tick() + limits['wall_seconds'])
    while budget.tick() < end:
        if response_path.exists():
            budget.read(limits['json_bytes'])
            raw = capture(response_path, limits['json_bytes'])
            reply = strict(raw)
            need(budget.tick() < end, 'Original local review cutoff after complete response capture/parse')
            need(reply['schema'] == 'neural066_method_review_response_v1' and reply['request_sha256'] == token and (reply['source_lock'] == authority['source_lock']) and (reply['review_authority'] == authority['review_authority']) and (reply['accepted'] is True) and (reply['fresh_state_carriage_admitted'] is True) and (reply['training_only_selection_admitted'] is True) and (reply['no_covert_channel_proof_claim'] is True), 'Exact independent semantic/content admission, no worker-created Boolean')
            budget.event({'kind': 'independent_content_admission', 'request': token, 'response': identity(reply)})
            need(budget.tick() < end, 'Original local review cutoff after final admission journal')
            return reply
        time.sleep(min(0.1, max(0, end - budget.tick())))
    raise TimeoutError('Independent content admission unavailable within original deadline')
