#!/usr/bin/env python3
"""Check complete NEURAL-013 predictions using only public metadata and output.

This performs no scoring, source-data authentication or execution qualification.
"""
import argparse
import json

from core import ContractError, public_queries, validate_submission
from safe_io import read_json, write_json


def inspect_submission(public, submission):
    """Return public coverage counts after the existing complete validation."""
    queries, predictions = validate_submission(public, submission)
    return {
        'schema': 'neural013-submission-preflight-v1',
        'status': 'valid_submission',
        'packet_id': public['packet_id'],
        'query_trials': len(queries),
        'query_sessions': len(set(queries.values())),
        'predicted_tokens': sum(len(tokens) for tokens in predictions.values()),
        'empty_predictions': sum(not tokens for tokens in predictions.values()),
        'private_targets_loaded': False,
        'source_panel_authentication': 'not_established_by_validation',
        'scoring_complexity_qualified': False,
        'scientific_success': None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', required=True)
    parser.add_argument('--submission', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        public = read_json(args.public)
        public_queries(public)
    except (ContractError, OSError):
        result = {
            'schema': 'neural013-submission-preflight-v1',
            'status': 'invalid_operator_packet',
            'reason': 'public manifest could not be validated',
            'private_targets_loaded': False,
        }
    else:
        try:
            result = inspect_submission(public, read_json(args.submission))
        except (ContractError, OSError):
            result = {
                'schema': 'neural013-submission-preflight-v1',
                'status': 'invalid_submission',
                'reason': 'complete valid query predictions required',
                'private_targets_loaded': False,
            }
    write_json(args.output, result)
    print(json.dumps({'status': result['status'], 'output': args.output}))
    return (0 if result['status'] == 'valid_submission' else
            3 if result['status'] == 'invalid_operator_packet' else 2)


if __name__ == '__main__':
    raise SystemExit(main())
