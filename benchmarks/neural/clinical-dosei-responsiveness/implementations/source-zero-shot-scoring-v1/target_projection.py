"""Pure private index-to-target join; no I/O, scoring or source authentication."""
import re

CASE_COUNT = 7345
RECORDING_COUNT = 171
CONDITION = 'native_marker_relative_30s_v1'
DEPENDENCY_SHA256 = {
    'indexed': 'dcb95c883a84f9601964899471d1e446e2dfa5d9e8c0efce1c90082cfb3a9741',
    'core': '00b4358cbd834f6d9a443c5c553920561301c4bfe2910075743ff92556a878be',
    'transport': '69fd0c85374240bba63fc212304b4af9882c8afee0ff8b7d0fbeea3e5b6ef048',
}


class TargetProjectionRefusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise TargetProjectionRefusal(message)


def project_targets(public_manifest, private_indices, *, secret, indexed, core, transport):
    """Return the scorer's exact private target envelope in public case order.

    The caller authenticates all input/dependency bytes and the complete source
    population. HMAC validates case/source identity, not the source label or an
    observation hash. No numerical observation is read or recomputed here.
    """
    require(type(secret) is bytes and len(secret) == 32, 'exact private32-byte key required')
    require(core.CONDITION == CONDITION, 'adopted source condition required')
    require(type(public_manifest) is list and len(public_manifest) == CASE_COUNT,
            'all7345 public observation bindings required')
    expected = transport.admit_manifest(public_manifest)
    require(type(private_indices) is list and len(private_indices) == CASE_COUNT,
            'all7345 private indices required')
    found = {}; clocks = {}
    for index in private_indices:
        clock, _, _, _, _ = indexed.validate_index(index, secret=secret, core=core)
        ident = index['case_id']; evaluator = index['evaluator']
        require(ident in expected and ident not in found, 'unique matched private case required')
        rid = evaluator['recording_id']
        require(type(rid) is str and re.fullmatch('[1-9][0-9]*', rid),
                'positive canonical source recording ID required')
        binding = clock.binding()
        if rid in clocks:
            require(clocks[rid] == binding, 'inconsistent complete clock within source recording')
        else:
            clocks[rid] = binding
        # The unchanged validator checks exact integer1..5 or null. Preserve it.
        found[ident] = {'case_id': ident, 'recording_id': rid,
                        'category': evaluator['moaas_grouped_ordinal']}
    require(set(found) == set(expected) and len(clocks) == RECORDING_COUNT,
            'complete matched population and171 source recording groups required')
    return {'schema': 'dosei_private_zero_shot_targets_v1', 'condition': CONDITION,
            'cases': [found[item['case_id']] for item in public_manifest]}
