"""Owner-side compatibility of complete score reports; no fitting or new oracle."""
import hashlib
from pathlib import Path
from deployment import decode, need, absolute
from profile import PACKET


def hash_owned(path, maximum):
    import stat
    path = absolute(str(path)); before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= maximum,
         'bounded complete owned artifact')
    digest = hashlib.sha256(); total = 0
    with path.open('rb') as stream:
        while True:
            part = stream.read(min(65536, maximum-total+1))
            if not part: break
            total += len(part); need(total <= maximum, 'owned artifact cap')
            digest.update(part)
    after = path.lstat()
    need(total == before.st_size and all(getattr(before,k) == getattr(after,k) for k in
         ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')), 'stable owned artifact')
    return {'path':str(path), 'bytes':total, 'sha256':digest.hexdigest()}


def inspect_score(path, submission_sha256, negative=False):
    path = absolute(str(path))
    before = path.lstat()
    # The preceding accepted lifecycle owns this fresh report. Read exactly once;
    # its own descriptor is returned for later independently selected review.
    need(0 < before.st_size <= 64*1024**2, 'complete bounded score report')
    import stat
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and not path.is_symlink(), 'ordinary owned score')
    with path.open('rb') as stream:
        raw = stream.read(before.st_size + 1)
    after = path.lstat()
    need(len(raw) == before.st_size and all(getattr(before,k) == getattr(after,k) for k in
         ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')), 'stable complete score')
    score = decode(raw)
    need(score['schema'] == 'PFC_FULL99_CONDITIONAL_SCORE_V1' and score['packet_sha256'] == PACKET[1]
         and score['candidate_sha256'] == submission_sha256, 'score/source/submission correspondence')
    need(score['roster'] == {'recordings':99, 'units':19186, 'animals':68, 'families':12,
         'analytic_contexts':16, 'gao_contexts':4}, 'complete profile roster')
    need(len(score['cases']) == 69 and len({c['case'] for c in score['cases']}) == 69
         and score['cases'][0]['case'] == 'full', 'all full/deletion cases')
    cells = 0; defined = 0; undefined = 0
    for case in score['cases']:
        need(len(case['moment_errors']) == 12, 'complete family scores')
        for family in case['moment_errors']:
            cells += family['cells']
            for field in ('counts', 'mean', 'variance'):
                target = 1 if negative and field == 'counts' else 0
                value = family[field]
                need(value['mean_absolute_error_binary64'] == target and
                     value['max_absolute_error_exact'] == [target, 1] and
                     value['unequal_cells'] == (family['cells'] if target else 0),
                     'unchanged exact positive/negative discrimination')
        contexts = case['continuous_comparisons']['contexts']
        need(len(contexts) == 16 and len(case['continuous_comparisons']['hierarchy_errors']) == 4,
             'all geometry/hierarchy contexts')
        for context in contexts.values():
            flags = context['geometry_defined']
            need(flags['candidate'] == flags['reference'], 'undefined states retained')
            defined += int(flags['reference']); undefined += int(not flags['reference'])
            if not negative:
                for name in ('enrichment','distances','cosine'):
                    if name in context:
                        err = context[name]
                        need(err['undefined_state_mismatches'] == 0, 'same undefined coordinates')
                        if err['undefined_coordinates'] == 0 and err['coordinates']:
                            need(err['mean_absolute_error'] == err['max_absolute_error'] == 0,
                                 'unchanged defined continuous scores')
                for value in context.get('partition_adjusted_rand', {}).values():
                    need(value == [1,1], 'unchanged partition agreement')
        if not negative:
            need(case['reference_hierarchy'] == case['candidate_hierarchy'], 'all hierarchy coefficients and undefined states')
            for err in case['continuous_comparisons']['hierarchy_errors'].values():
                need(err['undefined_state_mismatches'] == 0, 'hierarchy undefined correspondence')
                if err['undefined_coordinates'] == 0 and err['coordinates']:
                    need(err['mean_absolute_error'] == err['max_absolute_error'] == 0, 'defined hierarchy equality')
    need(cells == 531024 and cells*3 == 1593072, 'all exact fields retained')
    need((defined, undefined) == (1058, 46), 'all defined and undefined contexts')
    if not negative:
        directions = []
        for rows in score['candidate_animal_influence'].values():
            directions.extend(row for row in rows if row['predeclared_direction'] is not None)
        need(len(directions) == 8 and all(row['all_animals'] == 68 and row['defined_deletions'] == 65
             and row['complete_direction_stability'] is False for row in directions),
             'false complete-animal stability is retained')
    return {'path':str(path), 'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest(),
            'cases':69, 'exact_fields':cells*3, 'negative':negative,
            'defined_contexts':defined, 'undefined_contexts':undefined,
            'compatible':True, 'model_result':False}
