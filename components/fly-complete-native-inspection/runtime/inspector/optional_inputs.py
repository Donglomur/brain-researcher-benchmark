"""Join an authenticated descriptor supplement without replacing the base map."""
import hashlib
import json
import math

from structural_stream import need

PLAN_BYTES = 3419523
PLAN_SHA = '7eb06156b8ce98b9bb00f078ef64e8b57e99c5e1e234dc4c7222372a4d40b10c'
OPTIONAL_BYTES = 125940
OPTIONAL_SHA = 'e25d53f30c0404164f89553cf414c92c145bcb33eec341973cd4a43dc88ac034'
OPTIONAL = ('shift', 'allo_pos')


def join_optional(plan, supplement):
    need(supplement['schema'] == 'fly-native-optional-descriptors-v1' and
         supplement['base_plan_bytes'] == PLAN_BYTES and supplement['base_plan_sha256'] == PLAN_SHA,
         'optional/base map binding')
    files, extras = plan['files'], supplement['files']
    need(len(files) == len(extras) == 42 and sum(f['trial_count'] for f in files) == 1345,
         'full 42/1345 population')
    need(len({f['archive_member_id'] for f in files}) == 42, 'unique base members')
    present = dict.fromkeys(OPTIONAL, 0)
    result = []
    for base, extra in zip(files, extras):
        need(all(base[k] == extra[k] for k in ('archive_member_id', 'official_lookup_index', 'trial_count')),
             'optional member identity/order')
        need(len(base['trials']) == len(extra['trials']) == base['trial_count'], 'full trial descriptors')
        trials, file_fields = [], None
        for i, (old, added) in enumerate(zip(base['trials'], extra['trials'])):
            need(old['trial_index_zero_based'] == added['trial_index_zero_based'] == i,
                 'native trial identity/order')
            need(set(added['fields']) == set(OPTIONAL), 'both optional dispositions required')
            available = {k for k, v in added['fields'].items() if v is not None}
            if file_fields is None:
                file_fields = available
            need(file_fields == available, 'source struct fields must be uniform')
            for k, node in added['fields'].items():
                if node is None:
                    continue
                need(set(node) == {'class', 'dims', 'complex', 'logical'}, 'typed optional descriptor')
                need(node['class'] in ('double', 'single', 'int8', 'uint8', 'int16', 'uint16',
                                      'int32', 'uint32', 'int64', 'uint64') and node['complex'] is False
                     and type(node['logical']) is bool, 'real numerical optional field')
                dims = node['dims']
                need(type(dims) is list and 2 <= len(dims) <= 16 and
                     all(type(d) is int and d >= 0 for d in dims) and math.prod(dims) <= 20000,
                     'bounded exact optional shape')
                present[k] += 1
            trials.append(dict(old, optional_fields=added['fields']))
        result.append(dict(base, trials=trials))
    need(all(n == 235 for n in present.values()), 'full optional 235-present/1110-absent support')
    return dict(plan, files=result)


def read_exact(path, size, sha):
    with open(path, 'rb') as handle:
        body = handle.read(size+1)
    need(len(body) == size and hashlib.sha256(body).hexdigest() == sha, 'exact private metadata identity')
    return json.loads(body)


def load_and_join(path, optional_path):
    return join_optional(read_exact(path, PLAN_BYTES, PLAN_SHA),
                         read_exact(optional_path, OPTIONAL_BYTES, OPTIONAL_SHA))
