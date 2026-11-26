#!/usr/bin/env python3
"""Offline file scorer. This is not a candidate sandbox or scientific run grant."""
import argparse
import json
from core import ContractError, public_queries, score, compare, validate_submission
from safe_io import read_json, write_json


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--public', required=True)
    p.add_argument('--submission', required=True)
    p.add_argument('--comparator-submission', help='operator-selected complete comparator; joint report remains private')
    p.add_argument('--private', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args(argv)
    try:
        public = read_json(args.public)
        public_queries(public)
    except (ContractError, OSError):
        result = {'status': 'invalid_operator_packet', 'score': None,
                  'reason': 'public manifest could not be validated',
                  'private_targets_loaded': False}
    else:
        try:
            submission = read_json(args.submission)
            validate_submission(public, submission)
            comparator = None
            if args.comparator_submission is not None:
                comparator = read_json(args.comparator_submission)
                validate_submission(public, comparator)
        except (ContractError, OSError):
            result = {'status': 'invalid_submission', 'score': None,
                      'reason': 'complete valid query predictions required',
                      'private_targets_loaded': False}
        else:
            # Private path is never opened before complete public validation.
            # Do not put target values, source paths or OS errors in the report.
            private_loaded = False
            def load_private():
                nonlocal private_loaded
                value = read_json(args.private)
                private_loaded = True
                return value
            try:
                result = (score(public, submission, load_private) if comparator is None else
                          compare(public, submission, comparator, load_private))
            except (ContractError, OSError):
                result = {'status': 'invalid_operator_packet', 'score': None,
                          'reason': 'private target packet could not be validated'}
            result['private_targets_loaded'] = private_loaded
    write_json(args.output, result)
    print(json.dumps({'status': result['status'], 'output': args.output}))
    return 0 if result['status'] == 'scored' else 3 if result['status'] == 'invalid_operator_packet' else 2


if __name__ == '__main__':
    raise SystemExit(main())
