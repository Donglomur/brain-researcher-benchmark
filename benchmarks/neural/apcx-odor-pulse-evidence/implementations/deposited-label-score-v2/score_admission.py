"""Validate frozen prediction content using public packets before target reads.

This module receives parsed public packets and predictions only. It neither
opens files nor consumes owner documents. Hash authentication is still performed
by task.score; these checks additionally bind every predicted query to its
public condition, profile and complete query roster.
"""
import participant_core as core
import released_profile as profile
import grader


def validate_public_submissions(packets, submissions, methods, selections):
    """Refuse the complete operation before owners are opened if any arm fails.

    Reuse the scorer's target-independent record checks so optional complete
    probability columns, finite negative counts and numerical limits keep the
    existing score semantics. Prediction values and record order are unchanged.
    The caller separately authenticates every selected document's bytes.
    """
    if set(packets) != set(core.CONDITIONS):
        raise ValueError('both public conditions required before targets')
    expected_files = {f'{condition}__{method}.json'
                      for condition in core.CONDITIONS for method in methods}
    if set(submissions) != expected_files:
        raise ValueError('all frozen method/condition predictions required before targets')
    for condition in core.CONDITIONS:
        packet = packets[condition]
        expected_header = profile.submission(packet, [])
        if expected_header['condition'] != condition:
            raise ValueError('public packet condition binding before targets')
        expected_queries = {row['case_id']: row for session in packet['sessions']
                            for row in session['queries']}
        for method in methods:
            submission = submissions[f'{condition}__{method}.json']
            core.exact_keys(submission, expected_header)
            if any(submission[key] != expected_header[key]
                   for key in expected_header if key != 'records'):
                raise ValueError('exact public profile/packet/condition binding before targets')
            _, errors, _ = grader._validated_predictions(expected_queries, submission['records'])
            if errors:
                raise ValueError('complete valid public query predictions required before targets')
        if condition in selections:
            selection = selections[condition]
            if (selection.get('schema') != 'apcx-complete-condition-reference-selection-v1'
                    or selection.get('condition') != condition
                    or selection.get('participant_packet_sha256') != expected_header['participant_packet_sha256']
                    or selection.get('submissions') != {
                        method: submissions[f'{condition}__{method}.json'] for method in methods}):
                raise ValueError('reference selection/public packet binding before targets')
