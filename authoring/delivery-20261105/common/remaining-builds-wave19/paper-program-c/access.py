"""Full image/mount/source boundary, requiring an external trusted audit pin.

This validator does not inspect a running container or establish that an audit
was truthful. The expected proof pin is an operator input outside candidate
control. A qualified executor must bind that audit to its actual image/mounts.
"""
from core import TASK, REVISION, ROLES, need
from safe_io import capture, strict


def _osl(text):
    return 'osl_dynamics' in text.lower().replace('-', '_') or 'author_paper_archive' in text.lower()


def validate(proof, role, approved_image, approved_inventory, source_rows, author_source_hashes):
    need(role in ROLES, 'Exact actor role')
    need(set(proof) == {'schema', 'task_id', 'role', 'image_digest', 'inventory_sha256',
                       'complete_image_inventory', 'modules', 'distributions', 'source_files',
                       'mounts', 'network', 'fresh_context', 'outside_paths_unreachable'},
         'Complete external image/source exposure record')
    need(proof['schema'] == 'osl_execution_exposure_v1' and proof['task_id'] == TASK
         and proof['role'] == role, 'Role-bound external exposure audit')
    need(proof['image_digest'] == approved_image and proof['inventory_sha256'] == approved_inventory,
         'Exact separately approved full image and filesystem inventory')
    need(proof['complete_image_inventory'] is True and proof['fresh_context'] is True
         and proof['outside_paths_unreachable'] is True and proof['network'] == 'disabled',
         'Required externally verified isolation properties')
    need(type(proof['modules']) is list and type(proof['distributions']) is list
         and type(proof['source_files']) is list and type(proof['mounts']) is list,
         'Complete explicit inventories')
    got = {r['path']: {k: r[k] for k in ('bytes', 'sha256')} for r in proof['source_files']}
    expected = {r['path']: {k: r[k] for k in ('bytes', 'sha256')} for r in source_rows}
    need(len(got) == len(proof['source_files']) and got == expected,
         'All image/mounted scientific source files match approved role inventory')
    need(type(author_source_hashes) in (set, list, tuple) and author_source_hashes,
         'Complete known author-code hash denylist independently supplied')
    need(all(type(r.get('paper_method_implementation')) is bool for r in source_rows),
         'Every source has a reviewed origin classification, including derivatives/renames')
    permitted = {'paper', 'contract', 'input', 'program', 'output'}
    if role == 'B':
        permitted.add('historical_author_source')
    elif role == 'reference':
        permitted |= {'historical_author_source', 'operator_reference'}
    for mount in proof['mounts']:
        need(set(mount) == {'purpose', 'identity', 'read_only'}, 'Bound mount identity')
        need(mount['purpose'] in permitted, 'No operator/other-fold/other-attempt mount')
        need(mount['read_only'] is (mount['purpose'] != 'output'), 'Only fresh output writable')
    if role == 'A':
        need(not any(_osl(str(x)) for x in proof['modules'] + proof['distributions']),
             'A excludes every installed/reachable OSL implementation')
        need(not any(_osl(x) for x in got), 'A excludes author source, even off PYTHONPATH')
        need(not any(r['paper_method_implementation'] or r['sha256'] in author_source_hashes
                     for r in source_rows), 'A excludes renamed/derived/current author implementation')
    else:
        need(any(_osl(str(x)) for x in proof['modules']), 'Exact historical OSL in B/operator image')
        need(any(m['purpose'] == 'historical_author_source' and m['identity'] == REVISION
                 for m in proof['mounts']), 'Historical edition, not a current substitution')
    return {'role': role, 'image_digest': approved_image, 'inventory_sha256': approved_inventory,
            'audit_required_external': True, 'runtime_verified_by_this_validator': False}


def admit(path, trusted_pin, role, approved_image, approved_inventory, source_rows, author_source_hashes):
    raw = capture(path, 2_000_000, trusted_pin)
    return validate(strict(raw), role, approved_image, approved_inventory, source_rows, author_source_hashes)
